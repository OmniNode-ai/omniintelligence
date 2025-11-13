"""
Integration Test - Bridge Intelligence: Health Operation

Tests complete HTTP flow for GET /api/bridge/health:
1. Handler receives BRIDGE_HEALTH_REQUESTED event
2. Handler calls Bridge service HTTP endpoint
3. Handler publishes BRIDGE_HEALTH_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.bridge_intelligence_events import EnumBridgeEventType
from handlers.bridge_intelligence_handler import BridgeIntelligenceHandler


@pytest.fixture
def mock_health_response():
    """Mock successful health response."""
    return {
        "status": "healthy",
        "uptime_seconds": 3600.0,
        "version": "1.0.0",
        "dependencies": {
            "database": "healthy",
            "cache": "healthy",
        },
    }


@pytest.fixture
def sample_health_request():
    """Create sample health request."""
    correlation_id = str(uuid4())
    payload = {
        "include_dependencies": True,
        "timeout_ms": 5000,
    }

    return {
        "event_type": EnumBridgeEventType.BRIDGE_HEALTH_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestBridgeHealthIntegration:
    """Integration tests for Bridge Health operation."""

    async def test_health_check_success(
        self,
        sample_health_request,
        mock_health_response,
    ):
        """Test successful health check via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_health_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = BridgeIntelligenceHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_health_request)

            assert result is True

            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "bridge-health-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["status"] == "healthy"
            assert payload["version"] == "1.0.0"
