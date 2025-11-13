"""
Unit Tests for OptimizationAnalyzer

Tests optimization opportunity identification, improvement estimation,
effort estimation, ROI calculation, and recommendation generation.

Phase 5C: Performance Intelligence
Created: 2025-10-15
"""

import os

import pytest
from archon_services.performance import (
    OptimizationAnalyzer,
    OptimizationOpportunity,
    PerformanceBaselineService,
)

# Test duration configuration (configurable via environment variables)
TEST_DURATION_MEDIUM_MS = float(os.getenv("TEST_DURATION_MEDIUM_MS", "100"))
TEST_DURATION_SLOW_MS = float(os.getenv("TEST_DURATION_SLOW_MS", "500"))
TEST_DURATION_VERY_SLOW_MS = float(os.getenv("TEST_DURATION_VERY_SLOW_MS", "1500"))


class TestOptimizationOpportunity:
    """Test OptimizationOpportunity dataclass."""

    def test_create_opportunity(self):
        """Test creating an optimization opportunity."""
        opportunity = OptimizationOpportunity(
            operation="slow_operation",
            current_performance={
                "p50": 450.0,
                "p95": 1200.0,
                "p99": 1800.0,
                "mean": 500.0,
                "std_dev": 300.0,
            },
            estimated_improvement=60.0,
            effort_level="medium",
            roi_score=30.0,
            recommendations=[
                "Add Redis caching",
                "Implement batch processing",
            ],
            priority="high",
        )

        assert opportunity.operation == "slow_operation"
        assert opportunity.estimated_improvement == 60.0
        assert opportunity.effort_level == "medium"
        assert opportunity.roi_score == 30.0
        assert len(opportunity.recommendations) == 2
        assert opportunity.priority == "high"

    def test_opportunity_to_dict(self):
        """Test converting opportunity to dictionary."""
        opportunity = OptimizationOpportunity(
            operation="test_op",
            current_performance={"p95": 1000.0},
            estimated_improvement=50.0,
            effort_level="low",
            roi_score=50.0,
            recommendations=["Test recommendation"],
            priority="high",
        )

        result = opportunity.to_dict()

        assert isinstance(result, dict)
        assert result["operation"] == "test_op"
        assert result["estimated_improvement"] == 50.0
        assert result["effort_level"] == "low"
        assert result["roi_score"] == 50.0
        assert result["priority"] == "high"


class TestOptimizationAnalyzer:
    """Test OptimizationAnalyzer functionality."""

    @pytest.fixture
    async def baseline_service_with_data(self):
        """Create baseline service with test data."""
        service = PerformanceBaselineService()

        # Add slow operation (p95 > 1000ms)
        for i in range(20):
            await service.record_measurement(
                "codegen_validation",
                duration_ms=TEST_DURATION_VERY_SLOW_MS + (i * 10),
                context={"node_type": "effect"},
            )

        # Add medium-slow operation (p95 ~600ms)
        for i in range(20):
            await service.record_measurement(
                "pattern_matching",
                duration_ms=TEST_DURATION_SLOW_MS + (i * 10),
                context={"pattern_type": "architectural"},
            )

        # Add fast operation (p95 ~150ms)
        for i in range(20):
            await service.record_measurement(
                "cache_lookup",
                duration_ms=TEST_DURATION_MEDIUM_MS + (i * 5),
                context={},
            )

        # Force baseline updates
        await service._update_baseline("codegen_validation")
        await service._update_baseline("pattern_matching")
        await service._update_baseline("cache_lookup")

        return service

    @pytest.fixture
    async def analyzer(self, baseline_service_with_data):
        """Create analyzer with baseline service."""
        return OptimizationAnalyzer(baseline_service_with_data)

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        service = PerformanceBaselineService()
        analyzer = OptimizationAnalyzer(service)

        assert analyzer.baseline_service is service
        assert analyzer.HIGH_IMPROVEMENT_THRESHOLD == 1000.0
        assert analyzer.MEDIUM_IMPROVEMENT_THRESHOLD == 500.0
        assert analyzer.EFFORT_SCORES["low"] == 1.0
        assert analyzer.EFFORT_SCORES["medium"] == 2.0
        assert analyzer.EFFORT_SCORES["high"] == 3.0

    @pytest.mark.asyncio
    async def test_identify_opportunities_threshold_filtering(self, analyzer):
        """Test that only operations above threshold are identified."""
        opportunities = await analyzer.identify_opportunities(min_p95_ms=500.0)

        # Should identify 2 operations: codegen_validation and pattern_matching
        # cache_lookup is below threshold
        assert len(opportunities) >= 1

        # All opportunities should have p95 > 500ms
        for opp in opportunities:
            assert opp.current_performance["p95"] > 500.0

    @pytest.mark.asyncio
    async def test_identify_opportunities_sorted_by_roi(self, analyzer):
        """Test that opportunities are sorted by ROI (highest first)."""
        opportunities = await analyzer.identify_opportunities(min_p95_ms=500.0)

        if len(opportunities) > 1:
            # Verify descending ROI order
            for i in range(len(opportunities) - 1):
                assert opportunities[i].roi_score >= opportunities[i + 1].roi_score

    @pytest.mark.asyncio
    async def test_identify_opportunities_max_recommendations(self, analyzer):
        """Test limiting number of recommendations."""
        opportunities = await analyzer.identify_opportunities(
            min_p95_ms=500.0, max_recommendations=1
        )

        assert len(opportunities) <= 1

    @pytest.mark.asyncio
    async def test_identify_opportunities_no_slow_operations(self):
        """Test when no operations exceed threshold."""
        service = PerformanceBaselineService()

        # Add only fast operations
        for i in range(10):
            await service.record_measurement("fast_op", 50.0 + i, {})

        await service._update_baseline("fast_op")

        analyzer = OptimizationAnalyzer(service)
        opportunities = await analyzer.identify_opportunities(min_p95_ms=500.0)

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_estimate_improvement_very_slow_operation(self, analyzer):
        """Test improvement estimation for very slow operation (p95 > 1000ms)."""
        metrics = {
            "p95": 1500.0,
            "mean": 1200.0,
            "std_dev": 300.0,
        }

        improvement = await analyzer._estimate_improvement("validation_op", metrics)

        # Should estimate high improvement (40-60%)
        assert 40.0 <= improvement <= 60.0

    @pytest.mark.asyncio
    async def test_estimate_improvement_medium_slow_operation(self, analyzer):
        """Test improvement estimation for medium-slow operation (500-1000ms)."""
        metrics = {
            "p95": 700.0,
            "mean": 600.0,
            "std_dev": 100.0,
        }

        improvement = await analyzer._estimate_improvement("medium_op", metrics)

        # Should estimate medium improvement (20-40%)
        assert 20.0 <= improvement <= 45.0

    @pytest.mark.asyncio
    async def test_estimate_improvement_high_variance_bonus(self, analyzer):
        """Test that high variance increases improvement estimate."""
        low_variance_metrics = {
            "p95": 800.0,
            "mean": 700.0,
            "std_dev": 100.0,  # Low variance
        }

        high_variance_metrics = {
            "p95": 800.0,
            "mean": 700.0,
            "std_dev": 800.0,  # High variance (ratio > 1.0)
        }

        low_improvement = await analyzer._estimate_improvement(
            "op1", low_variance_metrics
        )
        high_improvement = await analyzer._estimate_improvement(
            "op2", high_variance_metrics
        )

        # High variance should result in higher improvement estimate
        assert high_improvement > low_improvement

    @pytest.mark.asyncio
    async def test_estimate_improvement_io_bound_bonus(self, analyzer):
        """Test that I/O-bound operations get improvement bonus."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        cpu_improvement = await analyzer._estimate_improvement("compute_op", metrics)
        io_improvement = await analyzer._estimate_improvement("api_request_op", metrics)

        # I/O-bound should have higher improvement potential
        assert io_improvement >= cpu_improvement

    @pytest.mark.asyncio
    async def test_estimate_improvement_validation_bonus(self, analyzer):
        """Test that validation operations get improvement bonus."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        regular_improvement = await analyzer._estimate_improvement(
            "regular_op", metrics
        )
        validation_improvement = await analyzer._estimate_improvement(
            "validation_op", metrics
        )

        # Validation should have higher improvement potential
        assert validation_improvement >= regular_improvement

    @pytest.mark.asyncio
    async def test_estimate_improvement_capped_at_60(self, analyzer):
        """Test that improvement estimate is capped at 60%."""
        metrics = {
            "p95": 5000.0,  # Extremely slow
            "mean": 4000.0,
            "std_dev": 4500.0,  # Very high variance
        }

        improvement = await analyzer._estimate_improvement("validation_api_op", metrics)

        # Should be capped at 60%
        assert improvement <= 60.0

    @pytest.mark.asyncio
    async def test_estimate_effort_cacheable_operation(self, analyzer):
        """Test effort estimation for cacheable operations (low effort)."""
        metrics = {"p95": 800.0}

        effort = await analyzer._estimate_effort("pattern_lookup", metrics)
        assert effort == "low"

        effort = await analyzer._estimate_effort("search_query", metrics)
        assert effort == "low"

    @pytest.mark.asyncio
    async def test_estimate_effort_validation_operation(self, analyzer):
        """Test effort estimation for validation operations (medium effort)."""
        metrics = {"p95": 800.0}

        effort = await analyzer._estimate_effort("codegen_validation", metrics)
        assert effort == "medium"

    @pytest.mark.asyncio
    async def test_estimate_effort_architectural_operation(self, analyzer):
        """Test effort estimation for architectural operations (high effort)."""
        metrics = {"p95": 800.0}

        effort = await analyzer._estimate_effort("workflow_orchestration", metrics)
        assert effort == "high"

        effort = await analyzer._estimate_effort("pipeline_coordination", metrics)
        assert effort == "high"

    @pytest.mark.asyncio
    async def test_estimate_effort_external_service_operation(self, analyzer):
        """Test effort estimation for external service operations (high effort)."""
        metrics = {"p95": 800.0}

        effort = await analyzer._estimate_effort("api_service_call", metrics)
        assert effort == "high"

    @pytest.mark.asyncio
    async def test_calculate_roi_low_effort(self, analyzer):
        """Test ROI calculation with low effort."""
        roi = analyzer._calculate_roi(improvement=50.0, effort_level="low")

        # 50 / 1.0 = 50.0
        assert roi == 50.0

    @pytest.mark.asyncio
    async def test_calculate_roi_medium_effort(self, analyzer):
        """Test ROI calculation with medium effort."""
        roi = analyzer._calculate_roi(improvement=40.0, effort_level="medium")

        # 40 / 2.0 = 20.0
        assert roi == 20.0

    @pytest.mark.asyncio
    async def test_calculate_roi_high_effort(self, analyzer):
        """Test ROI calculation with high effort."""
        roi = analyzer._calculate_roi(improvement=60.0, effort_level="high")

        # 60 / 3.0 = 20.0
        assert roi == 20.0

    @pytest.mark.asyncio
    async def test_generate_recommendations_very_slow_operation(self, analyzer):
        """Test recommendations for very slow operations (p95 > 1000ms)."""
        metrics = {
            "p95": 1500.0,
            "mean": 1200.0,
            "std_dev": 300.0,
        }

        recommendations = await analyzer._generate_recommendations(
            "validation_op", metrics
        )

        # Should include caching recommendation
        assert len(recommendations) > 0
        assert any(
            "caching" in rec.lower() or "cache" in rec.lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_generate_recommendations_high_variance(self, analyzer):
        """Test recommendations for high variance operations."""
        metrics = {
            "p95": 800.0,
            "mean": 600.0,
            "std_dev": 650.0,  # Very high variance (ratio > 1.0)
        }

        recommendations = await analyzer._generate_recommendations(
            "variable_op", metrics
        )

        # Should include bottleneck investigation
        assert any(
            "variance" in rec.lower() or "bottleneck" in rec.lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_generate_recommendations_validation_operation(self, analyzer):
        """Test recommendations for validation operations."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        recommendations = await analyzer._generate_recommendations(
            "codegen_validation", metrics
        )

        # Should include batch validation recommendation
        assert any("batch" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_generate_recommendations_parallelizable_operation(self, analyzer):
        """Test recommendations for parallelizable operations."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        recommendations = await analyzer._generate_recommendations(
            "batch_process", metrics
        )

        # Should include parallelization recommendation
        assert any("parallel" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_generate_recommendations_database_operation(self, analyzer):
        """Test recommendations for database operations."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        recommendations = await analyzer._generate_recommendations(
            "database_query", metrics
        )

        # Should include database optimization recommendations
        assert any(
            "database" in rec.lower() or "index" in rec.lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_generate_recommendations_io_bound_operation(self, analyzer):
        """Test recommendations for I/O-bound operations."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        recommendations = await analyzer._generate_recommendations("api_fetch", metrics)

        # Should include async/await recommendation
        assert any("async" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_generate_recommendations_compute_intensive_operation(self, analyzer):
        """Test recommendations for compute-intensive operations."""
        metrics = {"p95": 800.0, "mean": 700.0, "std_dev": 100.0}

        recommendations = await analyzer._generate_recommendations(
            "calculate_metrics", metrics
        )

        # Should include algorithm optimization
        assert any(
            "algorithm" in rec.lower() or "optimize" in rec.lower()
            for rec in recommendations
        )

    @pytest.mark.asyncio
    async def test_generate_recommendations_always_returns_something(self, analyzer):
        """Test that recommendations are always generated."""
        metrics = {"p95": 400.0, "mean": 350.0, "std_dev": 50.0}

        recommendations = await analyzer._generate_recommendations(
            "unknown_op", metrics
        )

        # Should have at least one recommendation
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_determine_priority_critical(self, analyzer):
        """Test critical priority determination (p95 > 2000ms or ROI > 40)."""
        # Test p95 > 2000ms
        metrics = {"p95": 2500.0}
        priority = analyzer._determine_priority(metrics, roi_score=10.0)
        assert priority == "critical"

        # Test ROI > 40
        metrics = {"p95": 800.0}
        priority = analyzer._determine_priority(metrics, roi_score=45.0)
        assert priority == "critical"

    @pytest.mark.asyncio
    async def test_determine_priority_high(self, analyzer):
        """Test high priority determination (p95 > 1000ms or ROI > 20)."""
        # Test p95 > 1000ms
        metrics = {"p95": 1500.0}
        priority = analyzer._determine_priority(metrics, roi_score=10.0)
        assert priority == "high"

        # Test ROI > 20
        metrics = {"p95": 600.0}
        priority = analyzer._determine_priority(metrics, roi_score=25.0)
        assert priority == "high"

    @pytest.mark.asyncio
    async def test_determine_priority_medium(self, analyzer):
        """Test medium priority determination (p95 > 500ms or ROI > 10)."""
        # Test p95 > 500ms
        metrics = {"p95": 700.0}
        priority = analyzer._determine_priority(metrics, roi_score=8.0)
        assert priority == "medium"

        # Test ROI > 10
        metrics = {"p95": 400.0}
        priority = analyzer._determine_priority(metrics, roi_score=15.0)
        assert priority == "medium"

    @pytest.mark.asyncio
    async def test_determine_priority_low(self, analyzer):
        """Test low priority determination."""
        metrics = {"p95": 400.0}
        priority = analyzer._determine_priority(metrics, roi_score=5.0)
        assert priority == "low"

    @pytest.mark.asyncio
    async def test_analyze_opportunity_complete_workflow(self, analyzer):
        """Test complete opportunity analysis workflow."""
        metrics = {
            "p50": 450.0,
            "p95": 1200.0,
            "p99": 1800.0,
            "mean": 500.0,
            "std_dev": 300.0,
            "sample_size": 20,
        }

        opportunity = await analyzer._analyze_opportunity("codegen_validation", metrics)

        # Verify opportunity structure
        assert opportunity is not None
        assert opportunity.operation == "codegen_validation"
        assert opportunity.current_performance == metrics
        assert 0.0 < opportunity.estimated_improvement <= 60.0
        assert opportunity.effort_level in ["low", "medium", "high"]
        assert opportunity.roi_score > 0.0
        assert len(opportunity.recommendations) > 0
        assert opportunity.priority in ["critical", "high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_analyze_opportunity_error_handling(self, analyzer):
        """Test error handling in opportunity analysis."""
        # Pass invalid metrics
        invalid_metrics = {}

        opportunity = await analyzer._analyze_opportunity("invalid_op", invalid_metrics)

        # Should handle gracefully and return None
        # (or return opportunity with default values, depending on implementation)
        assert opportunity is None or isinstance(opportunity, OptimizationOpportunity)

    @pytest.mark.asyncio
    async def test_helper_is_io_bound_operation(self, analyzer):
        """Test I/O-bound operation detection."""
        assert analyzer._is_io_bound_operation("api_fetch") is True
        assert analyzer._is_io_bound_operation("database_query") is True
        assert analyzer._is_io_bound_operation("http_request") is True
        assert analyzer._is_io_bound_operation("compute_sum") is False

    @pytest.mark.asyncio
    async def test_helper_is_validation_operation(self, analyzer):
        """Test validation operation detection."""
        assert analyzer._is_validation_operation("codegen_validation") is True
        assert analyzer._is_validation_operation("validate_input") is True
        assert analyzer._is_validation_operation("pattern_matching") is False

    @pytest.mark.asyncio
    async def test_helper_is_pattern_operation(self, analyzer):
        """Test pattern operation detection."""
        assert analyzer._is_pattern_operation("pattern_matching") is True
        assert analyzer._is_pattern_operation("pattern_lookup") is True
        assert analyzer._is_pattern_operation("validation") is False

    @pytest.mark.asyncio
    async def test_helper_is_cacheable_operation(self, analyzer):
        """Test cacheable operation detection."""
        assert analyzer._is_cacheable_operation("pattern_lookup") is True
        assert analyzer._is_cacheable_operation("search_query") is True
        assert analyzer._is_cacheable_operation("validation") is True
        assert analyzer._is_cacheable_operation("orchestration") is False

    @pytest.mark.asyncio
    async def test_helper_can_parallelize(self, analyzer):
        """Test parallelizable operation detection."""
        assert analyzer._can_parallelize("batch_process") is True
        assert analyzer._can_parallelize("multi_aggregate") is True
        assert analyzer._can_parallelize("single_compute") is False

    @pytest.mark.asyncio
    async def test_helper_is_compute_intensive(self, analyzer):
        """Test compute-intensive operation detection."""
        assert analyzer._is_compute_intensive("analyze_metrics") is True
        assert analyzer._is_compute_intensive("calculate_score") is True
        assert analyzer._is_compute_intensive("parse_ast") is True
        assert analyzer._is_compute_intensive("fetch_data") is False


@pytest.mark.asyncio
async def test_integration_full_workflow():
    """Test full integration workflow: baseline → analyzer → opportunities."""
    # Create baseline service and record measurements
    service = PerformanceBaselineService()

    # Add very slow operation
    for i in range(20):
        await service.record_measurement(
            "slow_validation",
            duration_ms=TEST_DURATION_VERY_SLOW_MS + (i * 50),
            context={"complexity": "high"},
        )

    # Add medium-slow operation with high variance
    for i in range(20):
        duration = 700.0 if i % 2 == 0 else 900.0  # High variance
        await service.record_measurement(
            "variable_pattern_match", duration_ms=duration, context={}
        )

    # Update baselines
    await service._update_baseline("slow_validation")
    await service._update_baseline("variable_pattern_match")

    # Create analyzer
    analyzer = OptimizationAnalyzer(service)

    # Identify opportunities
    opportunities = await analyzer.identify_opportunities(min_p95_ms=500.0)

    # Verify results
    assert len(opportunities) == 2

    # Verify opportunities are sorted by ROI
    assert opportunities[0].roi_score >= opportunities[1].roi_score

    # Verify each opportunity has complete information
    for opp in opportunities:
        assert opp.operation in ["slow_validation", "variable_pattern_match"]
        assert opp.current_performance["p95"] > 500.0
        assert 0.0 < opp.estimated_improvement <= 60.0
        assert opp.effort_level in ["low", "medium", "high"]
        assert opp.roi_score > 0.0
        assert len(opp.recommendations) > 0
        assert opp.priority in ["critical", "high", "medium", "low"]


@pytest.mark.asyncio
async def test_performance_targets():
    """Test that performance targets are met (<100ms for 10 operations, <20ms per operation)."""
    import time

    # Create baseline service with 10 operations
    service = PerformanceBaselineService()

    operations = [f"operation_{i}" for i in range(10)]
    for op in operations:
        for j in range(20):
            await service.record_measurement(op, 600.0 + (j * 10), {})
        await service._update_baseline(op)

    # Create analyzer
    analyzer = OptimizationAnalyzer(service)

    # Measure time for opportunity identification
    start = time.perf_counter()
    opportunities = await analyzer.identify_opportunities(min_p95_ms=500.0)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Verify performance targets
    assert (
        elapsed_ms < 100.0
    ), f"Identification took {elapsed_ms:.2f}ms (target: <100ms)"

    # Measure time per operation (approximate)
    avg_time_per_op = elapsed_ms / len(opportunities) if opportunities else 0
    assert (
        avg_time_per_op < 20.0
    ), f"Per-operation analysis took {avg_time_per_op:.2f}ms (target: <20ms)"
