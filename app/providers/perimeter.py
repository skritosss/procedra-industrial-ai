"""Whether a model endpoint is allowed to be called from this deployment.

A closed-perimeter installation is the reason the provider layer exists: the
plant will not let its data leave, and the first question its security team asks
is where the text is processed. Answering that with operator discipline alone is
not enough — one wrong `LLM_BASE_URL` and instructions describing the plant go to
a hosted API. The check therefore lives in the layer every model call passes
through, and it fails loudly rather than degrading in silence.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.core.network import is_public_address, resolve_host_addresses
from app.core.settings import Settings
from app.providers.errors import ProviderEgressBlockedError

DEFAULT_PORTS = {"http": 80, "https": 443}
PERIMETER_LOGGER = logging.getLogger("industrial_ai.perimeter")


def report_degraded(error: Exception, capability: str) -> None:
    """Record that a model call failed and the deterministic path took over.

    Sibling of `report_blocked`, and it exists for the same reason: without a
    line here, a wrong key, an unreachable endpoint, a rate limit and a malformed
    response are all indistinguishable from a deployment that was never given a
    model. The service keeps answering either way, so nothing else in the system
    marks the difference.
    """
    PERIMETER_LOGGER.warning(
        "model call failed, answering deterministically",
        extra={"capability": capability, "reason": f"{type(error).__name__}: {error}"},
    )


def report_blocked(error: ProviderEgressBlockedError, capability: str) -> None:
    """Record a refusal so it cannot pass as an ordinary model outage.

    The caller falls back to the deterministic path, which keeps the service
    answering. Without this line an operator would see only that the model is
    "not working" and would have no way to tell a misconfigured perimeter from
    an unreachable endpoint.
    """
    PERIMETER_LOGGER.error(
        "model call blocked by perimeter policy",
        extra={"capability": capability, "reason": str(error)},
    )


def ensure_endpoint_allowed(base_url: str | None, settings: Settings) -> None:
    """Raise when the configured endpoint would leave the perimeter.

    With external calls permitted this is a no-op: the deployment has said the
    hosted path is acceptable.
    """
    if settings.llm_allow_external_calls:
        return
    if not base_url:
        # No endpoint means the vendor default, which is on the public internet.
        raise ProviderEgressBlockedError(
            "perimeter",
            "LLM_ALLOW_EXTERNAL_CALLS is false and LLM_BASE_URL is empty: "
            "the vendor default endpoint is outside the perimeter"
        )
    hostname, port = _endpoint_target(base_url)
    try:
        addresses = resolve_host_addresses(hostname, port)
    except OSError as exc:
        # An unresolvable name is not proof of a leak. It is refused because the
        # opposite is also unproven, and a perimeter check that passes on
        # "unknown" is not a check.
        raise ProviderEgressBlockedError(
            "perimeter",
            f"LLM_BASE_URL host {hostname} does not resolve, so it cannot be shown to be internal"
        ) from exc
    public = sorted(str(address) for address in addresses if is_public_address(address))
    if public:
        raise ProviderEgressBlockedError(
            "perimeter",
            f"LLM_BASE_URL host {hostname} resolves to public address(es) {', '.join(public)}; "
            "a closed-perimeter deployment must point at an endpoint inside its own network"
        )


def endpoint_is_literal_public(base_url: str | None) -> bool:
    """True only when the endpoint is a literal public IP.

    Used at startup, where DNS may legitimately be unavailable and a hostname
    cannot be judged yet. A literal address needs no resolver, so it can be
    refused before the service accepts a single request.
    """
    if not base_url:
        return False
    hostname, port = _endpoint_target(base_url)
    try:
        addresses = resolve_host_addresses(hostname, port, resolver=_no_resolver)
    except (OSError, ValueError):
        return False
    return any(is_public_address(address) for address in addresses)


def _endpoint_target(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url if "://" in base_url else f"//{base_url}", scheme="https")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ProviderEgressBlockedError("perimeter", f"LLM_BASE_URL {base_url!r} has no host")
    return hostname, parsed.port or DEFAULT_PORTS.get(parsed.scheme, 443)


def _no_resolver(*_args: object, **_kwargs: object) -> list:
    raise OSError("startup check does not resolve names")
