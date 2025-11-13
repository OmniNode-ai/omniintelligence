"""
Freshness All Operations Integration Tests

Comprehensive integration tests for all 8 freshness operations with actual HTTP calls.

Operations Tested:
1. analyze - POST /freshness/analyze
2. stale - GET /freshness/stale
3. refresh - POST /freshness/refresh
4. stats - GET /freshness/stats
5. document - GET /freshness/document/{path}
6. cleanup - DELETE /freshness/cleanup
7. document_update - POST /freshness/events/document-update
8. event_stats - GET /freshness/events/stats

Created: 2025-10-22
"""

from unittest.mock import AsyncMock, patch
from urllib.parse import quote
from uuid import uuid4

import httpx
import pytest
from handlers.freshness_handler import FreshnessHandler


@pytest.mark.asyncio
class TestFreshnessAnalyzeIntegration:
    """Integration tests for Freshness Analyze operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def analyze_event(self):
        """Create test analyze event."""
        return {
            "event_type": "FRESHNESS_ANALYZE_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {
                "document_paths": ["/docs/test1.md", "/docs/test2.md"],
                "metadata": {"source": "test"},
            },
        }

    async def test_analyze_success(self, handler, analyze_event):
        """Test successful analyze HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "analyzed_count": 2,
            "stale_count": 1,
            "fresh_count": 1,
            "results": {"detailed": "analysis"},
        }

        with patch.object(httpx.AsyncClient, "post") as mock_post:
            # Create regular Mock for response (not AsyncMock)
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()  # Regular method, not async
            mock_post.return_value = mock_resp

            result = await handler.handle_event(analyze_event)

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "http://test-service:8053/freshness/analyze" in str(call_args)
            assert (
                call_args.kwargs["json"]["document_paths"]
                == analyze_event["payload"]["document_paths"]
            )
            handler._router.publish.assert_called_once()

    async def test_analyze_http_error(self, handler, analyze_event):
        """Test analyze HTTP error handling."""
        from unittest.mock import Mock

        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = Mock()
            mock_resp.status_code = 400
            mock_resp.text = "Bad Request"
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "400 Error", request=Mock(), response=mock_resp
            )
            mock_post.return_value = mock_resp

            result = await handler.handle_event(analyze_event)

            assert result is False
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessStaleIntegration:
    """Integration tests for Freshness Stale operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def stale_event(self):
        """Create test stale event."""
        return {
            "event_type": "FRESHNESS_STALE_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {"threshold_days": 30},
        }

    async def test_stale_success(self, handler, stale_event):
        """Test successful stale HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "stale_documents": [{"path": "/docs/old.md", "age_days": 45}],
            "total_count": 1,
            "threshold_days": 30,
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(stale_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "http://test-service:8053/freshness/stale" in str(call_args)
            assert call_args.kwargs["params"]["threshold_days"] == 30
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessRefreshIntegration:
    """Integration tests for Freshness Refresh operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def refresh_event(self):
        """Create test refresh event."""
        return {
            "event_type": "FRESHNESS_REFRESH_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {"document_paths": ["/docs/test.md"]},
        }

    async def test_refresh_success(self, handler, refresh_event):
        """Test successful refresh HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "refreshed_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "results": {},
        }

        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_post.return_value = mock_resp

            result = await handler.handle_event(refresh_event)

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "http://test-service:8053/freshness/refresh" in str(call_args)
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessStatsIntegration:
    """Integration tests for Freshness Stats operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def stats_event(self):
        """Create test stats event."""
        return {
            "event_type": "FRESHNESS_STATS_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {},
        }

    async def test_stats_success(self, handler, stats_event):
        """Test successful stats HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "total_documents": 100,
            "stale_documents": 20,
            "fresh_documents": 80,
            "average_age_days": 15.5,
            "breakdown": {},
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(stats_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "http://test-service:8053/freshness/stats" in str(call_args)
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessDocumentIntegration:
    """Integration tests for Freshness Document operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def document_event(self):
        """Create test document event."""
        return {
            "event_type": "FRESHNESS_DOCUMENT_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {"document_path": "/docs/test.md"},
        }

    async def test_document_success(self, handler, document_event):
        """Test successful document HTTP call with URL encoding."""
        from unittest.mock import Mock

        mock_response = {
            "document_path": "/docs/test.md",
            "is_stale": False,
            "age_days": 5.0,
            "last_modified": "2025-10-17T00:00:00Z",
            "freshness_score": 0.9,
            "history": None,
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(document_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            # Verify URL encoding was applied
            encoded_path = quote("/docs/test.md", safe="")
            assert f"http://test-service:8053/freshness/document/{encoded_path}" in str(
                call_args
            )
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessCleanupIntegration:
    """Integration tests for Freshness Cleanup operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def cleanup_event(self):
        """Create test cleanup event."""
        return {
            "event_type": "FRESHNESS_CLEANUP_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {"older_than_days": 90, "dry_run": True},
        }

    async def test_cleanup_success(self, handler, cleanup_event):
        """Test successful cleanup HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "deleted_count": 0,
            "skipped_count": 10,
            "dry_run": True,
        }

        with patch.object(httpx.AsyncClient, "delete") as mock_delete:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_delete.return_value = mock_resp

            result = await handler.handle_event(cleanup_event)

            assert result is True
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert "http://test-service:8053/freshness/cleanup" in str(call_args)
            assert call_args.kwargs["params"]["older_than_days"] == 90
            assert call_args.kwargs["params"]["dry_run"] == "true"
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessDocumentUpdateIntegration:
    """Integration tests for Freshness Document Update operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def document_update_event(self):
        """Create test document update event."""
        return {
            "event_type": "FRESHNESS_DOCUMENT_UPDATE_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {
                "document_path": "/docs/test.md",
                "event_type": "modified",
                "metadata": {},
            },
        }

    async def test_document_update_success(self, handler, document_update_event):
        """Test successful document update HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "document_path": "/docs/test.md",
            "event_type": "modified",
            "updated": True,
        }

        with patch.object(httpx.AsyncClient, "post") as mock_post:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_post.return_value = mock_resp

            result = await handler.handle_event(document_update_event)

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "http://test-service:8053/freshness/events/document-update" in str(
                call_args
            )
            handler._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestFreshnessEventStatsIntegration:
    """Integration tests for Freshness Event Stats operation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = FreshnessHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def event_stats_event(self):
        """Create test event stats event."""
        return {
            "event_type": "FRESHNESS_EVENT_STATS_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {"time_window_hours": 48},
        }

    async def test_event_stats_success(self, handler, event_stats_event):
        """Test successful event stats HTTP call."""
        from unittest.mock import Mock

        mock_response = {
            "total_events": 150,
            "events_by_type": {
                "modified": 100,
                "created": 30,
                "deleted": 20,
            },
            "time_window_hours": 48,
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(event_stats_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "http://test-service:8053/freshness/events/stats" in str(call_args)
            assert call_args.kwargs["params"]["time_window_hours"] == 48
            handler._router.publish.assert_called_once()
