"""
Integration test for Performance - Optimize operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.performance_events import PerformanceEventHelpers
from handlers.performance_handler import PerformanceHandler


@pytest.mark.asyncio
async def test_optimize_success():
    """Test successful optimization application flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "operation_name": "database_query",
        "category": "caching",
        "improvement_percent": 42.1,
        "baseline_ms": 245.5,
        "optimized_ms": 142.3,
        "test_duration_minutes": 5,
        "success": True,
    }
    http_client.post = AsyncMock(return_value=http_response)

    handler = PerformanceHandler()
    handler.http_client = http_client
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "operation_name": "database_query",
        "category": "caching",
        "test_duration_minutes": 5,
    }

    event = PerformanceEventHelpers.create_event_envelope(
        event_type="optimize_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.post.assert_called_once()
    assert "/performance/optimize" in http_client.post.call_args[0][0]
    producer.publish.assert_called_once()
