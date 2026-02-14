# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Tests for intelligence node introspection registration.

Validates that the introspection module correctly publishes STARTUP events
for all intelligence nodes and handles graceful degradation when the event
bus is unavailable.

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

# The runtime package __init__.py imports PluginIntelligence which triggers
# contract topic scanning. On some omnibase_core versions, this hits a
# broken import (EnumEvidenceTier). Guard against that here.
try:
    from omniintelligence.runtime.introspection import (
        INTELLIGENCE_NODES,
        IntrospectionResult,
        publish_intelligence_introspection,
        publish_intelligence_shutdown,
    )

    _CAN_IMPORT = True
except ImportError:
    _CAN_IMPORT = False

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="Cannot import introspection module due to omnibase_core version mismatch",
)


@pytest.mark.unit
class TestNodeDescriptor:
    """Test node descriptor deterministic node ID generation via public API."""

    def test_node_id_is_deterministic(self) -> None:
        """Same descriptor should produce the same UUID on repeated access."""
        desc = INTELLIGENCE_NODES[0]
        assert desc.node_id == desc.node_id

    def test_different_names_produce_different_ids(self) -> None:
        """Different node descriptors should produce different UUIDs."""
        desc1 = INTELLIGENCE_NODES[0]
        desc2 = INTELLIGENCE_NODES[1]
        assert desc1.name != desc2.name
        assert desc1.node_id != desc2.node_id

    def test_node_id_is_valid_uuid(self) -> None:
        """Node IDs must be valid UUIDs."""
        for desc in INTELLIGENCE_NODES:
            assert isinstance(desc.node_id, UUID), f"{desc.name} node_id is not a UUID"


@pytest.mark.unit
class TestIntelligenceNodes:
    """Test the INTELLIGENCE_NODES registry."""

    def test_all_expected_nodes_registered(self) -> None:
        """All intelligence nodes should be in the registry."""
        node_names = {d.name for d in INTELLIGENCE_NODES}
        expected_nodes = {
            "node_intelligence_orchestrator",
            "node_pattern_assembler_orchestrator",
            "node_intelligence_reducer",
            "node_quality_scoring_compute",
            "node_semantic_analysis_compute",
            "node_pattern_extraction_compute",
            "node_pattern_learning_compute",
            "node_pattern_matching_compute",
            "node_intent_classifier_compute",
            "node_execution_trace_parser_compute",
            "node_success_criteria_matcher_compute",
            "node_claude_hook_event_effect",
            "node_pattern_storage_effect",
            "node_pattern_promotion_effect",
            "node_pattern_demotion_effect",
            "node_pattern_feedback_effect",
            "node_pattern_lifecycle_effect",
        }
        assert node_names == expected_nodes

    def test_node_types_correct(self) -> None:
        """Node types should match their directory naming convention."""
        from omnibase_core.enums import EnumNodeKind

        for desc in INTELLIGENCE_NODES:
            if "orchestrator" in desc.name:
                assert desc.node_type == EnumNodeKind.ORCHESTRATOR, (
                    f"{desc.name} should be ORCHESTRATOR"
                )
            elif "reducer" in desc.name:
                assert desc.node_type == EnumNodeKind.REDUCER, (
                    f"{desc.name} should be REDUCER"
                )
            elif "compute" in desc.name:
                assert desc.node_type == EnumNodeKind.COMPUTE, (
                    f"{desc.name} should be COMPUTE"
                )
            elif "effect" in desc.name:
                assert desc.node_type == EnumNodeKind.EFFECT, (
                    f"{desc.name} should be EFFECT"
                )

    def test_unique_node_ids(self) -> None:
        """All node IDs should be unique."""
        ids = [d.node_id for d in INTELLIGENCE_NODES]
        assert len(ids) == len(set(ids)), "Duplicate node IDs found"


@pytest.mark.unit
class TestPublishIntelligenceIntrospection:
    """Test publish_intelligence_introspection function."""

    @pytest.mark.asyncio
    async def test_returns_empty_result_without_event_bus(self) -> None:
        """Should return empty IntrospectionResult when no event bus is provided."""
        result = await publish_intelligence_introspection(
            event_bus=None,
            correlation_id=uuid4(),
        )
        assert isinstance(result, IntrospectionResult)
        assert result.registered_nodes == []
        assert result.proxies == []

    @pytest.mark.asyncio
    async def test_publishes_for_all_nodes_with_event_bus(self) -> None:
        """Should attempt to publish for all nodes when event bus is available."""
        mock_event_bus = MagicMock()
        mock_event_bus.publish_envelope = AsyncMock(return_value=None)

        result = await publish_intelligence_introspection(
            event_bus=mock_event_bus,
            correlation_id=uuid4(),
            enable_heartbeat=False,
        )

        assert isinstance(result, IntrospectionResult)
        # Should have published for all nodes
        assert len(result.registered_nodes) == len(INTELLIGENCE_NODES)

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_publish_failure(self) -> None:
        """Should not raise when individual node introspection fails."""
        mock_event_bus = MagicMock()
        mock_event_bus.publish_envelope = AsyncMock(
            side_effect=RuntimeError("publish failed")
        )

        # Should not raise
        result = await publish_intelligence_introspection(
            event_bus=mock_event_bus,
            correlation_id=uuid4(),
            enable_heartbeat=False,
        )

        assert isinstance(result, IntrospectionResult)
        # No nodes should have succeeded
        assert result.registered_nodes == []


@pytest.mark.unit
class TestPublishIntelligenceShutdown:
    """Test publish_intelligence_shutdown function."""

    @pytest.mark.asyncio
    async def test_noop_without_event_bus(self) -> None:
        """Should do nothing when no event bus is provided."""
        await publish_intelligence_shutdown(
            event_bus=None,
            correlation_id=uuid4(),
        )

    @pytest.mark.asyncio
    async def test_publishes_shutdown_events(self) -> None:
        """Should publish shutdown events for all nodes."""
        mock_event_bus = MagicMock()
        mock_event_bus.publish_envelope = AsyncMock(return_value=None)

        await publish_intelligence_shutdown(
            event_bus=mock_event_bus,
            correlation_id=uuid4(),
        )

        # Should have been called for each node
        assert mock_event_bus.publish_envelope.call_count == len(INTELLIGENCE_NODES)
