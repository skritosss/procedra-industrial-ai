"""Errors the provider layer is allowed to raise.

Vendor SDK exceptions stop here. Call sites currently catch
`(OpenAIError, JSONDecodeError, ValidationError, ValueError)` — a list that grows
every time a provider is added and that silently changes meaning when an SDK
renames a class. Everything below is raised by our own code, so the callers can
catch one hierarchy and keep their fallback logic unchanged.
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base for every failure originating in the model layer."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class ProviderNotConfiguredError(ProviderError):
    """The provider cannot run at all: no key, no model, no endpoint.

    Distinct from unavailability because it is an operator mistake rather than a
    transient condition, and it should be reported at startup rather than
    absorbed as a fallback on every request.
    """


class ProviderUnavailableError(ProviderError):
    """The provider was reachable in principle but did not answer.

    Network failure, timeout, authentication rejection, quota. The deterministic
    fallback exists for exactly this case.
    """


class ProviderResponseError(ProviderError):
    """The provider answered, and the answer cannot be used.

    Malformed JSON, a payload that fails schema validation, a truncated response.
    Kept separate from unavailability because it usually means the prompt or the
    model choice is wrong, not the network.
    """


class ProviderEgressBlockedError(ProviderError):
    """A call was refused because the deployment forbids leaving the perimeter.

    Closed-perimeter installations set this policy and it is enforced in the
    provider layer rather than left to operator discipline: a misconfigured
    provider must fail loudly, not quietly send plant data to a hosted API.
    """
