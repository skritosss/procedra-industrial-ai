"""Address classification shared by every egress decision in the service.

Two features ask the same question from opposite sides. Video download requires
a target outside the machine and its network, so a private address is an attack.
A closed-perimeter installation requires the model endpoint to stay inside, so a
public address is a leak. Both need one answer to "is this address public", and
keeping a second copy of that predicate is how the two would eventually disagree.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[..., list]


def is_public_address(address: IPAddress) -> bool:
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def resolve_host_addresses(
    hostname: str,
    port: int,
    resolver: Resolver = socket.getaddrinfo,
) -> set[IPAddress]:
    """Every address a hostname answers with, or the literal it already is.

    Raises OSError when the name does not resolve. Callers decide what an
    unresolvable name means: for video it is a refusal, for the perimeter check
    it is a question that cannot be answered yet.
    """
    try:
        return {ipaddress.ip_address(hostname)}
    except ValueError:
        pass
    records = resolver(hostname, port, type=socket.SOCK_STREAM)
    addresses = {str(record[4][0]).split("%", 1)[0] for record in records if record[4]}
    if not addresses:
        raise OSError(f"Host {hostname} resolved to no addresses")
    return {ipaddress.ip_address(address) for address in addresses}
