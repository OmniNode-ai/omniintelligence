"""
Integration Tests - Pattern Learning HTTP Operations

Tests all 7 Pattern Learning operations end-to-end with HTTP calls:
1. Pattern Match
2. Hybrid Score
3. Semantic Analyze
4. Metrics
5. Cache Stats
6. Cache Clear
7. Health

Wave: 3
Module: Pattern Learning
HTTP Endpoints: POST/GET /api/pattern-learning/*
"""

from uuid import uuid4

import httpx
import pytest
import respx
from events.models.pattern_learning_events import (
    ModelCacheClearRequestPayload,
    ModelCacheStatsRequestPayload,
    ModelHealthRequestPayload,
    ModelHybridScoreRequestPayload,
    ModelMetricsRequestPayload,
    ModelPatternMatchRequestPayload,
    ModelSemanticAnalyzeRequestPayload,
)
from handlers.pattern_learning_handler import PatternLearningHandler


class TestPatternMatchIntegration:
    """Tests for Pattern Match operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_pattern_match_successful(self, handler):
        """Test successful pattern matching."""
        correlation_id = str(uuid4())
        mock_response = {
            "matches": [{"pattern_id": "p1", "similarity": 0.95}],
            "match_count": 1,
            "highest_similarity": 0.95,
            "cache_hit": False,
        }

        respx.post("http://localhost:8053/api/pattern-learning/pattern/match").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelPatternMatchRequestPayload(
            query_pattern="def test():", context={}
        )

        import time

        result = await handler._handle_pattern_match(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestHybridScoreIntegration:
    """Tests for Hybrid Score operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_hybrid_score_successful(self, handler):
        """Test successful hybrid scoring."""
        correlation_id = str(uuid4())
        mock_response = {
            "hybrid_score": 0.85,
            "semantic_score": 0.9,
            "keyword_score": 0.8,
            "structural_score": 0.85,
        }

        respx.post("http://localhost:8053/api/pattern-learning/hybrid/score").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelHybridScoreRequestPayload(
            pattern_id="pattern_123", query="def example():"
        )

        import time

        result = await handler._handle_hybrid_score(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestSemanticAnalyzeIntegration:
    """Tests for Semantic Analyze operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_semantic_analyze_successful(self, handler):
        """Test successful semantic analysis."""
        correlation_id = str(uuid4())
        mock_response = {
            "semantic_features": {"complexity": "low", "type": "function"},
            "embeddings": [0.1, 0.2, 0.3],
            "confidence": 0.92,
        }

        respx.post("http://localhost:8053/api/pattern-learning/semantic/analyze").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelSemanticAnalyzeRequestPayload(text="def hello():")

        import time

        result = await handler._handle_semantic_analyze(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestMetricsIntegration:
    """Tests for Metrics operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_metrics_successful(self, handler):
        """Test successful metrics retrieval."""
        correlation_id = str(uuid4())
        mock_response = {
            "total_patterns": 1000,
            "total_matches": 250,
            "average_similarity": 0.78,
            "cache_hit_rate": 0.65,
            "breakdown": {"by_language": {"python": 500, "javascript": 300}},
        }

        respx.get("http://localhost:8053/api/pattern-learning/metrics").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelMetricsRequestPayload()

        import time

        result = await handler._handle_metrics(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestCacheStatsIntegration:
    """Tests for Cache Stats operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_cache_stats_successful(self, handler):
        """Test successful cache stats retrieval."""
        correlation_id = str(uuid4())
        mock_response = {
            "total_entries": 500,
            "cache_size_bytes": 1024000,
            "hit_rate": 0.72,
            "miss_rate": 0.28,
            "eviction_count": 15,
            "entries": None,
        }

        respx.get("http://localhost:8053/api/pattern-learning/cache/stats").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelCacheStatsRequestPayload()

        import time

        result = await handler._handle_cache_stats(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestCacheClearIntegration:
    """Tests for Cache Clear operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_cache_clear_successful(self, handler):
        """Test successful cache clearing."""
        correlation_id = str(uuid4())
        mock_response = {"cleared_count": 150}

        respx.post("http://localhost:8053/api/pattern-learning/cache/clear").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelCacheClearRequestPayload(pattern="*")

        import time

        result = await handler._handle_cache_clear(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1


class TestHealthIntegration:
    """Tests for Health operation."""

    @pytest.fixture
    def handler(self):
        return PatternLearningHandler()

    @respx.mock
    @pytest.mark.asyncio
    async def test_health_successful(self, handler):
        """Test successful health check."""
        correlation_id = str(uuid4())
        mock_response = {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "cache": "ok",
                "patterns": "ok",
            },
            "uptime_seconds": 3600.5,
        }

        respx.get("http://localhost:8053/api/pattern-learning/health").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelHealthRequestPayload()

        import time

        result = await handler._handle_health(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        assert result is True
        assert handler.metrics["events_handled"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_health_service_degraded(self, handler):
        """Test health check when service is degraded."""
        correlation_id = str(uuid4())
        mock_response = {
            "status": "degraded",
            "checks": {
                "database": "ok",
                "cache": "error",
                "patterns": "ok",
            },
            "uptime_seconds": 7200.0,
        }

        respx.get("http://localhost:8053/api/pattern-learning/health").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelHealthRequestPayload()

        import time

        result = await handler._handle_health(
            correlation_id, payload.model_dump(), time.perf_counter()
        )

        # Should still succeed - health endpoint returned 200
        assert result is True
