"""
Integration test for Entity Extraction - Search operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.entity_extraction_events import EntityExtractionEventHelpers
from handlers.entity_extraction_handler import EntityExtractionHandler


@pytest.mark.asyncio
async def test_entity_search_success():
    """Test successful entity search flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "results_count": 7,
    }
    http_client.get = AsyncMock(return_value=http_response)

    handler = EntityExtractionHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "query": "authentication",
        "limit": 10,
    }

    event = EntityExtractionEventHelpers.create_event_envelope(
        event_type="entity_search_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.get.assert_called_once()
    assert "http://localhost:8053/entities/search" in http_client.get.call_args[0][0]
    producer.publish.assert_called_once()
