from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import functools
import http.client
import ipaddress
import socket
import ssl
from typing import Any, cast
import urllib.error
import urllib.parse
import urllib.request

import yt_dlp
from yt_dlp.networking import Request, Response
from yt_dlp.networking.exceptions import HTTPError, RequestError, TransportError

from app.core.network import is_public_address


Resolver = Callable[..., list[tuple[Any, ...]]]


class EgressPolicyError(ValueError):
    """A URL cannot be fetched without crossing the configured egress boundary."""


@dataclass(frozen=True)
class ResolvedTarget:
    url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


class VideoEgressPolicy:
    def __init__(
        self,
        allowed_hosts: tuple[str, ...],
        timeout_seconds: float,
        *,
        resolver: Resolver = socket.getaddrinfo,
    ) -> None:
        self.allowed_hosts = allowed_hosts
        self.timeout_seconds = timeout_seconds
        self._resolver = resolver

    def resolve(self, url: str) -> ResolvedTarget:
        if not isinstance(url, str) or not url or any(ord(character) < 32 for character in url):
            raise EgressPolicyError("URL is invalid")
        if "\\" in url:
            raise EgressPolicyError("URL authority must not contain backslashes")

        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EgressPolicyError("URL must start with http:// or https://")
        if parsed.username is not None or parsed.password is not None:
            raise EgressPolicyError("URL credentials are not allowed")
        if "%" in parsed.netloc:
            raise EgressPolicyError("Encoded URL hosts and IPv6 zone identifiers are not allowed")

        hostname = parsed.hostname
        if not hostname:
            raise EgressPolicyError("URL host is required")
        try:
            hostname = hostname.encode("idna").decode("ascii").lower().rstrip(".")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except (UnicodeError, ValueError) as exc:
            raise EgressPolicyError("URL host or port is invalid") from exc
        if not 1 <= port <= 65535:
            raise EgressPolicyError("URL port is invalid")
        if self.allowed_hosts and not _hostname_allowed(hostname, self.allowed_hosts):
            raise EgressPolicyError("Video URL host is not allowed by current configuration")
        if hostname in {"localhost", "localhost.localdomain"}:
            raise EgressPolicyError("URL must point to a public host")

        addresses = self._resolve_addresses(hostname, port)
        return ResolvedTarget(url=url, hostname=hostname, port=port, addresses=addresses)

    def _resolve_addresses(self, hostname: str, port: int) -> tuple[str, ...]:
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            try:
                records = self._resolver(hostname, port, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise EgressPolicyError("Unable to resolve URL host") from exc
            raw_addresses = {str(record[4][0]).split("%", 1)[0] for record in records if record[4]}
            if not raw_addresses:
                raise EgressPolicyError("Unable to resolve URL host")
            try:
                parsed_addresses = {ipaddress.ip_address(address) for address in raw_addresses}
            except ValueError as exc:
                raise EgressPolicyError("URL host resolved to an invalid address") from exc
        else:
            parsed_addresses = {literal}

        if any(not is_public_address(address) for address in parsed_addresses):
            raise EgressPolicyError("URL must point only to public host IP addresses")
        return tuple(sorted(str(address) for address in parsed_addresses))

    def build_opener(self, cookiejar: Any | None = None) -> urllib.request.OpenerDirector:
        opener = urllib.request.OpenerDirector()
        handlers: list[urllib.request.BaseHandler] = [
            _PinnedHTTPHandler(self),
            _PinnedHTTPSHandler(self),
            urllib.request.HTTPCookieProcessor(cookiejar),
            urllib.request.UnknownHandler(),
            urllib.request.HTTPDefaultErrorHandler(),
            urllib.request.HTTPErrorProcessor(),
            _ValidatedRedirectHandler(self),
        ]
        for handler in handlers:
            opener.add_handler(handler)
        opener.addheaders = []
        return opener

    def open(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
        method: str | None = None,
        timeout: float | None = None,
        cookiejar: Any | None = None,
    ) -> Any:
        self.resolve(url)
        request_headers = dict(headers or {})
        request_headers["Accept-Encoding"] = "identity"
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        return self.build_opener(cookiejar).open(request, timeout=timeout or self.timeout_seconds)


def _hostname_allowed(hostname: str, allowed_hosts: tuple[str, ...]) -> bool:
    return any(hostname == allowed or hostname.endswith(f".{allowed}") for allowed in allowed_hosts)


def _connect_to_resolved_target(
    target: ResolvedTarget,
    timeout: float | object,
    source_address: tuple[str, int] | None,
) -> socket.socket:
    last_error: OSError | None = None
    effective_timeout = timeout if isinstance(timeout, (int, float)) else None
    for address in target.addresses:
        try:
            return socket.create_connection(
                (address, target.port),
                timeout=effective_timeout,
                source_address=source_address,
            )
        except OSError as exc:
            last_error = exc
    raise last_error or OSError("No validated address was available")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *, target: ResolvedTarget, **kwargs: Any) -> None:
        self._resolved_target = target
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        source_address = getattr(self, "source_address", None)
        self.sock = _connect_to_resolved_target(self._resolved_target, self.timeout, source_address)
        if getattr(self, "_tunnel_host", None):
            getattr(self, "_tunnel")()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, target: ResolvedTarget, **kwargs: Any) -> None:
        self._resolved_target = target
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        source_address = getattr(self, "source_address", None)
        self.sock = _connect_to_resolved_target(self._resolved_target, self.timeout, source_address)
        server_hostname = self.host
        tunnel_host = getattr(self, "_tunnel_host", None)
        if tunnel_host:
            getattr(self, "_tunnel")()
            server_hostname = str(tunnel_host)
        context = getattr(self, "_context")
        self.sock = context.wrap_socket(self.sock, server_hostname=server_hostname)


class _PinnedHTTPHandler(urllib.request.AbstractHTTPHandler):
    def __init__(self, policy: VideoEgressPolicy) -> None:
        super().__init__()
        self._policy = policy

    def http_open(self, request: urllib.request.Request) -> Any:
        target = self._policy.resolve(request.full_url)
        factory = functools.partial(_PinnedHTTPConnection, target=target)
        return self.do_open(factory, request)

    http_request = urllib.request.AbstractHTTPHandler.do_request_


class _PinnedHTTPSHandler(urllib.request.AbstractHTTPHandler):
    def __init__(self, policy: VideoEgressPolicy, context: ssl.SSLContext | None = None) -> None:
        super().__init__()
        self._policy = policy
        self._context = context or ssl.create_default_context()

    def https_open(self, request: urllib.request.Request) -> Any:
        target = self._policy.resolve(request.full_url)
        factory = functools.partial(_PinnedHTTPSConnection, target=target)
        return self.do_open(factory, request, context=self._context)

    https_request = urllib.request.AbstractHTTPHandler.do_request_


class _ValidatedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, policy: VideoEgressPolicy) -> None:
        super().__init__()
        self._policy = policy

    def redirect_request(
        self,
        request: urllib.request.Request,
        response: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        absolute_url = urllib.parse.urljoin(request.full_url, new_url)
        self._policy.resolve(absolute_url)
        redirected = super().redirect_request(request, response, code, message, headers, absolute_url)
        if redirected is not None and _url_origin(request.full_url) != _url_origin(absolute_url):
            for header in ("Authorization", "Cookie", "Proxy-Authorization", "Host"):
                redirected.remove_header(header)
        return redirected


def _url_origin(url: str) -> tuple[str, str | None, int | None]:
    parsed = urllib.parse.urlsplit(url)
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        port = None
    return parsed.scheme, parsed.hostname, port


class SafeYoutubeDL(yt_dlp.YoutubeDL):
    def __init__(self, params: Mapping[str, Any], policy: VideoEgressPolicy) -> None:
        self._egress_policy = policy
        super().__init__(cast(Any, dict(params)))
        self._safe_opener = policy.build_opener(self.cookiejar)

    def urlopen(self, request: Request | urllib.request.Request | str) -> Response:
        if isinstance(request, str):
            url = request
            data = None
            method = None
            request_headers: Mapping[str, str] = {}
            timeout = self._egress_policy.timeout_seconds
        elif isinstance(request, urllib.request.Request):
            url = request.full_url
            data = request.data
            method = request.get_method()
            request_headers = request.headers
            timeout = getattr(request, "timeout", self._egress_policy.timeout_seconds)
        else:
            url = request.url
            data = request.data
            method = request.method
            request_headers = request.headers
            timeout = request.extensions.get("timeout", self._egress_policy.timeout_seconds)

        headers = dict(self.params.get("http_headers") or {})
        headers.update(request_headers)
        headers["Accept-Encoding"] = "identity"
        urllib_request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            result = self._safe_opener.open(urllib_request, timeout=timeout)
        except EgressPolicyError as exc:
            raise RequestError(str(exc), cause=exc) from exc
        except urllib.error.HTTPError as exc:
            response = Response(
                fp=cast(Any, exc),
                url=exc.geturl(),
                headers=dict(exc.headers.items()),
                status=exc.code,
                reason=str(exc.reason),
            )
            raise HTTPError(response) from exc
        except urllib.error.URLError as exc:
            raise TransportError(cause=exc) from exc
        return Response(
            fp=result,
            url=result.geturl(),
            headers=result.headers,
            status=result.getcode(),
            reason=str(getattr(result, "reason", "")) or None,
        )
