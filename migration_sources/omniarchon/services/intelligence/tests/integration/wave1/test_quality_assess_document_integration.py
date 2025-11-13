"""
Integration test for Quality Assessment - Document operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.quality_assessment_events import QualityAssessmentEventHelpers
from handlers.quality_assessment_handler import QualityAssessmentHandler


@pytest.mark.asyncio
async def test_document_assessment_success():
    """Test successful document assessment flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    # Mock HTTP response
    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "quality_score": 0.85,
        "completeness_score": 0.90,
        "structure_score": 0.80,
        "clarity_score": 0.88,
        "word_count": 500,
        "section_count": 5,
    }
    http_client.post = AsyncMock(return_value=http_response)

    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {"content": "# Documentation\n\nThis is a test document."}

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="document_assessment_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.post.assert_called_once()
    assert "http://localhost:8053/assess/document" in http_client.post.call_args[0][0]
    producer.publish.assert_called_once()


@pytest.mark.asyncio
async def test_document_assessment_invalid_input():
    """Test document assessment with invalid input (400 error)."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    import httpx

    http_response = MagicMock()
    http_response.status_code = 400
    http_response.text = "Invalid content"
    http_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=http_response
        )
    )

    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {"content": ""}

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="document_assessment_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is False
    published_event = producer.publish.call_args[1]["event"]
    # Extract error_code from payload (dict or object)
    payload = published_event["payload"]
    error_code = (
        payload.get("error_code") if isinstance(payload, dict) else payload.error_code
    )
    error_code_value = error_code.value if hasattr(error_code, "value") else error_code
    assert error_code_value == "INVALID_INPUT"
