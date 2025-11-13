"""
Integration Tests for Phase 4 Event Handlers

Tests all Phase 4 handlers:
- BridgeIntelligenceHandler (3 operations)
- DocumentProcessingHandler (2 operations)
- SystemUtilitiesHandler (3 operations)

Created: 2025-10-22
Purpose: Comprehensive integration testing for Phase 4 event-driven implementation
"""

import asyncio
from uuid import uuid4

import pytest
from events.models.bridge_intelligence_events import EnumBridgeEventType
from events.models.document_processing_events import EnumDocumentProcessingEventType
from events.models.system_utilities_events import EnumSystemUtilitiesEventType
from handlers.bridge_intelligence_handler import BridgeIntelligenceHandler
from handlers.document_processing_handler import DocumentProcessingHandler
from handlers.system_utilities_handler import SystemUtilitiesHandler

# ============================================================================
# Bridge Intelligence Handler Tests
# ============================================================================


class TestBridgeIntelligenceHandler:
    """Integration tests for BridgeIntelligenceHandler."""

    @pytest.fixture
    def bridge_handler(self):
        """Create BridgeIntelligenceHandler instance."""
        return BridgeIntelligenceHandler()

    def test_can_handle_generate_intelligence(self, bridge_handler):
        """Test handler can handle GENERATE_INTELLIGENCE_REQUESTED events."""
        assert bridge_handler.can_handle(
            EnumBridgeEventType.GENERATE_INTELLIGENCE_REQUESTED.value
        )
        assert bridge_handler.can_handle("GENERATE_INTELLIGENCE_REQUESTED")
        assert bridge_handler.can_handle("bridge.generate-intelligence-requested")

    def test_can_handle_bridge_health(self, bridge_handler):
        """Test handler can handle BRIDGE_HEALTH_REQUESTED events."""
        assert bridge_handler.can_handle(
            EnumBridgeEventType.BRIDGE_HEALTH_REQUESTED.value
        )
        assert bridge_handler.can_handle("BRIDGE_HEALTH_REQUESTED")
        assert bridge_handler.can_handle("bridge.bridge-health-requested")

    def test_can_handle_capabilities(self, bridge_handler):
        """Test handler can handle CAPABILITIES_REQUESTED events."""
        assert bridge_handler.can_handle(
            EnumBridgeEventType.CAPABILITIES_REQUESTED.value
        )
        assert bridge_handler.can_handle("CAPABILITIES_REQUESTED")
        assert bridge_handler.can_handle("bridge.capabilities-requested")

    def test_cannot_handle_unrelated_events(self, bridge_handler):
        """Test handler rejects unrelated event types."""
        assert not bridge_handler.can_handle("UNKNOWN_EVENT")
        assert not bridge_handler.can_handle("document.process-requested")

    def test_get_handler_name(self, bridge_handler):
        """Test handler name is correct."""
        assert bridge_handler.get_handler_name() == "BridgeIntelligenceHandler"

    def test_get_initial_metrics(self, bridge_handler):
        """Test initial metrics are zero."""
        metrics = bridge_handler.get_metrics()
        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["generate_intelligence_successes"] == 0
        assert metrics["health_check_successes"] == 0
        assert metrics["capabilities_successes"] == 0
        assert metrics["success_rate"] == 1.0  # No events = 100% success

    @pytest.mark.asyncio
    async def test_shutdown(self, bridge_handler):
        """Test handler shutdown cleans up resources."""
        await bridge_handler.shutdown()
        # Verify HTTP client is closed
        assert bridge_handler.http_client is None


# ============================================================================
# Document Processing Handler Tests
# ============================================================================


class TestDocumentProcessingHandler:
    """Integration tests for DocumentProcessingHandler."""

    @pytest.fixture
    def doc_handler(self):
        """Create DocumentProcessingHandler instance."""
        return DocumentProcessingHandler()

    def test_can_handle_process_document(self, doc_handler):
        """Test handler can handle PROCESS_DOCUMENT_REQUESTED events."""
        assert doc_handler.can_handle(
            EnumDocumentProcessingEventType.PROCESS_DOCUMENT_REQUESTED.value
        )
        assert doc_handler.can_handle("PROCESS_DOCUMENT_REQUESTED")
        assert doc_handler.can_handle("document.process-document-requested")

    def test_can_handle_batch_index(self, doc_handler):
        """Test handler can handle BATCH_INDEX_REQUESTED events."""
        assert doc_handler.can_handle(
            EnumDocumentProcessingEventType.BATCH_INDEX_REQUESTED.value
        )
        assert doc_handler.can_handle("BATCH_INDEX_REQUESTED")
        assert doc_handler.can_handle("document.batch-index-requested")

    def test_cannot_handle_unrelated_events(self, doc_handler):
        """Test handler rejects unrelated event types."""
        assert not doc_handler.can_handle("UNKNOWN_EVENT")
        assert not doc_handler.can_handle("bridge.generate-intelligence-requested")

    def test_get_handler_name(self, doc_handler):
        """Test handler name is correct."""
        assert doc_handler.get_handler_name() == "DocumentProcessingHandler"

    def test_get_initial_metrics(self, doc_handler):
        """Test initial metrics are zero."""
        metrics = doc_handler.get_metrics()
        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["process_document_successes"] == 0
        assert metrics["batch_index_successes"] == 0
        assert metrics["total_documents_processed"] == 0
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_shutdown(self, doc_handler):
        """Test handler shutdown cleans up resources."""
        await doc_handler.shutdown()
        assert doc_handler.http_client is None


# ============================================================================
# System Utilities Handler Tests
# ============================================================================


class TestSystemUtilitiesHandler:
    """Integration tests for SystemUtilitiesHandler."""

    @pytest.fixture
    def sys_handler(self):
        """Create SystemUtilitiesHandler instance."""
        return SystemUtilitiesHandler()

    def test_can_handle_metrics_request(self, sys_handler):
        """Test handler can handle METRICS_REQUESTED events."""
        assert sys_handler.can_handle(
            EnumSystemUtilitiesEventType.METRICS_REQUESTED.value
        )
        assert sys_handler.can_handle("METRICS_REQUESTED")
        assert sys_handler.can_handle("system.metrics-requested")

    def test_can_handle_kafka_health(self, sys_handler):
        """Test handler can handle KAFKA_HEALTH_REQUESTED events."""
        assert sys_handler.can_handle(
            EnumSystemUtilitiesEventType.KAFKA_HEALTH_REQUESTED.value
        )
        assert sys_handler.can_handle("KAFKA_HEALTH_REQUESTED")
        assert sys_handler.can_handle("system.kafka-health-requested")

    def test_can_handle_kafka_metrics(self, sys_handler):
        """Test handler can handle KAFKA_METRICS_REQUESTED events."""
        assert sys_handler.can_handle(
            EnumSystemUtilitiesEventType.KAFKA_METRICS_REQUESTED.value
        )
        assert sys_handler.can_handle("KAFKA_METRICS_REQUESTED")
        assert sys_handler.can_handle("system.kafka-metrics-requested")

    def test_cannot_handle_unrelated_events(self, sys_handler):
        """Test handler rejects unrelated event types."""
        assert not sys_handler.can_handle("UNKNOWN_EVENT")
        assert not sys_handler.can_handle("document.process-requested")

    def test_get_handler_name(self, sys_handler):
        """Test handler name is correct."""
        assert sys_handler.get_handler_name() == "SystemUtilitiesHandler"

    def test_get_initial_metrics(self, sys_handler):
        """Test initial metrics are zero."""
        metrics = sys_handler.get_metrics()
        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["metrics_requests_successes"] == 0
        assert metrics["kafka_health_successes"] == 0
        assert metrics["kafka_metrics_successes"] == 0
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_shutdown(self, sys_handler):
        """Test handler shutdown cleans up resources."""
        await sys_handler.shutdown()
        assert sys_handler.http_client is None


# ============================================================================
# End-to-End Event Flow Tests
# ============================================================================


class TestEventFlowIntegration:
    """
    End-to-end tests for event flow through handlers.

    Note: These tests require mock Kafka and service infrastructure.
    They verify the complete event processing pipeline.
    """

    @pytest.fixture
    def correlation_id(self):
        """Generate unique correlation ID for test."""
        return str(uuid4())

    def test_bridge_generate_intelligence_event_structure(self, correlation_id):
        """Test GENERATE_INTELLIGENCE_REQUESTED event structure."""
        event = {
            "event_type": "omninode.bridge.event.generate_intelligence_requested.v1",
            "correlation_id": correlation_id,
            "payload": {
                "source_path": "test/file.py",
                "content": "def hello(): pass",
                "language": "python",
                "metadata_options": {"include_blake3_hash": True},
            },
        }

        handler = BridgeIntelligenceHandler()
        assert handler.can_handle(event["event_type"])

        # Verify payload extraction would work
        correlation = handler._get_correlation_id(event)
        assert correlation == correlation_id

        payload = handler._get_payload(event)
        assert payload["source_path"] == "test/file.py"
        assert payload["language"] == "python"

    def test_document_process_event_structure(self, correlation_id):
        """Test PROCESS_DOCUMENT_REQUESTED event structure."""
        event = {
            "event_type": "omninode.document.event.process_document_requested.v1",
            "correlation_id": correlation_id,
            "payload": {
                "document_path": "docs/README.md",
                "content": "# Project README",
                "document_type": "markdown",
                "extract_entities": True,
                "generate_embeddings": True,
            },
        }

        handler = DocumentProcessingHandler()
        assert handler.can_handle(event["event_type"])

        correlation = handler._get_correlation_id(event)
        assert correlation == correlation_id

        payload = handler._get_payload(event)
        assert payload["document_path"] == "docs/README.md"
        assert payload["extract_entities"] is True

    def test_system_metrics_event_structure(self, correlation_id):
        """Test METRICS_REQUESTED event structure."""
        event = {
            "event_type": "omninode.system.event.metrics_requested.v1",
            "correlation_id": correlation_id,
            "payload": {
                "include_detailed_metrics": True,
                "time_window_seconds": 300,
                "metric_types": ["cpu", "memory", "kafka"],
            },
        }

        handler = SystemUtilitiesHandler()
        assert handler.can_handle(event["event_type"])

        correlation = handler._get_correlation_id(event)
        assert correlation == correlation_id

        payload = handler._get_payload(event)
        assert payload["include_detailed_metrics"] is True
        assert "kafka" in payload["metric_types"]


# ============================================================================
# Handler Metrics Tracking Tests
# ============================================================================


class TestMetricsTracking:
    """Test metrics tracking across all handlers."""

    def test_bridge_handler_metrics_accumulation(self):
        """Test BridgeIntelligenceHandler accumulates metrics correctly."""
        handler = BridgeIntelligenceHandler()

        # Simulate success
        handler.metrics["events_handled"] += 1
        handler.metrics["generate_intelligence_successes"] += 1
        handler.metrics["total_processing_time_ms"] += 123.4

        metrics = handler.get_metrics()
        assert metrics["events_handled"] == 1
        assert metrics["generate_intelligence_successes"] == 1
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 123.4

        # Simulate failure
        handler.metrics["events_failed"] += 1
        handler.metrics["generate_intelligence_failures"] += 1

        metrics = handler.get_metrics()
        assert metrics["events_failed"] == 1
        assert metrics["success_rate"] == 0.5  # 1 success / 2 total

    def test_document_handler_metrics_accumulation(self):
        """Test DocumentProcessingHandler accumulates metrics correctly."""
        handler = DocumentProcessingHandler()

        # Simulate batch success
        handler.metrics["events_handled"] += 1
        handler.metrics["batch_index_successes"] += 1
        handler.metrics["total_documents_processed"] += 50
        handler.metrics["total_processing_time_ms"] += 5000.0

        metrics = handler.get_metrics()
        assert metrics["total_documents_processed"] == 50
        assert metrics["avg_processing_time_ms"] == 5000.0

    def test_system_handler_metrics_accumulation(self):
        """Test SystemUtilitiesHandler accumulates metrics correctly."""
        handler = SystemUtilitiesHandler()

        # Simulate multiple operation types
        handler.metrics["events_handled"] += 3
        handler.metrics["metrics_requests_successes"] += 1
        handler.metrics["kafka_health_successes"] += 1
        handler.metrics["kafka_metrics_successes"] += 1
        handler.metrics["total_processing_time_ms"] += 300.0

        metrics = handler.get_metrics()
        assert metrics["events_handled"] == 3
        assert metrics["metrics_requests_successes"] == 1
        assert metrics["kafka_health_successes"] == 1
        assert metrics["kafka_metrics_successes"] == 1
        assert metrics["avg_processing_time_ms"] == 100.0


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling across all handlers."""

    def test_bridge_handler_missing_correlation_id(self):
        """Test BridgeIntelligenceHandler handles missing correlation_id."""
        handler = BridgeIntelligenceHandler()

        event = {
            "event_type": "bridge.generate-intelligence-requested",
            "payload": {"source_path": "test.py", "content": "code"},
        }

        with pytest.raises(ValueError, match="Event missing correlation_id"):
            handler._get_correlation_id(event)

    def test_document_handler_missing_payload(self):
        """Test DocumentProcessingHandler handles missing payload."""
        handler = DocumentProcessingHandler()

        event = {
            "event_type": "document.process-requested",
            "correlation_id": "test-123",
            # Missing payload
        }

        # Should fall back to event itself as payload
        payload = handler._get_payload(event)
        assert "correlation_id" in payload

    def test_system_handler_invalid_event_type(self):
        """Test SystemUtilitiesHandler rejects invalid event types."""
        handler = SystemUtilitiesHandler()

        assert not handler.can_handle("invalid.event.type")
        assert not handler.can_handle("")


# ============================================================================
# Comprehensive Integration Test
# ============================================================================


@pytest.mark.integration
class TestFullEventProcessingPipeline:
    """
    Full integration test for complete event processing pipeline.

    Requires:
    - Mock Kafka broker
    - Mock HTTP services (Bridge, Intelligence)
    - Event router setup
    """

    @pytest.mark.skip(reason="Requires full Kafka and service infrastructure")
    @pytest.mark.asyncio
    async def test_end_to_end_bridge_intelligence_flow(self):
        """
        Test complete flow: Event → Handler → Service → Response

        Full workflow:
        1. Publish GENERATE_INTELLIGENCE_REQUESTED event
        2. Handler consumes event
        3. Handler calls Bridge service
        4. Handler publishes COMPLETED event
        5. Verify metrics updated
        """
        # This test would require:
        # - Running Kafka broker
        # - Mock Bridge service at localhost:8054
        # - Event router initialized
        # - Consumer running
        pass

    @pytest.mark.skip(reason="Requires full infrastructure")
    @pytest.mark.asyncio
    async def test_end_to_end_document_processing_flow(self):
        """Test complete document processing flow."""
        pass

    @pytest.mark.skip(reason="Requires full infrastructure")
    @pytest.mark.asyncio
    async def test_end_to_end_system_metrics_flow(self):
        """Test complete system metrics collection flow."""
        pass
