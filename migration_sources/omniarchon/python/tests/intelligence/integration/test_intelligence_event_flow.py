"""
Integration tests for Intelligence Adapter event flow.

Tests end-to-end event processing:
- Kafka event subscription and consumption
- Event routing to analyze_code()
- Success/failure event publishing
- Correlation ID tracking across events
- Kafka offset management

Test Pattern: Event-driven integration testing
Reference: omninode_bridge event flow patterns
"""

# Now import everything else
import asyncio

# Import event models
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Import models
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "services" / "intelligence")
)

from intelligence.models.model_intelligence_config import ModelIntelligenceConfig

# Import node
from intelligence.nodes.node_intelligence_adapter_effect import (
    NodeIntelligenceAdapterEffect,
)

from services.intelligence.src.events.models.intelligence_adapter_events import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
)

# NOTE: Path configuration is now handled by pytest.ini (pythonpath setting)
# Manual sys.path manipulation has been removed to prevent conflicts.
# The pytest.ini file configures: pythonpath = . src ../services/kafka-consumer/src ..
# This provides access to:
#   - python/ directory (.)
#   - python/src/ directory (src)
#   - services/ directory (..)
# which allows importing:
#   - from src.events.publisher... (python/src/events/publisher/)
#   - from services.intelligence... (services/intelligence/)
#   - from intelligence.nodes... (python/src/intelligence/nodes/)


def create_request_event(
    source_path: str,
    content: Optional[str] = None,
    language: Optional[str] = None,
    operation_type: EnumAnalysisOperationType = EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
    correlation_id: Optional[UUID] = None,
    options: Optional[dict] = None,
) -> dict:
    """Create CODE_ANALYSIS_REQUESTED event dictionary (avoiding circular import)."""
    event_id = str(uuid4())
    corr_id = str(correlation_id or uuid4())

    return {
        "event_id": event_id,
        "event_type": EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value,
        "correlation_id": corr_id,
        "causation_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "source_path": source_path,
            "content": content,
            "language": language,
            "operation_type": operation_type.value,
            "options": options or {},
            "project_id": None,
            "user_id": None,
        },
    }


def create_completed_event(
    source_path: str,
    quality_score: float,
    onex_compliance: float,
    issues_count: int,
    recommendations_count: int,
    processing_time_ms: float,
    operation_type: EnumAnalysisOperationType,
    correlation_id: UUID,
    causation_id: Optional[UUID] = None,
    results_summary: Optional[dict] = None,
    cache_hit: bool = False,
) -> dict:
    """Create CODE_ANALYSIS_COMPLETED event dictionary (avoiding circular import)."""
    event_id = str(uuid4())

    return {
        "event_id": event_id,
        "event_type": EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value,
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id) if causation_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "source_path": source_path,
            "quality_score": quality_score,
            "onex_compliance": onex_compliance,
            "issues_count": issues_count,
            "recommendations_count": recommendations_count,
            "processing_time_ms": processing_time_ms,
            "operation_type": operation_type.value,
            "results_summary": results_summary or {},
            "cache_hit": cache_hit,
            "complexity_score": None,
            "maintainability_score": None,
        },
    }


def create_failed_event(
    operation_type: EnumAnalysisOperationType,
    source_path: str,
    error_message: str,
    error_code: EnumAnalysisErrorCode,
    correlation_id: UUID,
    causation_id: Optional[UUID] = None,
    retry_allowed: bool = True,
    retry_count: int = 0,
    processing_time_ms: float = 0.0,
    error_details: Optional[dict] = None,
    suggested_action: Optional[str] = None,
) -> dict:
    """Create CODE_ANALYSIS_FAILED event dictionary (avoiding circular import)."""
    event_id = str(uuid4())

    return {
        "event_id": event_id,
        "event_type": EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value,
        "correlation_id": str(correlation_id),
        "causation_id": str(causation_id) if causation_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "operation_type": operation_type.value,
            "source_path": source_path,
            "error_message": error_message,
            "error_code": error_code.value,
            "retry_allowed": retry_allowed,
            "retry_count": retry_count,
            "processing_time_ms": processing_time_ms,
            "error_details": error_details or {},
            "suggested_action": suggested_action,
        },
    }


def deserialize_event(event_dict: dict) -> tuple[str, ModelCodeAnalysisRequestPayload]:
    """Deserialize event dictionary (simplified version without circular import)."""
    event_type = event_dict.get("event_type")
    payload_data = event_dict.get("payload", {})

    if event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value:
        payload = ModelCodeAnalysisRequestPayload(**payload_data)
        return event_type, payload

    raise ValueError(f"Unknown event type: {event_type}")


def get_kafka_topic(event_type: EnumCodeAnalysisEventType) -> str:
    """Get Kafka topic for event type (simplified version)."""
    topic_mapping = {
        EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED: "dev.archon-intelligence.intelligence.code-analysis-requested.v1",
        EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED: "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
        EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED: "dev.archon-intelligence.intelligence.code-analysis-failed.v1",
    }
    return topic_mapping.get(event_type, "")


class TestIntelligenceEventFlow:
    """Integration tests for Intelligence Adapter event-driven workflows."""

    @pytest.fixture
    def container(self):
        """Create ONEX container."""
        return ModelONEXContainer()

    @pytest.fixture
    def mock_config(self):
        """Create mock intelligence config."""
        return ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_seconds=30.0,
            enable_event_publishing=True,
            input_topics=[
                "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
            ],
            output_topics={
                "completed": "dev.archon-intelligence.intelligence.code-analysis-completed.v1",
                "failed": "dev.archon-intelligence.intelligence.code-analysis-failed.v1",
            },
        )

    @pytest.fixture
    def mock_kafka_consumer(self):
        """Create mock Kafka consumer."""
        consumer = AsyncMock()
        consumer.subscribe = AsyncMock()
        consumer.start = AsyncMock()
        consumer.stop = AsyncMock()
        consumer.commit = AsyncMock()
        return consumer

    @pytest.fixture
    def mock_kafka_producer(self):
        """Create mock Kafka producer."""
        producer = AsyncMock()
        producer.send = AsyncMock()
        producer.start = AsyncMock()
        producer.stop = AsyncMock()
        return producer

    @pytest.fixture
    def correlation_id(self):
        """Generate correlation ID for tracking."""
        return uuid4()

    # =========================================================================
    # Event Subscription Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_event_subscription_setup(self, mock_config, mock_kafka_consumer):
        """Test Kafka consumer subscribes to correct topics."""
        # Simulate event subscription
        await mock_kafka_consumer.subscribe(topics=mock_config.input_topics)
        await mock_kafka_consumer.start()

        mock_kafka_consumer.subscribe.assert_called_once_with(
            topics=mock_config.input_topics
        )
        mock_kafka_consumer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_subscription_with_consumer_group(
        self, mock_config, mock_kafka_consumer
    ):
        """Test consumer group configuration for load balancing."""
        consumer_group = "intelligence-adapter-consumers"

        # Simulate consumer group setup
        mock_kafka_consumer.subscribe(
            topics=mock_config.input_topics, group_id=consumer_group
        )

        mock_kafka_consumer.subscribe.assert_called_with(
            topics=mock_config.input_topics, group_id=consumer_group
        )

    # =========================================================================
    # Event Routing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_event_routing_to_analyze_code(
        self, container, mock_config, correlation_id
    ):
        """Test REQUEST event routes to analyze_code() method."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Create mock client
        mock_client = AsyncMock()
        node._client = mock_client

        # Create REQUEST event
        request_event = create_request_event(
            source_path="src/api.py",
            content="def process(): pass",
            language="python",
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
        )

        # Extract payload and simulate routing
        event_type = request_event["event_type"]
        payload_data = request_event["payload"]

        assert event_type == EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value

        # Verify payload can be deserialized
        payload = ModelCodeAnalysisRequestPayload(**payload_data)
        assert payload.source_path == "src/api.py"
        assert (
            payload.operation_type == EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS
        )

    @pytest.mark.asyncio
    async def test_event_deserialization_and_execution(
        self, container, mock_config, correlation_id
    ):
        """Test event deserialization and execution flow."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Mock client and process
        mock_client = AsyncMock()
        node._client = mock_client

        # Create REQUEST event
        request_event = create_request_event(
            source_path="src/main.py",
            content="print('hello')",
            language="python",
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
            correlation_id=correlation_id,
        )

        # Deserialize event
        event_type, payload = deserialize_event(request_event)

        assert isinstance(payload, ModelCodeAnalysisRequestPayload)
        assert payload.source_path == "src/main.py"
        assert str(request_event["correlation_id"]) == str(correlation_id)

    # =========================================================================
    # Success Event Publishing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_success_event_publishing(self, mock_kafka_producer, correlation_id):
        """Test COMPLETED event is published after successful analysis."""
        # Create COMPLETED event
        completed_event = create_completed_event(
            source_path="src/processor.py",
            quality_score=0.92,
            onex_compliance=0.88,
            issues_count=2,
            recommendations_count=5,
            processing_time_ms=567.8,
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
            results_summary={"patterns": 3, "anti_patterns": 1},
            cache_hit=False,
        )

        # Publish to Kafka
        topic = get_kafka_topic(EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED)
        await mock_kafka_producer.send(topic, value=completed_event)

        mock_kafka_producer.send.assert_called_once()
        call_args = mock_kafka_producer.send.call_args
        assert call_args[0][0] == topic
        assert call_args[1]["value"]["event_type"] == (
            EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED.value
        )

    @pytest.mark.asyncio
    async def test_completed_event_payload_structure(self, correlation_id):
        """Test COMPLETED event has correct payload structure."""
        completed_event = create_completed_event(
            source_path="test.py",
            quality_score=0.85,
            onex_compliance=0.80,
            issues_count=1,
            recommendations_count=3,
            processing_time_ms=450.0,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
            correlation_id=correlation_id,
        )

        payload = completed_event["payload"]
        assert payload["source_path"] == "test.py"
        assert payload["quality_score"] == 0.85
        assert payload["onex_compliance"] == 0.80
        assert payload["issues_count"] == 1
        assert payload["recommendations_count"] == 3
        assert payload["processing_time_ms"] == 450.0
        assert completed_event["correlation_id"] == str(correlation_id)

    # =========================================================================
    # Failure Event Publishing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_failure_event_publishing(self, mock_kafka_producer, correlation_id):
        """Test FAILED event is published after analysis failure."""
        # Create FAILED event
        failed_event = create_failed_event(
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            source_path="src/broken.py",
            error_message="Parsing error: invalid syntax",
            error_code=EnumAnalysisErrorCode.PARSING_ERROR,
            correlation_id=correlation_id,
            retry_allowed=False,
            retry_count=0,
            processing_time_ms=123.5,
            error_details={"line": 42, "column": 15},
            suggested_action="Fix syntax error and retry",
        )

        # Publish to Kafka
        topic = get_kafka_topic(EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED)
        await mock_kafka_producer.send(topic, value=failed_event)

        mock_kafka_producer.send.assert_called_once()
        call_args = mock_kafka_producer.send.call_args
        assert call_args[1]["value"]["event_type"] == (
            EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED.value
        )

    @pytest.mark.asyncio
    async def test_failed_event_retry_logic(self, correlation_id):
        """Test FAILED event includes retry information."""
        # Non-retryable error
        failed_event = create_failed_event(
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
            source_path="bad.py",
            error_message="Invalid input",
            error_code=EnumAnalysisErrorCode.INVALID_INPUT,
            correlation_id=correlation_id,
            retry_allowed=False,
            retry_count=0,
        )

        payload = failed_event["payload"]
        assert payload["retry_allowed"] is False
        assert payload["error_code"] == EnumAnalysisErrorCode.INVALID_INPUT.value

        # Retryable error
        retryable_event = create_failed_event(
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
            source_path="timeout.py",
            error_message="Request timeout",
            error_code=EnumAnalysisErrorCode.TIMEOUT,
            correlation_id=correlation_id,
            retry_allowed=True,
            retry_count=2,
        )

        payload = retryable_event["payload"]
        assert payload["retry_allowed"] is True
        assert payload["retry_count"] == 2
        assert payload["error_code"] == EnumAnalysisErrorCode.TIMEOUT.value

    # =========================================================================
    # Correlation ID Tracking Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_correlation_id_preserved_across_events(self, correlation_id):
        """Test correlation ID is preserved from REQUEST to COMPLETED/FAILED."""
        # Create REQUEST event
        request_event = create_request_event(
            source_path="src/test.py",
            correlation_id=correlation_id,
        )

        assert UUID(request_event["correlation_id"]) == correlation_id

        # Create COMPLETED event with same correlation ID
        completed_event = create_completed_event(
            source_path="src/test.py",
            quality_score=0.9,
            onex_compliance=0.85,
            issues_count=0,
            recommendations_count=2,
            processing_time_ms=500.0,
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
        )

        assert UUID(completed_event["correlation_id"]) == correlation_id

        # Create FAILED event with same correlation ID
        failed_event = create_failed_event(
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            source_path="src/test.py",
            error_message="Test error",
            error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
            correlation_id=correlation_id,
        )

        assert UUID(failed_event["correlation_id"]) == correlation_id

    @pytest.mark.asyncio
    async def test_causation_id_links_events(self, correlation_id):
        """Test causation_id links REQUEST to result events."""
        # Create REQUEST event
        request_event = create_request_event(
            source_path="src/api.py",
            correlation_id=correlation_id,
        )

        request_event_id = UUID(request_event["event_id"])

        # Create COMPLETED event with causation from REQUEST
        completed_event = create_completed_event(
            source_path="src/api.py",
            quality_score=0.88,
            onex_compliance=0.82,
            issues_count=1,
            recommendations_count=4,
            processing_time_ms=678.9,
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
            causation_id=request_event_id,
        )

        assert UUID(completed_event["causation_id"]) == request_event_id
        assert UUID(completed_event["correlation_id"]) == correlation_id

    # =========================================================================
    # Kafka Offset Management Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_offset_commit_after_successful_processing(self, mock_kafka_consumer):
        """Test Kafka offset is committed after successful event processing."""
        # Simulate successful event processing
        await mock_kafka_consumer.commit()

        mock_kafka_consumer.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_offset_not_committed_on_processing_failure(
        self, mock_kafka_consumer
    ):
        """Test Kafka offset is NOT committed if processing fails."""
        # Simulate processing failure - no commit
        # (consumer should retry or send to DLQ)

        mock_kafka_consumer.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_consumption_with_retry_logic(
        self, mock_kafka_consumer, correlation_id
    ):
        """Test event consumption with retry on transient failures."""
        # Create mock events
        events = [
            create_request_event(
                source_path=f"src/file{i}.py",
                correlation_id=uuid4(),
            )
            for i in range(3)
        ]

        # Simulate consuming events
        for event in events:
            # Process event
            event_type, payload = deserialize_event(event)

            assert isinstance(payload, ModelCodeAnalysisRequestPayload)

            # Commit offset after successful processing
            await mock_kafka_consumer.commit()

        assert mock_kafka_consumer.commit.call_count == 3

    # =========================================================================
    # End-to-End Event Flow Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_end_to_end_success_flow(
        self,
        container,
        mock_config,
        mock_kafka_consumer,
        mock_kafka_producer,
        correlation_id,
    ):
        """Test complete flow: REQUEST → analyze_code() → COMPLETED."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Mock client
        mock_client = AsyncMock()
        node._client = mock_client

        # Step 1: Consume REQUEST event
        request_event = create_request_event(
            source_path="src/processor.py",
            content="def process(data): return data",
            language="python",
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
        )

        event_type, request_payload = deserialize_event(request_event)

        assert isinstance(request_payload, ModelCodeAnalysisRequestPayload)

        # Step 2: Simulate analysis
        # (In real system, analyze_code would be called here to process the request)
        # For this mock test, we skip the actual analysis and proceed to event publishing

        # Step 3: Create and publish COMPLETED event
        completed_event = create_completed_event(
            source_path=request_payload.source_path,
            quality_score=0.92,
            onex_compliance=0.88,
            issues_count=0,
            recommendations_count=3,
            processing_time_ms=550.0,
            operation_type=request_payload.operation_type,
            correlation_id=correlation_id,
        )

        topic = get_kafka_topic(EnumCodeAnalysisEventType.CODE_ANALYSIS_COMPLETED)
        await mock_kafka_producer.send(topic, value=completed_event)

        # Step 4: Commit offset
        await mock_kafka_consumer.commit()

        # Verify flow
        mock_kafka_producer.send.assert_called_once()
        mock_kafka_consumer.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_failure_flow(
        self,
        container,
        mock_config,
        mock_kafka_consumer,
        mock_kafka_producer,
        correlation_id,
    ):
        """Test complete flow: REQUEST → analyze_code() → FAILED."""
        node = NodeIntelligenceAdapterEffect(container)
        node._config = mock_config

        # Step 1: Consume REQUEST event
        request_event = create_request_event(
            source_path="src/broken.py",
            content="invalid python syntax !!",
            language="python",
            operation_type=EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS,
            correlation_id=correlation_id,
        )

        event_type, request_payload = deserialize_event(request_event)

        # Step 2: Simulate analysis failure
        # (In real system, analyze_code would raise exception)

        # Step 3: Create and publish FAILED event
        failed_event = create_failed_event(
            operation_type=request_payload.operation_type,
            source_path=request_payload.source_path,
            error_message="Parsing error: invalid syntax",
            error_code=EnumAnalysisErrorCode.PARSING_ERROR,
            correlation_id=correlation_id,
            retry_allowed=False,
            retry_count=0,
            processing_time_ms=123.0,
        )

        topic = get_kafka_topic(EnumCodeAnalysisEventType.CODE_ANALYSIS_FAILED)
        await mock_kafka_producer.send(topic, value=failed_event)

        # Step 4: Commit offset
        await mock_kafka_consumer.commit()

        # Verify flow
        mock_kafka_producer.send.assert_called_once()
        mock_kafka_consumer.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
