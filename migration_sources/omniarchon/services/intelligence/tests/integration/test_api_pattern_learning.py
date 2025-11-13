#!/usr/bin/env python3
"""
Integration Tests for Pattern Learning API

Tests complete request/response cycles for all Pattern Learning API endpoints:
1. POST /api/pattern-learning/pattern/match - Pattern matching
2. POST /api/pattern-learning/hybrid/score - Hybrid scoring
3. POST /api/pattern-learning/semantic/analyze - Semantic analysis
4. GET  /api/pattern-learning/metrics - Service metrics
5. GET  /api/pattern-learning/cache/stats - Cache statistics
6. DELETE /api/pattern-learning/cache/clear - Clear cache
7. GET  /api/pattern-learning/health - Health check

These tests verify:
- Success cases (200 responses)
- Validation errors (422 responses)
- Error handling (500 responses)
- Response schema validation
- Performance targets (<200ms per request)

Author: Archon Intelligence Team
Date: 2025-10-16
"""

import time
from typing import Any, Dict

import pytest
from api.pattern_learning.routes import router as pattern_learning_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ============================================================================
# Response Parsing Helper
# ============================================================================


def parse_response(response):
    """
    Parse API response handling both old (flat) and new (nested) formats.

    New format:
        {"status": "success", "data": {...}, "metadata": {...}}

    Old format:
        {"pattern1": "...", "pattern2": "...", ...}

    Returns: (data_dict, metadata_dict, is_success)
    """
    result = response.json()

    # Check if new format (has "status" and "data" keys)
    if "status" in result and "data" in result:
        is_success = result["status"] == "success"
        data = result.get("data", {})
        metadata = result.get("metadata", {})
    else:
        # Old format - return as-is
        is_success = result.get("success", True)
        data = result
        metadata = {}

    return data, metadata, is_success


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app instance with pattern learning router."""
    app = FastAPI(title="Pattern Learning Test API")
    app.include_router(pattern_learning_router)
    return app


@pytest.fixture
def test_client(app: FastAPI) -> TestClient:
    """Create test client for API testing."""
    return TestClient(app)


@pytest.fixture
def sample_pattern_match_request() -> Dict[str, Any]:
    """Sample pattern match request payload."""
    return {
        "pattern1": "NodeValidationEffect",
        "pattern2": "NodeProcessingEffect",
        "use_semantic": True,
        "use_structural": True,
    }


@pytest.fixture
def sample_hybrid_score_request() -> Dict[str, Any]:
    """Sample hybrid score request payload."""
    return {
        "content1": "class NodeUserEffect(NodeBase): pass",
        "content2": "class NodeDataEffect(NodeBase): pass",
        "semantic_weight": 0.6,
        "structural_weight": 0.4,
    }


@pytest.fixture
def sample_semantic_analysis_request() -> Dict[str, Any]:
    """Sample semantic analysis request payload."""
    return {
        "content": "This is ONEX-compliant code with proper error handling and type hints.",
        "language": "en",
        "extract_concepts": True,
        "extract_themes": True,
        "min_confidence": 0.5,
    }


# ============================================================================
# Pattern Match API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestPatternMatchAPI:
    """Integration tests for pattern matching endpoint."""

    def test_pattern_match_success(
        self, test_client: TestClient, sample_pattern_match_request: Dict[str, Any]
    ):
        """Test successful pattern matching with valid request."""
        start_time = time.time()
        response = test_client.post(
            "/api/pattern-learning/pattern/match", json=sample_pattern_match_request
        )
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify success
        assert is_success

        # Verify response structure
        assert "pattern1" in data
        assert "pattern2" in data
        assert "similarity_score" in data
        assert "confidence" in data
        assert "method" in data
        # processing_time_ms may be in data or metadata
        assert "processing_time_ms" in data or "processing_time_ms" in metadata

        # Verify data types
        assert isinstance(data["similarity_score"], (int, float))
        assert isinstance(data["confidence"], (int, float))
        assert 0.0 <= data["similarity_score"] <= 1.0
        assert 0.0 <= data["confidence"] <= 1.0

        # Verify method selection
        assert data["method"] in ["structural", "hybrid", "semantic"]

        # Performance assertion (<300ms)
        assert (
            elapsed < 300
        ), f"Pattern match took {elapsed:.2f}ms, exceeds 300ms target"

        print(f"\n✓ Pattern Match: {elapsed:.2f}ms")

    def test_pattern_match_structural_only(self, test_client: TestClient):
        """Test pattern matching with structural similarity only."""
        request = {
            "pattern1": "NodeValidationEffect",
            "pattern2": "NodeProcessingEffect",
            "use_semantic": False,
            "use_structural": True,
        }

        response = test_client.post("/api/pattern-learning/pattern/match", json=request)

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["method"] == "structural"

    def test_pattern_match_semantic_only(self, test_client: TestClient):
        """Test pattern matching with semantic similarity only."""
        request = {
            "pattern1": "NodeValidationEffect",
            "pattern2": "NodeProcessingEffect",
            "use_semantic": True,
            "use_structural": False,
        }

        response = test_client.post("/api/pattern-learning/pattern/match", json=request)

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        # Method should indicate semantic or hybrid
        assert data["method"] in ["semantic", "hybrid"]

    def test_pattern_match_validation_error_missing_pattern(
        self, test_client: TestClient
    ):
        """Test pattern matching with missing required field."""
        request = {
            "pattern1": "NodeValidationEffect",
            # Missing pattern2
            "use_semantic": True,
        }

        response = test_client.post("/api/pattern-learning/pattern/match", json=request)

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

    def test_pattern_match_empty_patterns(self, test_client: TestClient):
        """Test pattern matching with empty pattern strings."""
        request = {
            "pattern1": "",
            "pattern2": "",
            "use_semantic": True,
            "use_structural": True,
        }

        response = test_client.post("/api/pattern-learning/pattern/match", json=request)

        # Should process but return low confidence
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["similarity_score"] == 0.0


# ============================================================================
# Hybrid Score API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestHybridScoreAPI:
    """Integration tests for hybrid scoring endpoint."""

    def test_hybrid_score_success(
        self, test_client: TestClient, sample_hybrid_score_request: Dict[str, Any]
    ):
        """Test successful hybrid scoring with valid request."""
        start_time = time.time()
        response = test_client.post(
            "/api/pattern-learning/hybrid/score", json=sample_hybrid_score_request
        )
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        assert "content1_preview" in data
        assert "content2_preview" in data
        assert "hybrid_score" in data
        assert "semantic_component" in data
        assert "structural_component" in data
        assert "confidence" in data
        assert "processing_time_ms" in data

        # Verify component structure
        semantic = data["semantic_component"]
        assert "score" in semantic
        assert "weight" in semantic
        assert semantic["weight"] == 0.6

        structural = data["structural_component"]
        assert "score" in structural
        assert "weight" in structural
        assert structural["weight"] == 0.4

        # Verify score ranges
        assert 0.0 <= data["hybrid_score"] <= 1.0
        assert 0.0 <= semantic["score"] <= 1.0
        assert 0.0 <= structural["score"] <= 1.0

        # Performance assertion (<150ms)
        assert elapsed < 150, f"Hybrid score took {elapsed:.2f}ms, exceeds 150ms target"

        print(f"\n✓ Hybrid Score: {elapsed:.2f}ms")

    def test_hybrid_score_equal_weights(self, test_client: TestClient):
        """Test hybrid scoring with equal weights."""
        request = {
            "content1": "class NodeUserEffect(NodeBase): pass",
            "content2": "class NodeDataEffect(NodeBase): pass",
            "semantic_weight": 0.5,
            "structural_weight": 0.5,
        }

        response = test_client.post("/api/pattern-learning/hybrid/score", json=request)

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["semantic_component"]["weight"] == 0.5
        assert data["structural_component"]["weight"] == 0.5

    def test_hybrid_score_semantic_only_weight(self, test_client: TestClient):
        """Test hybrid scoring with semantic-only weight."""
        request = {
            "content1": "class NodeUserEffect(NodeBase): pass",
            "content2": "class NodeDataEffect(NodeBase): pass",
            "semantic_weight": 1.0,
            "structural_weight": 0.0,
        }

        response = test_client.post("/api/pattern-learning/hybrid/score", json=request)

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["semantic_component"]["weight"] == 1.0
        assert data["structural_component"]["weight"] == 0.0

    def test_hybrid_score_validation_error_invalid_weight(
        self, test_client: TestClient
    ):
        """Test hybrid scoring with invalid weight (out of range)."""
        request = {
            "content1": "test content",
            "content2": "test content 2",
            "semantic_weight": 1.5,  # Invalid: >1.0
            "structural_weight": 0.5,
        }

        response = test_client.post("/api/pattern-learning/hybrid/score", json=request)

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

    def test_hybrid_score_validation_error_negative_weight(
        self, test_client: TestClient
    ):
        """Test hybrid scoring with negative weight."""
        request = {
            "content1": "test content",
            "content2": "test content 2",
            "semantic_weight": -0.5,  # Invalid: <0.0
            "structural_weight": 1.5,
        }

        response = test_client.post("/api/pattern-learning/hybrid/score", json=request)

        assert response.status_code == 422  # Validation error


# ============================================================================
# Semantic Analysis API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestSemanticAnalysisAPI:
    """Integration tests for semantic analysis endpoint."""

    def test_semantic_analysis_success(
        self, test_client: TestClient, sample_semantic_analysis_request: Dict[str, Any]
    ):
        """Test successful semantic analysis with valid request."""
        start_time = time.time()
        response = test_client.post(
            "/api/pattern-learning/semantic/analyze",
            json=sample_semantic_analysis_request,
        )
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        assert "content_preview" in data
        assert "language" in data
        assert "concepts" in data
        assert "themes" in data
        assert "domains" in data
        assert "confidence" in data
        assert "from_cache" in data
        # processing_time_ms may be in data or metadata
        assert "processing_time_ms" in data or "processing_time_ms" in metadata

        # Verify data types
        assert isinstance(data["concepts"], list)
        assert isinstance(data["themes"], list)
        assert isinstance(data["domains"], list)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["from_cache"], bool)

        # Verify confidence range
        assert 0.0 <= data["confidence"] <= 1.0

        # Performance assertion (<500ms)
        assert (
            elapsed < 500
        ), f"Semantic analysis took {elapsed:.2f}ms, exceeds 500ms target"

        print(f"\n✓ Semantic Analysis: {elapsed:.2f}ms")

    def test_semantic_analysis_minimal_request(self, test_client: TestClient):
        """Test semantic analysis with minimal required fields."""
        request = {"content": "Sample code for analysis"}

        response = test_client.post(
            "/api/pattern-learning/semantic/analyze", json=request
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["language"] == "en"  # Default language
        assert data["content_preview"] == "Sample code for analysis"

    def test_semantic_analysis_custom_language(self, test_client: TestClient):
        """Test semantic analysis with custom language."""
        request = {"content": "Contenu d'analyse sémantique", "language": "fr"}

        response = test_client.post(
            "/api/pattern-learning/semantic/analyze", json=request
        )

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)
        assert data["language"] == "fr"

    def test_semantic_analysis_custom_confidence_threshold(
        self, test_client: TestClient
    ):
        """Test semantic analysis with custom confidence threshold."""
        request = {"content": "Test content", "min_confidence": 0.8}

        response = test_client.post(
            "/api/pattern-learning/semantic/analyze", json=request
        )

        assert response.status_code == 200

    def test_semantic_analysis_validation_error_missing_content(
        self, test_client: TestClient
    ):
        """Test semantic analysis with missing content field."""
        request = {"language": "en"}  # Missing content

        response = test_client.post(
            "/api/pattern-learning/semantic/analyze", json=request
        )

        assert response.status_code == 422  # Validation error

    def test_semantic_analysis_validation_error_invalid_confidence(
        self, test_client: TestClient
    ):
        """Test semantic analysis with invalid confidence threshold."""
        request = {"content": "Test content", "min_confidence": 1.5}  # Invalid: >1.0

        response = test_client.post(
            "/api/pattern-learning/semantic/analyze", json=request
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# Cache Stats API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestCacheStatsAPI:
    """Integration tests for cache statistics endpoint."""

    def test_cache_stats_success(self, test_client: TestClient):
        """Test successful retrieval of cache statistics."""
        start_time = time.time()
        response = test_client.get("/api/pattern-learning/cache/stats")
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        assert "total_entries" in data
        assert "hit_rate" in data
        assert "miss_rate" in data
        assert "evictions" in data
        assert "avg_lookup_time_ms" in data
        assert "memory_usage_bytes" in data

        # Verify data types
        assert isinstance(data["total_entries"], int)
        assert isinstance(data["hit_rate"], (int, float))
        assert isinstance(data["miss_rate"], (int, float))
        assert isinstance(data["evictions"], int)
        assert isinstance(data["avg_lookup_time_ms"], (int, float))
        assert isinstance(data["memory_usage_bytes"], int)

        # Verify value ranges
        assert data["total_entries"] >= 0
        assert 0.0 <= data["hit_rate"] <= 1.0
        assert 0.0 <= data["miss_rate"] <= 1.0
        assert data["evictions"] >= 0
        assert data["avg_lookup_time_ms"] >= 0.0
        assert data["memory_usage_bytes"] >= 0

        # Performance assertion (<50ms)
        assert elapsed < 50, f"Cache stats took {elapsed:.2f}ms, exceeds 50ms target"

        print(f"\n✓ Cache Stats: {elapsed:.2f}ms")

    def test_cache_stats_no_parameters_required(self, test_client: TestClient):
        """Test that cache stats endpoint requires no parameters."""
        response = test_client.get("/api/pattern-learning/cache/stats")
        assert response.status_code == 200


# ============================================================================
# Cache Clear API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestCacheClearAPI:
    """Integration tests for cache clear endpoint."""

    def test_cache_clear_success(self, test_client: TestClient):
        """Test successful cache clear operation."""
        start_time = time.time()
        response = test_client.delete("/api/pattern-learning/cache/clear")
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        # API may return just message or status+message
        assert "message" in data
        assert data["message"] == "Cache cleared"

        # Verify success via parse_response
        assert is_success

        # timestamp may be in data or metadata (optional)
        # Note: timestamp is optional and may not be present

        # Performance assertion (<50ms)
        assert elapsed < 50, f"Cache clear took {elapsed:.2f}ms, exceeds 50ms target"

        print(f"\n✓ Cache Clear: {elapsed:.2f}ms")

    def test_cache_clear_idempotent(self, test_client: TestClient):
        """Test that cache clear is idempotent (can be called multiple times)."""
        # Clear cache twice
        response1 = test_client.delete("/api/pattern-learning/cache/clear")
        response2 = test_client.delete("/api/pattern-learning/cache/clear")

        # Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200


# ============================================================================
# Metrics API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestMetricsAPI:
    """Integration tests for pattern learning metrics endpoint."""

    def test_metrics_success(self, test_client: TestClient):
        """Test successful retrieval of pattern learning metrics."""
        start_time = time.time()
        response = test_client.get("/api/pattern-learning/metrics")
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        # API may return metrics directly or nested
        # The actual response has cache, langextract, hybrid_scoring at top level
        # So data itself contains the metrics
        assert isinstance(data, dict)
        assert len(data) > 0  # Has some metrics

        # Verify success via parse_response
        assert is_success

        # timestamp may be in data or metadata (optional)

        # Performance assertion (<100ms)
        assert elapsed < 100, f"Metrics took {elapsed:.2f}ms, exceeds 100ms target"

        print(f"\n✓ Metrics: {elapsed:.2f}ms")

    def test_metrics_no_parameters_required(self, test_client: TestClient):
        """Test that metrics endpoint requires no parameters."""
        response = test_client.get("/api/pattern-learning/metrics")
        assert response.status_code == 200


# ============================================================================
# Health Check API Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
class TestHealthCheckAPI:
    """Integration tests for health check endpoint."""

    def test_health_check_success(self, test_client: TestClient):
        """Test successful health check."""
        start_time = time.time()
        response = test_client.get("/api/pattern-learning/health")
        elapsed = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # Verify response structure
        assert "status" in data
        # API returns "checks" not "components"
        checks_key = "checks" if "checks" in data else "components"
        assert checks_key in data
        assert "timestamp" in data or "timestamp" in metadata
        # response_time_ms may be in data or nested in checks
        response_time_key = (
            "response_time_ms"
            if "response_time_ms" in data
            else (
                "response_time_ms"
                if checks_key in data and "response_time_ms" in data.get(checks_key, {})
                else None
            )
        )

        # Verify status values
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Verify checks/components is a dict
        assert isinstance(data[checks_key], dict)

        # Verify expected components
        expected_components = [
            "hybrid_scorer",
            "pattern_similarity",
            "semantic_cache",
            "langextract_client",
        ]
        for component in expected_components:
            assert component in data[checks_key]
            assert isinstance(data[checks_key][component], str)

        # Performance assertion (<200ms)
        assert elapsed < 200, f"Health check took {elapsed:.2f}ms, exceeds 200ms target"

        print(f"\n✓ Health Check: {elapsed:.2f}ms")
        print(f"  Status: {data['status']}")
        print(f"  Components: {len(data[checks_key])}")

    def test_health_check_component_status(self, test_client: TestClient):
        """Test that health check includes component statuses."""
        response = test_client.get("/api/pattern-learning/health")

        assert response.status_code == 200
        data, metadata, is_success = parse_response(response)

        # API returns "checks" not "components"
        checks_key = "checks" if "checks" in data else "components"

        # Verify each component has a status
        for component, status in data[checks_key].items():
            # Skip response_time_ms which is numeric
            if component == "response_time_ms":
                continue
            assert (
                status
                in [
                    "operational",
                    "error: ",  # Prefix for error messages
                ]
                or status.startswith("error: ")
                or status.startswith("operational")
            )

    def test_health_check_no_parameters_required(self, test_client: TestClient):
        """Test that health check requires no parameters."""
        response = test_client.get("/api/pattern-learning/health")
        assert response.status_code == 200


# ============================================================================
# Performance Benchmark Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.pattern_learning
@pytest.mark.performance
class TestPatternLearningAPIPerformance:
    """Performance benchmark tests for Pattern Learning API."""

    def test_concurrent_pattern_matching(self, test_client: TestClient):
        """Test concurrent pattern matching requests."""
        import concurrent.futures

        def make_request():
            request = {
                "pattern1": "NodeValidationEffect",
                "pattern2": "NodeProcessingEffect",
                "use_semantic": True,
                "use_structural": True,
            }
            return test_client.post("/api/pattern-learning/pattern/match", json=request)

        # Execute 10 concurrent requests
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [f.result() for f in futures]
        elapsed = (time.time() - start_time) * 1000

        # Verify all succeeded
        assert all(r.status_code == 200 for r in responses)

        # Performance: Should complete in <2s
        assert elapsed < 2000, f"Concurrent requests took {elapsed:.2f}ms, exceeds 2s"

        print(f"\n✓ Concurrent Pattern Matching (10 requests): {elapsed:.2f}ms")

    def test_api_endpoint_latency_summary(self, test_client: TestClient):
        """Benchmark latency for all Pattern Learning API endpoints."""
        endpoints = [
            (
                "POST",
                "/api/pattern-learning/pattern/match",
                {"pattern1": "A", "pattern2": "B"},
            ),
            (
                "POST",
                "/api/pattern-learning/hybrid/score",
                {"content1": "A", "content2": "B"},
            ),
            ("POST", "/api/pattern-learning/semantic/analyze", {"content": "Test"}),
            ("GET", "/api/pattern-learning/cache/stats", None),
            ("GET", "/api/pattern-learning/metrics", None),
            ("GET", "/api/pattern-learning/health", None),
        ]

        results = []
        for method, path, payload in endpoints:
            start = time.time()
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json=payload)
            elapsed = (time.time() - start) * 1000

            results.append((path, elapsed, response.status_code))
            assert response.status_code == 200

        # Print summary
        print("\n" + "=" * 70)
        print("Pattern Learning API Latency Summary")
        print("=" * 70)
        for path, elapsed, status in results:
            print(f"{path:<50} {elapsed:>6.2f}ms (HTTP {status})")
        print("=" * 70)

        # All endpoints should be <500ms
        for path, elapsed, _ in results:
            assert elapsed < 500, f"{path} took {elapsed:.2f}ms, exceeds 500ms"


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short", "-m", "integration"])
