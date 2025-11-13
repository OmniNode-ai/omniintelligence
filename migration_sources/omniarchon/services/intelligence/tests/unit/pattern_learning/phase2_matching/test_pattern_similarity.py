#!/usr/bin/env python3
"""
Pattern Similarity Scoring Tests

Comprehensive test suite for the pattern similarity scoring algorithm.

Test Coverage:
- Concept overlap (identical, partial, empty)
- Theme similarity
- Domain alignment
- Structure match
- Weighted combination
- Custom weights
- Performance benchmark (<100ms target)
- Edge cases (empty lists, nulls, invalid data)

Coverage Target: >90%

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import time
from typing import Dict, List
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase2_matching.node_pattern_similarity_compute import (
    NodePatternSimilarityCompute,
    PatternSimilarityConfig,
    PatternSimilarityScorer,
    SemanticAnalysisResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_scorer():
    """Provide a scorer with default weights."""
    return PatternSimilarityScorer()


@pytest.fixture
def custom_scorer():
    """Provide a scorer with custom weights."""
    config = PatternSimilarityConfig(
        concept_weight=0.40,
        theme_weight=0.25,
        domain_weight=0.20,
        structure_weight=0.10,
        relationship_weight=0.05,
    )
    return PatternSimilarityScorer(config)


@pytest.fixture
def compute_node():
    """Provide a compute node instance."""
    return NodePatternSimilarityCompute()


# ============================================================================
# Test Data
# ============================================================================


def create_semantic_result(
    concepts: List[str] = None,
    themes: List[str] = None,
    domain_indicators: List[str] = None,
    semantic_patterns: List[Dict] = None,
    semantic_context: Dict = None,
) -> SemanticAnalysisResult:
    """Helper to create semantic analysis results."""
    return SemanticAnalysisResult(
        concepts=concepts or [],
        themes=themes or [],
        domain_indicators=domain_indicators or [],
        semantic_patterns=semantic_patterns or [],
        semantic_context=semantic_context or {},
    )


# ============================================================================
# Configuration Tests
# ============================================================================


def test_config_weights_sum_to_one():
    """Test that default config weights sum to 1.0."""
    config = PatternSimilarityConfig()
    total = (
        config.concept_weight
        + config.theme_weight
        + config.domain_weight
        + config.structure_weight
        + config.relationship_weight
    )
    assert 0.99 <= total <= 1.01, f"Weights must sum to 1.0, got {total}"


def test_config_custom_weights_validation():
    """Test that custom weights must sum to 1.0."""
    # Valid weights
    config = PatternSimilarityConfig(
        concept_weight=0.40,
        theme_weight=0.25,
        domain_weight=0.20,
        structure_weight=0.10,
        relationship_weight=0.05,
    )
    assert config is not None

    # Invalid weights - should raise ValueError
    with pytest.raises(ValueError, match="Weights must sum to 1.0"):
        PatternSimilarityConfig(
            concept_weight=0.50,
            theme_weight=0.30,
            domain_weight=0.20,
            structure_weight=0.10,
            relationship_weight=0.10,  # Total > 1.0
        )


# ============================================================================
# Concept Overlap Tests
# ============================================================================


def test_concept_overlap_identical(default_scorer):
    """Test concept overlap with identical concepts."""
    task = create_semantic_result(
        concepts=["authentication", "user", "security", "jwt"]
    )
    pattern = create_semantic_result(
        concepts=["authentication", "user", "security", "jwt"]
    )

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["concept_score"] == 1.0, "Identical concepts should score 1.0"


def test_concept_overlap_partial(default_scorer):
    """Test concept overlap with partial overlap."""
    task = create_semantic_result(
        concepts=["authentication", "user", "security", "jwt"]
    )
    pattern = create_semantic_result(
        concepts=["authentication", "user", "oauth", "session"]
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Intersection: {authentication, user} = 2
    # Union: {authentication, user, security, jwt, oauth, session} = 6
    # Expected: 2/6 = 0.333...
    expected = 2 / 6
    assert (
        abs(result["concept_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['concept_score']:.3f}"


def test_concept_overlap_empty_both(default_scorer):
    """Test concept overlap when both lists are empty."""
    task = create_semantic_result(concepts=[])
    pattern = create_semantic_result(concepts=[])

    result = default_scorer.calculate_similarity(task, pattern)
    assert (
        result["concept_score"] == 1.0
    ), "Empty lists should be considered identical (score 1.0)"


def test_concept_overlap_empty_one(default_scorer):
    """Test concept overlap when one list is empty."""
    task = create_semantic_result(concepts=["authentication", "user"])
    pattern = create_semantic_result(concepts=[])

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["concept_score"] == 0.0, "One empty list should result in score 0.0"


def test_concept_overlap_case_insensitive(default_scorer):
    """Test that concept matching is case-insensitive."""
    task = create_semantic_result(concepts=["Authentication", "USER", "Security"])
    pattern = create_semantic_result(concepts=["authentication", "user", "security"])

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["concept_score"] == 1.0, "Concept matching should be case-insensitive"


# ============================================================================
# Theme Similarity Tests
# ============================================================================


def test_theme_similarity(default_scorer):
    """Test theme similarity calculation."""
    task = create_semantic_result(themes=["security", "access_control", "api_design"])
    pattern = create_semantic_result(
        themes=["security", "access_control", "data_validation"]
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Intersection: {security, access_control} = 2
    # Union: {security, access_control, api_design, data_validation} = 4
    # Expected: 2/4 = 0.5
    expected = 0.5
    assert (
        abs(result["theme_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['theme_score']:.3f}"


def test_theme_similarity_no_overlap(default_scorer):
    """Test theme similarity with no overlap."""
    task = create_semantic_result(themes=["frontend", "ui", "react"])
    pattern = create_semantic_result(themes=["backend", "database", "api"])

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["theme_score"] == 0.0, "No theme overlap should score 0.0"


# ============================================================================
# Domain Alignment Tests
# ============================================================================


def test_domain_alignment(default_scorer):
    """Test domain alignment calculation."""
    task = create_semantic_result(
        domain_indicators=["python", "fastapi", "async", "postgresql"]
    )
    pattern = create_semantic_result(
        domain_indicators=["python", "fastapi", "async", "mongodb"]
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Intersection: {python, fastapi, async} = 3
    # Union: {python, fastapi, async, postgresql, mongodb} = 5
    # Expected: 3/5 = 0.6
    expected = 0.6
    assert (
        abs(result["domain_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['domain_score']:.3f}"


def test_domain_alignment_perfect(default_scorer):
    """Test domain alignment with perfect match."""
    task = create_semantic_result(domain_indicators=["python", "fastapi", "async"])
    pattern = create_semantic_result(domain_indicators=["python", "fastapi", "async"])

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["domain_score"] == 1.0, "Perfect domain match should score 1.0"


# ============================================================================
# Structure Match Tests
# ============================================================================


def test_structure_match(default_scorer):
    """Test structural pattern matching."""
    task = create_semantic_result(
        semantic_patterns=[
            {"pattern_type": "authentication_flow", "confidence": 0.9},
            {"pattern_type": "error_handling", "confidence": 0.8},
            {"pattern_type": "data_validation", "confidence": 0.7},
        ]
    )
    pattern = create_semantic_result(
        semantic_patterns=[
            {"pattern_type": "authentication_flow", "confidence": 0.95},
            {"pattern_type": "error_handling", "confidence": 0.85},
            {"pattern_type": "logging", "confidence": 0.75},
        ]
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Pattern types: {authentication_flow, error_handling} intersection
    # Union: {authentication_flow, error_handling, data_validation, logging}
    # Expected: 2/4 = 0.5
    expected = 0.5
    assert (
        abs(result["structure_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['structure_score']:.3f}"


def test_structure_match_empty_patterns(default_scorer):
    """Test structure matching with empty patterns."""
    task = create_semantic_result(semantic_patterns=[])
    pattern = create_semantic_result(semantic_patterns=[])

    result = default_scorer.calculate_similarity(task, pattern)
    assert result["structure_score"] == 1.0, "Empty patterns should score 1.0"


# ============================================================================
# Relationship Type Match Tests
# ============================================================================


def test_relationship_match(default_scorer):
    """Test relationship type matching."""
    task = create_semantic_result(
        semantic_context={
            "relationships": [
                {"type": "depends_on", "source": "a", "target": "b"},
                {"type": "implements", "source": "c", "target": "d"},
                {"type": "extends", "source": "e", "target": "f"},
            ]
        }
    )
    pattern = create_semantic_result(
        semantic_context={
            "relationships": [
                {"type": "depends_on", "source": "x", "target": "y"},
                {"type": "implements", "source": "z", "target": "w"},
                {"type": "uses", "source": "p", "target": "q"},
            ]
        }
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Relationship types: {depends_on, implements} intersection
    # Union: {depends_on, implements, extends, uses}
    # Expected: 2/4 = 0.5
    expected = 0.5
    assert (
        abs(result["relationship_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['relationship_score']:.3f}"


def test_relationship_match_no_context(default_scorer):
    """Test relationship matching with no context."""
    task = create_semantic_result(semantic_context={})
    pattern = create_semantic_result(semantic_context={})

    result = default_scorer.calculate_similarity(task, pattern)
    # No relationships means both are empty, which should be 1.0
    assert result["relationship_score"] == 1.0


# ============================================================================
# Weighted Combination Tests
# ============================================================================


def test_weighted_combination(default_scorer):
    """Test final weighted similarity calculation."""
    task = create_semantic_result(
        concepts=["a", "b", "c", "d"],  # 4/6 = 0.667 overlap
        themes=["x", "y", "z"],  # 2/4 = 0.5 overlap
        domain_indicators=["python", "async"],  # 2/3 = 0.667 overlap
    )
    pattern = create_semantic_result(
        concepts=["a", "b", "e", "f"],
        themes=["x", "y", "w"],
        domain_indicators=["python", "sync"],
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Manual calculation with default weights:
    # concept: 2/6 = 0.333 * 0.30 = 0.100
    # theme: 2/4 = 0.500 * 0.20 = 0.100
    # domain: 1/3 = 0.333 * 0.20 = 0.067
    # structure: 0.0 * 0.15 = 0.0
    # relationship: 1.0 * 0.15 = 0.15
    # Total ≈ 0.417

    assert 0.0 <= result["final_similarity"] <= 1.0
    assert "concept_score" in result
    assert "theme_score" in result
    assert "domain_score" in result
    assert "structure_score" in result
    assert "relationship_score" in result


def test_custom_weights(custom_scorer):
    """Test similarity calculation with custom weights."""
    config = custom_scorer.config
    assert config.concept_weight == 0.40
    assert config.theme_weight == 0.25
    assert config.domain_weight == 0.20
    assert config.structure_weight == 0.10
    assert config.relationship_weight == 0.05

    task = create_semantic_result(
        concepts=["a", "b"],
        themes=["x", "y"],
        domain_indicators=["python"],
    )
    pattern = create_semantic_result(
        concepts=["a", "b"],
        themes=["x", "y"],
        domain_indicators=["python"],
    )

    result = custom_scorer.calculate_similarity(task, pattern)

    # All perfect matches should give 1.0 final score
    assert result["final_similarity"] == 1.0


# ============================================================================
# ONEX Compute Node Tests
# ============================================================================


@pytest.mark.asyncio
async def test_compute_node_execute(compute_node):
    """Test ONEX compute node execution."""
    task = create_semantic_result(
        concepts=["authentication", "user", "security"],
        themes=["security", "access_control"],
        domain_indicators=["python", "fastapi"],
    )
    pattern = create_semantic_result(
        concepts=["authentication", "user", "jwt"],
        themes=["security", "api_design"],
        domain_indicators=["python", "django"],
    )

    correlation_id = uuid4()
    result = await compute_node.execute_compute(task, pattern, correlation_id)

    assert "similarity_scores" in result
    assert "correlation_id" in result
    assert "computation_metadata" in result

    scores = result["similarity_scores"]
    assert "concept_score" in scores
    assert "theme_score" in scores
    assert "domain_score" in scores
    assert "structure_score" in scores
    assert "relationship_score" in scores
    assert "final_similarity" in scores

    # Verify correlation ID
    assert result["correlation_id"] == str(correlation_id)

    # Verify metadata
    metadata = result["computation_metadata"]
    assert metadata["concept_count_task"] == 3
    assert metadata["concept_count_pattern"] == 3


def test_compute_node_sync(compute_node):
    """Test synchronous compute method."""
    task = create_semantic_result(concepts=["a", "b", "c"])
    pattern = create_semantic_result(concepts=["a", "b", "d"])

    result = compute_node.compute_similarity_sync(task, pattern)

    assert "concept_score" in result
    assert "final_similarity" in result
    assert 0.0 <= result["final_similarity"] <= 1.0


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_performance_benchmark(compute_node):
    """Test that similarity computation meets <100ms target."""
    # Create realistic test data
    task = create_semantic_result(
        concepts=["auth", "user", "security", "jwt", "token", "session"] * 10,
        themes=["security", "access", "api", "backend", "database"] * 5,
        domain_indicators=["python", "fastapi", "async", "postgresql"] * 8,
        semantic_patterns=[
            {"pattern_type": f"pattern_{i}", "confidence": 0.8} for i in range(20)
        ],
        semantic_context={
            "relationships": [
                {"type": f"rel_type_{i}", "source": "a", "target": "b"}
                for i in range(30)
            ]
        },
    )
    pattern = create_semantic_result(
        concepts=["auth", "user", "oauth", "session", "cookie", "csrf"] * 10,
        themes=["security", "access", "frontend", "ui", "ux"] * 5,
        domain_indicators=["python", "django", "sync", "mysql"] * 8,
        semantic_patterns=[
            {"pattern_type": f"pattern_{i}", "confidence": 0.7} for i in range(25)
        ],
        semantic_context={
            "relationships": [
                {"type": f"rel_type_{i}", "source": "x", "target": "y"}
                for i in range(35)
            ]
        },
    )

    # Warm-up run
    await compute_node.execute_compute(task, pattern)

    # Measure performance
    iterations = 100
    start_time = time.perf_counter()

    for _ in range(iterations):
        await compute_node.execute_compute(task, pattern)

    end_time = time.perf_counter()
    avg_time_ms = ((end_time - start_time) / iterations) * 1000

    print(f"\n  Average computation time: {avg_time_ms:.2f}ms")
    assert avg_time_ms < 100, f"Performance target not met: {avg_time_ms:.2f}ms > 100ms"


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_edge_case_null_lists(default_scorer):
    """Test handling of None values in lists."""
    task = create_semantic_result(concepts=None)
    pattern = create_semantic_result(concepts=None)

    # Should handle None gracefully (treat as empty list)
    result = default_scorer.calculate_similarity(task, pattern)
    assert isinstance(result, dict)
    assert "final_similarity" in result


def test_edge_case_very_large_lists(default_scorer):
    """Test performance with very large lists."""
    task = create_semantic_result(concepts=[f"concept_{i}" for i in range(1000)])
    pattern = create_semantic_result(
        concepts=[f"concept_{i}" for i in range(500, 1500)]
    )

    start_time = time.perf_counter()
    result = default_scorer.calculate_similarity(task, pattern)
    end_time = time.perf_counter()

    elapsed_ms = (end_time - start_time) * 1000
    assert elapsed_ms < 100, f"Large list processing too slow: {elapsed_ms:.2f}ms"
    assert 0.0 <= result["final_similarity"] <= 1.0


def test_edge_case_duplicate_items(default_scorer):
    """Test that duplicates are handled correctly."""
    task = create_semantic_result(concepts=["a", "a", "b", "b", "c"])
    pattern = create_semantic_result(concepts=["a", "b", "b", "c", "c"])

    result = default_scorer.calculate_similarity(task, pattern)

    # Sets should remove duplicates: {a, b, c} vs {a, b, c} = 1.0
    assert result["concept_score"] == 1.0


def test_edge_case_special_characters(default_scorer):
    """Test handling of special characters in strings."""
    task = create_semantic_result(
        concepts=["auth@email.com", "user-name", "security#1"]
    )
    pattern = create_semantic_result(
        concepts=["auth@email.com", "user-name", "security#2"]
    )

    result = default_scorer.calculate_similarity(task, pattern)

    # Should handle special characters: 2/4 = 0.5
    expected = 0.5
    assert (
        abs(result["concept_score"] - expected) < 0.01
    ), f"Expected {expected:.3f}, got {result['concept_score']:.3f}"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_end_to_end_realistic_scenario(compute_node):
    """Test end-to-end with realistic task and pattern data."""
    # Realistic task: Add OAuth2 authentication
    task = create_semantic_result(
        concepts=["oauth2", "authentication", "google", "authorization", "token"],
        themes=["security", "authentication", "api_integration"],
        domain_indicators=["python", "fastapi", "async", "jwt"],
        semantic_patterns=[
            {"pattern_type": "authentication_flow", "confidence": 0.9},
            {"pattern_type": "token_management", "confidence": 0.85},
        ],
        semantic_context={
            "relationships": [
                {
                    "type": "implements",
                    "source": "oauth_provider",
                    "target": "base_auth",
                },
                {"type": "uses", "source": "oauth_provider", "target": "jwt_handler"},
            ]
        },
    )

    # Realistic pattern: Previous JWT authentication implementation
    pattern = create_semantic_result(
        concepts=["jwt", "authentication", "token", "authorization", "user"],
        themes=["security", "authentication", "access_control"],
        domain_indicators=["python", "fastapi", "async", "postgresql"],
        semantic_patterns=[
            {"pattern_type": "authentication_flow", "confidence": 0.95},
            {"pattern_type": "token_management", "confidence": 0.9},
        ],
        semantic_context={
            "relationships": [
                {"type": "implements", "source": "jwt_provider", "target": "base_auth"},
                {"type": "uses", "source": "jwt_provider", "target": "token_store"},
            ]
        },
    )

    result = await compute_node.execute_compute(task, pattern)

    scores = result["similarity_scores"]

    # Should have high similarity due to overlapping concepts and themes
    assert scores["final_similarity"] > 0.5, "Similar auth tasks should score >0.5"
    assert scores["concept_score"] > 0.4, "Shared auth concepts should score >0.4"
    assert scores["theme_score"] >= 0.5, "Shared security themes should score >=0.5"
    assert scores["structure_score"] >= 0.5, "Similar patterns should score >=0.5"

    print(f"\n  Realistic scenario similarity: {scores['final_similarity']:.3f}")
    print(f"  - Concept score: {scores['concept_score']:.3f}")
    print(f"  - Theme score: {scores['theme_score']:.3f}")
    print(f"  - Domain score: {scores['domain_score']:.3f}")
    print(f"  - Structure score: {scores['structure_score']:.3f}")
    print(f"  - Relationship score: {scores['relationship_score']:.3f}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short", "-s"])
