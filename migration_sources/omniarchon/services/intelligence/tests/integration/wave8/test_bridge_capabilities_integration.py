"""
Integration Test - Bridge Intelligence: Capabilities Operation

Tests complete HTTP flow for GET /api/bridge/capabilities:
1. Handler receives CAPABILITIES_REQUESTED event
2. Handler calls Bridge service HTTP endpoint
3. Handler publishes CAPABILITIES_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.bridge_intelligence_events import EnumBridgeEventType
from handlers.bridge_intelligence_handler import BridgeIntelligenceHandler


@pytest.fixture
def mock_capabilities_response():
    """Mock successful capabilities response."""
    return {
        "capabilities": [
            "metadata_generation",
            "quality_analysis",
            "pattern_detection",
        ],
        "supported_languages": ["python", "typescript", "rust"],
        "metadata_features": ["complexity", "maintainability", "security"],
        "version_info": {"service_version": "1.0.0", "api_version": "v1"},
        "rate_limits": {"requests_per_minute": 100, "burst_size": 20},
    }


@pytest.fixture
def sample_capabilities_request():
    """Create sample capabilities request."""
    correlation_id = str(uuid4())
    payload = {
        "include_versions": True,
        "include_limits": True,
    }

    return {
        "event_type": EnumBridgeEventType.CAPABILITIES_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestBridgeCapabilitiesIntegration:
    """Integration tests for Bridge Capabilities operation."""

    async def test_capabilities_success(
        self,
        sample_capabilities_request,
        mock_capabilities_response,
    ):
        """Test successful capabilities retrieval via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_capabilities_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = BridgeIntelligenceHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_capabilities_request)

            assert result is True

            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "capabilities-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert len(payload["capabilities"]) == 3
            assert len(payload["supported_languages"]) == 3
