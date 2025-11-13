"""
Comprehensive Unit Tests for IntelligenceAdapterHandler

Tests for intelligence adapter handler covering:
- Event routing (can_handle)
- Event handling for all operation types
- Operation routing (pattern extraction, infrastructure scan, model discovery, schema discovery)
- Legacy quality assessment operations
- Response publishing (completed/failed)
- Error handling and validation
- Correlation ID and payload extraction
- Metrics tracking
- Code quality analysis

Created: 2025-11-04
Purpose: Improve coverage from 17.8% to 75%+ for intelligence_adapter_handler.py
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from events.models.intelligence_adapter_events import (
    EnumAnalysisErrorCode,
    EnumAnalysisOperationType,
    EnumCodeAnalysisEventType,
)
from handlers.intelligence_adapter_handler import IntelligenceAdapterHandler

# ==============================================================================
# Test Fixtures
# ==============================================================================


class MockEventEnvelope:
    """Mock event envelope for testing."""

    def __init__(
        self,
        correlation_id: str = None,
        payload: Dict[str, Any] = None,
    ):
        self.correlation_id = correlation_id or str(uuid4())
        self.payload = payload or {}


@pytest.fixture
def mock_quality_scorer():
    """Mock ComprehensiveONEXScorer."""
    scorer = Mock()
    scorer.analyze_content = Mock(
        return_value={
            "quality_score": 0.85,
            "onex_compliance_score": 0.90,
            "relevance_score": 0.88,
            "architectural_era": "advanced_archon",
        }
    )
    return scorer


@pytest.fixture
def mock_pattern_extraction_handler():
    """Mock PatternExtractionHandler."""
    handler = AsyncMock()
    handler.execute = AsyncMock(
        return_value={
            "patterns": [
                {
                    "name": "ONEX Effect Pattern",
                    "description": "Effect node pattern",
                    "confidence": 0.95,
                }
            ],
            "total_patterns": 1,
        }
    )
    return handler


@pytest.fixture
def mock_infrastructure_scan_handler():
    """Mock InfrastructureScanHandler."""
    handler = AsyncMock()
    handler.execute = AsyncMock(
        return_value={
            "infrastructure": {
                "databases": ["postgresql", "qdrant"],
                "message_queues": ["kafka"],
            },
            "health": "healthy",
        }
    )
    return handler


@pytest.fixture
def mock_model_discovery_handler():
    """Mock ModelDiscoveryHandler."""
    handler = AsyncMock()
    handler.execute = AsyncMock(
        return_value={
            "models": [
                {"name": "ModelUser", "file_path": "/models/user.py"},
                {"name": "ModelProduct", "file_path": "/models/product.py"},
            ],
            "total_models": 2,
        }
    )
    return handler


@pytest.fixture
def mock_schema_discovery_handler():
    """Mock SchemaDiscoveryHandler."""
    handler = AsyncMock()
    handler.execute = AsyncMock(
        return_value={
            "schemas": [
                {
                    "table": "users",
                    "columns": [
                        {"name": "id", "type": "uuid"},
                        {"name": "email", "type": "varchar"},
                    ],
                }
            ],
            "total_tables": 1,
        }
    )
    return handler


@pytest.fixture
def mock_router():
    """Mock HybridEventRouter."""
    router = AsyncMock()
    router.initialize = AsyncMock()
    router.publish = AsyncMock()
    return router


@pytest.fixture
def handler(
    mock_quality_scorer,
    mock_pattern_extraction_handler,
    mock_infrastructure_scan_handler,
    mock_model_discovery_handler,
    mock_schema_discovery_handler,
):
    """Create IntelligenceAdapterHandler with mocked dependencies."""
    handler = IntelligenceAdapterHandler(quality_scorer=mock_quality_scorer)

    # Replace operation handlers with mocks
    handler.pattern_extraction_handler = mock_pattern_extraction_handler
    handler.infrastructure_scan_handler = mock_infrastructure_scan_handler
    handler.model_discovery_handler = mock_model_discovery_handler
    handler.schema_discovery_handler = mock_schema_discovery_handler

    return handler


# ==============================================================================
# Test: Initialization
# ==============================================================================


def test_initialization_with_scorer(mock_quality_scorer):
    """Test handler initialization with provided quality scorer."""
    handler = IntelligenceAdapterHandler(quality_scorer=mock_quality_scorer)

    assert handler.quality_scorer == mock_quality_scorer
    assert handler.pattern_extraction_handler is not None
    assert handler.infrastructure_scan_handler is not None
    assert handler.model_discovery_handler is not None
    assert handler.schema_discovery_handler is not None
    assert handler.metrics["events_handled"] == 0
    assert handler.metrics["events_failed"] == 0


def test_initialization_without_scorer():
    """Test handler initialization creates default quality scorer."""
    with patch(
        "handlers.intelligence_adapter_handler.ComprehensiveONEXScorer"
    ) as mock_scorer_class:
        mock_scorer_instance = Mock()
        mock_scorer_class.return_value = mock_scorer_instance

        handler = IntelligenceAdapterHandler()

        assert handler.quality_scorer == mock_scorer_instance
        mock_scorer_class.assert_called_once()


def test_initialization_metrics():
    """Test handler initializes all metrics correctly."""
    handler = IntelligenceAdapterHandler()

    assert "events_handled" in handler.metrics
    assert "events_failed" in handler.metrics
    assert "total_processing_time_ms" in handler.metrics
    assert "analysis_successes" in handler.metrics
    assert "analysis_failures" in handler.metrics
    assert "pattern_extraction_count" in handler.metrics
    assert "infrastructure_scan_count" in handler.metrics
    assert "model_discovery_count" in handler.metrics
    assert "schema_discovery_count" in handler.metrics


# ==============================================================================
# Test: can_handle
# ==============================================================================


def test_can_handle_enum_event_type(handler):
    """Test can_handle with EnumCodeAnalysisEventType."""
    assert handler.can_handle(EnumCodeAnalysisEventType.CODE_ANALYSIS_REQUESTED.value)


def test_can_handle_string_event_type(handler):
    """Test can_handle with string event type."""
    assert handler.can_handle("CODE_ANALYSIS_REQUESTED")


def test_can_handle_qualified_event_type(handler):
    """Test can_handle with qualified event type."""
    assert handler.can_handle("intelligence.code-analysis-requested")


def test_can_handle_full_event_type(handler):
    """Test can_handle with full Kafka event type."""
    assert handler.can_handle("omninode.intelligence.event.code_analysis_requested.v1")


def test_can_handle_invalid_event_type(handler):
    """Test can_handle with invalid event type."""
    assert not handler.can_handle("INVALID_EVENT_TYPE")
    assert not handler.can_handle("something.else.v1")


# ==============================================================================
# Test: _get_correlation_id
# ==============================================================================


def test_get_correlation_id_from_dict(handler):
    """Test extracting correlation_id from dict event."""
    correlation_id = str(uuid4())
    event = {"correlation_id": correlation_id, "payload": {}}

    result = handler._get_correlation_id(event)
    assert result == correlation_id


def test_get_correlation_id_from_dict_payload(handler):
    """Test extracting correlation_id from dict event payload."""
    correlation_id = str(uuid4())
    event = {"payload": {"correlation_id": correlation_id}}

    result = handler._get_correlation_id(event)
    assert result == correlation_id


def test_get_correlation_id_from_object(handler):
    """Test extracting correlation_id from object event."""
    correlation_id = str(uuid4())
    event = MockEventEnvelope(correlation_id=correlation_id)

    result = handler._get_correlation_id(event)
    assert result == correlation_id


def test_get_correlation_id_from_object_payload(handler):
    """Test extracting correlation_id from object event payload."""
    correlation_id = str(uuid4())
    event = MockEventEnvelope(payload={"correlation_id": correlation_id})
    event.correlation_id = None  # Force fallback to payload

    result = handler._get_correlation_id(event)
    assert result == correlation_id


def test_get_correlation_id_missing(handler):
    """Test error when correlation_id is missing."""
    event = {"payload": {}}

    with pytest.raises(ValueError, match="Event missing correlation_id"):
        handler._get_correlation_id(event)


def test_get_correlation_id_converts_uuid(handler):
    """Test correlation_id UUID is converted to string."""
    correlation_id = uuid4()
    event = {"correlation_id": correlation_id}

    result = handler._get_correlation_id(event)
    assert result == str(correlation_id)
    assert isinstance(result, str)


# ==============================================================================
# Test: _get_payload
# ==============================================================================


def test_get_payload_from_dict_with_payload_key(handler):
    """Test extracting payload from dict event with payload key."""
    payload = {"source_path": "/test.py", "content": "code"}
    event = {"payload": payload, "other": "data"}

    result = handler._get_payload(event)
    assert result == payload


def test_get_payload_from_dict_without_payload_key(handler):
    """Test extracting payload from dict event (event itself is payload)."""
    event = {"source_path": "/test.py", "content": "code"}

    result = handler._get_payload(event)
    assert result == event


def test_get_payload_from_object(handler):
    """Test extracting payload from object event."""
    payload = {"source_path": "/test.py", "content": "code"}
    event = MockEventEnvelope(payload=payload)

    result = handler._get_payload(event)
    assert result == payload


def test_get_payload_from_object_missing(handler):
    """Test error when payload is missing from object."""
    event = Mock(spec=[])  # Object with no payload attribute

    with pytest.raises(ValueError, match="Event missing payload"):
        handler._get_payload(event)


# ==============================================================================
# Test: handle_event - Pattern Extraction
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_pattern_extraction_success(handler, mock_router):
    """Test successful pattern extraction operation."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/patterns/effect_node.py",
            "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
            "options": {"limit": 10},
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["events_handled"] == 1
    assert handler.metrics["pattern_extraction_count"] == 1
    assert handler.metrics["analysis_successes"] == 1

    # Verify operation handler was called
    handler.pattern_extraction_handler.execute.assert_called_once_with(
        source_path="/patterns/effect_node.py",
        options={"limit": 10},
    )

    # Verify response was published
    mock_router.publish.assert_called_once()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.COMPLETED_TOPIC
    assert call_args.kwargs["key"] == correlation_id


@pytest.mark.asyncio
async def test_handle_event_pattern_extraction_no_content_required(
    handler, mock_router
):
    """Test pattern extraction doesn't require content field."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/patterns/effect_node.py",
            "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
            # No content field - should still work
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["pattern_extraction_count"] == 1


# ==============================================================================
# Test: handle_event - Infrastructure Scan
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_infrastructure_scan_success(handler, mock_router):
    """Test successful infrastructure scan operation."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/infrastructure",
            "operation_type": EnumAnalysisOperationType.INFRASTRUCTURE_SCAN.value,
            "options": {"include_health": True},
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["infrastructure_scan_count"] == 1
    assert handler.metrics["analysis_successes"] == 1

    # Verify operation handler was called
    handler.infrastructure_scan_handler.execute.assert_called_once()


# ==============================================================================
# Test: handle_event - Model Discovery
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_model_discovery_success(handler, mock_router):
    """Test successful model discovery operation."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/models",
            "operation_type": EnumAnalysisOperationType.MODEL_DISCOVERY.value,
            "options": {"recursive": True},
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["model_discovery_count"] == 1
    assert handler.metrics["analysis_successes"] == 1


# ==============================================================================
# Test: handle_event - Schema Discovery
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_schema_discovery_success(handler, mock_router):
    """Test successful schema discovery operation."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/database/schema",
            "operation_type": EnumAnalysisOperationType.SCHEMA_DISCOVERY.value,
            "options": {"include_indexes": True},
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["schema_discovery_count"] == 1
    assert handler.metrics["analysis_successes"] == 1


# ==============================================================================
# Test: handle_event - Legacy Quality Assessment
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_quality_assessment_success(handler, mock_router):
    """Test successful quality assessment operation."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/code/module.py",
            "content": "def hello(): pass",
            "language": "python",
            "operation_type": EnumAnalysisOperationType.QUALITY_ASSESSMENT.value,
            "options": {},
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    assert handler.metrics["analysis_successes"] == 1

    # Verify quality scorer was called
    handler.quality_scorer.analyze_content.assert_called_once_with(
        content="def hello(): pass",
        file_path="/code/module.py",
    )


@pytest.mark.asyncio
async def test_handle_event_quality_assessment_missing_content(handler, mock_router):
    """Test quality assessment fails when content is missing."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/code/module.py",
            # Missing content field
            "operation_type": EnumAnalysisOperationType.QUALITY_ASSESSMENT.value,
        },
    }

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["events_failed"] == 1
    assert handler.metrics["analysis_failures"] == 1

    # Verify failed response was published
    mock_router.publish.assert_called_once()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.FAILED_TOPIC


@pytest.mark.asyncio
async def test_handle_event_comprehensive_analysis_missing_content(
    handler, mock_router
):
    """Test comprehensive analysis fails when content is missing."""
    handler._router = mock_router
    handler._router_initialized = True

    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/code/module.py",
            "operation_type": EnumAnalysisOperationType.COMPREHENSIVE_ANALYSIS.value,
        },
    }

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["analysis_failures"] == 1


# ==============================================================================
# Test: handle_event - Error Cases
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_event_missing_source_path(handler, mock_router):
    """Test event handling fails when source_path is missing."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            # Missing source_path
            "content": "code",
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["events_failed"] == 1
    assert handler.metrics["analysis_failures"] == 1

    # Verify failed response was published
    mock_router.publish.assert_called_once()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.FAILED_TOPIC


@pytest.mark.asyncio
async def test_handle_event_operation_handler_exception(handler, mock_router):
    """Test handling of operation handler exceptions."""
    handler._router = mock_router
    handler._router_initialized = True

    # Make pattern extraction handler raise exception
    handler.pattern_extraction_handler.execute.side_effect = Exception(
        "Qdrant connection failed"
    )

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/patterns/test.py",
            "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
        },
    }

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["events_failed"] == 1
    assert handler.metrics["analysis_failures"] == 1

    # Verify failed response was published
    mock_router.publish.assert_called()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.FAILED_TOPIC


@pytest.mark.asyncio
async def test_handle_event_quality_scorer_exception(handler, mock_router):
    """Test handling of quality scorer exceptions."""
    handler._router = mock_router
    handler._router_initialized = True

    # Make quality scorer raise exception
    handler.quality_scorer.analyze_content.side_effect = Exception("Scorer error")

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/code/module.py",
            "content": "code",
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["analysis_failures"] == 1


@pytest.mark.asyncio
async def test_handle_event_publish_error_fails_gracefully(handler, mock_router):
    """Test that publish errors in error handler are logged but don't crash."""
    handler._router = mock_router
    handler._router_initialized = True

    # Make publish raise exception
    mock_router.publish.side_effect = Exception("Kafka connection failed")

    correlation_id = str(uuid4())
    event = {
        "correlation_id": correlation_id,
        "payload": {
            "source_path": "/code/module.py",
            # Missing content to trigger error path
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }

    # Should not raise exception
    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["events_failed"] == 1


@pytest.mark.asyncio
async def test_handle_event_no_correlation_id_in_error_path(handler):
    """Test error handling when correlation_id extraction fails."""
    # Create event that will fail to extract correlation_id
    event = {"payload": {}}  # No correlation_id

    result = await handler.handle_event(event)

    assert result is False
    assert handler.metrics["events_failed"] == 1


# ==============================================================================
# Test: _analyze_code_quality
# ==============================================================================


@pytest.mark.asyncio
async def test_analyze_code_quality_success(handler):
    """Test successful code quality analysis."""
    result = await handler._analyze_code_quality(
        content="def hello(): pass",
        source_path="/test.py",
        language="python",
        operation_type="QUALITY_ASSESSMENT",
        options={},
    )

    assert "quality_score" in result
    assert "onex_compliance" in result
    assert result["quality_score"] == 0.85
    assert result["onex_compliance"] == 0.90


@pytest.mark.asyncio
async def test_analyze_code_quality_with_optional_fields(handler):
    """Test code quality analysis includes optional fields when present."""
    result = await handler._analyze_code_quality(
        content="code",
        source_path="/test.py",
        language="python",
        operation_type="QUALITY_ASSESSMENT",
        options={},
    )

    assert "relevance_score" in result
    assert "architectural_era" in result
    assert result["relevance_score"] == 0.88
    assert result["architectural_era"] == "advanced_archon"


@pytest.mark.asyncio
async def test_analyze_code_quality_without_optional_fields(handler):
    """Test code quality analysis without optional fields."""
    handler.quality_scorer.analyze_content.return_value = {
        "quality_score": 0.75,
        "onex_compliance_score": 0.80,
        # No relevance_score or architectural_era
    }

    result = await handler._analyze_code_quality(
        content="code",
        source_path="/test.py",
        language="python",
        operation_type="QUALITY_ASSESSMENT",
        options={},
    )

    assert "quality_score" in result
    assert "onex_compliance" in result
    assert "relevance_score" not in result
    assert "architectural_era" not in result


@pytest.mark.asyncio
async def test_analyze_code_quality_scorer_exception(handler):
    """Test code quality analysis handles scorer exceptions."""
    handler.quality_scorer.analyze_content.side_effect = Exception("Scorer failed")

    with pytest.raises(Exception, match="Scorer failed"):
        await handler._analyze_code_quality(
            content="code",
            source_path="/test.py",
            language="python",
            operation_type="QUALITY_ASSESSMENT",
            options={},
        )


# ==============================================================================
# Test: _publish_operation_response
# ==============================================================================


@pytest.mark.asyncio
async def test_publish_operation_response_with_dict(handler, mock_router):
    """Test publishing operation response with dict result."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    operation_result = {"patterns": [], "total_patterns": 0}

    await handler._publish_operation_response(
        correlation_id=correlation_id,
        operation_result=operation_result,
        source_path="/test.py",
        operation_type="PATTERN_EXTRACTION",
        processing_time_ms=123.45,
    )

    mock_router.publish.assert_called_once()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.COMPLETED_TOPIC
    assert call_args.kwargs["key"] == correlation_id

    # Verify event envelope structure
    event = call_args.kwargs["event"]
    assert "payload" in event
    assert "correlation_id" in event
    assert "metadata" in event


@pytest.mark.asyncio
async def test_publish_operation_response_with_pydantic_model(handler, mock_router):
    """Test publishing operation response with Pydantic model result."""
    handler._router = mock_router
    handler._router_initialized = True

    # Create mock Pydantic model
    mock_result = Mock()
    mock_result.model_dump = Mock(return_value={"data": "test"})

    correlation_id = str(uuid4())

    await handler._publish_operation_response(
        correlation_id=correlation_id,
        operation_result=mock_result,
        source_path="/test.py",
        operation_type="PATTERN_EXTRACTION",
        processing_time_ms=100.0,
    )

    mock_result.model_dump.assert_called_once()
    mock_router.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_operation_response_unsupported_type(handler, mock_router):
    """Test publishing operation response with unsupported result type."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    operation_result = "invalid_type"  # String is not dict or Pydantic model

    with pytest.raises(ValueError, match="Unsupported operation result type"):
        await handler._publish_operation_response(
            correlation_id=correlation_id,
            operation_result=operation_result,
            source_path="/test.py",
            operation_type="PATTERN_EXTRACTION",
            processing_time_ms=100.0,
        )


@pytest.mark.asyncio
async def test_publish_operation_response_string_correlation_id(handler, mock_router):
    """Test publishing operation response converts string correlation_id to UUID."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())
    operation_result = {"data": "test"}

    await handler._publish_operation_response(
        correlation_id=correlation_id,
        operation_result=operation_result,
        source_path="/test.py",
        operation_type="TEST",
        processing_time_ms=100.0,
    )

    # Verify correlation_id was converted to UUID
    call_args = mock_router.publish.call_args
    event = call_args.kwargs["event"]
    assert isinstance(event["correlation_id"], UUID)


@pytest.mark.asyncio
async def test_publish_operation_response_initializes_router(handler, mock_router):
    """Test publishing operation response initializes router if needed."""
    handler._router = mock_router
    handler._router_initialized = False

    correlation_id = str(uuid4())
    operation_result = {"data": "test"}

    await handler._publish_operation_response(
        correlation_id=correlation_id,
        operation_result=operation_result,
        source_path="/test.py",
        operation_type="TEST",
        processing_time_ms=100.0,
    )

    mock_router.initialize.assert_called_once()
    assert handler._router_initialized is True


@pytest.mark.asyncio
async def test_publish_operation_response_publish_exception(handler, mock_router):
    """Test publishing operation response handles publish exceptions."""
    handler._router = mock_router
    handler._router_initialized = True
    mock_router.publish.side_effect = Exception("Publish failed")

    correlation_id = str(uuid4())
    operation_result = {"data": "test"}

    with pytest.raises(Exception, match="Publish failed"):
        await handler._publish_operation_response(
            correlation_id=correlation_id,
            operation_result=operation_result,
            source_path="/test.py",
            operation_type="TEST",
            processing_time_ms=100.0,
        )


# ==============================================================================
# Test: _publish_failed_response
# ==============================================================================


@pytest.mark.asyncio
async def test_publish_failed_response_success(handler, mock_router):
    """Test publishing failed response."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())

    await handler._publish_failed_response(
        correlation_id=correlation_id,
        source_path="/test.py",
        operation_type="QUALITY_ASSESSMENT",
        error_code=EnumAnalysisErrorCode.INVALID_INPUT,
        error_message="Invalid input data",
        retry_allowed=False,
        processing_time_ms=50.0,
        error_details={"field": "content"},
    )

    mock_router.publish.assert_called_once()
    call_args = mock_router.publish.call_args
    assert call_args.kwargs["topic"] == handler.FAILED_TOPIC
    assert call_args.kwargs["key"] == correlation_id


@pytest.mark.asyncio
async def test_publish_failed_response_converts_operation_type(handler, mock_router):
    """Test publishing failed response converts operation_type to enum."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())

    # Use string operation_type
    await handler._publish_failed_response(
        correlation_id=correlation_id,
        source_path="/test.py",
        operation_type="PATTERN_EXTRACTION",
        error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
        error_message="Error",
        retry_allowed=True,
        processing_time_ms=100.0,
    )

    mock_router.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_failed_response_invalid_operation_type(handler, mock_router):
    """Test publishing failed response with invalid operation_type defaults to COMPREHENSIVE_ANALYSIS."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())

    # Use invalid operation_type string
    await handler._publish_failed_response(
        correlation_id=correlation_id,
        source_path="/test.py",
        operation_type="INVALID_OPERATION",
        error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
        error_message="Error",
        retry_allowed=True,
        processing_time_ms=100.0,
    )

    # Should not raise exception, defaults to COMPREHENSIVE_ANALYSIS
    mock_router.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_failed_response_string_correlation_id(handler, mock_router):
    """Test publishing failed response converts string correlation_id to UUID."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())

    await handler._publish_failed_response(
        correlation_id=correlation_id,
        source_path="/test.py",
        operation_type="QUALITY_ASSESSMENT",
        error_code=EnumAnalysisErrorCode.INVALID_INPUT,
        error_message="Error",
        retry_allowed=False,
        processing_time_ms=50.0,
    )

    mock_router.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_failed_response_no_error_details(handler, mock_router):
    """Test publishing failed response without error_details."""
    handler._router = mock_router
    handler._router_initialized = True

    correlation_id = str(uuid4())

    await handler._publish_failed_response(
        correlation_id=correlation_id,
        source_path="/test.py",
        operation_type="QUALITY_ASSESSMENT",
        error_code=EnumAnalysisErrorCode.INVALID_INPUT,
        error_message="Error",
        retry_allowed=False,
        processing_time_ms=50.0,
        # error_details not provided
    )

    mock_router.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_failed_response_publish_exception(handler, mock_router):
    """Test publishing failed response handles publish exceptions."""
    handler._router = mock_router
    handler._router_initialized = True
    mock_router.publish.side_effect = Exception("Publish failed")

    correlation_id = str(uuid4())

    with pytest.raises(Exception, match="Publish failed"):
        await handler._publish_failed_response(
            correlation_id=correlation_id,
            source_path="/test.py",
            operation_type="QUALITY_ASSESSMENT",
            error_code=EnumAnalysisErrorCode.INTERNAL_ERROR,
            error_message="Error",
            retry_allowed=True,
            processing_time_ms=100.0,
        )


# ==============================================================================
# Test: Metrics
# ==============================================================================


def test_get_handler_name(handler):
    """Test get_handler_name returns correct name."""
    assert handler.get_handler_name() == "IntelligenceAdapterHandler"


def test_get_metrics_initial_state(handler):
    """Test get_metrics with initial state."""
    metrics = handler.get_metrics()

    assert metrics["events_handled"] == 0
    assert metrics["events_failed"] == 0
    assert metrics["success_rate"] == 1.0
    assert metrics["avg_processing_time_ms"] == 0.0
    assert metrics["handler_name"] == "IntelligenceAdapterHandler"


@pytest.mark.asyncio
async def test_get_metrics_after_successful_events(handler, mock_router):
    """Test get_metrics after successful events."""
    handler._router = mock_router
    handler._router_initialized = True

    # Process two successful events
    for i in range(2):
        event = {
            "correlation_id": str(uuid4()),
            "payload": {
                "source_path": f"/test{i}.py",
                "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
            },
        }
        await handler.handle_event(event)

    metrics = handler.get_metrics()

    assert metrics["events_handled"] == 2
    assert metrics["events_failed"] == 0
    assert metrics["success_rate"] == 1.0
    assert metrics["avg_processing_time_ms"] > 0
    assert metrics["pattern_extraction_count"] == 2


@pytest.mark.asyncio
async def test_get_metrics_after_failed_events(handler, mock_router):
    """Test get_metrics after failed events."""
    handler._router = mock_router
    handler._router_initialized = True

    # Process failed event (missing source_path)
    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }
    await handler.handle_event(event)

    metrics = handler.get_metrics()

    assert metrics["events_handled"] == 0
    assert metrics["events_failed"] == 1
    assert metrics["success_rate"] == 0.0
    assert metrics["analysis_failures"] == 1


@pytest.mark.asyncio
async def test_get_metrics_mixed_success_failure(handler, mock_router):
    """Test get_metrics with mixed success and failure."""
    handler._router = mock_router
    handler._router_initialized = True

    # Successful event
    success_event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/test.py",
            "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
        },
    }
    await handler.handle_event(success_event)

    # Failed event
    failed_event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }
    await handler.handle_event(failed_event)

    metrics = handler.get_metrics()

    assert metrics["events_handled"] == 1
    assert metrics["events_failed"] == 1
    assert metrics["success_rate"] == 0.5


# ==============================================================================
# Test: Multiple Operation Types
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_multiple_operation_types(handler, mock_router):
    """Test handling events with all different operation types."""
    handler._router = mock_router
    handler._router_initialized = True

    operations = [
        EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
        EnumAnalysisOperationType.INFRASTRUCTURE_SCAN.value,
        EnumAnalysisOperationType.MODEL_DISCOVERY.value,
        EnumAnalysisOperationType.SCHEMA_DISCOVERY.value,
    ]

    for i, operation_type in enumerate(operations):
        event = {
            "correlation_id": str(uuid4()),
            "payload": {
                "source_path": f"/test{i}.py",
                "operation_type": operation_type,
            },
        }
        result = await handler.handle_event(event)
        assert result is True

    # Verify all operation-specific metrics were incremented
    assert handler.metrics["pattern_extraction_count"] == 1
    assert handler.metrics["infrastructure_scan_count"] == 1
    assert handler.metrics["model_discovery_count"] == 1
    assert handler.metrics["schema_discovery_count"] == 1
    assert handler.metrics["events_handled"] == 4


@pytest.mark.asyncio
async def test_handle_event_logs_quality_score(handler, mock_router):
    """Test handle_event logs quality score for quality assessment operations."""
    handler._router = mock_router
    handler._router_initialized = True

    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/test.py",
            "content": "code",
            "operation_type": "QUALITY_ASSESSMENT",
        },
    }

    with patch("handlers.intelligence_adapter_handler.logger") as mock_logger:
        result = await handler.handle_event(event)

        assert result is True
        # Verify logger.info was called with quality score
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_handle_event_with_default_options(handler, mock_router):
    """Test handle_event with default options when not provided."""
    handler._router = mock_router
    handler._router_initialized = True

    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/test.py",
            "operation_type": EnumAnalysisOperationType.PATTERN_EXTRACTION.value,
            # No options provided
        },
    }

    result = await handler.handle_event(event)

    assert result is True
    # Verify handler was called with empty dict options
    handler.pattern_extraction_handler.execute.assert_called_once_with(
        source_path="/test.py",
        options={},
    )


@pytest.mark.asyncio
async def test_handle_event_with_default_language(handler, mock_router):
    """Test handle_event with default language when not provided."""
    handler._router = mock_router
    handler._router_initialized = True

    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/test.py",
            "content": "code",
            "operation_type": "QUALITY_ASSESSMENT",
            # No language provided, should default to 'python'
        },
    }

    result = await handler.handle_event(event)

    assert result is True


@pytest.mark.asyncio
async def test_handle_event_with_default_operation_type(handler, mock_router):
    """Test handle_event with default operation_type when not provided."""
    handler._router = mock_router
    handler._router_initialized = True

    event = {
        "correlation_id": str(uuid4()),
        "payload": {
            "source_path": "/test.py",
            "content": "code",
            # No operation_type provided, should default to 'QUALITY_ASSESSMENT'
        },
    }

    result = await handler.handle_event(event)

    assert result is True
