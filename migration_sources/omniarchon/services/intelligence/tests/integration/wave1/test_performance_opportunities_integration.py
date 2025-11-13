"""
Integration test for Performance - Opportunities operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.performance_events import PerformanceEventHelpers
from handlers.performance_handler import PerformanceHandler


@pytest.mark.asyncio
async def test_opportunities_success():
    """Test successful opportunities identification flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "operation_name": "slow_query",
        "opportunities_count": 5,
        "total_potential_improvement_percent": 42.5,
        "categories": ["caching", "database_query"],
    }
    http_client.get = AsyncMock(return_value=http_response)

    handler = PerformanceHandler()
    handler.http_client = http_client
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "operation_name": "slow_query",
    }

    event = PerformanceEventHelpers.create_event_envelope(
        event_type="opportunities_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.get.assert_called_once()
    assert "/performance/opportunities/slow_query" in http_client.get.call_args[0][0]
    producer.publish.assert_called_once()
