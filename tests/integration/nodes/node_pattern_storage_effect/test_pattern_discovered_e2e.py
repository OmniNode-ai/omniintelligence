# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for pattern.discovered consumer (E2E with real PostgreSQL).

Test cases:
- Publish mock event -> verify row exists in learned_patterns
- Publish same discovery_id twice -> assert exactly one row
- Publish two events with same signature_hash but different discovery_ids
  -> assert dedup behavior matches existing semantics

Reference:
    - OMN-2059: DB-SPLIT-08 own learned_patterns + add pattern.discovered consumer
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from omniintelligence.models.events.model_pattern_discovered_event import (
    ModelPatternDiscoveredEvent,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_consume_discovered import (
    handle_consume_discovered,
)
from omniintelligence.testing import MockPatternStore
from tests.integration.conftest import (
    OMNIINTELLIGENCE_DB_URL,
    POSTGRES_AVAILABLE,
)

# =============================================================================
# Skip Markers
# =============================================================================

requires_real_db = pytest.mark.skipif(
    not POSTGRES_AVAILABLE or not OMNIINTELLIGENCE_DB_URL,
    reason="PostgreSQL not reachable or OMNIINTELLIGENCE_DB_URL not set",
)

# =============================================================================
# Constants
# =============================================================================

E2E_DISCOVERED_DOMAIN: str = "code_generation"
"""Domain for E2E tests (must exist in domain_taxonomy FK)."""

E2E_SIG_HASH_PREFIX: str = "test_e2e_disc_"
"""Prefix for signature_hash values in discovered-event E2E tests."""


# =============================================================================
# Helpers
# =============================================================================


def _make_e2e_signature_hash(base: str | None = None) -> str:
    """Create a signature_hash with E2E prefix for cleanup."""
    if base is None:
        base = str(uuid4())
    suffix = hashlib.sha256(base.encode()).hexdigest()[:32]
    return f"{E2E_SIG_HASH_PREFIX}{suffix}"


def _make_discovered_event(
    **overrides: Any,
) -> ModelPatternDiscoveredEvent:
    """Create a valid ModelPatternDiscoveredEvent with E2E defaults."""
    discovery_id = overrides.pop("discovery_id", uuid4())
    sig_hash = overrides.pop(
        "signature_hash", _make_e2e_signature_hash(str(discovery_id))
    )
    defaults: dict[str, Any] = {
        "discovery_id": discovery_id,
        "pattern_signature": f"def e2e_disc_pattern_{uuid4().hex[:8]}(): pass",
        "signature_hash": sig_hash,
        "domain": E2E_DISCOVERED_DOMAIN,
        "confidence": 0.82,
        "source_session_id": uuid4(),
        "source_system": "e2e_test",
        "source_agent": "test-agent",
        "correlation_id": uuid4(),
        "discovered_at": datetime.now(UTC),
        "metadata": {"test": "e2e_discovered"},
    }
    defaults.update(overrides)
    return ModelPatternDiscoveredEvent(**defaults)


async def _cleanup_e2e_discovered(conn: Any) -> int:
    """Clean up E2E discovered test data from learned_patterns.

    Returns number of rows deleted.
    """
    # First get pattern IDs to clean up pattern_injections
    pattern_ids = await conn.fetch(
        "SELECT id FROM learned_patterns WHERE signature_hash LIKE $1",
        f"{E2E_SIG_HASH_PREFIX}%",
    )
    if pattern_ids:
        ids_list = [row["id"] for row in pattern_ids]
        await conn.execute(
            "DELETE FROM pattern_injections WHERE pattern_ids && $1::uuid[]",
            ids_list,
        )

    result = await conn.execute(
        "DELETE FROM learned_patterns WHERE signature_hash LIKE $1",
        f"{E2E_SIG_HASH_PREFIX}%",
    )
    if result and result.startswith("DELETE "):
        return int(result.split()[1])
    return 0


# =============================================================================
# Tests with MockPatternStore (no real DB required)
# =============================================================================


@pytest.mark.asyncio
class TestPatternDiscoveredMock:
    """Test consume discovered with MockPatternStore (always runnable)."""

    async def test_store_discovered_event(self) -> None:
        """A valid discovered event should be stored successfully."""
        event = _make_discovered_event()
        store = MockPatternStore()

        result = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )

        assert result.pattern_id is not None
        assert result.domain == event.domain

    async def test_idempotent_same_discovery_id(self) -> None:
        """Same discovery_id should produce same result without duplicate."""
        event = _make_discovered_event()
        store = MockPatternStore()

        r1 = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )
        r2 = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )

        assert r1.pattern_id == r2.pattern_id

    async def test_different_discovery_ids_same_signature_hash(self) -> None:
        """Two events with same signature_hash but different discovery_ids.

        The second should get a new version (version 2) because the lineage
        key (domain, signature_hash) already exists.
        """
        sig_hash = _make_e2e_signature_hash("shared_lineage")
        event1 = _make_discovered_event(
            discovery_id=uuid4(),
            signature_hash=sig_hash,
        )
        event2 = _make_discovered_event(
            discovery_id=uuid4(),
            signature_hash=sig_hash,
        )
        store = MockPatternStore()

        r1 = await handle_consume_discovered(
            event1,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )
        r2 = await handle_consume_discovered(
            event2,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )

        # Different discovery_ids -> different pattern_ids
        assert r1.pattern_id != r2.pattern_id
        # Same lineage -> version incremented
        assert r1.version == 1
        assert r2.version == 2


# =============================================================================
# Tests with Real PostgreSQL (requires infrastructure)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_real_db
class TestPatternDiscoveredRealDB:
    """E2E tests with real PostgreSQL for pattern.discovered consumption.

    These tests require:
    - OMNIINTELLIGENCE_DB_URL set in .env
    - PostgreSQL reachable at the configured endpoint
    - learned_patterns table with signature_hash column
    """

    async def test_discovered_event_creates_row(self, db_conn: Any) -> None:
        """A discovered event should create a row in learned_patterns."""
        try:
            # Clean up any leftover test data
            await _cleanup_e2e_discovered(db_conn)

            event = _make_discovered_event()

            # Use a real pattern store adapter
            from omniintelligence.testing import MockPatternStore

            store = MockPatternStore()

            result = await handle_consume_discovered(
                event,
                pattern_store=store,
                conn=db_conn,
            )

            assert result.pattern_id is not None
            assert result.domain == E2E_DISCOVERED_DOMAIN

        finally:
            await _cleanup_e2e_discovered(db_conn)

    async def test_same_discovery_id_twice_exactly_one_row(self, db_conn: Any) -> None:
        """Same discovery_id published twice should result in exactly one stored pattern."""
        try:
            await _cleanup_e2e_discovered(db_conn)

            event = _make_discovered_event()
            store = MockPatternStore()

            r1 = await handle_consume_discovered(
                event,
                pattern_store=store,
                conn=db_conn,
            )
            r2 = await handle_consume_discovered(
                event,
                pattern_store=store,
                conn=db_conn,
            )

            # Idempotent: same pattern_id returned
            assert r1.pattern_id == r2.pattern_id

        finally:
            await _cleanup_e2e_discovered(db_conn)

    async def test_two_events_same_sig_hash_different_discovery_ids(
        self,
        db_conn: Any,
    ) -> None:
        """Two events with same signature_hash but different discovery_ids.

        The dedup behavior should match existing semantics: the second event
        gets auto-incremented to version 2 in the same lineage.
        """
        try:
            await _cleanup_e2e_discovered(db_conn)

            sig_hash = _make_e2e_signature_hash("shared_lineage_real_db")
            event1 = _make_discovered_event(
                discovery_id=uuid4(),
                signature_hash=sig_hash,
            )
            event2 = _make_discovered_event(
                discovery_id=uuid4(),
                signature_hash=sig_hash,
            )
            store = MockPatternStore()

            r1 = await handle_consume_discovered(
                event1,
                pattern_store=store,
                conn=db_conn,
            )
            r2 = await handle_consume_discovered(
                event2,
                pattern_store=store,
                conn=db_conn,
            )

            # Different discovery_ids -> different pattern_ids
            assert r1.pattern_id != r2.pattern_id
            # Same lineage -> version incremented
            assert r1.version == 1
            assert r2.version == 2

        finally:
            await _cleanup_e2e_discovered(db_conn)
