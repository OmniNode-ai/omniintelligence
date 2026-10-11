# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""No shipped YAML configuration carries a private-network address (OMN-20936).

Deployment endpoints belong to whoever runs the system and arrive through an
environment variable or a private overlay. A contract or registry that names a
private host forces every consumer onto it.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src" / "omniintelligence"
# The RFC 5737 documentation ranges are what examples should use; they are
# reserved, never routed, and not a deployment's address.
_DOCUMENTATION_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def _private_addresses(text: str) -> list[str]:
    found: list[str] = []
    for candidate in _IPV4.findall(text):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if (
            address.is_private
            and not address.is_loopback
            and not address.is_unspecified
            and not address.is_link_local
            and not any(address in network for network in _DOCUMENTATION_NETWORKS)
        ):
            found.append(candidate)
    return found


def test_the_detector_finds_a_private_address() -> None:
    """Positive control: private-range addresses are found; documentation and loopback are not."""
    lan = ".".join(("192", "168", "1", "5"))
    ten = ".".join(("10", "1", "2", "3"))
    assert _private_addresses(f'default_endpoint: "http://{lan}:8100"') == [lan]
    assert _private_addresses(f"host: {ten}") == [ten]
    assert _private_addresses("host: 192.0.2.10") == []
    assert _private_addresses("bind: 127.0.0.1 and 0.0.0.0") == []


def test_no_shipped_yaml_names_a_private_address() -> None:
    files = sorted(_SRC.rglob("*.yaml"))
    assert files, "found no shipped YAML to check"
    offenders = {
        str(path.relative_to(_SRC)): addresses
        for path in files
        if (addresses := _private_addresses(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}
