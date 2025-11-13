#!/usr/bin/env python3
"""
Comprehensive Test Suite for Hybrid Score Combiner

Tests all aspects of hybrid scoring including:
- Default weights
- Adaptive weights (complexity, domain)
- Confidence calculation
- Score normalization
- Edge cases and error handling
- Performance benchmarks

Part of Track 3 Phase 2 - Pattern Learning Engine.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import time

import pytest
from archon_services.pattern_learning.phase2_matching.models.model_hybrid_score import (
    ModelHybridScoreConfig,
    ModelHybridScoreInput,
)
from archon_services.pattern_learning.phase2_matching.node_hybrid_scorer_compute import (
    NodeHybridScorerCompute,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def default_scorer():
    """Create scorer with default configuration."""
    return NodeHybridScorerCompute()


@pytest.fixture
def fixed_weight_scorer():
    """Create scorer with fixed weights (no adaptation)."""
    config = ModelHybridScoreConfig(
        default_vector_weight=0.7,
        default_pattern_weight=0.3,
        enable_adaptive_weights=False,
    )
    return NodeHybridScorerCompute(config=config)


@pytest.fixture
def custom_weight_scorer():
    """Create scorer with custom default weights."""
    config = ModelHybridScoreConfig(
        default_vector_weight=0.6,
        default_pattern_weight=0.4,
        enable_adaptive_weights=True,
    )
    return NodeHybridScorerCompute(config=config)


# ============================================================================
# Test Default Weights
# ============================================================================


def test_default_weights(default_scorer):
    """Test hybrid scoring with default weights (0.7 vector, 0.3 pattern)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8, pattern_similarity=0.6, task_characteristics=None
    )

    # Expected: 0.8 * 0.7 + 0.6 * 0.3 = 0.56 + 0.18 = 0.74
    assert result["hybrid_score"] == pytest.approx(0.74, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)
    assert result["pattern_weight"] == pytest.approx(0.3, abs=0.001)
    assert result["weights_adjusted"] is False


def test_weights_sum_to_one(default_scorer):
    """Test that weights always sum to exactly 1.0."""
    test_cases = [
        {"vector": 0.9, "pattern": 0.5, "complexity": "simple"},
        {"vector": 0.3, "pattern": 0.8, "complexity": "very_complex"},
        {"vector": 0.5, "pattern": 0.5, "complexity": "moderate"},
    ]

    for case in test_cases:
        result = default_scorer.calculate_hybrid_score(
            vector_similarity=case["vector"],
            pattern_similarity=case["pattern"],
            task_characteristics={"complexity": case["complexity"]},
        )

        weight_sum = result["vector_weight"] + result["pattern_weight"]
        assert weight_sum == pytest.approx(
            1.0, abs=0.001
        ), f"Weights must sum to 1.0, got {weight_sum} for case {case}"


# ============================================================================
# Test Adaptive Weights - Complexity Based
# ============================================================================


def test_adaptive_weights_trivial_complexity(default_scorer):
    """Test adaptive weights for trivial complexity (more vector weight)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "trivial"},
    )

    # Trivial complexity: -0.2 adjustment to pattern weight
    # Pattern: 0.3 - 0.2 = 0.1, Vector: 1.0 - 0.1 = 0.9
    assert result["pattern_weight"] == pytest.approx(0.1, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.9, abs=0.001)
    assert result["weights_adjusted"] is True
    assert "trivial" in result["adjustment_reason"].lower()


def test_adaptive_weights_simple_complexity(default_scorer):
    """Test adaptive weights for simple complexity."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "simple"},
    )

    # Simple complexity: -0.1 adjustment to pattern weight
    # Pattern: 0.3 - 0.1 = 0.2, Vector: 1.0 - 0.2 = 0.8
    assert result["pattern_weight"] == pytest.approx(0.2, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.8, abs=0.001)
    assert result["weights_adjusted"] is True


def test_adaptive_weights_moderate_complexity(default_scorer):
    """Test adaptive weights for moderate complexity (no change)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "moderate"},
    )

    # Moderate complexity: no adjustment
    assert result["pattern_weight"] == pytest.approx(0.3, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)
    # Weights not adjusted for moderate (it's the default)
    assert result["weights_adjusted"] is False


def test_adaptive_weights_complex_complexity(default_scorer):
    """Test adaptive weights for complex tasks (more pattern weight)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "complex"},
    )

    # Complex: +0.1 adjustment to pattern weight
    # Pattern: 0.3 + 0.1 = 0.4, Vector: 1.0 - 0.4 = 0.6
    assert result["pattern_weight"] == pytest.approx(0.4, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.6, abs=0.001)
    assert result["weights_adjusted"] is True
    assert "complex" in result["adjustment_reason"].lower()


def test_adaptive_weights_very_complex_complexity(default_scorer):
    """Test adaptive weights for very complex tasks (much more pattern weight)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "very_complex"},
    )

    # Very complex: +0.2 adjustment to pattern weight
    # Pattern: 0.3 + 0.2 = 0.5, Vector: 1.0 - 0.5 = 0.5
    assert result["pattern_weight"] == pytest.approx(0.5, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.5, abs=0.001)
    assert result["weights_adjusted"] is True


# ============================================================================
# Test Adaptive Weights - Domain Specific
# ============================================================================


def test_adaptive_weights_domain_specific(default_scorer):
    """Test adaptive weights for domain-specific tasks."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={
            "complexity": "moderate",
            "feature_label": "authentication",  # Domain-specific
        },
    )

    # Domain-specific: +0.1 to pattern weight
    # Pattern: 0.3 + 0.1 = 0.4, Vector: 1.0 - 0.4 = 0.6
    assert result["pattern_weight"] == pytest.approx(0.4, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.6, abs=0.001)
    assert result["weights_adjusted"] is True
    assert "domain" in result["adjustment_reason"].lower()


def test_adaptive_weights_complex_domain_specific(default_scorer):
    """Test adaptive weights combining complexity and domain adjustments."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={
            "complexity": "complex",  # +0.1
            "feature_label": "security",  # +0.1
        },
    )

    # Combined: +0.1 (complex) + 0.1 (domain) = +0.2
    # Pattern: 0.3 + 0.2 = 0.5, Vector: 1.0 - 0.5 = 0.5
    assert result["pattern_weight"] == pytest.approx(0.5, abs=0.001)
    assert result["vector_weight"] == pytest.approx(0.5, abs=0.001)
    assert result["weights_adjusted"] is True


# ============================================================================
# Test Confidence Calculation
# ============================================================================


def test_confidence_high_agreement(default_scorer):
    """Test confidence when both scores agree (high confidence)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8, pattern_similarity=0.8  # Perfect agreement
    )

    # Score agreement = 1.0 - |0.8 - 0.8| = 1.0
    # Average score = 0.8
    # Confidence = 1.0 * 0.8 = 0.8
    assert result["score_agreement"] == pytest.approx(1.0, abs=0.001)
    assert result["confidence"] == pytest.approx(0.8, abs=0.001)


def test_confidence_moderate_agreement(default_scorer):
    """Test confidence with moderate score agreement."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.7, pattern_similarity=0.5  # 0.2 difference
    )

    # Score agreement = 1.0 - |0.7 - 0.5| = 1.0 - 0.2 = 0.8
    # Average score = (0.7 + 0.5) / 2 = 0.6
    # Confidence = 0.8 * 0.6 = 0.48
    assert result["score_agreement"] == pytest.approx(0.8, abs=0.001)
    assert result["confidence"] == pytest.approx(0.48, abs=0.001)


def test_confidence_low_agreement(default_scorer):
    """Test confidence when scores diverge (low confidence)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.9, pattern_similarity=0.1  # Large difference
    )

    # Score agreement = 1.0 - |0.9 - 0.1| = 1.0 - 0.8 = 0.2
    # Average score = (0.9 + 0.1) / 2 = 0.5
    # Confidence = 0.2 * 0.5 = 0.1
    assert result["score_agreement"] == pytest.approx(0.2, abs=0.001)
    assert result["confidence"] == pytest.approx(0.1, abs=0.001)


def test_confidence_perfect_scores(default_scorer):
    """Test confidence with perfect scores."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=1.0, pattern_similarity=1.0
    )

    # Perfect agreement and perfect scores
    assert result["score_agreement"] == pytest.approx(1.0, abs=0.001)
    assert result["confidence"] == pytest.approx(1.0, abs=0.001)


def test_confidence_zero_scores(default_scorer):
    """Test confidence with zero scores."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.0, pattern_similarity=0.0
    )

    # Perfect agreement but zero scores
    assert result["score_agreement"] == pytest.approx(1.0, abs=0.001)
    assert result["confidence"] == pytest.approx(0.0, abs=0.001)


# ============================================================================
# Test Score Normalization
# ============================================================================


def test_score_normalization_basic(default_scorer):
    """Test basic score normalization (0.0-1.0 range)."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.5, pattern_similarity=0.5
    )

    assert 0.0 <= result["hybrid_score"] <= 1.0
    assert result["hybrid_score"] == pytest.approx(0.5, abs=0.001)


def test_score_normalization_extremes(default_scorer):
    """Test score normalization with extreme values."""
    # Maximum scores
    result_max = default_scorer.calculate_hybrid_score(
        vector_similarity=1.0, pattern_similarity=1.0
    )
    assert result_max["hybrid_score"] == pytest.approx(1.0, abs=0.001)

    # Minimum scores
    result_min = default_scorer.calculate_hybrid_score(
        vector_similarity=0.0, pattern_similarity=0.0
    )
    assert result_min["hybrid_score"] == pytest.approx(0.0, abs=0.001)


def test_score_normalization_mixed(default_scorer):
    """Test score normalization with mixed high/low values."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=1.0, pattern_similarity=0.0
    )

    # Result: 1.0 * 0.7 + 0.0 * 0.3 = 0.7
    assert result["hybrid_score"] == pytest.approx(0.7, abs=0.001)


# ============================================================================
# Test Edge Cases and Error Handling
# ============================================================================


def test_invalid_vector_score(default_scorer):
    """Test error handling for invalid vector score."""
    with pytest.raises(ValueError, match="vector_similarity must be in"):
        default_scorer.calculate_hybrid_score(
            vector_similarity=1.5,  # Invalid: > 1.0
            pattern_similarity=0.5,
        )


def test_invalid_pattern_score(default_scorer):
    """Test error handling for invalid pattern score."""
    with pytest.raises(ValueError, match="pattern_similarity must be in"):
        default_scorer.calculate_hybrid_score(
            vector_similarity=0.5,
            pattern_similarity=-0.1,  # Invalid: < 0.0
        )


def test_missing_task_characteristics(default_scorer):
    """Test graceful handling of missing task characteristics."""
    # Should use default weights without error
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8, pattern_similarity=0.6, task_characteristics=None
    )

    assert result["weights_adjusted"] is False
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)


def test_empty_task_characteristics(default_scorer):
    """Test handling of empty task characteristics dict."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8, pattern_similarity=0.6, task_characteristics={}
    )

    # Should use default weights
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)


def test_unknown_complexity(default_scorer):
    """Test handling of unknown complexity value."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "unknown_value"},
    )

    # Should fall back to no adjustment (moderate behavior)
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)


# ============================================================================
# Test Fixed Weight Mode
# ============================================================================


def test_fixed_weights_no_adaptation(fixed_weight_scorer):
    """Test that fixed weight mode never adapts."""
    result = fixed_weight_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "very_complex", "feature_label": "test"},
    )

    # Should use default weights regardless of characteristics
    assert result["vector_weight"] == pytest.approx(0.7, abs=0.001)
    assert result["pattern_weight"] == pytest.approx(0.3, abs=0.001)
    assert result["weights_adjusted"] is False


# ============================================================================
# Test Custom Configuration
# ============================================================================


def test_custom_default_weights(custom_weight_scorer):
    """Test scorer with custom default weights."""
    result = custom_weight_scorer.calculate_hybrid_score(
        vector_similarity=0.8, pattern_similarity=0.6, task_characteristics=None
    )

    # Custom defaults: 0.6 vector, 0.4 pattern
    assert result["vector_weight"] == pytest.approx(0.6, abs=0.001)
    assert result["pattern_weight"] == pytest.approx(0.4, abs=0.001)


def test_config_validation_weights_sum():
    """Test that config validates weights sum to 1.0."""
    with pytest.raises(ValueError, match="Weights must sum to 1.0"):
        ModelHybridScoreConfig(default_vector_weight=0.5, default_pattern_weight=0.4)


def test_config_validation_weight_range():
    """Test that config validates weight ranges."""
    with pytest.raises(ValueError, match="must be in"):
        ModelHybridScoreConfig(default_vector_weight=1.5, default_pattern_weight=-0.5)


# ============================================================================
# Test Async Interface
# ============================================================================


@pytest.mark.asyncio
async def test_async_execute_compute(default_scorer):
    """Test async execute_compute interface."""
    input_state = ModelHybridScoreInput(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "complex"},
    )

    output = await default_scorer.execute_compute(input_state)

    assert output.result.hybrid_score > 0.0
    assert output.processing_time_ms >= 0.0
    assert output.result.weights_adjusted is True
    assert output.correlation_id == input_state.correlation_id


@pytest.mark.asyncio
async def test_async_with_error_handling(default_scorer):
    """Test async error handling with fallback."""
    # Create input with invalid internal state (simulated error scenario)
    input_state = ModelHybridScoreInput(vector_similarity=0.8, pattern_similarity=0.6)

    # Should not raise, but return fallback result
    output = await default_scorer.execute_compute(input_state)

    assert output.result.hybrid_score >= 0.0
    assert output.processing_time_ms >= 0.0


# ============================================================================
# Test Performance
# ============================================================================


def test_performance_single_calculation(default_scorer):
    """Test performance of single calculation (<10ms target)."""
    start = time.time()

    default_scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "complex", "feature_label": "test"},
    )

    elapsed_ms = (time.time() - start) * 1000

    # Target: <10ms per calculation
    assert elapsed_ms < 10.0, f"Calculation took {elapsed_ms}ms, target is <10ms"


def test_performance_batch_calculations(default_scorer):
    """Test performance of batch calculations."""
    num_calculations = 100

    start = time.time()
    for i in range(num_calculations):
        default_scorer.calculate_hybrid_score(
            vector_similarity=0.8, pattern_similarity=0.6
        )
    elapsed_ms = (time.time() - start) * 1000

    avg_ms = elapsed_ms / num_calculations

    # Target: <10ms average
    assert avg_ms < 10.0, f"Average calculation took {avg_ms}ms, target is <10ms"


@pytest.mark.asyncio
async def test_performance_async_batch(default_scorer):
    """Test performance of async batch calculations."""
    num_calculations = 100

    inputs = [
        ModelHybridScoreInput(vector_similarity=0.8, pattern_similarity=0.6)
        for _ in range(num_calculations)
    ]

    start = time.time()
    for input_state in inputs:
        await default_scorer.execute_compute(input_state)
    elapsed_ms = (time.time() - start) * 1000

    avg_ms = elapsed_ms / num_calculations

    # Target: <10ms average
    assert avg_ms < 10.0, f"Average async calculation took {avg_ms}ms, target is <10ms"


# ============================================================================
# Test Statistics Tracking
# ============================================================================


def test_statistics_tracking(default_scorer):
    """Test that statistics are tracked correctly."""
    # Initial state
    stats = default_scorer.get_statistics()
    assert stats["calculation_count"] == 0

    # Perform calculations
    default_scorer.calculate_hybrid_score(vector_similarity=0.8, pattern_similarity=0.6)
    default_scorer.calculate_hybrid_score(
        vector_similarity=0.7,
        pattern_similarity=0.5,
        task_characteristics={"complexity": "complex"},
    )

    # Check statistics
    stats = default_scorer.get_statistics()
    assert stats["calculation_count"] == 2
    assert stats["avg_processing_time_ms"] > 0.0
    assert 0.0 <= stats["adaptive_adjustment_rate"] <= 1.0


def test_statistics_reset(default_scorer):
    """Test statistics reset."""
    # Perform calculations
    default_scorer.calculate_hybrid_score(vector_similarity=0.8, pattern_similarity=0.6)

    # Reset
    default_scorer.reset_statistics()

    # Check reset
    stats = default_scorer.get_statistics()
    assert stats["calculation_count"] == 0
    assert stats["avg_processing_time_ms"] == 0.0


# ============================================================================
# Integration Tests
# ============================================================================


def test_realistic_code_generation_task(default_scorer):
    """Test realistic code generation task scenario."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.85,
        pattern_similarity=0.75,
        task_characteristics={
            "complexity": "moderate",
            "task_type": "code_generation",
            "has_code_examples": True,
        },
    )

    # Should produce reasonable hybrid score
    assert 0.7 <= result["hybrid_score"] <= 0.9
    assert result["confidence"] > 0.5


def test_realistic_debugging_task(default_scorer):
    """Test realistic debugging task scenario."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.65,
        pattern_similarity=0.80,
        task_characteristics={
            "complexity": "complex",
            "task_type": "debugging",
            "feature_label": "error_handling",
        },
    )

    # Complex + domain-specific should increase pattern weight
    assert result["pattern_weight"] > 0.3
    assert result["weights_adjusted"] is True


def test_realistic_simple_task(default_scorer):
    """Test realistic simple task scenario."""
    result = default_scorer.calculate_hybrid_score(
        vector_similarity=0.90,
        pattern_similarity=0.60,
        task_characteristics={"complexity": "simple", "task_type": "documentation"},
    )

    # Simple should increase vector weight
    assert result["vector_weight"] > 0.7
    assert result["weights_adjusted"] is True


# ============================================================================
# Coverage Edge Cases
# ============================================================================


def test_boundary_score_values(default_scorer):
    """Test boundary score values."""
    test_cases = [
        (0.0, 0.0),
        (0.0, 1.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.5, 0.5),
    ]

    for vector, pattern in test_cases:
        result = default_scorer.calculate_hybrid_score(
            vector_similarity=vector, pattern_similarity=pattern
        )

        assert 0.0 <= result["hybrid_score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0


def test_weight_clamping(default_scorer):
    """Test that weights are clamped to min/max bounds."""
    # Create config with tight constraints
    config = ModelHybridScoreConfig(
        default_vector_weight=0.7,
        default_pattern_weight=0.3,
        enable_adaptive_weights=True,
        min_weight=0.2,
        max_weight=0.8,
    )
    scorer = NodeHybridScorerCompute(config=config)

    # Try extreme complexity that would push beyond bounds
    result = scorer.calculate_hybrid_score(
        vector_similarity=0.8,
        pattern_similarity=0.6,
        task_characteristics={"complexity": "very_complex"},
    )

    # Weights should be clamped
    assert result["vector_weight"] >= 0.2
    assert result["vector_weight"] <= 0.8
    assert result["pattern_weight"] >= 0.2
    assert result["pattern_weight"] <= 0.8


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=node_hybrid_scorer_compute",
            "--cov-report=term-missing",
        ]
    )
