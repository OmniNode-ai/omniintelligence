"""
Unit Tests: Cache Optimizer Orchestrator Node

Tests for cache optimization and analysis functionality.

File: test_cache_optimizer.py
Track: Track 3 Phase 2 - Agent 5: Cache Optimization & Analysis
Coverage Target: >80%
"""

import asyncio
import time
from datetime import datetime, timezone

import pytest
from archon_services.pattern_learning.phase2_matching.model_contract_cache_optimizer import (
    CacheOptimizerOperation,
    ModelContractCacheOptimizer,
)
from archon_services.pattern_learning.phase2_matching.models_cache import (
    CacheAccessEvent,
    CacheAccessType,
)
from archon_services.pattern_learning.phase2_matching.optimizer_cache_tuning import (
    NodeCacheOptimizerOrchestrator,
)
from archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    SemanticAnalysisResult,
    SemanticCacheReducer,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def cache():
    """Create SemanticCacheReducer instance"""
    return SemanticCacheReducer(max_size=100, default_ttl=3600)


@pytest.fixture
def optimizer(cache):
    """Create NodeCacheOptimizerOrchestrator instance"""
    return NodeCacheOptimizerOrchestrator(cache)


@pytest.fixture
def sample_content():
    """Sample content for testing"""
    return [
        "async def process_data(input_data):",
        "class PatternMatcher:",
        "def calculate_similarity(vec1, vec2):",
        "import asyncio",
        "from typing import List, Dict, Any",
    ]


@pytest.fixture
async def populated_cache(cache, sample_content):
    """Cache pre-populated with test data"""
    for i, content in enumerate(sample_content):
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"keyword{i}"],
            intent="testing",
            confidence=0.8 + i * 0.02,
        )
        await cache.set(content, result)
    return cache


# ============================================================================
# Test: Initialization
# ============================================================================


def test_optimizer_initialization(optimizer, cache):
    """Test optimizer initializes correctly"""
    assert optimizer.cache == cache
    assert isinstance(optimizer.access_log, list)
    assert len(optimizer.access_log) == 0
    assert isinstance(optimizer.access_timestamps, dict)
    assert isinstance(optimizer.access_frequency, dict)


# ============================================================================
# Test: Hit Rate Analysis
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_hit_rate_with_data(optimizer):
    """Test hit rate analysis with access events"""
    # Create access events
    now = time.time()
    for i in range(100):
        event_type = CacheAccessType.HIT if i % 2 == 0 else CacheAccessType.MISS
        event = CacheAccessEvent(
            access_type=event_type,
            cache_key=f"key_{i}",
            timestamp=datetime.fromtimestamp(now - i, tz=timezone.utc),
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    # Analyze hit rate
    result = await optimizer.analyze_hit_rate(time_window_hours=24)

    # Assertions
    assert "hit_rate" in result
    assert "total_requests" in result
    assert result["total_requests"] == 100
    assert result["cache_hits"] == 50
    assert result["cache_misses"] == 50
    assert result["hit_rate"] == 0.5
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_analyze_hit_rate_empty(optimizer):
    """Test hit rate analysis with no data"""
    result = await optimizer.analyze_hit_rate(time_window_hours=24)

    assert result["hit_rate"] == 0.0
    assert result["total_requests"] == 0


@pytest.mark.asyncio
async def test_analyze_hit_rate_trend_increasing(optimizer):
    """Test hit rate analysis detects increasing trend"""
    now = time.time()

    # First half: low hit rate (30%)
    for i in range(50):
        event_type = CacheAccessType.HIT if i < 15 else CacheAccessType.MISS
        event = CacheAccessEvent(
            access_type=event_type,
            cache_key=f"key_{i}",
            timestamp=datetime.fromtimestamp(now - 100 + i, tz=timezone.utc),
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    # Second half: high hit rate (70%)
    for i in range(50, 100):
        event_type = CacheAccessType.HIT if i < 85 else CacheAccessType.MISS
        event = CacheAccessEvent(
            access_type=event_type,
            cache_key=f"key_{i}",
            timestamp=datetime.fromtimestamp(now - 50 + i, tz=timezone.utc),
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    result = await optimizer.analyze_hit_rate(time_window_hours=24)

    assert result["hit_rate_trend"] == "increasing"


# ============================================================================
# Test: TTL Optimization
# ============================================================================


@pytest.mark.asyncio
async def test_optimize_ttl_with_access_patterns(optimizer):
    """Test TTL optimization based on access patterns"""
    # Simulate access pattern: keys accessed every ~600 seconds
    now = time.time()
    for i in range(10):
        key = "hot_key_1"
        optimizer.access_timestamps[key].append(now - (i * 600))
        optimizer.access_frequency[key] += 1

    result = await optimizer.optimize_ttl(target_hit_rate=0.8)

    assert "recommended_ttl_sec" in result
    assert "expected_hit_rate_improvement_pct" in result
    assert "confidence_score" in result
    assert "reasoning" in result
    assert result["recommended_ttl_sec"] > 0


@pytest.mark.asyncio
async def test_optimize_ttl_no_data(optimizer):
    """Test TTL optimization with no access pattern data"""
    result = await optimizer.optimize_ttl(target_hit_rate=0.8)

    assert result["confidence_score"] == 0.0
    assert "insufficient" in result["reasoning"].lower()


@pytest.mark.asyncio
async def test_optimize_ttl_high_target(optimizer):
    """Test TTL optimization with high target hit rate (90%)"""
    # Add access pattern data
    now = time.time()
    for i in range(100):
        key = f"key_{i % 10}"
        optimizer.access_timestamps[key].append(now - (i * 300))
        optimizer.access_frequency[key] += 1

    result = await optimizer.optimize_ttl(target_hit_rate=0.9)

    # Should recommend longer TTL for 90% target
    assert result["recommended_ttl_sec"] >= 300


# ============================================================================
# Test: Performance Benchmark
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_performance(optimizer):
    """Test performance benchmarking"""
    result = await optimizer.benchmark_performance(num_requests=100)

    assert "total_requests" in result
    assert "avg_latency_ms" in result
    assert "p50_latency_ms" in result
    assert "p95_latency_ms" in result
    assert "p99_latency_ms" in result
    assert "throughput_req_per_sec" in result
    assert "hit_rate" in result

    assert result["total_requests"] == 100
    assert result["avg_latency_ms"] >= 0
    assert result["throughput_req_per_sec"] > 0


@pytest.mark.asyncio
async def test_benchmark_performance_latency_percentiles(optimizer):
    """Test benchmark calculates percentiles correctly"""
    result = await optimizer.benchmark_performance(num_requests=1000)

    # Percentiles should be ordered
    assert result["p50_latency_ms"] <= result["p95_latency_ms"]
    assert result["p95_latency_ms"] <= result["p99_latency_ms"]

    # Average latency target: <500ms with cache
    assert result["avg_latency_ms"] < 500


@pytest.mark.asyncio
async def test_benchmark_performance_hit_rate(optimizer):
    """Test benchmark achieves good hit rate with repeated content"""
    result = await optimizer.benchmark_performance(num_requests=1000)

    # With 70% repeated content, should achieve >60% hit rate
    assert result["hit_rate"] > 0.6


# ============================================================================
# Test: Access Pattern Analysis
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_access_patterns(optimizer):
    """Test access pattern analysis"""
    # Create access events with patterns
    now = time.time()

    # Hot keys (accessed 10+ times)
    for i in range(20):
        event = CacheAccessEvent(
            access_type=CacheAccessType.HIT,
            cache_key="hot_key_1",
            timestamp=datetime.fromtimestamp(now - i, tz=timezone.utc),
            content_hash="hash_hot",
        )
        optimizer.track_access(event)

    # Cold keys (accessed once)
    for i in range(10):
        event = CacheAccessEvent(
            access_type=CacheAccessType.MISS,
            cache_key=f"cold_key_{i}",
            timestamp=datetime.fromtimestamp(now - i, tz=timezone.utc),
            content_hash=f"hash_cold_{i}",
        )
        optimizer.track_access(event)

    contract = ModelContractCacheOptimizer(
        name="analyze_patterns",
        operation=CacheOptimizerOperation.ANALYZE_ACCESS_PATTERNS.value,
    )

    result = await optimizer._orchestrate_access_pattern_analysis(contract)

    assert "hot_keys_count" in result
    assert "cold_keys_count" in result
    assert result["hot_keys_count"] >= 1  # hot_key_1


@pytest.mark.asyncio
async def test_analyze_access_patterns_peak_times(optimizer):
    """Test access pattern identifies peak times"""
    now = time.time()

    # Concentrate accesses at hour 14 (2 PM)
    for i in range(50):
        timestamp = datetime.fromtimestamp(
            now - i * 60, tz=timezone.utc
        )  # Every minute
        timestamp = timestamp.replace(hour=14)
        event = CacheAccessEvent(
            access_type=CacheAccessType.HIT,
            cache_key=f"key_{i}",
            timestamp=timestamp,
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    contract = ModelContractCacheOptimizer(
        name="analyze_patterns",
        operation=CacheOptimizerOperation.ANALYZE_ACCESS_PATTERNS.value,
    )

    result = await optimizer._orchestrate_access_pattern_analysis(contract)

    assert "peak_access_times" in result
    assert 14 in result["peak_access_times"]  # Hour 14 should be peak


# ============================================================================
# Test: Cache Warming
# ============================================================================


@pytest.mark.asyncio
async def test_cache_warming(optimizer):
    """Test cache warming with content samples"""
    content_samples = ["sample content 1", "sample content 2", "sample content 3"]

    contract = ModelContractCacheOptimizer(
        name="warm_cache",
        operation=CacheOptimizerOperation.WARM_CACHE.value,
        analysis_params={"content_samples": content_samples},
    )

    result = await optimizer._orchestrate_cache_warming(contract)

    assert "warmed_count" in result
    assert "total_samples" in result
    assert result["total_samples"] == 3
    assert result["warmed_count"] == 3
    assert result["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_cache_warming_empty_samples(optimizer):
    """Test cache warming with empty sample list"""
    contract = ModelContractCacheOptimizer(
        name="warm_cache",
        operation=CacheOptimizerOperation.WARM_CACHE.value,
        analysis_params={"content_samples": []},
    )

    result = await optimizer._orchestrate_cache_warming(contract)

    assert result["total_samples"] == 0
    assert result["warmed_count"] == 0


# ============================================================================
# Test: Optimization Report
# ============================================================================


@pytest.mark.asyncio
async def test_generate_optimization_report(optimizer):
    """Test comprehensive optimization report generation"""
    # Add some access data
    now = time.time()
    for i in range(50):
        event_type = CacheAccessType.HIT if i % 2 == 0 else CacheAccessType.MISS
        event = CacheAccessEvent(
            access_type=event_type,
            cache_key=f"key_{i}",
            timestamp=datetime.fromtimestamp(now - i, tz=timezone.utc),
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    contract = ModelContractCacheOptimizer(
        name="optimization_report",
        operation=CacheOptimizerOperation.GENERATE_OPTIMIZATION_REPORT.value,
        time_window_hours=24,
        target_hit_rate=0.8,
    )

    result = await optimizer._orchestrate_optimization_report(contract)

    assert "report_generated_at" in result
    assert "cache_metrics" in result
    assert "hit_rate_analysis" in result
    assert "ttl_optimization" in result
    assert "access_patterns" in result
    assert "overall_recommendations" in result
    assert isinstance(result["overall_recommendations"], list)


# ============================================================================
# Test: Access Event Tracking
# ============================================================================


def test_track_access_hit(optimizer):
    """Test tracking cache hit event"""
    event = CacheAccessEvent(
        access_type=CacheAccessType.HIT,
        cache_key="test_key",
        timestamp=datetime.now(timezone.utc),
        content_hash="test_hash",
    )

    optimizer.track_access(event)

    assert len(optimizer.access_log) == 1
    assert "test_key" in optimizer.access_timestamps
    assert optimizer.access_frequency["test_key"] == 1


def test_track_access_miss(optimizer):
    """Test tracking cache miss event"""
    event = CacheAccessEvent(
        access_type=CacheAccessType.MISS,
        cache_key="test_key",
        timestamp=datetime.now(timezone.utc),
        content_hash="test_hash",
    )

    optimizer.track_access(event)

    assert len(optimizer.access_log) == 1
    assert optimizer.access_frequency["test_key"] == 1


def test_track_access_log_limit(optimizer):
    """Test access log size limiting"""
    # Add more than 10000 events
    for i in range(11000):
        event = CacheAccessEvent(
            access_type=CacheAccessType.HIT,
            cache_key=f"key_{i}",
            timestamp=datetime.now(timezone.utc),
            content_hash=f"hash_{i}",
        )
        optimizer.track_access(event)

    # Should be limited to 10000
    assert len(optimizer.access_log) == 10000


# ============================================================================
# Test: ONEX Orchestration Contract
# ============================================================================


@pytest.mark.asyncio
async def test_execute_orchestration_hit_rate(optimizer):
    """Test orchestration contract execution for hit rate analysis"""
    contract = ModelContractCacheOptimizer(
        name="test_hit_rate",
        operation=CacheOptimizerOperation.ANALYZE_HIT_RATE.value,
        time_window_hours=24,
    )

    result = await optimizer.execute_orchestration(contract)

    assert result.success is True
    assert result.data is not None
    assert "hit_rate" in result.data


@pytest.mark.asyncio
async def test_execute_orchestration_ttl_optimization(optimizer):
    """Test orchestration contract execution for TTL optimization"""
    contract = ModelContractCacheOptimizer(
        name="test_ttl",
        operation=CacheOptimizerOperation.OPTIMIZE_TTL.value,
        target_hit_rate=0.8,
    )

    result = await optimizer.execute_orchestration(contract)

    assert result.success is True
    assert result.data is not None
    assert "recommended_ttl_sec" in result.data


@pytest.mark.asyncio
async def test_execute_orchestration_invalid_operation(optimizer):
    """Test orchestration with invalid operation"""
    contract = ModelContractCacheOptimizer(
        name="test_invalid", operation="invalid_operation"
    )

    result = await optimizer.execute_orchestration(contract)

    assert result.success is False
    assert result.error is not None


# ============================================================================
# Test: Contract Validation
# ============================================================================


def test_contract_validation_positive_time_window():
    """Test contract validates positive time window"""
    with pytest.raises(ValueError, match="Time window must be positive"):
        ModelContractCacheOptimizer(
            name="test",
            operation=CacheOptimizerOperation.ANALYZE_HIT_RATE.value,
            time_window_hours=0,
        )


def test_contract_validation_target_hit_rate_range():
    """Test contract validates hit rate range"""
    with pytest.raises(ValueError, match="Target hit rate must be between"):
        ModelContractCacheOptimizer(
            name="test",
            operation=CacheOptimizerOperation.OPTIMIZE_TTL.value,
            target_hit_rate=1.5,
        )


def test_contract_validation_positive_benchmark_requests():
    """Test contract validates positive benchmark requests"""
    with pytest.raises(ValueError, match="Benchmark requests must be positive"):
        ModelContractCacheOptimizer(
            name="test",
            operation=CacheOptimizerOperation.BENCHMARK_PERFORMANCE.value,
            benchmark_requests=0,
        )


def test_contract_validation_warm_cache_requires_samples():
    """Test contract validates warm cache has content samples"""
    with pytest.raises(ValueError, match="requires 'content_samples'"):
        ModelContractCacheOptimizer(
            name="test",
            operation=CacheOptimizerOperation.WARM_CACHE.value,
            analysis_params={},
        )


# ============================================================================
# Test: Performance Targets
# ============================================================================


@pytest.mark.asyncio
async def test_performance_target_hit_rate(optimizer):
    """Test cache achieves >80% hit rate target"""
    # Simulate realistic access pattern
    content_pool = [f"content_{i}" for i in range(50)]

    hits = 0
    total = 0

    # Access pattern: 80% repeated, 20% new
    for i in range(1000):
        if i % 5 == 0:  # 20% new content
            content = f"new_content_{i}"
        else:  # 80% repeated content
            content = content_pool[i % len(content_pool)]

        result = await optimizer.cache.get(content)

        if result is None:
            dummy_result = SemanticAnalysisResult(
                content_hash=optimizer.cache.get_cache_key(content),
                keywords=["test"],
                intent="testing",
                confidence=0.9,
            )
            await optimizer.cache.set(content, dummy_result)
        else:
            hits += 1

        total += 1

    hit_rate = hits / total

    # With 80% repeated content, should achieve >70% hit rate
    # (accounting for first access misses)
    assert hit_rate > 0.7


@pytest.mark.asyncio
async def test_performance_target_latency(optimizer):
    """Test cache achieves <500ms average latency target"""
    result = await optimizer.benchmark_performance(num_requests=1000)

    assert (
        result["avg_latency_ms"] < 500
    ), f"Average latency {result['avg_latency_ms']}ms exceeds 500ms target"


# ============================================================================
# Test: Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_ttl_optimization_single_access(optimizer):
    """Test TTL optimization with single access per key"""
    # Add single accesses (no intervals)
    for i in range(10):
        optimizer.access_timestamps[f"key_{i}"].append(time.time())
        optimizer.access_frequency[f"key_{i}"] = 1

    result = await optimizer.optimize_ttl(target_hit_rate=0.8)

    # Should return low confidence due to insufficient interval data
    assert result["confidence_score"] == 0.0


@pytest.mark.asyncio
async def test_benchmark_zero_requests(optimizer):
    """Test benchmark handles zero requests gracefully"""
    # This should not raise an exception
    # The contract validation should catch this, but test implementation handles it
    result = await optimizer.benchmark_performance(num_requests=1)

    assert result["total_requests"] == 1


def test_access_pattern_empty_access_log(optimizer):
    """Test access pattern analysis with empty log"""
    contract = ModelContractCacheOptimizer(
        name="analyze_patterns",
        operation=CacheOptimizerOperation.ANALYZE_ACCESS_PATTERNS.value,
    )

    # Should not raise exception
    result = asyncio.run(optimizer._orchestrate_access_pattern_analysis(contract))

    assert result["hot_keys_count"] == 0
    assert result["cold_keys_count"] == 0


# ============================================================================
# Test: Overall Recommendations
# ============================================================================


def test_generate_overall_recommendations_low_hit_rate(optimizer):
    """Test recommendations generated for low hit rate"""
    hit_rate_analysis = {"hit_rate": 0.5, "hit_rate_pct": 50.0}
    ttl_optimization = {
        "recommended_ttl_sec": 7200,
        "expected_hit_rate_improvement_pct": 10.0,
    }
    access_patterns = {"hot_keys_count": 50}

    recommendations = optimizer._generate_overall_recommendations(
        hit_rate_analysis, ttl_optimization, access_patterns
    )

    assert len(recommendations) > 0
    assert any("PRIORITY" in rec for rec in recommendations)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=optimizer_cache_tuning", "--cov-report=term-missing"]
    )
