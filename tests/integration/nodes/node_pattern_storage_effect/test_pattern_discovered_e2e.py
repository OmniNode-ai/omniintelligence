# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for pattern.discovered consumer.

Two test classes:
1. TestPatternDiscoveredMock - Pure mock tests (always runnable, no infra)
2. TestPatternDiscoveredWithDBFixture - Mock-based tests gated on DB availability

Test cases:
- Consume a discovered event and verify storage output
- Publish same discovery_id twice -> assert idempotent (same pattern_id)
- Publish two events with same signature_hash but different discovery_ids
  -> assert version auto-increment in the same lineage

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
# Tests with MockPatternStore + db_conn fixture (integration marker)
#
# NOTE: These tests use MockPatternStore (in-memory) rather than a real
# AdapterPatternStore because AdapterPatternStore requires a
# PostgresRepositoryRuntime backed by an asyncpg Pool, which is not
# directly compatible with the raw asyncpg.Connection from db_conn.
#
# The db_conn fixture is accepted but unused by MockPatternStore.
# The tests are kept under the integration marker so they run in CI
# alongside other integration tests and still verify the handler wiring.
#
# When a lightweight ProtocolPatternStore adapter that accepts a raw
# asyncpg connection is available, these should be migrated to use it.
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_real_db
class TestPatternDiscoveredWithDBFixture:
    """Integration tests for pattern.discovered consumption using MockPatternStore.

    These tests exercise the handler wiring (event mapping, idempotency, version
    increment) with an in-memory MockPatternStore. The db_conn fixture is present
    for infrastructure availability gating but is not used for actual SQL execution.

    For real database E2E tests, use AdapterPatternStore once a raw-connection
    compatible adapter is available.
    """

    async def test_discovered_event_creates_pattern(self, db_conn: Any) -> None:
        """A discovered event should be stored successfully via the handler."""
        event = _make_discovered_event()
        store = MockPatternStore()

        result = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=db_conn,
        )

        assert result.pattern_id is not None
        assert result.domain == E2E_DISCOVERED_DOMAIN

    async def test_same_discovery_id_twice_is_idempotent(self, db_conn: Any) -> None:
        """Same discovery_id published twice should return the same pattern_id."""
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

    async def test_two_events_same_sig_hash_different_discovery_ids(
        self,
        db_conn: Any,
    ) -> None:
        """Two events with same signature_hash but different discovery_ids.

        The dedup behavior should match existing semantics: the second event
        gets auto-incremented to version 2 in the same lineage.
        """
        sig_hash = _make_e2e_signature_hash("shared_lineage_mock_db")
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
