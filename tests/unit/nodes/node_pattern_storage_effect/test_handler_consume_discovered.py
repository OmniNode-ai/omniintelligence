# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_consume_discovered.

Tests the mapping from ModelPatternDiscoveredEvent to ModelPatternStorageInput
and delegation to handle_store_pattern.

Test cases:
- Happy path: valid event -> stored successfully
- Idempotent replay: same discovery_id processed twice -> same result
- Low confidence rejected at event creation: confidence < 0.5 -> Pydantic validation
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

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_consume_discovered import (
    _map_discovered_to_storage_input,
    handle_consume_discovered,
)
from omniintelligence.testing import MockPatternStore, make_discovered_event

# White-box import: _map_discovered_to_storage_input is a private helper, but
# we intentionally test it directly to verify the field-by-field mapping from
# ModelPatternDiscoveredEvent to ModelPatternStorageInput without going through
# the full async handler.  This coupling is acceptable because the mapping
# contract is critical and the function is unlikely to be relocated.


# =============================================================================
# Tests: Event Model Validation
# =============================================================================


class TestModelPatternDiscoveredEventValidation:
    """Test Pydantic validation on ModelPatternDiscoveredEvent."""

    def test_valid_event_creates_successfully(self) -> None:
        """A valid event should be created without errors."""
        event = make_discovered_event()
        assert event.event_type == "PatternDiscovered"
        assert event.confidence >= 0.5

    def test_confidence_below_threshold_raises(self) -> None:
        """Confidence < 0.5 should be rejected by Pydantic validation."""
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            make_discovered_event(confidence=0.3)

    def test_timezone_naive_discovered_at_raises(self) -> None:
        """discovered_at without tzinfo should be rejected."""
        with pytest.raises(ValueError, match="timezone-aware"):
            make_discovered_event(
                discovered_at=datetime(2025, 1, 1, 12, 0, 0),
            )

    def test_pattern_signature_over_500_chars_raises(self) -> None:
        """pattern_signature > 500 characters should be rejected."""
        with pytest.raises(ValueError, match="at most 500"):
            make_discovered_event(pattern_signature="x" * 501)

    def test_frozen_model_is_immutable(self) -> None:
        """Frozen model should not allow attribute modification."""
        event = make_discovered_event()
        with pytest.raises(ValidationError):
            event.confidence = 0.99  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields should be rejected."""
        with pytest.raises(ValueError):
            make_discovered_event(unexpected_field="nope")


# =============================================================================
# Tests: Mapping
# =============================================================================


class TestMapDiscoveredToStorageInput:
    """Test the mapping from discovery event to storage input."""

    def test_maps_discovery_id_to_pattern_id(self) -> None:
        """discovery_id should become pattern_id for idempotency."""
        event = make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.pattern_id == event.discovery_id

    def test_maps_pattern_signature_to_signature(self) -> None:
        """pattern_signature should map to signature field."""
        event = make_discovered_event(pattern_signature="test_sig")
        result = _map_discovered_to_storage_input(event)
        assert result.signature == "test_sig"

    def test_maps_signature_hash(self) -> None:
        """signature_hash should pass through."""
        event = make_discovered_event(signature_hash="hash_abc")
        result = _map_discovered_to_storage_input(event)
        assert result.signature_hash == "hash_abc"

    def test_maps_domain(self) -> None:
        """domain should pass through."""
        event = make_discovered_event(domain="testing")
        result = _map_discovered_to_storage_input(event)
        assert result.domain == "testing"

    def test_maps_confidence(self) -> None:
        """confidence should pass through."""
        event = make_discovered_event(confidence=0.92)
        result = _map_discovered_to_storage_input(event)
        assert result.confidence == 0.92

    def test_maps_correlation_id(self) -> None:
        """correlation_id should pass through."""
        cid = uuid4()
        event = make_discovered_event(correlation_id=cid)
        result = _map_discovered_to_storage_input(event)
        assert result.correlation_id == cid

    def test_version_defaults_to_1(self) -> None:
        """Version should default to 1 for new patterns."""
        event = make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.version == 1

    def test_maps_metadata_actor_to_source_system(self) -> None:
        """source_system should become metadata.actor."""
        event = make_discovered_event(source_system="omniclaude")
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.actor == "omniclaude"

    def test_maps_metadata_source_run_id_to_session(self) -> None:
        """source_session_id should become metadata.source_run_id."""
        sid = uuid4()
        event = make_discovered_event(source_session_id=sid)
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.source_run_id == str(sid)

    def test_maps_learned_at_to_discovered_at(self) -> None:
        """discovered_at should become learned_at."""
        ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        event = make_discovered_event(discovered_at=ts)
        result = _map_discovered_to_storage_input(event)
        assert result.learned_at == ts

    def test_maps_source_agent_to_additional_attributes(self) -> None:
        """source_agent should be in metadata.additional_attributes."""
        event = make_discovered_event(source_agent="my-agent")
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.additional_attributes.get("source_agent") == "my-agent"

    def test_source_agent_none_omitted_from_additional_attributes(self) -> None:
        """When source_agent is None, it should NOT appear in additional_attributes."""
        event = make_discovered_event(source_agent=None)
        result = _map_discovered_to_storage_input(event)
        assert "source_agent" not in result.metadata.additional_attributes

    def test_includes_discovered_tag(self) -> None:
        """Tags should include 'discovered' and source_system."""
        event = make_discovered_event(source_system="omniclaude")
        result = _map_discovered_to_storage_input(event)
        assert "discovered" in result.metadata.tags
        assert "omniclaude" in result.metadata.tags

    def test_learning_context_is_pattern_discovery(self) -> None:
        """learning_context should be 'pattern_discovery'."""
        event = make_discovered_event()
        result = _map_discovered_to_storage_input(event)
        assert result.metadata.learning_context == "pattern_discovery"

    def test_reserved_key_with_non_string_value_silently_dropped(self) -> None:
        """A reserved key with a non-string value is silently dropped.

        When event.metadata contains a reserved key (e.g. 'source_agent')
        whose value is not a string (e.g. an integer), the reserved-key
        check on line 67 skips it, and then the isinstance(value, str) guard
        on line 69 also skips it.  The net effect is a silent drop — no error,
        no entry in additional_attributes.

        This test documents the edge case so upstream bugs that send wrong
        types for reserved keys don't go unnoticed in test coverage.
        """
        event = make_discovered_event(
            source_agent=None,  # Explicit source_agent is None, so line 80 skips it
            metadata={"source_agent": 42},  # Reserved key with int value
        )
        result = _map_discovered_to_storage_input(event)
        # The integer value is dropped by the reserved-key guard, so
        # source_agent should not appear in additional_attributes at all.
        assert "source_agent" not in result.metadata.additional_attributes

    def test_reserved_metadata_fields_do_not_leak_into_additional_attributes(
        self,
    ) -> None:
        """Top-level ModelPatternStorageMetadata field names in event.metadata
        must be blocked by _RESERVED_KEYS to prevent key collisions.

        If event.metadata contained 'actor' or 'source_run_id' with string
        values, those could overwrite the explicit top-level fields in the
        constructed ModelPatternStorageMetadata (since additional_attributes
        is a separate dict, the collision is conceptual — but the name reuse
        is confusing and should be prevented).
        """
        event = make_discovered_event(
            metadata={
                "source_run_id": "attacker-run-id",
                "actor": "attacker-actor",
                "learning_context": "attacker-context",
                "tags": "should-be-dropped",
                "additional_attributes": "should-be-dropped",
                "legitimate_key": "kept",
            },
        )
        result = _map_discovered_to_storage_input(event)
        attrs = result.metadata.additional_attributes
        # Reserved keys are blocked — none of them leak into additional_attributes
        assert "source_run_id" not in attrs
        assert "actor" not in attrs
        assert "learning_context" not in attrs
        assert "tags" not in attrs
        assert "additional_attributes" not in attrs
        # Non-reserved string keys pass through normally
        assert attrs["legitimate_key"] == "kept"

    def test_reserved_metadata_field_with_non_string_value_silently_dropped(
        self,
    ) -> None:
        """A top-level metadata field name with a non-string value is also
        silently dropped (covered by the reserved-key guard before the
        isinstance check is reached).
        """
        event = make_discovered_event(
            metadata={
                "actor": 999,  # Reserved + non-string
                "learning_context": ["list", "not", "string"],  # Reserved + non-string
                "normal_key": "normal_value",
            },
        )
        result = _map_discovered_to_storage_input(event)
        attrs = result.metadata.additional_attributes
        assert "actor" not in attrs
        assert "learning_context" not in attrs
        assert attrs["normal_key"] == "normal_value"


# =============================================================================
# Tests: Handler (async)
# =============================================================================


@pytest.mark.asyncio
class TestHandleConsumeDiscovered:
    """Test handle_consume_discovered with mock dependencies."""

    async def test_happy_path_stores_pattern(self) -> None:
        """Valid event should be stored successfully."""
        event = make_discovered_event()
        store = MockPatternStore()

        result = await handle_consume_discovered(
            event,
            pattern_store=store,
            conn=None,  # type: ignore[arg-type]  # MockPatternStore ignores conn
        )

        assert result.success
        assert result.event is not None
        assert result.event.pattern_id is not None
        assert result.event.domain == event.domain
        assert result.event.signature == event.pattern_signature
        assert result.event.signature_hash == event.signature_hash
        assert result.event.correlation_id == event.correlation_id

    async def test_idempotent_replay_returns_same_result(self) -> None:
        """Same discovery_id processed twice should return same result."""
        event = make_discovered_event()
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

        assert result1.success and result1.event is not None
        assert result2.success and result2.event is not None
        assert result1.event.pattern_id == result2.event.pattern_id
        assert result1.event.domain == result2.event.domain

    async def test_low_confidence_rejected_at_event_creation(self) -> None:
        """Confidence below threshold is rejected by Pydantic at event creation.

        Note: Pydantic rejects confidence < 0.5 before the handler runs,
        so this validates the model-level validation boundary.
        """
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.5"):
            make_discovered_event(confidence=0.3)
