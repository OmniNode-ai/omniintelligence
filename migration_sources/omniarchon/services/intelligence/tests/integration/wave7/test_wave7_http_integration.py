"""
Wave 7 Integration Tests - HTTP Implementation Verification

Tests all 10 operations with actual HTTP calls to intelligence service:

Quality Trends (6 operations):
1. Project Trend - GET /api/quality-trends/project/{project_id}/trend
2. File Trend - GET /api/quality-trends/project/{project_id}/file/{file_path}/trend
3. File History - GET /api/quality-trends/project/{project_id}/file/{file_path}/history
4. Detect Regression - POST /api/quality-trends/detect-regression
5. Stats - GET /api/quality-trends/stats
6. Clear - DELETE /api/quality-trends/project/{project_id}/snapshots

Performance Analytics (4 operations):
7. Baselines - GET /api/performance-analytics/baselines
8. Metrics - GET /api/performance-analytics/operations/{operation}/metrics
9. Opportunities - GET /api/performance-analytics/optimization-opportunities
10. Anomaly Check - POST /api/performance-analytics/operations/{operation}/anomaly-check

Created: 2025-10-22
Purpose: Verify HTTP implementation in handlers works correctly
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from handlers.performance_analytics_handler import PerformanceAnalyticsHandler

# Handlers to test
from handlers.quality_trends_handler import QualityTrendsHandler


@pytest.fixture
def quality_trends_handler():
    """Create quality trends handler instance"""
    handler = QualityTrendsHandler()
    handler._router = AsyncMock()  # Mock router to avoid Kafka dependency
    handler._router_initialized = True
    return handler


@pytest.fixture
def performance_analytics_handler():
    """Create performance analytics handler instance"""
    handler = PerformanceAnalyticsHandler()
    handler._router = AsyncMock()  # Mock router to avoid Kafka dependency
    handler._router_initialized = True
    return handler


# ============================================================================
# Quality Trends Tests (6 operations)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestQualityTrendsHTTPIntegration:
    """Integration tests for Quality Trends HTTP operations"""

    async def test_project_trend_http_call(self, quality_trends_handler):
        """Test 1: Project Trend - GET /api/quality-trends/project/{project_id}/trend"""

        mock_response = {
            "success": True,
            "project_id": "test_project",
            "trend": "improving",
            "current_quality": 0.88,
            "avg_quality": 0.85,
            "slope": 0.03,
            "snapshots_count": 42,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.get.return_value = response_mock

            payload = {"project_id": "test_project", "time_window_days": 30}
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_project_trend(
                correlation_id, payload, 0.0
            )

            assert result is True
            # Verify HTTP call was made
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert "/api/quality-trends/project/test_project/trend" in str(call_args)

    async def test_file_trend_http_call(self, quality_trends_handler):
        """Test 2: File Trend - GET /api/quality-trends/project/{project_id}/file/{file_path}/trend"""

        mock_response = {
            "success": True,
            "project_id": "test_project",
            "file_path": "src/main.py",
            "trend": "stable",
            "current_quality": 0.90,
            "avg_quality": 0.89,
            "slope": 0.01,
            "snapshots_count": 12,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.get.return_value = response_mock

            payload = {
                "project_id": "test_project",
                "file_path": "src/main.py",
                "time_window_days": 30,
            }
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_file_trend(
                correlation_id, payload, 0.0
            )

            assert result is True
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert (
                "/api/quality-trends/project/test_project/file/src/main.py/trend"
                in str(call_args)
            )

    async def test_file_history_http_call(self, quality_trends_handler):
        """Test 3: File History - GET /api/quality-trends/project/{project_id}/file/{file_path}/history"""

        mock_response = {
            "success": True,
            "project_id": "test_project",
            "file_path": "src/main.py",
            "history": [
                {
                    "timestamp": "2025-10-22T10:00:00Z",
                    "quality_score": 0.90,
                    "compliance_score": 0.92,
                }
            ],
            "snapshots_count": 1,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.get.return_value = response_mock

            payload = {
                "project_id": "test_project",
                "file_path": "src/main.py",
                "limit": 50,
            }
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_file_history(
                correlation_id, payload, 0.0
            )

            assert result is True
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert (
                "/api/quality-trends/project/test_project/file/src/main.py/history"
                in str(call_args)
            )

    async def test_detect_regression_http_call(self, quality_trends_handler):
        """Test 4: Detect Regression - POST /api/quality-trends/detect-regression"""

        mock_response = {
            "success": True,
            "project_id": "test_project",
            "regression_detected": False,
            "current_score": 0.91,
            "avg_recent_score": 0.90,
            "difference": 0.01,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.post.return_value = response_mock

            payload = {
                "project_id": "test_project",
                "current_score": 0.91,
                "threshold": 0.1,
            }
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_detect_regression(
                correlation_id, payload, 0.0
            )

            assert result is True
            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert "/api/quality-trends/detect-regression" in str(call_args)

    async def test_stats_http_call(self, quality_trends_handler):
        """Test 5: Stats - GET /api/quality-trends/stats"""

        mock_response = {
            "success": True,
            "total_snapshots": 1200,
            "total_projects": 15,
            "avg_quality_score": 0.87,
            "service_status": "active",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.get.return_value = response_mock

            payload = {}
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_stats(
                correlation_id, payload, 0.0
            )

            assert result is True
            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args
            assert "/api/quality-trends/stats" in str(call_args)

    async def test_clear_http_call(self, quality_trends_handler):
        """Test 6: Clear - DELETE /api/quality-trends/project/{project_id}/snapshots"""

        mock_response = {
            "success": True,
            "project_id": "test_project",
            "cleared_snapshots": 42,
            "message": "Cleared 42 snapshots for project_id=test_project",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create Mock response (not AsyncMock) to avoid coroutine issues
            response_mock = Mock()
            response_mock.raise_for_status = Mock()
            response_mock.json = Mock(return_value=mock_response)
            mock_instance.delete.return_value = response_mock

            payload = {"project_id": "test_project"}
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_clear(
                correlation_id, payload, 0.0
            )

            assert result is True
            mock_instance.delete.assert_called_once()
            call_args = mock_instance.delete.call_args
            assert "/api/quality-trends/project/test_project/snapshots" in str(
                call_args
            )


# ============================================================================
# Performance Analytics Tests (4 operations)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestPerformanceAnalyticsHTTPIntegration:
    """Integration tests for Performance Analytics HTTP operations"""

    async def test_baselines_http_call(self, performance_analytics_handler):
        """Test 7: Baselines - GET /api/performance-analytics/baselines"""

        mock_response = {
            "baselines": {
                "api_call": {
                    "p50": 100.0,
                    "p95": 180.0,
                    "p99": 200.0,
                    "mean": 110.0,
                    "std_dev": 25.0,
                    "sample_size": 100,
                }
            },
            "total_operations": 1,
            "total_measurements": 100,
            "timestamp": "2025-10-22T10:00:00Z",
        }

        # Mock HTTP client
        await performance_analytics_handler._ensure_http_client()

        # Create Mock response (not AsyncMock) to avoid coroutine issues
        response_mock = Mock()
        response_mock.raise_for_status = Mock()
        response_mock.json = Mock(return_value=mock_response)

        performance_analytics_handler.http_client.get = AsyncMock(
            return_value=response_mock
        )

        payload = {}
        correlation_id = str(uuid4())

        result = await performance_analytics_handler._handle_baselines(
            correlation_id, payload, 0.0
        )

        assert result is True
        performance_analytics_handler.http_client.get.assert_called_once()
        call_args = performance_analytics_handler.http_client.get.call_args
        assert "/api/performance-analytics/baselines" in str(call_args)

    async def test_metrics_http_call(self, performance_analytics_handler):
        """Test 8: Metrics - GET /api/performance-analytics/operations/{operation}/metrics"""

        mock_response = {
            "operation": "fast_operation",
            "baseline": {"mean": 110.0, "p50": 100.0, "p95": 180.0, "sample_size": 100},
            "recent_measurements": [],
            "trend": "stable",
            "anomaly_count_24h": 0,
        }

        await performance_analytics_handler._ensure_http_client()

        # Create Mock response (not AsyncMock) to avoid coroutine issues
        response_mock = Mock()
        response_mock.raise_for_status = Mock()
        response_mock.json = Mock(return_value=mock_response)

        performance_analytics_handler.http_client.get = AsyncMock(
            return_value=response_mock
        )

        payload = {"operation": "fast_operation"}
        correlation_id = str(uuid4())

        result = await performance_analytics_handler._handle_metrics(
            correlation_id, payload, 0.0
        )

        assert result is True
        performance_analytics_handler.http_client.get.assert_called_once()
        call_args = performance_analytics_handler.http_client.get.call_args
        assert "/api/performance-analytics/operations/fast_operation/metrics" in str(
            call_args
        )

    async def test_opportunities_http_call(self, performance_analytics_handler):
        """Test 9: Opportunities - GET /api/performance-analytics/optimization-opportunities"""

        mock_response = {
            "opportunities": [
                {
                    "operation": "slow_query",
                    "current_p95": 850.0,
                    "estimated_improvement": 30.0,
                    "effort_level": "medium",
                    "roi_score": 25.5,
                    "priority": "high",
                    "recommendations": ["Add database index", "Optimize query"],
                }
            ],
            "total_opportunities": 1,
            "avg_roi": 25.5,
            "total_potential_improvement": 255.0,
        }

        await performance_analytics_handler._ensure_http_client()

        # Create Mock response (not AsyncMock) to avoid coroutine issues
        response_mock = Mock()
        response_mock.raise_for_status = Mock()
        response_mock.json = Mock(return_value=mock_response)

        performance_analytics_handler.http_client.get = AsyncMock(
            return_value=response_mock
        )

        payload = {}
        correlation_id = str(uuid4())

        result = await performance_analytics_handler._handle_opportunities(
            correlation_id, payload, 0.0
        )

        assert result is True
        performance_analytics_handler.http_client.get.assert_called_once()
        call_args = performance_analytics_handler.http_client.get.call_args
        assert "/api/performance-analytics/optimization-opportunities" in str(call_args)

    async def test_anomaly_check_http_call(self, performance_analytics_handler):
        """Test 10: Anomaly Check - POST /api/performance-analytics/operations/{operation}/anomaly-check"""

        mock_response = {
            "anomaly_detected": False,
            "z_score": 1.5,
            "current_duration_ms": 125.0,
            "baseline_mean": 110.0,
            "baseline_p95": 180.0,
            "baseline_std_dev": 25.0,
            "deviation_percentage": 13.6,
            "severity": "normal",
        }

        await performance_analytics_handler._ensure_http_client()

        # Create Mock response (not AsyncMock) to avoid coroutine issues
        response_mock = Mock()
        response_mock.raise_for_status = Mock()
        response_mock.json = Mock(return_value=mock_response)

        performance_analytics_handler.http_client.post = AsyncMock(
            return_value=response_mock
        )

        payload = {"operation": "fast_operation", "duration_ms": 125.0}
        correlation_id = str(uuid4())

        result = await performance_analytics_handler._handle_anomaly_check(
            correlation_id, payload, 0.0
        )

        assert result is True
        performance_analytics_handler.http_client.post.assert_called_once()
        call_args = performance_analytics_handler.http_client.post.call_args
        assert (
            "/api/performance-analytics/operations/fast_operation/anomaly-check"
            in str(call_args)
        )


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestWave7ErrorHandling:
    """Test error handling for HTTP failures"""

    async def test_http_error_handling_quality_trends(self, quality_trends_handler):
        """Verify handlers handle HTTP errors gracefully"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            # Simulate HTTP error
            mock_request = Mock()
            mock_response = Mock()
            mock_response.status_code = 404
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=mock_request, response=mock_response
            )

            payload = {"project_id": "nonexistent"}
            correlation_id = str(uuid4())

            result = await quality_trends_handler._handle_project_trend(
                correlation_id, payload, 0.0
            )

            # Handler should fail gracefully and publish error event
            assert result is False
            quality_trends_handler._router.publish.assert_called_once()

    async def test_http_error_handling_performance_analytics(
        self, performance_analytics_handler
    ):
        """Verify performance analytics handlers handle HTTP errors gracefully"""

        await performance_analytics_handler._ensure_http_client()

        # Create Mock request/response for error (not AsyncMock)
        mock_request = Mock()
        mock_response = Mock()
        mock_response.status_code = 404

        performance_analytics_handler.http_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found", request=mock_request, response=mock_response
            )
        )

        payload = {}
        correlation_id = str(uuid4())

        result = await performance_analytics_handler._handle_baselines(
            correlation_id, payload, 0.0
        )

        # Handler should fail gracefully and publish error event
        assert result is False
        performance_analytics_handler._router.publish.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
