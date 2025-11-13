"""
Integration test for Quality Assessment - Code operation.

Tests the complete flow:
1. REQUEST event published
2. HTTP call to intelligence service
3. COMPLETED event published with results
4. Error handling (HTTP errors, timeouts)
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.quality_assessment_events import (
    EnumQualityAssessmentEventType,
    QualityAssessmentEventHelpers,
)
from handlers.quality_assessment_handler import QualityAssessmentHandler


@pytest.mark.asyncio
async def test_code_assessment_success():
    """Test successful code assessment flow with HTTP call."""
    # Setup
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    # Mock HTTP response
    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "quality_score": 0.87,
        "onex_compliance_score": 0.92,
        "complexity": {"score": 0.75},
        "maintainability": {"score": 0.85},
        "patterns": [{"type": "ONEX_EFFECT"}],
        "issues": [],
        "recommendations": ["Add type hints"],
    }
    http_client.post = AsyncMock(return_value=http_response)

    # Create handler
    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    # Create request event
    payload = {
        "content": "def hello():\n    return 'world'",
        "source_path": "src/api.py",
        "language": "python",
    }

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="code_assessment_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    # Execute
    result = await handler.handle_event(event)

    # Verify
    assert result is True

    # Verify HTTP call
    http_client.post.assert_called_once()
    call_args = http_client.post.call_args
    assert "http://localhost:8053/assess/code" in call_args[0][0]
    assert call_args[1]["json"]["content"] == payload["content"]

    # Verify completed event published
    producer.publish.assert_called_once()
    published_event = producer.publish.call_args[1]["event"]
    # Extract event_type from metadata (omnibase_core pattern)
    event_type = published_event.get("metadata", {}).get("event_type", "")
    assert "completed" in event_type.lower()
    assert published_event["correlation_id"] == correlation_id


@pytest.mark.asyncio
async def test_code_assessment_http_error():
    """Test code assessment with HTTP 500 error."""
    # Setup
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    # Mock HTTP error
    import httpx

    http_response = MagicMock()
    http_response.status_code = 500
    http_response.text = "Internal Server Error"
    http_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=http_response
        )
    )

    # Create handler
    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    # Create request event
    payload = {
        "content": "def hello():\n    pass",
        "source_path": "src/api.py",
        "language": "python",
    }

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="code_assessment_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    # Execute
    result = await handler.handle_event(event)

    # Verify
    assert result is False

    # Verify failed event published
    producer.publish.assert_called_once()
    published_event = producer.publish.call_args[1]["event"]
    # Extract event_type from metadata (omnibase_core pattern)
    event_type = published_event.get("metadata", {}).get("event_type", "")
    assert "failed" in event_type.lower()
    assert published_event["correlation_id"] == correlation_id


@pytest.mark.asyncio
async def test_code_assessment_timeout():
    """Test code assessment with timeout error."""
    # Setup
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    # Mock timeout error
    import httpx

    http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

    # Create handler
    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    # Create request event
    payload = {
        "content": "def hello():\n    pass",
        "source_path": "src/api.py",
        "language": "python",
    }

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="code_assessment_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    # Execute
    result = await handler.handle_event(event)

    # Verify
    assert result is False

    # Verify timeout error in failed event
    producer.publish.assert_called_once()
    published_event = producer.publish.call_args[1]["event"]
    # Extract event_type from metadata (omnibase_core pattern)
    event_type = published_event.get("metadata", {}).get("event_type", "")
    assert "failed" in event_type.lower()
    # Extract error_code from payload (dict or object)
    payload = published_event["payload"]
    error_code = (
        payload.get("error_code") if isinstance(payload, dict) else payload.error_code
    )
    error_code_value = error_code.value if hasattr(error_code, "value") else error_code
    assert error_code_value == "TIMEOUT"
