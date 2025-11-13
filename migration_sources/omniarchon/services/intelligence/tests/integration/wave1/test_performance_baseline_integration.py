"""
Integration test for Performance - Baseline operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.performance_events import PerformanceEventHelpers
from handlers.performance_handler import PerformanceHandler


@pytest.mark.asyncio
async def test_baseline_success():
    """Test successful baseline establishment flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "operation_name": "api_endpoint",
        "average_response_time_ms": 245.5,
        "p50_ms": 220.0,
        "p95_ms": 380.0,
        "p99_ms": 450.0,
        "sample_size": 100,
        "source": "measurement",
    }
    http_client.post = AsyncMock(return_value=http_response)

    handler = PerformanceHandler()
    handler.http_client = http_client
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "operation_name": "api_endpoint",
        "metrics": {"avg_ms": 250},
    }

    event = PerformanceEventHelpers.create_event_envelope(
        event_type="baseline_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.post.assert_called_once()
    assert "/performance/baseline" in http_client.post.call_args[0][0]
    producer.publish.assert_called_once()
