"""
Integration test for Entity Extraction - Relationships operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.entity_extraction_events import EntityExtractionEventHelpers
from handlers.entity_extraction_handler import EntityExtractionHandler


@pytest.mark.asyncio
async def test_relationship_query_success():
    """Test successful relationship query flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "relationships_count": 12,
    }
    http_client.get = AsyncMock(return_value=http_response)

    handler = EntityExtractionHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "entity_id": "entity_123",
        "limit": 20,
    }

    event = EntityExtractionEventHelpers.create_event_envelope(
        event_type="relationship_query_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.get.assert_called_once()
    assert (
        "http://localhost:8053/relationships/entity_123"
        in http_client.get.call_args[0][0]
    )
    producer.publish.assert_called_once()
