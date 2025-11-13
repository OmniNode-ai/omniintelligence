"""
Wave 5 Comprehensive Integration Tests

Tests all 10 HTTP implementations in event handlers:
- Autonomous Learning (6): patterns_success, predict_agent, predict_time, safety_score, stats, health
- Pattern Analytics (4): success_rates, top_patterns, emerging, history

Tests verify:
1. HTTP call to correct endpoint with correct params
2. Response parsing and validation
3. Event publishing with correct payload structure
4. Error handling for HTTP failures
5. Correlation ID preservation throughout flow

Marker Usage:
    pytest -m wave5                # Run all Wave 5 tests
    pytest -m autonomous_learning  # Run autonomous learning tests
    pytest -m pattern_analytics    # Run pattern analytics tests
    pytest tests/integration/wave5 # Run all Wave 5 integration tests

Created: 2025-10-22
Purpose: Integration tests for Wave 5 HTTP implementation
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

# Import event models
from events.models.autonomous_learning_events import (
    AutonomousLearningEventHelpers,
    EnumAutonomousEventType,
)
from events.models.pattern_analytics_events import (
    EnumPatternAnalyticsEventType,
    PatternAnalyticsEventHelpers,
)

# Import handlers
from handlers.autonomous_learning_handler import AutonomousLearningHandler
from handlers.pattern_analytics_handler import PatternAnalyticsHandler

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_http_response():
    """Create mock HTTP response."""

    def _create_response(status_code=200, json_data=None):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json = MagicMock(return_value=json_data or {})
        response.text = json.dumps(json_data or {})
        response.raise_for_status = MagicMock()
        return response

    return _create_response


@pytest.fixture
def correlation_id():
    """Generate unique correlation ID."""
    return str(uuid4())


# ============================================================================
# Autonomous Learning Tests (6 operations)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.wave5
@pytest.mark.autonomous_learning
class TestAutonomousLearningIntegration:
    """Integration tests for autonomous learning handler HTTP implementations."""

    @pytest.fixture
    async def handler(self):
        """Create autonomous learning handler with mocked router."""
        handler = AutonomousLearningHandler()
        handler._router = AsyncMock()
        handler._router.publish = AsyncMock()
        yield handler

    async def test_patterns_success_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test patterns_success makes correct HTTP POST call."""
        payload = {"min_success_rate": 0.8, "limit": 10}

        mock_result = {
            "patterns": [
                {"pattern_id": "p1", "success_rate": 0.92, "executions": 120},
                {"pattern_id": "p2", "success_rate": 0.85, "executions": 95},
            ],
            "count": 2,
            "filters_applied": {"min_success_rate": 0.8},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            event = {"correlation_id": correlation_id, "payload": payload}
            success = await handler._handle_pattern_success(
                correlation_id, payload, 0.0
            )

            # Verify HTTP call
            assert success is True
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "/api/autonomous/patterns/success" in call_args[0][0]
            assert call_args[1]["json"]["min_success_rate"] == 0.8

            # Verify event published
            handler._router.publish.assert_called_once()

    async def test_predict_agent_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test predict_agent makes correct HTTP POST call."""
        payload = {"context": {"domain": "api"}, "requirements": {"language": "python"}}

        mock_result = {
            "recommended_agent": "agent-api-architect",
            "confidence_score": 0.89,
            "confidence_level": "high",
            "reasoning": "Based on 120 similar tasks",
            "alternative_agents": [{"agent": "agent-api-engineer", "confidence": 0.76}],
            "expected_success_rate": 0.92,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_agent_predict(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "/api/autonomous/predict/agent" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_predict_time_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test predict_time makes correct HTTP POST call."""
        payload = {
            "task_description": "Implement API endpoint",
            "agent": "agent-api-architect",
            "complexity": "moderate",
        }

        mock_result = {
            "estimated_duration_ms": 285000,
            "p25_duration_ms": 210000,
            "p75_duration_ms": 350000,
            "p95_duration_ms": 480000,
            "confidence_score": 0.85,
            "time_breakdown": {
                "research": 60000,
                "planning": 45000,
                "implementation": 150000,
                "testing": 30000,
            },
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_time_predict(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "/api/autonomous/predict/time" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_safety_score_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test safety_score makes correct HTTP GET call."""
        payload = {"task_type": "code_generation", "context": {"risk_level": "low"}}

        mock_result = {
            "safety_score": 0.78,
            "safety_rating": "moderate",
            "can_execute_autonomously": True,
            "requires_human_review": False,
            "risk_factors": [{"factor": "complexity", "score": 0.72}],
            "safety_checks_required": ["code_review", "test_coverage"],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_safety_score(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/autonomous/calculate/safety" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_stats_http_call(self, handler, correlation_id, mock_http_response):
        """Test stats makes correct HTTP GET call."""
        payload = {}

        mock_result = {
            "total_patterns": 156,
            "total_agents": 12,
            "average_success_rate": 0.87,
            "total_executions": 2450,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_stats(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/autonomous/stats" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_health_http_call(self, handler, correlation_id, mock_http_response):
        """Test health makes correct HTTP GET call."""
        payload = {}

        mock_result = {
            "status": "healthy",
            "service": "autonomous-learning",
            "version": "1.0.0",
            "uptime_seconds": 86400,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_health(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/autonomous/health" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_http_error_handling(self, handler, correlation_id):
        """Test HTTP error handling publishes failed event."""
        payload = {"min_success_rate": 0.8, "limit": 10}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            # Simulate HTTP 500 error
            error_response = MagicMock()
            error_response.status_code = 500
            error_response.text = "Internal Server Error"
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "HTTP 500", request=MagicMock(), response=error_response
                )
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_pattern_success(
                correlation_id, payload, 0.0
            )

            # Should return False and publish failed event
            assert success is False
            handler._router.publish.assert_called_once()


# ============================================================================
# Pattern Analytics Tests (4 operations)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.wave5
@pytest.mark.pattern_analytics
class TestPatternAnalyticsIntegration:
    """Integration tests for pattern analytics handler HTTP implementations."""

    @pytest.fixture
    async def handler(self):
        """Create pattern analytics handler with mocked router."""
        handler = PatternAnalyticsHandler()
        handler._router = AsyncMock()
        handler._router.publish = AsyncMock()
        yield handler

    async def test_success_rates_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test success_rates makes correct HTTP GET call."""
        payload = {"min_success_rate": 0.75}

        mock_result = {
            "patterns": [{"pattern_id": "p1", "success_rate": 0.92}],
            "summary": {"avg_rate": 0.88},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_success_rates(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/pattern-analytics/success-rates" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_top_patterns_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test top_patterns makes correct HTTP GET call."""
        payload = {"limit": 10, "min_score": 0.8}

        mock_result = {
            "top_patterns": [{"pattern_id": "p1", "score": 0.95}],
            "total_patterns": 156,
            "filter_criteria": {},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_top_patterns(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/pattern-analytics/top-patterns" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_emerging_http_call(
        self, handler, correlation_id, mock_http_response
    ):
        """Test emerging makes correct HTTP GET call."""
        payload = {"time_window_hours": 24, "min_occurrences": 3}

        mock_result = {
            "emerging_patterns": [{"pattern_id": "new1"}],
            "total_emerging": 5,
            "time_window_hours": 24,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_emerging(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert "/api/pattern-analytics/emerging-patterns" in call_args[0][0]
            handler._router.publish.assert_called_once()

    async def test_history_http_call(self, handler, correlation_id, mock_http_response):
        """Test history makes correct HTTP GET call."""
        payload = {"pattern_id": "pattern-123"}

        mock_result = {
            "pattern_id": "pattern-123",
            "pattern_name": "test_pattern",
            "feedback_history": [],
            "summary": {},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                return_value=mock_http_response(200, mock_result)
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_history(correlation_id, payload, 0.0)

            assert success is True
            mock_client_instance.get.assert_called_once()
            call_args = mock_client_instance.get.call_args
            assert (
                "/api/pattern-analytics/pattern/pattern-123/history" in call_args[0][0]
            )
            handler._router.publish.assert_called_once()

    async def test_http_error_handling(self, handler, correlation_id):
        """Test HTTP error handling publishes failed event."""
        payload = {"min_success_rate": 0.75}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            # Simulate HTTP 404 error
            error_response = MagicMock()
            error_response.status_code = 404
            error_response.text = "Not Found"
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "HTTP 404", request=MagicMock(), response=error_response
                )
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            success = await handler._handle_success_rates(correlation_id, payload, 0.0)

            # Should return False and publish failed event
            assert success is False
            handler._router.publish.assert_called_once()


# ============================================================================
# Cross-Handler Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.wave5
class TestWave5CrossHandler:
    """Cross-handler integration tests for Wave 5."""

    async def test_correlation_id_preserved(self, correlation_id):
        """Test correlation ID preserved through HTTP call chain."""
        handler = AutonomousLearningHandler()
        handler._router = AsyncMock()
        handler._router.publish = AsyncMock()

        payload = {}
        mock_result = {
            "status": "healthy",
            "service": "autonomous",
            "version": "1.0.0",
            "uptime_seconds": 100,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            response = MagicMock()
            response.status_code = 200
            response.json = MagicMock(return_value=mock_result)
            response.raise_for_status = MagicMock()
            mock_client_instance.get = AsyncMock(return_value=response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await handler._handle_health(correlation_id, payload, 0.0)

            # Verify correlation ID in published event
            publish_call = handler._router.publish.call_args
            assert publish_call is not None
            # Access keyword arguments (publish is called with topic=, event=, key=)
            event_envelope = publish_call[1]["event"]  # event kwarg is the envelope
            # Correlation ID should be in the key
            assert str(correlation_id) in publish_call[1]["key"]

    async def test_timeout_configuration(self):
        """Test timeout is correctly configured for HTTP clients."""
        handler = AutonomousLearningHandler()
        assert handler.timeout == 10.0

        analytics_handler = PatternAnalyticsHandler()
        assert analytics_handler.timeout == 10.0

    async def test_base_url_configuration(self):
        """Test base URL is correctly configured from environment."""
        import os

        # Default value
        handler = AutonomousLearningHandler()
        assert handler.base_url == "http://localhost:8053"

        # With environment override
        with patch.dict(os.environ, {"INTELLIGENCE_SERVICE_URL": "http://custom:9000"}):
            handler2 = AutonomousLearningHandler()
            assert handler2.base_url == "http://custom:9000"
