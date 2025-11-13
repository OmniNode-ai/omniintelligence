"""
Integration Test - Bridge Intelligence: Generate Intelligence Operation

Tests complete HTTP flow for POST /api/bridge/generate-intelligence:
1. Handler receives GENERATE_INTELLIGENCE_REQUESTED event
2. Handler calls Bridge service HTTP endpoint
3. Handler publishes GENERATE_INTELLIGENCE_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.bridge_intelligence_events import EnumBridgeEventType
from handlers.bridge_intelligence_handler import BridgeIntelligenceHandler


@pytest.fixture
def mock_intelligence_response():
    """Mock successful intelligence generation response."""
    return {
        "metadata": {
            "complexity": 0.75,
            "maintainability": 0.82,
            "quality_score": 0.79,
        },
        "blake3_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
        "intelligence_score": 0.85,
        "cache_hit": False,
    }


@pytest.fixture
def sample_generate_request():
    """Create sample generate intelligence request."""
    correlation_id = str(uuid4())
    payload = {
        "source_path": "src/test_module.py",
        "content": "def hello(): return 'world'",
        "language": "python",
        "metadata_options": {},
    }

    return {
        "event_type": EnumBridgeEventType.GENERATE_INTELLIGENCE_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestBridgeGenerateIntelligenceIntegration:
    """Integration tests for Bridge Generate Intelligence operation."""

    async def test_generate_intelligence_success(
        self,
        sample_generate_request,
        mock_intelligence_response,
    ):
        """Test successful intelligence generation via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_intelligence_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", return_value=mock_response
        ) as mock_post:
            handler = BridgeIntelligenceHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_generate_request)

            assert result is True

            # Verify HTTP call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/api/bridge/generate-intelligence" in call_args[0][0]

            # Verify request payload
            json_data = call_args[1]["json"]
            assert json_data["source_path"] == "src/test_module.py"
            assert json_data["language"] == "python"

            # Verify response published
            handler._router.publish.assert_called_once()

    async def test_generate_intelligence_missing_required_fields(self):
        """Test intelligence generation with missing required fields."""
        correlation_id = str(uuid4())
        invalid_payload = {
            "source_path": None,  # Missing
            "content": None,  # Missing
        }

        event = {
            "event_type": EnumBridgeEventType.GENERATE_INTELLIGENCE_REQUESTED.value,
            "correlation_id": correlation_id,
            "payload": invalid_payload,
        }

        handler = BridgeIntelligenceHandler()
        handler._router = AsyncMock()
        handler._router.publish = AsyncMock()
        handler._router_initialized = True

        result = await handler.handle_event(event)

        assert result is False

        # Verify failure response published
        publish_call = handler._router.publish.call_args
        topic = publish_call[1]["topic"]
        assert "generate-intelligence-failed" in topic
