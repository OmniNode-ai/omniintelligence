"""
Test Suite for Hybrid Pattern Scoring Monitoring

Validates that all Prometheus metrics are correctly exposed and that
helper functions work as expected.
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest
from archon_services.pattern_learning.phase2_matching.monitoring_hybrid_patterns import (  # Metrics
    cache_hit_rate,
    cache_hit_total,
    cache_miss_total,
    get_metrics_summary,
    hybrid_scoring_duration,
    initialize_system_info,
    instrument_async_function,
    instrument_sync_function,
    langextract_errors_total,
    langextract_requests_total,
    record_cache_hit,
    record_cache_miss,
    record_circuit_breaker_state,
    record_pattern_similarity,
    record_retry_attempt,
    track_cache_lookup,
    track_hybrid_scoring,
    track_langextract_request,
)
from prometheus_client import REGISTRY

# Add src directory to path


class TestMetricsRegistration:
    """Test that all metrics are properly registered with Prometheus."""

    def test_langextract_metrics_registered(self):
        """Verify langextract metrics are registered."""
        metric_names = [m.name for m in REGISTRY.collect()]

        # Note: Prometheus stores Counters without _total suffix internally
        assert "langextract_requests" in metric_names
        assert "langextract_request_duration_seconds" in metric_names
        assert "langextract_errors" in metric_names
        assert "langextract_circuit_breaker_state" in metric_names

    def test_cache_metrics_registered(self):
        """Verify cache metrics are registered."""
        metric_names = [m.name for m in REGISTRY.collect()]

        # Note: Prometheus stores Counters without _total suffix internally
        assert "semantic_cache_hits" in metric_names
        assert "semantic_cache_misses" in metric_names
        assert "semantic_cache_hit_rate" in metric_names
        assert "semantic_cache_size_entries" in metric_names

    def test_hybrid_scoring_metrics_registered(self):
        """Verify hybrid scoring metrics are registered."""
        metric_names = [m.name for m in REGISTRY.collect()]

        assert "hybrid_scoring_duration_seconds" in metric_names
        # Note: Prometheus stores Counters without _total suffix internally
        assert "hybrid_scoring_requests" in metric_names
        assert "pattern_similarity_score" in metric_names


class TestContextManagers:
    """Test context manager helper functions."""

    def test_track_langextract_request_success(self):
        """Test langextract request tracking on success."""
        initial_count = langextract_requests_total.labels(
            endpoint="/extract", status="success"
        )._value.get()

        with track_langextract_request("/extract"):
            time.sleep(0.1)  # Simulate work

        final_count = langextract_requests_total.labels(
            endpoint="/extract", status="success"
        )._value.get()

        assert final_count == initial_count + 1

    def test_track_langextract_request_error(self):
        """Test langextract request tracking on error."""
        initial_count = langextract_requests_total.labels(
            endpoint="/extract", status="error"
        )._value.get()

        initial_error_count = langextract_errors_total.labels(
            endpoint="/extract", error_type="ValueError"
        )._value.get()

        try:
            with track_langextract_request("/extract"):
                raise ValueError("Test error")
        except ValueError:
            pass

        final_count = langextract_requests_total.labels(
            endpoint="/extract", status="error"
        )._value.get()

        final_error_count = langextract_errors_total.labels(
            endpoint="/extract", error_type="ValueError"
        )._value.get()

        assert final_count == initial_count + 1
        assert final_error_count == initial_error_count + 1

    def test_track_hybrid_scoring_success(self):
        """Test hybrid scoring tracking."""
        # Track if the context manager completes successfully
        # We can't easily access histogram internals in prometheus_client,
        # so we verify the tracking completes without errors
        try:
            with track_hybrid_scoring(strategy="test_strategy"):
                time.sleep(0.05)  # Simulate scoring
            test_passed = True
        except Exception:
            test_passed = False

        assert test_passed, "Hybrid scoring tracking should complete successfully"

    def test_track_cache_lookup(self):
        """Test cache lookup tracking."""
        with track_cache_lookup():
            time.sleep(0.01)  # Simulate lookup

        # Just verify no errors occur
        assert True


class TestRecordFunctions:
    """Test record helper functions."""

    def test_record_cache_hit(self):
        """Test cache hit recording."""
        initial_hits = cache_hit_total._value.get()

        record_cache_hit()

        final_hits = cache_hit_total._value.get()
        assert final_hits == initial_hits + 1

    def test_record_cache_miss(self):
        """Test cache miss recording."""
        initial_misses = cache_miss_total._value.get()

        record_cache_miss()

        final_misses = cache_miss_total._value.get()
        assert final_misses == initial_misses + 1

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate auto-calculation."""
        # Record some hits and misses
        for _ in range(3):
            record_cache_hit()
        for _ in range(1):
            record_cache_miss()

        hit_rate = cache_hit_rate._value.get()

        # Hit rate should be calculated (but exact value depends on previous state)
        assert 0.0 <= hit_rate <= 1.0

    def test_record_pattern_similarity(self):
        """Test pattern similarity recording."""
        test_scores = [0.1, 0.5, 0.9]

        for score in test_scores:
            record_pattern_similarity("semantic", score)
            record_pattern_similarity("structural", score)
            record_pattern_similarity("hybrid", score)

        # Just verify no errors occur
        assert True

    def test_record_circuit_breaker_state(self):
        """Test circuit breaker state recording."""
        states = ["closed", "open", "half_open"]

        for state in states:
            record_circuit_breaker_state("/test_endpoint", state)

        # Just verify no errors occur
        assert True

    def test_record_retry_attempt(self):
        """Test retry attempt recording."""
        for attempt in range(1, 4):
            record_retry_attempt("/test_endpoint", attempt)

        # Just verify no errors occur
        assert True


class TestInstrumentation:
    """Test function instrumentation decorators."""

    @pytest.mark.asyncio
    async def test_instrument_async_function(self):
        """Test async function instrumentation."""

        @instrument_async_function("semantic_similarity", {"type": "test"})
        async def test_async_function():
            await asyncio.sleep(0.1)
            return "result"

        result = await test_async_function()

        assert result == "result"

    def test_instrument_sync_function(self):
        """Test sync function instrumentation."""

        @instrument_sync_function("structural_similarity", {"type": "test"})
        def test_sync_function():
            time.sleep(0.05)
            return "result"

        result = test_sync_function()

        assert result == "result"


class TestSystemInfo:
    """Test system information functions."""

    def test_initialize_system_info(self):
        """Test system info initialization."""
        initialize_system_info(
            version="1.0.0-test",
            config={
                "environment": "test",
                "langextract_url": "http://test:8000",
                "cache_enabled": True,
            },
        )

        # Just verify no errors occur
        assert True

    def test_get_metrics_summary(self):
        """Test metrics summary retrieval."""
        summary = get_metrics_summary()

        # Verify summary structure
        assert "cache" in summary
        assert "langextract" in summary
        assert "hybrid_scoring" in summary

        # Verify cache section
        assert "hits" in summary["cache"]
        assert "misses" in summary["cache"]
        assert "hit_rate" in summary["cache"]
        assert "size" in summary["cache"]

        # Verify hit rate is valid
        assert 0.0 <= summary["cache"]["hit_rate"] <= 1.0


class TestEndToEndScenario:
    """Test complete monitoring scenario."""

    @pytest.mark.asyncio
    async def test_complete_monitoring_flow(self):
        """Test a complete monitoring workflow."""

        # Initialize system
        initialize_system_info(
            version="1.0.0-test",
            config={
                "environment": "test",
                "langextract_url": "http://test:8000",
                "cache_enabled": True,
            },
        )

        # Simulate langextract request
        with track_langextract_request("/extract"):
            await asyncio.sleep(0.05)

        # Simulate cache operations
        with track_cache_lookup():
            # Cache miss
            record_cache_miss()

        # Simulate hybrid scoring
        with track_hybrid_scoring(strategy="adaptive"):
            # Calculate scores
            semantic_score = 0.85
            structural_score = 0.72
            hybrid_score = (semantic_score * 0.6) + (structural_score * 0.4)

            # Record scores
            record_pattern_similarity("semantic", semantic_score)
            record_pattern_similarity("structural", structural_score)
            record_pattern_similarity("hybrid", hybrid_score)

        # Get metrics summary
        summary = get_metrics_summary()

        # Verify data was recorded
        assert summary["cache"]["misses"] > 0
        assert summary["langextract"]["total_requests"] > 0
        assert summary["hybrid_scoring"]["total_requests"] > 0


class TestPrometheusExport:
    """Test Prometheus metrics export."""

    def test_metrics_export_format(self):
        """Test that metrics can be exported in Prometheus format."""
        from prometheus_client import generate_latest

        metrics_output = generate_latest(REGISTRY).decode("utf-8")

        # Verify key metrics are in output
        assert "langextract_requests_total" in metrics_output
        assert "semantic_cache_hit_rate" in metrics_output
        assert "hybrid_scoring_duration_seconds" in metrics_output

    def test_metrics_have_help_text(self):
        """Test that metrics have help text."""
        from prometheus_client import generate_latest

        metrics_output = generate_latest(REGISTRY).decode("utf-8")

        # Verify HELP lines exist
        assert "# HELP langextract_requests_total" in metrics_output
        assert "# HELP semantic_cache_hit_rate" in metrics_output
        assert "# HELP hybrid_scoring_duration_seconds" in metrics_output

    def test_metrics_have_type_annotations(self):
        """Test that metrics have type annotations."""
        from prometheus_client import generate_latest

        metrics_output = generate_latest(REGISTRY).decode("utf-8")

        # Verify TYPE lines exist
        assert "# TYPE langextract_requests_total counter" in metrics_output
        assert "# TYPE semantic_cache_hit_rate gauge" in metrics_output
        assert "# TYPE hybrid_scoring_duration_seconds histogram" in metrics_output


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
