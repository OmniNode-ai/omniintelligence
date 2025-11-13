"""
Integration test for Quality Assessment - Compliance Check operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.quality_assessment_events import QualityAssessmentEventHelpers
from handlers.quality_assessment_handler import QualityAssessmentHandler


@pytest.mark.asyncio
async def test_compliance_check_success():
    """Test successful compliance check flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "compliance_score": 0.92,
        "violations_count": 2,
        "recommendations_count": 3,
    }
    http_client.post = AsyncMock(return_value=http_response)

    handler = QualityAssessmentHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "content": "class NodeDataTransformerCompute:\n    pass",
        "architecture_type": "onex",
    }

    event = QualityAssessmentEventHelpers.create_event_envelope(
        event_type="compliance_check_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.post.assert_called_once()
    assert "http://localhost:8053/compliance/check" in http_client.post.call_args[0][0]
    producer.publish.assert_called_once()
