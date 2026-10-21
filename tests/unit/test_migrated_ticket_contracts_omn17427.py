# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Migrated ticket contracts remain discoverable and retain their source bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from omnibase_core.models.ticket.model_ticket_contract import ModelTicketContract

pytestmark = pytest.mark.unit

_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.mark.parametrize(
    ("ticket", "source_blob"),
    [
        ("OMN-16764", 0x4E04932831A4E164091612608FD909AF626B5A9C),
        ("OMN-17492", 0x46ACC8FDE9B67187F180BAE9132338FC563856B5),
        ("OMN-21047", 0xC0747EEC835D7CB050E18026853C1A13984C57A2),
    ],
    ids=["OMN-16764", "OMN-17492", "OMN-21047"],
)
def test_migrated_contract_preserves_source(ticket: str, source_blob: int) -> None:
    """Read the resolver's repository path and compare with the original OCC blob."""
    content = (_CONTRACTS / f"{ticket}.yaml").read_bytes()
    contract = ModelTicketContract.from_yaml(content.decode("utf-8"))
    assert contract.ticket_id == ticket
    assert contract.dod_evidence

    # Git blob identity includes the header, not just the file's SHA-1 digest.
    header = f"blob {len(content)}\0".encode("ascii")
    digest = hashlib.sha1(header + content, usedforsecurity=False).digest()
    assert int.from_bytes(digest, "big") == source_blob
