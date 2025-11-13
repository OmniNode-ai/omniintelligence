"""
Integration test for Entity Extraction - Code operation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from events.models.entity_extraction_events import EntityExtractionEventHelpers
from handlers.entity_extraction_handler import EntityExtractionHandler


@pytest.mark.asyncio
async def test_code_extraction_success():
    """Test successful code extraction flow."""
    correlation_id = uuid4()
    http_client = AsyncMock()
    producer = AsyncMock()

    http_response = MagicMock()
    http_response.status_code = 200
    http_response.json.return_value = {
        "entities_count": 15,
        "entity_types": ["FUNCTION", "CLASS", "VARIABLE"],
        "confidence_mean": 0.92,
    }
    http_client.post = AsyncMock(return_value=http_response)

    handler = EntityExtractionHandler(http_client=http_client)
    handler._router = producer
    handler._router_initialized = True

    payload = {
        "content": "class Example:\n    def method(self): pass",
        "source_path": "src/example.py",
        "language": "python",
        "extract_types": ["CLASS", "FUNCTION"],
    }

    event = EntityExtractionEventHelpers.create_event_envelope(
        event_type="code_extraction_requested",
        payload=payload,
        correlation_id=correlation_id,
    )

    result = await handler.handle_event(event)

    assert result is True
    http_client.post.assert_called_once()
    assert "http://localhost:8053/extract/code" in http_client.post.call_args[0][0]
    producer.publish.assert_called_once()
