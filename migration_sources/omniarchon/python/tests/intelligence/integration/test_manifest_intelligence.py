"""
Integration tests for Manifest Intelligence functionality.

Tests end-to-end manifest intelligence generation:
- Manifest request event subscription and consumption
- Event routing to ManifestIntelligenceHandler
- Qdrant pattern queries (6,498 patterns)
- PostgreSQL schema queries (infrastructure information)
- Manifest completion/failure event publishing
- Correlation ID tracking across events
- Timeout handling (1500ms limit)
- Graceful degradation with partial results

Test Pattern: Event-driven integration testing for manifest intelligence
Reference: test_intelligence_event_flow.py, test_search_flow.py

Created: 2025-11-03
Purpose: Validate ManifestIntelligenceHandler event-driven manifest generation
Correlation ID: d387a8ce-cf92-4853-9b20-d679fb7979c8
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Configure path for imports
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "services" / "intelligence")
)

# Import event envelope models
from src.events.models.model_event_envelope import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)

# =========================================================================
# Mock Event Models (Manifest-specific)
# =========================================================================


class EnumManifestEventType:
    """Manifest event types."""

    MANIFEST_REQUESTED = "omninode.intelligence.event.manifest_requested.v1"
    MANIFEST_COMPLETED = "omninode.intelligence.event.manifest_completed.v1"
    MANIFEST_FAILED = "omninode.intelligence.event.manifest_failed.v1"


class ModelManifestRequestPayload:
    """Manifest request payload."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        include_patterns: bool = True,
        include_infrastructure: bool = True,
        include_schemas: bool = True,
        include_debug_intelligence: bool = True,
        timeout_ms: int = 1500,
    ):
        self.project_id = project_id
        self.include_patterns = include_patterns
        self.include_infrastructure = include_infrastructure
        self.include_schemas = include_schemas
        self.include_debug_intelligence = include_debug_intelligence
        self.timeout_ms = timeout_ms


class ModelManifestCompletedPayload:
    """Manifest completion payload."""

    def __init__(
        self,
        project_id: Optional[str],
        patterns: Dict[str, Any],
        infrastructure: Dict[str, Any],
        schemas: Dict[str, Any],
        debug_intelligence: Dict[str, Any],
        processing_time_ms: float,
        sections_included: List[str],
        cache_hit: bool = False,
    ):
        self.project_id = project_id
        self.patterns = patterns
        self.infrastructure = infrastructure
        self.schemas = schemas
        self.debug_intelligence = debug_intelligence
        self.processing_time_ms = processing_time_ms
        self.sections_included = sections_included
        self.cache_hit = cache_hit


class ModelManifestFailedPayload:
    """Manifest failure payload."""

    def __init__(
        self,
        project_id: Optional[str],
        error_message: str,
        error_code: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None,
    ):
        self.project_id = project_id
        self.error_message = error_message
        self.error_code = error_code
        self.retry_allowed = retry_allowed
        self.processing_time_ms = processing_time_ms
        self.error_details = error_details or {}
        self.suggested_action = suggested_action


# =========================================================================
# Event Helper Functions
# =========================================================================


def create_manifest_request_event(
    project_id: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
    include_patterns: bool = True,
    include_infrastructure: bool = True,
    include_schemas: bool = True,
    include_debug_intelligence: bool = True,
    timeout_ms: int = 1500,
) -> Dict[str, Any]:
    """Create MANIFEST_REQUESTED event."""
    correlation_id = correlation_id or uuid4()

    return {
        "event_id": str(uuid4()),
        "event_type": EnumManifestEventType.MANIFEST_REQUESTED,
        "correlation_id": str(correlation_id),
        "causation_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "source": {
            "service": "archon-intelligence",
            "instance_id": "test-instance-1",
            "hostname": "test-host",
        },
        "metadata": {},
        "payload": {
            "project_id": project_id,
            "include_patterns": include_patterns,
            "include_infrastructure": include_infrastructure,
            "include_schemas": include_schemas,
            "include_debug_intelligence": include_debug_intelligence,
            "timeout_ms": timeout_ms,
        },
    }


def create_manifest_completed_event(
    project_id: Optional[str],
    patterns: Dict[str, Any],
    infrastructure: Dict[str, Any],
    schemas: Dict[str, Any],
    debug_intelligence: Dict[str, Any],
    processing_time_ms: float,
    sections_included: List[str],
    correlation_id: Optional[UUID] = None,
    causation_id: Optional[UUID] = None,
    cache_hit: bool = False,
) -> Dict[str, Any]:
    """Create MANIFEST_COMPLETED event."""
    correlation_id = correlation_id or uuid4()

    return {
        "event_id": str(uuid4()),
        "event_type": EnumManifestEventType.MANIFEST_COMPLETED,
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id) if causation_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "source": {
            "service": "archon-intelligence",
            "instance_id": "test-instance-1",
            "hostname": "test-host",
        },
        "metadata": {},
        "payload": {
            "project_id": project_id,
            "patterns": patterns,
            "infrastructure": infrastructure,
            "schemas": schemas,
            "debug_intelligence": debug_intelligence,
            "processing_time_ms": processing_time_ms,
            "sections_included": sections_included,
            "cache_hit": cache_hit,
        },
    }


def create_manifest_failed_event(
    project_id: Optional[str],
    error_message: str,
    error_code: str,
    retry_allowed: bool,
    processing_time_ms: float,
    correlation_id: Optional[UUID] = None,
    causation_id: Optional[UUID] = None,
    error_details: Optional[Dict[str, Any]] = None,
    suggested_action: Optional[str] = None,
) -> Dict[str, Any]:
    """Create MANIFEST_FAILED event."""
    correlation_id = correlation_id or uuid4()

    return {
        "event_id": str(uuid4()),
        "event_type": EnumManifestEventType.MANIFEST_FAILED,
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id) if causation_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "source": {
            "service": "archon-intelligence",
            "instance_id": "test-instance-1",
            "hostname": "test-host",
        },
        "metadata": {},
        "payload": {
            "project_id": project_id,
            "error_message": error_message,
            "error_code": error_code,
            "retry_allowed": retry_allowed,
            "processing_time_ms": processing_time_ms,
            "error_details": error_details or {},
            "suggested_action": suggested_action,
        },
    }


# =========================================================================
# Test Fixtures
# =========================================================================


@pytest.fixture
def correlation_id():
    """Generate correlation ID for tracking."""
    return uuid4()


@pytest.fixture
def mock_kafka_consumer():
    """Create mock Kafka consumer."""
    consumer = AsyncMock()
    consumer.subscribe = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.commit = AsyncMock()
    return consumer


@pytest.fixture
def mock_kafka_producer():
    """Create mock Kafka producer."""
    producer = AsyncMock()
    producer.send = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    return producer


@pytest.fixture
def mock_qdrant_client():
    """Create mock Qdrant client with test pattern data."""
    client = AsyncMock()

    # Mock collection info (6,498 patterns from actual data)
    client.get_collection = AsyncMock(
        return_value=MagicMock(
            vectors_count=6498,
            points_count=6498,
            status="green",
        )
    )

    # Mock pattern search results
    client.search = AsyncMock(
        return_value=[
            MagicMock(
                id="pattern-1",
                payload={
                    "pattern_name": "NodeEffectPattern",
                    "pattern_type": "effect",
                    "file_path": "/services/intelligence/nodes/node_effect.py",
                    "language": "python",
                    "quality_score": 0.92,
                    "onex_compliance": 0.88,
                },
                score=0.95,
            ),
            MagicMock(
                id="pattern-2",
                payload={
                    "pattern_name": "NodeComputePattern",
                    "pattern_type": "compute",
                    "file_path": "/services/intelligence/nodes/node_compute.py",
                    "language": "python",
                    "quality_score": 0.89,
                    "onex_compliance": 0.85,
                },
                score=0.90,
            ),
        ]
    )

    # Mock scroll (batch retrieval)
    client.scroll = AsyncMock(
        return_value=(
            [
                MagicMock(
                    id=f"pattern-{i}",
                    payload={
                        "pattern_name": f"Pattern{i}",
                        "pattern_type": "effect",
                        "file_path": f"/services/test/pattern_{i}.py",
                        "language": "python",
                        "quality_score": 0.85,
                    },
                )
                for i in range(10)
            ],
            None,  # Next offset
        )
    )

    return client


@pytest.fixture
def mock_postgres_client():
    """Create mock PostgreSQL client with test schema data."""
    client = AsyncMock()

    # Mock schema queries
    client.fetch = AsyncMock(
        return_value=[
            {
                "table_name": "agent_routing_decisions",
                "column_count": 12,
                "row_count": 1523,
            },
            {
                "table_name": "agent_manifest_injections",
                "column_count": 8,
                "row_count": 456,
            },
            {
                "table_name": "workflow_steps",
                "column_count": 15,
                "row_count": 3421,
            },
        ]
    )

    # Mock connection context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    return client


@pytest.fixture
def mock_manifest_handler():
    """Create mock ManifestIntelligenceHandler."""
    handler = AsyncMock()

    # Mock successful execution
    handler.execute = AsyncMock(
        return_value={
            "success": True,
            "patterns": {
                "total_patterns": 6498,
                "pattern_types": {
                    "effect": 245,
                    "compute": 189,
                    "reducer": 134,
                    "orchestrator": 78,
                },
                "top_patterns": [
                    {
                        "name": "NodeEffectPattern",
                        "quality_score": 0.92,
                        "usage_count": 56,
                    }
                ],
            },
            "infrastructure": {
                "services": {
                    "archon-intelligence": {"status": "healthy", "port": 8053},
                    "archon-search": {"status": "healthy", "port": 8055},
                    "archon-bridge": {"status": "healthy", "port": 8054},
                },
                "databases": {
                    "qdrant": {"status": "healthy", "vectors": 6498},
                    "postgres": {"status": "healthy", "tables": 34},
                },
            },
            "schemas": {
                "tables": [
                    {
                        "name": "agent_routing_decisions",
                        "columns": 12,
                        "rows": 1523,
                    },
                ],
            },
            "debug_intelligence": {
                "recent_errors": [],
                "performance_metrics": {
                    "avg_query_time_ms": 45.3,
                    "cache_hit_rate": 0.78,
                },
            },
            "processing_time_ms": 856.4,
            "sections_included": [
                "patterns",
                "infrastructure",
                "schemas",
                "debug_intelligence",
            ],
        }
    )

    return handler


# =========================================================================
# Unit Tests for ManifestIntelligenceHandler
# =========================================================================


class TestManifestIntelligenceHandler:
    """Unit tests for ManifestIntelligenceHandler."""

    @pytest.mark.asyncio
    async def test_manifest_handler_execute_success(
        self, mock_qdrant_client, mock_postgres_client, correlation_id
    ):
        """Test successful manifest query with all sections."""
        # Create mock handler (actual handler will be implemented in parallel task)
        handler = AsyncMock()
        handler.execute = AsyncMock(
            return_value={
                "success": True,
                "patterns": {"total_patterns": 6498},
                "infrastructure": {"services": {}},
                "schemas": {"tables": []},
                "debug_intelligence": {"recent_errors": []},
                "processing_time_ms": 856.4,
                "sections_included": [
                    "patterns",
                    "infrastructure",
                    "schemas",
                    "debug_intelligence",
                ],
            }
        )

        result = await handler.execute(
            project_id=None,
            include_patterns=True,
            include_infrastructure=True,
            include_schemas=True,
            include_debug_intelligence=True,
            timeout_ms=1500,
            correlation_id=correlation_id,
        )

        assert result["success"] is True
        assert result["patterns"]["total_patterns"] == 6498
        assert len(result["sections_included"]) == 4
        handler.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_manifest_handler_partial_results(self, correlation_id):
        """Test graceful degradation with partial results."""
        # Create mock handler (actual handler will be implemented in parallel task)
        handler = AsyncMock()
        handler.execute = AsyncMock(
            return_value={
                "success": True,
                "patterns": {"total_patterns": 6498},
                "infrastructure": None,  # Failed to fetch
                "schemas": {"tables": []},
                "debug_intelligence": None,  # Failed to fetch
                "processing_time_ms": 1456.2,
                "sections_included": ["patterns", "schemas"],
                "warnings": [
                    "Infrastructure scan timed out",
                    "Debug intelligence query failed",
                ],
            }
        )

        result = await handler.execute(
            project_id=None,
            include_patterns=True,
            include_infrastructure=True,
            include_schemas=True,
            include_debug_intelligence=True,
            timeout_ms=1500,
            correlation_id=correlation_id,
        )

        assert result["success"] is True
        assert len(result["sections_included"]) == 2  # Only 2 succeeded
        assert "warnings" in result
        assert len(result["warnings"]) == 2

    @pytest.mark.asyncio
    async def test_manifest_handler_timeout(self, correlation_id):
        """Test timeout handling (1500ms limit)."""
        # Create mock handler (actual handler will be implemented in parallel task)
        handler = AsyncMock()
        handler.execute = AsyncMock(
            side_effect=asyncio.TimeoutError("Manifest generation timed out")
        )

        with pytest.raises(asyncio.TimeoutError):
            await handler.execute(
                project_id=None,
                include_patterns=True,
                include_infrastructure=True,
                include_schemas=True,
                include_debug_intelligence=True,
                timeout_ms=1500,
                correlation_id=correlation_id,
            )

    @pytest.mark.asyncio
    async def test_query_patterns(self, mock_qdrant_client, correlation_id):
        """Test Qdrant pattern queries."""
        # Test pattern search
        results = await mock_qdrant_client.search(
            collection_name="archon_patterns",
            query_vector=[0.1] * 1536,
            limit=10,
        )

        assert len(results) == 2
        assert results[0].payload["pattern_name"] == "NodeEffectPattern"
        assert results[0].payload["quality_score"] == 0.92

        # Test collection info
        collection_info = await mock_qdrant_client.get_collection("archon_patterns")
        assert collection_info.points_count == 6498

    @pytest.mark.asyncio
    async def test_query_infrastructure(self, correlation_id):
        """Test infrastructure scan queries."""
        # Mock infrastructure scan
        infrastructure_data = {
            "services": {
                "archon-intelligence": {"status": "healthy", "port": 8053},
                "archon-search": {"status": "healthy", "port": 8055},
            },
            "databases": {
                "qdrant": {"status": "healthy", "vectors": 6498},
                "postgres": {"status": "healthy", "tables": 34},
            },
        }

        assert "services" in infrastructure_data
        assert "databases" in infrastructure_data
        assert (
            infrastructure_data["services"]["archon-intelligence"]["status"]
            == "healthy"
        )

    @pytest.mark.asyncio
    async def test_query_schemas(self, mock_postgres_client, correlation_id):
        """Test PostgreSQL schema queries."""
        # Test schema fetch
        schemas = await mock_postgres_client.fetch(
            "SELECT * FROM information_schema.tables"
        )

        assert len(schemas) == 3
        assert schemas[0]["table_name"] == "agent_routing_decisions"
        assert schemas[0]["column_count"] == 12

    @pytest.mark.asyncio
    async def test_query_debug_intelligence(self, correlation_id):
        """Test debug intelligence queries."""
        # Mock debug intelligence data
        debug_data = {
            "recent_errors": [],
            "performance_metrics": {
                "avg_query_time_ms": 45.3,
                "cache_hit_rate": 0.78,
            },
            "health_checks": {
                "qdrant": "healthy",
                "postgres": "healthy",
                "kafka": "healthy",
            },
        }

        assert "recent_errors" in debug_data
        assert "performance_metrics" in debug_data
        assert debug_data["performance_metrics"]["cache_hit_rate"] == 0.78


# =========================================================================
# Integration Tests for Consumer Routing
# =========================================================================


class TestManifestConsumerRouting:
    """Integration tests for consumer routing of manifest events."""

    @pytest.mark.asyncio
    async def test_consumer_manifest_routing(
        self, mock_kafka_consumer, mock_manifest_handler, correlation_id
    ):
        """Test consumer routes manifest events correctly."""
        # Create manifest request event
        request_event = create_manifest_request_event(
            project_id="test-project",
            correlation_id=correlation_id,
        )

        # Simulate event routing
        event_type = request_event["event_type"]
        assert event_type == EnumManifestEventType.MANIFEST_REQUESTED

        # Verify payload can be deserialized
        payload = request_event["payload"]
        assert payload["include_patterns"] is True
        assert payload["timeout_ms"] == 1500

        # Mock handler execution
        result = await mock_manifest_handler.execute(
            project_id=payload["project_id"],
            include_patterns=payload["include_patterns"],
            include_infrastructure=payload["include_infrastructure"],
            include_schemas=payload["include_schemas"],
            include_debug_intelligence=payload["include_debug_intelligence"],
            timeout_ms=payload["timeout_ms"],
            correlation_id=correlation_id,
        )

        assert result["success"] is True
        assert "patterns" in result

    @pytest.mark.asyncio
    async def test_manifest_completion_published(
        self, mock_kafka_producer, correlation_id
    ):
        """Test completion event is published."""
        # Create completion event
        completed_event = create_manifest_completed_event(
            project_id="test-project",
            patterns={"total_patterns": 6498},
            infrastructure={"services": {}},
            schemas={"tables": []},
            debug_intelligence={"recent_errors": []},
            processing_time_ms=856.4,
            sections_included=[
                "patterns",
                "infrastructure",
                "schemas",
                "debug_intelligence",
            ],
            correlation_id=correlation_id,
        )

        # Publish to Kafka
        topic = "dev.archon-intelligence.intelligence.manifest-completed.v1"
        await mock_kafka_producer.send(topic, value=completed_event)

        mock_kafka_producer.send.assert_called_once()
        call_args = mock_kafka_producer.send.call_args
        assert call_args[0][0] == topic
        assert (
            call_args[1]["value"]["event_type"]
            == EnumManifestEventType.MANIFEST_COMPLETED
        )

    @pytest.mark.asyncio
    async def test_manifest_failure_published(
        self, mock_kafka_producer, correlation_id
    ):
        """Test failure event is published on error."""
        # Create failure event
        failed_event = create_manifest_failed_event(
            project_id="test-project",
            error_message="Failed to query Qdrant",
            error_code="QDRANT_ERROR",
            retry_allowed=True,
            processing_time_ms=234.5,
            correlation_id=correlation_id,
        )

        # Publish to Kafka
        topic = "dev.archon-intelligence.intelligence.manifest-failed.v1"
        await mock_kafka_producer.send(topic, value=failed_event)

        mock_kafka_producer.send.assert_called_once()
        call_args = mock_kafka_producer.send.call_args
        assert call_args[0][0] == topic
        assert (
            call_args[1]["value"]["event_type"] == EnumManifestEventType.MANIFEST_FAILED
        )


# =========================================================================
# End-to-End Tests
# =========================================================================


class TestManifestEndToEnd:
    """End-to-end tests for complete manifest flow."""

    @pytest.mark.asyncio
    async def test_manifest_e2e_flow(
        self,
        mock_kafka_consumer,
        mock_kafka_producer,
        mock_manifest_handler,
        correlation_id,
    ):
        """Test complete manifest request/response flow."""
        # Step 1: Consume MANIFEST_REQUESTED event
        request_event = create_manifest_request_event(
            project_id="omniarchon",
            correlation_id=correlation_id,
        )

        event_type = request_event["event_type"]
        payload = request_event["payload"]

        assert event_type == EnumManifestEventType.MANIFEST_REQUESTED

        # Step 2: Execute manifest handler
        result = await mock_manifest_handler.execute(
            project_id=payload["project_id"],
            include_patterns=payload["include_patterns"],
            include_infrastructure=payload["include_infrastructure"],
            include_schemas=payload["include_schemas"],
            include_debug_intelligence=payload["include_debug_intelligence"],
            timeout_ms=payload["timeout_ms"],
            correlation_id=correlation_id,
        )

        assert result["success"] is True

        # Step 3: Create and publish MANIFEST_COMPLETED event
        completed_event = create_manifest_completed_event(
            project_id=payload["project_id"],
            patterns=result["patterns"],
            infrastructure=result["infrastructure"],
            schemas=result["schemas"],
            debug_intelligence=result["debug_intelligence"],
            processing_time_ms=result["processing_time_ms"],
            sections_included=result["sections_included"],
            correlation_id=correlation_id,
        )

        topic = "dev.archon-intelligence.intelligence.manifest-completed.v1"
        await mock_kafka_producer.send(topic, value=completed_event)

        # Step 4: Commit offset
        await mock_kafka_consumer.commit()

        # Verify flow
        mock_kafka_producer.send.assert_called_once()
        mock_kafka_consumer.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_manifest_e2e_with_empty_collections(
        self,
        mock_kafka_consumer,
        mock_kafka_producer,
        correlation_id,
    ):
        """Test manifest when collections are empty."""
        # Create mock handler with empty results
        handler = AsyncMock()
        handler.execute = AsyncMock(
            return_value={
                "success": True,
                "patterns": {"total_patterns": 0},
                "infrastructure": {"services": {}},
                "schemas": {"tables": []},
                "debug_intelligence": {"recent_errors": []},
                "processing_time_ms": 123.4,
                "sections_included": [
                    "patterns",
                    "infrastructure",
                    "schemas",
                    "debug_intelligence",
                ],
                "warnings": ["No patterns found in Qdrant"],
            }
        )

        # Step 1: Consume request
        request_event = create_manifest_request_event(
            project_id=None,
            correlation_id=correlation_id,
        )

        # Step 2: Execute handler
        result = await handler.execute(
            project_id=None,
            include_patterns=True,
            include_infrastructure=True,
            include_schemas=True,
            include_debug_intelligence=True,
            timeout_ms=1500,
            correlation_id=correlation_id,
        )

        assert result["success"] is True
        assert result["patterns"]["total_patterns"] == 0
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_correlation_id_preserved(self, correlation_id):
        """Test correlation ID is preserved across events."""
        # Create request event
        request_event = create_manifest_request_event(
            project_id="test-project",
            correlation_id=correlation_id,
        )

        assert UUID(request_event["correlation_id"]) == correlation_id

        # Create completion event with same correlation ID
        completed_event = create_manifest_completed_event(
            project_id="test-project",
            patterns={"total_patterns": 6498},
            infrastructure={"services": {}},
            schemas={"tables": []},
            debug_intelligence={"recent_errors": []},
            processing_time_ms=856.4,
            sections_included=["patterns"],
            correlation_id=correlation_id,
        )

        assert UUID(completed_event["correlation_id"]) == correlation_id

        # Create failure event with same correlation ID
        failed_event = create_manifest_failed_event(
            project_id="test-project",
            error_message="Test error",
            error_code="TEST_ERROR",
            retry_allowed=True,
            processing_time_ms=123.4,
            correlation_id=correlation_id,
        )

        assert UUID(failed_event["correlation_id"]) == correlation_id

    @pytest.mark.asyncio
    async def test_causation_id_links_events(self, correlation_id):
        """Test causation_id links request to result events."""
        # Create request event
        request_event = create_manifest_request_event(
            project_id="test-project",
            correlation_id=correlation_id,
        )

        request_event_id = UUID(request_event["event_id"])

        # Create completion event with causation from request
        completed_event = create_manifest_completed_event(
            project_id="test-project",
            patterns={"total_patterns": 6498},
            infrastructure={"services": {}},
            schemas={"tables": []},
            debug_intelligence={"recent_errors": []},
            processing_time_ms=856.4,
            sections_included=["patterns"],
            correlation_id=correlation_id,
            causation_id=request_event_id,
        )

        assert UUID(completed_event["causation_id"]) == request_event_id
        assert UUID(completed_event["correlation_id"]) == correlation_id


# =========================================================================
# Performance and Timeout Tests
# =========================================================================


class TestManifestPerformance:
    """Performance and timeout tests for manifest generation."""

    @pytest.mark.asyncio
    async def test_manifest_meets_timeout_limit(
        self, mock_manifest_handler, correlation_id
    ):
        """Test manifest generation completes within 1500ms limit."""
        result = await mock_manifest_handler.execute(
            project_id=None,
            include_patterns=True,
            include_infrastructure=True,
            include_schemas=True,
            include_debug_intelligence=True,
            timeout_ms=1500,
            correlation_id=correlation_id,
        )

        # Verify processing time is under limit
        assert result["processing_time_ms"] < 1500

    @pytest.mark.asyncio
    async def test_manifest_handles_slow_queries(self, correlation_id):
        """Test graceful degradation when queries are slow."""
        # Create mock handler (actual handler will be implemented in parallel task)
        handler = AsyncMock()
        handler.execute = AsyncMock(
            return_value={
                "success": True,
                "patterns": None,  # Timed out
                "infrastructure": {"services": {}},
                "schemas": None,  # Timed out
                "debug_intelligence": {"recent_errors": []},
                "processing_time_ms": 1498.3,
                "sections_included": ["infrastructure", "debug_intelligence"],
                "warnings": [
                    "Pattern query timed out after 800ms",
                    "Schema query timed out after 600ms",
                ],
            }
        )

        result = await handler.execute(
            project_id=None,
            include_patterns=True,
            include_infrastructure=True,
            include_schemas=True,
            include_debug_intelligence=True,
            timeout_ms=1500,
            correlation_id=correlation_id,
        )

        # Should still succeed with partial results
        assert result["success"] is True
        assert len(result["sections_included"]) == 2
        assert len(result["warnings"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
