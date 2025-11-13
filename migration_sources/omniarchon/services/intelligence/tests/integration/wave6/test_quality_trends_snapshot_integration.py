"""
Integration Test: Quality Trends - Snapshot
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: POST /api/quality-trends/snapshot
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.quality_trends
class TestQualityTrendsSnapshotIntegration:
    """Integration tests for Quality Trends Snapshot operation."""

    @pytest.mark.asyncio
    async def test_snapshot_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete snapshot flow with successful HTTP response."""
        from handlers.quality_trends_handler import QualityTrendsHandler

        # Create handler
        handler = QualityTrendsHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {
            "project_id": "test_project_001",
            "file_path": "src/test_module.py",
            "quality_score": 0.88,
            "onex_compliance_score": 0.92,
            "correlation_id": correlation_id,
            "violations": [],
            "warnings": [],
        }
        event = mock_event_envelope(
            correlation_id, payload, event_type="SNAPSHOT_REQUESTED"
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "project_id": "test_project_001",
            "file_path": "src/test_module.py",
            "quality_score": 0.88,
            "snapshot_id": "snap_20250122_001",
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler processed successfully
            assert result is True

            # Verify HTTP call was made
            mock_client.post.assert_called_once_with(
                "http://localhost:8053/api/quality-trends/snapshot", json=payload
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify event structure
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            assert str(published_event["correlation_id"]) == correlation_id

            # Verify payload structure
            result_payload = published_event["payload"]
            assert "project_id" in result_payload
            assert result_payload["project_id"] == "test_project_001"
            assert "file_path" in result_payload
            assert result_payload["file_path"] == "src/test_module.py"
            assert "quality_score" in result_payload
            assert result_payload["quality_score"] == 0.88
            assert "snapshot_id" in result_payload
            assert result_payload["snapshot_id"] == "snap_20250122_001"

    @pytest.mark.asyncio
    async def test_snapshot_http_error_handling(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test snapshot flow when HTTP service returns error."""
        import httpx
        from handlers.quality_trends_handler import QualityTrendsHandler

        # Create handler
        handler = QualityTrendsHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {
            "project_id": "test_project_001",
            "file_path": "src/test.py",
            "quality_score": 0.75,
            "onex_compliance_score": 0.80,
            "correlation_id": correlation_id,
            "violations": [],
            "warnings": [],
        }
        event = mock_event_envelope(
            correlation_id, payload, event_type="SNAPSHOT_REQUESTED"
        )

        # Mock HTTP error
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Internal Server Error",
                    request=AsyncMock(),
                    response=AsyncMock(),
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler failed gracefully
            assert result is False

            # Verify error response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify error payload
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            result_payload = published_event["payload"]
            assert "error_message" in result_payload
            assert "project_id" in result_payload
            assert result_payload["project_id"] == "test_project_001"
            assert "file_path" in result_payload
            assert result_payload["file_path"] == "src/test.py"
