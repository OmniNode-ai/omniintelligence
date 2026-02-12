# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_consume_discovered.

Tests the mapping from ModelPatternDiscoveredEvent to ModelPatternStorageInput
and delegation to handle_store_pattern.

Test cases:
- Happy path: valid event -> stored successfully
- Idempotent replay: same discovery_id processed twice -> same result
- Governance rejection: confidence < 0.5 -> rejected (Pydantic validation)
- Timezone-naive rejection: discovered_at without tzinfo -> validation error
- Field constraints: pattern_signature > 500 chars -> validation error

Reference:
    - OMN-2059: DB-SPLIT-08 own learned_patterns + add pattern.discovered consumer
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.models.events.model_pattern_discovered_event import (
    ModelPatternDiscoveredEvent,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_consume_discovered import (
    _map_discovered_to_storage_input,
    handle_consume_discovered,
)
from omniintelligence.testing import MockPatternStore

# =============================================================================
# Fixtures
# =============================================================================


def _make_discovered_event(
    **overrides,
) -> ModelPatternDiscoveredEvent:
    """Create a valid ModelPatternDiscoveredEvent with sensible defaults."""
    defaults = {
        "discovery_id": uuid4(),
        "pattern_signature": "def example_pattern(): return True",
        "signature_hash": "abc123def456789",
        "domain": "code_generation",
        "confidence": 0.85,
        "source_session_id": uuid4(),
        "source_system": "omniclaude",
        "source_agent": "test-agent",
        "correlation_id": uuid4(),
        "discovered_at": datetime.now(UTC),
        "metadata": {"context": "unit_test"},
    }
    defaults.update(overrides)
    return ModelPatternDiscoveredEvent(**defaults)


# =============================================================================
# Tests: Event Model Validation
# =============================================================================


class TestModelPatternDiscoveredEventValidation:
    """Test Pydantic validation on ModelPatternDiscoveredEvent."""

    def test_valid_event_creates_successfully(self) -> None:
        """A valid event should be created without errors."""
        event = _make_discovered_event()
        assert event.event_type == "PatternDiscovered"
        assert event.confidence >= 0.5

    def test_confidence_below_threshold_raises(self) -> None:
        """Confidence < 0.5 should be rejected by Pydantic validation."""
        with pytest.raises(ValueError, match="greater than or equal to 0.5"):
            _make_discovered_event(confidence=0.3)

    def test_timezone_naive_discovered_at_raises(self) -> None:
        """discovered_at without tzinfo should be rejected."""
        with pytest.raises(ValueError, match="timezone-aware"):
            _make_discovered_event(
                discovered_at=datetime(2025, 1, 1, 12, 0, 0),
            )

    def test_pattern_signature_over_500_chars_raises(self) -> None:
        """pattern_signature > 500 characters should be rejected."""
        with pytest.raises(ValueError, match="at most 500"):
            _make_discovered_event(pattern_signature="x" * 501)

    def test_frozen_model_is_immutable(self) -> None:
        """Frozen model should not allow attribute modification."""
        event = _make_discovered_event()
        with pytest.raises(ValidationError):
            event.confidence = 0.99  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields should be rejected."""
        with pytest.raises(ValueError):
            _make_discovered_event(unexpected_field="nope")


# =============================================================================
# Tests: Mapping
# =============================================================================


class TestMapDiscoveredToStorageInput:
    """Test the mapping from discovery event to storage input."""

    def test_maps_discovery_id_to_pattern_id(self) -> None:
        """discovery_id should become pattern_id for idempotency."""
        event = _make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.pattern_id == event.discovery_id

    def test_maps_pattern_signature_to_signature(self) -> None:
        """pattern_signature should map to signature field."""
        event = _make_discovered_event(pattern_signature="test_sig")
        result = _map_discovered_to_storage_input(event)
        assert result.signature == "test_sig"

    def test_maps_signature_hash(self) -> None:
        """signature_hash should pass through."""
        event = _make_discovered_event(signature_hash="hash_abc")
        result = _map_discovered_to_storage_input(event)
        assert result.signature_hash == "hash_abc"

    def test_maps_domain(self) -> None:
        """domain should pass through."""
        event = _make_discovered_event(domain="testing")
        result = _map_discovered_to_storage_input(event)
        assert result.domain == "testing"

    def test_maps_confidence(self) -> None:
        """confidence should pass through."""
        event = _make_discovered_event(confidence=0.92)
        result = _map_discovered_to_storage_input(event)
        assert result.confidence == 0.92

    def test_maps_correlation_id(self) -> None:
        """correlation_id should pass through."""
        cid = uuid4()
        event = _make_discovered_event(correlation_id=cid)
        result = _map_discovered_to_storage_input(event)
        assert result.correlation_id == cid

    def test_version_defaults_to_1(self) -> None:
        """Version should default to 1 for new patterns."""
        event = _make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.version == 1

    def test_maps_metadata_actor_to_source_system(self) -> None:
        """source_system should become metadata.actor."""
        event = _make_discovered_event(source_system="omniclaude")
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.actor == "omniclaude"

    def test_maps_metadata_source_run_id_to_session(self) -> None:
        """source_session_id should become metadata.source_run_id."""
        sid = uuid4()
        event = _make_discovered_event(source_session_id=sid)
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.source_run_id == str(sid)

    def test_maps_learned_at_to_discovered_at(self) -> None:
        """discovered_at should become learned_at."""
        ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        event = _make_discovered_event(discovered_at=ts)
        result = _map_discovered_to_storage_input(event)
        assert result.learned_at == ts

    def test_maps_source_agent_to_additional_attributes(self) -> None:
        """source_agent should be in metadata.additional_attributes."""
        event = _make_discovered_event(source_agent="my-agent")
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.additional_attributes.get("source_agent") == "my-agent"

    def test_includes_discovered_tag(self) -> None:
        """Tags should include 'discovered' and source_system."""
        event = _make_discovered_event(source_system="omniclaude")
        result = _map_discovered_to_storage_input(event)
        assert "discovered" in result.metadata.tags
        assert "omniclaude" in result.metadata.tags

    def test_learning_context_is_pattern_discovery(self) -> None:
        """learning_context should be 'pattern_discovery'."""
        event = _make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.learning_context == "pattern_discovery"


# =============================================================================
# Tests: Handler (async)
# =============================================================================


@pytest.mark.asyncio
class TestHandleConsumeDiscovered:
    """Test handle_consume_discovered with mock dependencies."""

    async def test_happy_path_stores_pattern(self) -> None:
        """Valid event should be stored successfully."""
        event = _make_discovered_event()
        store = MockPatternStore()

        result = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]  # MockPatternStore ignores conn
        )

        assert result.pattern_id is not None
        assert result.domain == event.domain
        assert result.signature == event.pattern_signature
        assert result.signature_hash == event.signature_hash
        assert result.correlation_id == event.correlation_id

    async def test_idempotent_replay_returns_same_result(self) -> None:
        """Same discovery_id processed twice should return same result."""
        event = _make_discovered_event()
        store = MockPatternStore()

        result1 = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )
        result2 = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]
        )

        assert result1.pattern_id == result2.pattern_id
        assert result1.domain == result2.domain

    async def test_governance_rejection_low_confidence(self) -> None:
        """Confidence below threshold should raise ValueError.

        Note: Pydantic rejects confidence < 0.5 at event creation time,
        so this tests that the validation boundary is respected.
        """
        with pytest.raises(ValueError, match="greater than or equal to 0.5"):
            _make_discovered_event(confidence=0.3)
