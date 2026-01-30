# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for pattern clustering handler.

This module tests the pattern clustering functionality:
    - compute_similarity: 5-component weighted similarity computation
    - cluster_patterns: Single-linkage clustering with determinism guarantees

Key test areas:
    - Similarity computation correctness and component breakdown
    - Context similarity special cases (both empty, one empty, both present)
    - Clustering determinism (same inputs = same output, regardless of order)
    - Medoid selection and tie-breaking
    - Replay artifact emission
    - Input validation and error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Import directly from handler modules to avoid triggering omniintelligence.__init__
# which imports omnibase_core
from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_pattern_clustering import (
    cluster_patterns,
    compute_similarity,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.presets import (
    ONEX_PATTERN_KEYWORDS,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    SimilarityWeightsDict,
    StructuralFeaturesDict,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_structural_features() -> StructuralFeaturesDict:
    """Sample structural features with typical values."""
    return StructuralFeaturesDict(
        class_count=1,
        function_count=3,
        max_nesting_depth=2,
        line_count=50,
        cyclomatic_complexity=5,
        has_type_hints=True,
        has_docstrings=True,
    )


@pytest.fixture
def sample_features_python(
    sample_structural_features: StructuralFeaturesDict,
) -> ExtractedFeaturesDict:
    """Sample Python features with full extraction."""
    return ExtractedFeaturesDict(
        item_id="item-001",
        keywords=("def", "class", "import", "typing", "frozen", "Field"),
        pattern_indicators=("NodeCompute", "frozen", "TypedDict"),
        structural=sample_structural_features,
        base_classes=("NodeCompute",),
        decorators=(),
        labels=("compute", "pure"),
        language="python",
        extraction_quality="full",
    )


@pytest.fixture
def sample_features_similar() -> ExtractedFeaturesDict:
    """Features similar to sample_features_python with minor differences."""
    return ExtractedFeaturesDict(
        item_id="item-002",
        keywords=("def", "class", "import", "typing", "frozen", "Protocol"),
        pattern_indicators=("NodeCompute", "frozen", "Protocol"),
        structural=StructuralFeaturesDict(
            class_count=1,
            function_count=4,  # Slight difference
            max_nesting_depth=2,
            line_count=55,  # Slight difference
            cyclomatic_complexity=6,  # Slight difference
            has_type_hints=True,
            has_docstrings=True,
        ),
        base_classes=("NodeCompute",),
        decorators=(),
        labels=("compute", "pure", "functional"),
        language="python",
        extraction_quality="full",
    )


@pytest.fixture
def sample_features_different() -> ExtractedFeaturesDict:
    """Features completely different from sample_features_python."""
    return ExtractedFeaturesDict(
        item_id="item-003",
        keywords=("async", "await", "httpx", "post", "response"),
        pattern_indicators=("NodeEffect", "async"),
        structural=StructuralFeaturesDict(
            class_count=0,
            function_count=10,
            max_nesting_depth=5,
            line_count=200,
            cyclomatic_complexity=15,
            has_type_hints=False,
            has_docstrings=False,
        ),
        base_classes=("NodeEffect",),
        decorators=("asynccontextmanager",),
        labels=("effect", "io", "network"),
        language="python",
        extraction_quality="full",
    )


@pytest.fixture
def sample_features_no_context() -> ExtractedFeaturesDict:
    """Features with no ONEX context keywords."""
    return ExtractedFeaturesDict(
        item_id="item-004",
        keywords=("foo", "bar", "baz"),  # No ONEX keywords
        pattern_indicators=("NodeCompute",),
        structural=StructuralFeaturesDict(
            class_count=1,
            function_count=2,
            max_nesting_depth=1,
            line_count=30,
            cyclomatic_complexity=3,
            has_type_hints=True,
            has_docstrings=True,
        ),
        base_classes=("NodeCompute",),
        decorators=(),
        labels=("compute",),
        language="python",
        extraction_quality="full",
    )


@pytest.fixture
def mock_replay_emitter() -> MagicMock:
    """Mock emitter that captures emit() calls."""
    emitter = MagicMock()
    emitter.emit = MagicMock()
    return emitter


def make_features(
    item_id: str,
    keywords: tuple[str, ...] = (),
    pattern_indicators: tuple[str, ...] = (),
    labels: tuple[str, ...] = (),
    class_count: int = 1,
    function_count: int = 2,
    max_nesting_depth: int = 1,
    line_count: int = 50,
    cyclomatic_complexity: int = 5,
    has_type_hints: bool = True,
    has_docstrings: bool = True,
    base_classes: tuple[str, ...] = (),
    decorators: tuple[str, ...] = (),
    language: str = "python",
) -> ExtractedFeaturesDict:
    """Factory function to create ExtractedFeaturesDict with custom values."""
    return ExtractedFeaturesDict(
        item_id=item_id,
        keywords=keywords,
        pattern_indicators=pattern_indicators,
        structural=StructuralFeaturesDict(
            class_count=class_count,
            function_count=function_count,
            max_nesting_depth=max_nesting_depth,
            line_count=line_count,
            cyclomatic_complexity=cyclomatic_complexity,
            has_type_hints=has_type_hints,
            has_docstrings=has_docstrings,
        ),
        base_classes=base_classes,
        decorators=decorators,
        labels=labels,
        language=language,
        extraction_quality="full",
    )


# =============================================================================
# compute_similarity Tests
# =============================================================================


@pytest.mark.unit
class TestComputeSimilarityIdentical:
    """Tests for compute_similarity with identical features."""

    def test_compute_similarity_identical_features(
        self, sample_features_python: ExtractedFeaturesDict
    ) -> None:
        """Identical features should return similarity of 1.0."""
        result = compute_similarity(sample_features_python, sample_features_python)

        assert result["similarity"] == 1.0
        assert result["keyword_similarity"] == 1.0
        assert result["pattern_similarity"] == 1.0
        assert result["structural_similarity"] == 1.0
        assert result["label_similarity"] == 1.0
        # Context similarity: both have same ONEX keywords -> 1.0
        assert result["context_similarity"] == 1.0

    def test_compute_similarity_identical_returns_all_components(
        self, sample_features_python: ExtractedFeaturesDict
    ) -> None:
        """Result should contain all component scores and weights used."""
        result = compute_similarity(sample_features_python, sample_features_python)

        # Verify all expected keys are present
        assert "similarity" in result
        assert "keyword_similarity" in result
        assert "pattern_similarity" in result
        assert "structural_similarity" in result
        assert "label_similarity" in result
        assert "context_similarity" in result
        assert "weights_used" in result

        # Verify weights_used contains all weight keys
        weights = result["weights_used"]
        assert "keyword" in weights
        assert "pattern" in weights
        assert "structural" in weights
        assert "label" in weights
        assert "context" in weights


@pytest.mark.unit
class TestComputeSimilarityDisjoint:
    """Tests for compute_similarity with disjoint (completely different) features."""

    def test_compute_similarity_disjoint_features(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
    ) -> None:
        """Completely different features should have similarity near 0.0."""
        result = compute_similarity(sample_features_python, sample_features_different)

        # Keywords are disjoint
        assert result["keyword_similarity"] == 0.0

        # Pattern indicators are disjoint (NodeCompute vs NodeEffect)
        assert result["pattern_similarity"] < 0.5

        # Labels are disjoint
        assert result["label_similarity"] == 0.0

        # Final similarity should be low
        assert result["similarity"] < 0.3

    def test_compute_similarity_disjoint_structural_contributes(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
    ) -> None:
        """Structural differences reduce similarity."""
        result = compute_similarity(sample_features_python, sample_features_different)

        # Structural features are quite different (different counts, depths, etc.)
        # But not necessarily 0.0 due to normalization
        assert result["structural_similarity"] < 1.0


@pytest.mark.unit
class TestComputeSimilarityPartialOverlap:
    """Tests for compute_similarity with partial overlap."""

    def test_compute_similarity_partial_overlap(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
    ) -> None:
        """Similar features with partial overlap should have intermediate similarity."""
        result = compute_similarity(sample_features_python, sample_features_similar)

        # Should be between 0 and 1
        assert 0.0 < result["similarity"] < 1.0
        assert 0.0 < result["keyword_similarity"] < 1.0
        assert 0.0 < result["pattern_similarity"] < 1.0
        assert 0.0 < result["label_similarity"] < 1.0

    def test_compute_similarity_partial_overlap_high(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
    ) -> None:
        """Similar features should have relatively high overall similarity."""
        result = compute_similarity(sample_features_python, sample_features_similar)

        # These features are intentionally similar
        assert result["similarity"] > 0.5


@pytest.mark.unit
class TestComputeSimilarityCustomWeights:
    """Tests for compute_similarity with custom weights."""

    def test_compute_similarity_custom_weights_emphasize_keyword(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
    ) -> None:
        """Custom weights should affect final similarity calculation."""
        # Emphasize keyword similarity
        custom_weights: SimilarityWeightsDict = {
            "keyword": 0.60,
            "pattern": 0.10,
            "structural": 0.10,
            "label": 0.10,
            "context": 0.10,
        }

        result_default = compute_similarity(
            sample_features_python, sample_features_similar
        )
        result_custom = compute_similarity(
            sample_features_python, sample_features_similar, weights=custom_weights
        )

        # Raw component scores should be the same
        assert (
            result_default["keyword_similarity"] == result_custom["keyword_similarity"]
        )
        assert (
            result_default["pattern_similarity"] == result_custom["pattern_similarity"]
        )

        # But final similarity differs due to weights
        assert result_default["similarity"] != result_custom["similarity"]

        # Verify custom weights are reflected in output
        assert result_custom["weights_used"]["keyword"] == 0.60

    def test_compute_similarity_custom_weights_calculation_verification(
        self,
    ) -> None:
        """Verify weighted calculation is mathematically correct."""
        # Create features where we know exact component values
        features_a = make_features(
            item_id="a",
            keywords=("a", "b"),
            pattern_indicators=("x",),
            labels=("label1",),
        )
        features_b = make_features(
            item_id="b",
            keywords=("a", "b"),  # Same -> keyword_similarity = 1.0
            pattern_indicators=("y",),  # Different -> pattern_similarity = 0.0
            labels=("label1",),  # Same -> label_similarity = 1.0
        )

        # With equal weights, we can verify the calculation
        equal_weights: SimilarityWeightsDict = {
            "keyword": 0.20,
            "pattern": 0.20,
            "structural": 0.20,
            "label": 0.20,
            "context": 0.20,
        }

        result = compute_similarity(features_a, features_b, weights=equal_weights)

        # keyword = 1.0 (identical)
        assert result["keyword_similarity"] == 1.0

        # pattern = 0.0 (disjoint)
        assert result["pattern_similarity"] == 0.0

        # label = 1.0 (identical)
        assert result["label_similarity"] == 1.0

        # structural = 1.0 (identical features factory creates same structural)
        assert result["structural_similarity"] == 1.0

        # context: both have no ONEX keywords -> 0.5 (neutral)
        assert result["context_similarity"] == 0.5

        # Verify calculation: 0.2*(1.0) + 0.2*(0.0) + 0.2*(1.0) + 0.2*(1.0) + 0.2*(0.5)
        # = 0.2 + 0 + 0.2 + 0.2 + 0.1 = 0.7
        assert result["similarity"] == pytest.approx(0.7)


@pytest.mark.unit
class TestComputeSimilarityReturnsAllComponents:
    """Tests verifying compute_similarity returns complete result dict."""

    def test_compute_similarity_returns_all_components(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
    ) -> None:
        """Verify SimilarityResultDict contains all raw component scores."""
        result = compute_similarity(sample_features_python, sample_features_different)

        # All component scores should be floats in [0.0, 1.0]
        assert isinstance(result["similarity"], float)
        assert isinstance(result["keyword_similarity"], float)
        assert isinstance(result["pattern_similarity"], float)
        assert isinstance(result["structural_similarity"], float)
        assert isinstance(result["label_similarity"], float)
        assert isinstance(result["context_similarity"], float)

        for key in [
            "similarity",
            "keyword_similarity",
            "pattern_similarity",
            "structural_similarity",
            "label_similarity",
            "context_similarity",
        ]:
            assert 0.0 <= result[key] <= 1.0, f"{key} out of range"


@pytest.mark.unit
class TestContextSimilarity:
    """Tests for context similarity special cases."""

    def test_context_similarity_both_empty(
        self, sample_features_no_context: ExtractedFeaturesDict
    ) -> None:
        """Both items with no context tokens should return context_similarity = 0.5."""
        # Create another feature with no ONEX keywords
        features_b = make_features(
            item_id="b",
            keywords=("alpha", "beta", "gamma"),  # No ONEX keywords
        )

        result = compute_similarity(sample_features_no_context, features_b)

        # Both empty context -> neutral 0.5
        assert result["context_similarity"] == 0.5

    def test_context_similarity_one_empty(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_no_context: ExtractedFeaturesDict,
    ) -> None:
        """One item has context, other doesn't -> context_similarity = 0.0."""
        # sample_features_python has ONEX keywords (frozen, Field)
        # sample_features_no_context has none

        result = compute_similarity(sample_features_python, sample_features_no_context)

        # One empty -> asymmetric penalty of 0.0
        assert result["context_similarity"] == 0.0

    def test_context_similarity_both_present(
        self, sample_features_python: ExtractedFeaturesDict
    ) -> None:
        """Both items with context tokens should compute Jaccard similarity."""
        # Create feature with some overlapping ONEX keywords
        features_b = make_features(
            item_id="b",
            keywords=("frozen", "TypedDict", "other"),  # Some ONEX keywords
        )

        result = compute_similarity(sample_features_python, features_b)

        # Both have ONEX keywords, so Jaccard is computed
        # sample_features_python has: frozen, Field
        # features_b has: frozen, TypedDict
        # Intersection of ONEX context: frozen
        # Union of ONEX context: frozen, Field, TypedDict (if TypedDict is in ONEX_PATTERN_KEYWORDS)
        # Actual intersection/union depends on ONEX_PATTERN_KEYWORDS
        assert 0.0 < result["context_similarity"] <= 1.0

    def test_context_similarity_identical_context(
        self,
    ) -> None:
        """Identical context tokens should return context_similarity = 1.0."""
        # Use keywords that are known ONEX pattern keywords
        onex_keywords = tuple(list(ONEX_PATTERN_KEYWORDS)[:3])

        features_a = make_features(item_id="a", keywords=onex_keywords)
        features_b = make_features(item_id="b", keywords=onex_keywords)

        result = compute_similarity(features_a, features_b)

        assert result["context_similarity"] == 1.0


# =============================================================================
# cluster_patterns Tests - Determinism
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsDeterminism:
    """Tests verifying cluster_patterns is deterministic."""

    def test_cluster_patterns_deterministic_ordering_same_input(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
    ) -> None:
        """Same inputs called multiple times should produce identical output."""
        features_list = [
            sample_features_python,
            sample_features_similar,
            sample_features_different,
        ]

        result1 = cluster_patterns(features_list, threshold=0.5)
        result2 = cluster_patterns(features_list, threshold=0.5)
        result3 = cluster_patterns(features_list, threshold=0.5)

        # Same number of clusters
        assert len(result1) == len(result2) == len(result3)

        # Same cluster IDs and members
        for i in range(len(result1)):
            assert result1[i]["cluster_id"] == result2[i]["cluster_id"]
            assert result1[i]["member_ids"] == result2[i]["member_ids"]
            assert result1[i]["centroid_features"] == result2[i]["centroid_features"]

    def test_cluster_patterns_deterministic_ordering_different_input_order(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
    ) -> None:
        """Same items in different order should produce same clusters (sorted by item_id)."""
        features_forward = [
            sample_features_python,
            sample_features_similar,
            sample_features_different,
        ]
        features_reverse = [
            sample_features_different,
            sample_features_similar,
            sample_features_python,
        ]
        features_scrambled = [
            sample_features_similar,
            sample_features_different,
            sample_features_python,
        ]

        result_forward = cluster_patterns(features_forward, threshold=0.5)
        result_reverse = cluster_patterns(features_reverse, threshold=0.5)
        result_scrambled = cluster_patterns(features_scrambled, threshold=0.5)

        # Same number of clusters
        assert len(result_forward) == len(result_reverse) == len(result_scrambled)

        # Same cluster assignments regardless of input order
        for i in range(len(result_forward)):
            assert result_forward[i]["cluster_id"] == result_reverse[i]["cluster_id"]
            assert result_forward[i]["member_ids"] == result_reverse[i]["member_ids"]
            assert (
                result_forward[i]["cluster_id"] == result_scrambled[i]["cluster_id"]
            )
            assert (
                result_forward[i]["member_ids"] == result_scrambled[i]["member_ids"]
            )


# =============================================================================
# cluster_patterns Tests - Basic Clustering Behavior
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsBasic:
    """Tests for basic cluster_patterns behavior."""

    def test_cluster_patterns_single_item(
        self, sample_features_python: ExtractedFeaturesDict
    ) -> None:
        """Single item should result in one cluster containing that item."""
        result = cluster_patterns([sample_features_python])

        assert len(result) == 1
        assert result[0]["cluster_id"] == "cluster-0001"
        assert result[0]["member_ids"] == ("item-001",)
        assert result[0]["member_count"] == 1
        assert result[0]["internal_similarity"] == 1.0  # Single item = perfect

    def test_cluster_patterns_all_similar(
        self,
    ) -> None:
        """All items highly similar (>threshold) should form one cluster."""
        # Create very similar features
        features_a = make_features(
            item_id="a",
            keywords=("def", "class", "import"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )
        features_b = make_features(
            item_id="b",
            keywords=("def", "class", "import"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )
        features_c = make_features(
            item_id="c",
            keywords=("def", "class", "import"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )

        # Very low threshold to ensure they cluster together
        result = cluster_patterns([features_a, features_b, features_c], threshold=0.5)

        assert len(result) == 1
        assert result[0]["member_count"] == 3
        assert set(result[0]["member_ids"]) == {"a", "b", "c"}

    def test_cluster_patterns_all_different(
        self,
    ) -> None:
        """All items dissimilar (<threshold) should each be in own cluster."""
        # Create very different features
        features_a = make_features(
            item_id="a",
            keywords=("x1", "x2", "x3"),
            pattern_indicators=("PatternA",),
            labels=("labelA",),
        )
        features_b = make_features(
            item_id="b",
            keywords=("y1", "y2", "y3"),
            pattern_indicators=("PatternB",),
            labels=("labelB",),
        )
        features_c = make_features(
            item_id="c",
            keywords=("z1", "z2", "z3"),
            pattern_indicators=("PatternC",),
            labels=("labelC",),
        )

        # High threshold so they don't cluster
        result = cluster_patterns([features_a, features_b, features_c], threshold=0.99)

        assert len(result) == 3
        assert all(c["member_count"] == 1 for c in result)

    def test_cluster_patterns_two_groups(
        self,
    ) -> None:
        """Items forming two distinct groups should produce two clusters."""
        # Group 1: similar to each other
        g1_a = make_features(
            item_id="g1-a",
            keywords=("compute", "pure", "functional"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )
        g1_b = make_features(
            item_id="g1-b",
            keywords=("compute", "pure", "functional"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )

        # Group 2: similar to each other but different from group 1
        g2_a = make_features(
            item_id="g2-a",
            keywords=("effect", "io", "network"),
            pattern_indicators=("NodeEffect",),
            labels=("effect",),
        )
        g2_b = make_features(
            item_id="g2-b",
            keywords=("effect", "io", "network"),
            pattern_indicators=("NodeEffect",),
            labels=("effect",),
        )

        result = cluster_patterns(
            [g1_a, g1_b, g2_a, g2_b],
            threshold=0.5,
        )

        assert len(result) == 2
        # Verify each cluster has 2 members
        assert result[0]["member_count"] == 2
        assert result[1]["member_count"] == 2


# =============================================================================
# cluster_patterns Tests - Cluster ID and Leader Assignment
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsClusterIdAssignment:
    """Tests for cluster ID assignment by leader."""

    def test_cluster_patterns_cluster_id_by_leader(
        self,
    ) -> None:
        """Cluster IDs should be assigned by sorted leader (smallest item_id)."""
        # Create features with specific item_ids
        features_z = make_features(
            item_id="z-item",
            keywords=("a",),
        )
        features_a = make_features(
            item_id="a-item",
            keywords=("b",),
        )
        features_m = make_features(
            item_id="m-item",
            keywords=("c",),
        )

        # High threshold so each is its own cluster
        result = cluster_patterns([features_z, features_a, features_m], threshold=0.99)

        assert len(result) == 3

        # cluster-0001 should have smallest leader (a-item)
        assert result[0]["cluster_id"] == "cluster-0001"
        assert result[0]["member_ids"][0] == "a-item"

        # cluster-0002 should have second smallest leader (m-item)
        assert result[1]["cluster_id"] == "cluster-0002"
        assert result[1]["member_ids"][0] == "m-item"

        # cluster-0003 should have largest leader (z-item)
        assert result[2]["cluster_id"] == "cluster-0003"
        assert result[2]["member_ids"][0] == "z-item"


# =============================================================================
# cluster_patterns Tests - Medoid Selection
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsMedoidSelection:
    """Tests for medoid selection in clusters."""

    def test_cluster_patterns_medoid_selection_highest_avg_similarity(
        self,
    ) -> None:
        """Centroid should be the medoid (highest avg similarity to others)."""
        # Create a cluster where one member is clearly more central
        # Member A is slightly different from B and C
        # B and C are very similar to each other
        # So B or C should be the medoid (higher avg similarity)

        features_a = make_features(
            item_id="member-a",
            keywords=("unique", "different", "special"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )
        features_b = make_features(
            item_id="member-b",
            keywords=("common", "shared", "similar"),
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )
        features_c = make_features(
            item_id="member-c",
            keywords=("common", "shared", "similar"),  # Same as B
            pattern_indicators=("NodeCompute",),
            labels=("compute",),
        )

        # Low threshold to cluster all together
        result = cluster_patterns(
            [features_a, features_b, features_c],
            threshold=0.3,
        )

        # Should form one cluster
        assert len(result) == 1
        cluster = result[0]
        assert cluster["member_count"] == 3

        # Centroid should be B or C (they are more central)
        centroid_id = cluster["centroid_features"]["item_id"]
        assert centroid_id in ("member-b", "member-c")

    def test_cluster_patterns_medoid_tiebreak_by_smallest_item_id(
        self,
    ) -> None:
        """When avg similarities tie, smallest item_id wins."""
        # Create perfectly identical features (all have same avg similarity)
        features = [
            make_features(
                item_id=f"item-{c}",
                keywords=("identical",),
                pattern_indicators=("Same",),
                labels=("same",),
            )
            for c in ["c", "a", "b"]  # Intentionally not sorted
        ]

        # Low threshold to cluster all together
        result = cluster_patterns(features, threshold=0.3)

        assert len(result) == 1
        cluster = result[0]

        # Tie-break: smallest item_id (item-a) should be centroid
        assert cluster["centroid_features"]["item_id"] == "item-a"


# =============================================================================
# cluster_patterns Tests - Input Validation
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsInputValidation:
    """Tests for input validation in cluster_patterns."""

    def test_cluster_patterns_max_input_items_exceeded(
        self,
    ) -> None:
        """Exceeding max_input_items should raise PatternLearningValidationError."""
        # Create more items than the limit
        features_list = [
            make_features(item_id=f"item-{i}") for i in range(10)
        ]

        with pytest.raises(PatternLearningValidationError) as exc_info:
            cluster_patterns(features_list, max_input_items=5)

        assert "Input size 10 exceeds maximum allowed 5" in str(exc_info.value)
        assert "O(n^2)" in str(exc_info.value)

    def test_cluster_patterns_empty_list(
        self,
        mock_replay_emitter: MagicMock,
    ) -> None:
        """Empty input should return empty output without crashing."""
        result = cluster_patterns([], replay_emitter=mock_replay_emitter)

        assert result == []

        # Replay artifact should still be emitted
        mock_replay_emitter.emit.assert_called_once()
        call_args = mock_replay_emitter.emit.call_args
        assert call_args[0][0] == "clustering_result"
        payload = call_args[0][1]
        assert payload["cluster_assignment_map"] == {}
        assert payload["cluster_leaders"] == {}
        assert payload["cluster_scores_summary"] == {}


# =============================================================================
# cluster_patterns Tests - Replay Artifact Emission
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsReplayArtifact:
    """Tests for replay artifact emission in cluster_patterns."""

    def test_cluster_patterns_replay_artifact_emitted(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
        mock_replay_emitter: MagicMock,
    ) -> None:
        """Replay emitter should be called with correct payload shape."""
        cluster_patterns(
            [sample_features_python, sample_features_similar],
            threshold=0.5,
            replay_emitter=mock_replay_emitter,
        )

        # Verify emit was called
        mock_replay_emitter.emit.assert_called_once()

        # Verify call arguments
        call_args = mock_replay_emitter.emit.call_args
        name = call_args[0][0]
        payload = call_args[0][1]

        assert name == "clustering_result"

    def test_cluster_patterns_replay_artifact_payload_shape(
        self,
        sample_features_python: ExtractedFeaturesDict,
        sample_features_similar: ExtractedFeaturesDict,
        sample_features_different: ExtractedFeaturesDict,
        mock_replay_emitter: MagicMock,
    ) -> None:
        """Replay payload should have correct structure."""
        cluster_patterns(
            [
                sample_features_python,
                sample_features_similar,
                sample_features_different,
            ],
            threshold=0.5,
            replay_emitter=mock_replay_emitter,
        )

        call_args = mock_replay_emitter.emit.call_args
        payload = call_args[0][1]

        # Verify required keys
        assert "cluster_assignment_map" in payload
        assert "cluster_leaders" in payload
        assert "cluster_scores_summary" in payload

        # Verify cluster_assignment_map structure
        assignment_map = payload["cluster_assignment_map"]
        assert isinstance(assignment_map, dict)
        # Each item should be mapped to a cluster
        assert "item-001" in assignment_map
        assert "item-002" in assignment_map
        assert "item-003" in assignment_map

        # Verify cluster_leaders structure
        leaders = payload["cluster_leaders"]
        assert isinstance(leaders, dict)
        for cluster_id, leader_id in leaders.items():
            assert cluster_id.startswith("cluster-")
            assert isinstance(leader_id, str)

        # Verify cluster_scores_summary structure
        summary = payload["cluster_scores_summary"]
        assert isinstance(summary, dict)
        for cluster_id, scores in summary.items():
            assert cluster_id.startswith("cluster-")
            assert "size" in scores
            assert "avg_intra_similarity" in scores
            assert isinstance(scores["size"], int)
            assert isinstance(scores["avg_intra_similarity"], float)

    def test_cluster_patterns_replay_artifact_assignment_map_complete(
        self,
        mock_replay_emitter: MagicMock,
    ) -> None:
        """Every input item should appear in cluster_assignment_map."""
        features = [
            make_features(item_id=f"item-{i}") for i in range(5)
        ]

        cluster_patterns(features, threshold=0.99, replay_emitter=mock_replay_emitter)

        payload = mock_replay_emitter.emit.call_args[0][1]
        assignment_map = payload["cluster_assignment_map"]

        # All items should be assigned
        for i in range(5):
            assert f"item-{i}" in assignment_map


# =============================================================================
# cluster_patterns Tests - Internal Similarity
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsInternalSimilarity:
    """Tests for internal similarity computation in clusters."""

    def test_cluster_patterns_single_member_internal_similarity(
        self,
        sample_features_python: ExtractedFeaturesDict,
    ) -> None:
        """Single-member cluster should have internal_similarity = 1.0."""
        result = cluster_patterns([sample_features_python], threshold=0.99)

        assert len(result) == 1
        assert result[0]["internal_similarity"] == 1.0

    def test_cluster_patterns_multi_member_internal_similarity(
        self,
    ) -> None:
        """Multi-member cluster should have computed internal_similarity."""
        # Create similar items
        features = [
            make_features(
                item_id=f"item-{i}",
                keywords=("shared", "keywords"),
                pattern_indicators=("NodeCompute",),
                labels=("label",),
            )
            for i in range(3)
        ]

        result = cluster_patterns(features, threshold=0.5)

        assert len(result) == 1
        # Internal similarity should be high since items are similar
        assert result[0]["internal_similarity"] > 0.5


# =============================================================================
# cluster_patterns Tests - Pattern Type
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsPatternType:
    """Tests for pattern type detection in clusters."""

    def test_cluster_patterns_pattern_type_dominant(
        self,
    ) -> None:
        """Pattern type should be the most common pattern indicator."""
        # Create cluster where NodeCompute appears most
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute", "frozen")),
            make_features(item_id="b", pattern_indicators=("NodeCompute",)),
            make_features(item_id="c", pattern_indicators=("NodeEffect",)),
        ]

        result = cluster_patterns(features, threshold=0.3)

        # Assuming they cluster together (adjust threshold if needed)
        # The pattern_type should be "NodeCompute" (most frequent)
        for cluster in result:
            if cluster["member_count"] == 3:
                # NodeCompute appears 3 times, NodeEffect 1 time, frozen 1 time
                assert cluster["pattern_type"] == "NodeCompute"

    def test_cluster_patterns_pattern_type_unknown_when_empty(
        self,
    ) -> None:
        """Pattern type should be 'unknown' when no pattern indicators."""
        features = make_features(item_id="a", pattern_indicators=())

        result = cluster_patterns([features])

        assert len(result) == 1
        assert result[0]["pattern_type"] == "unknown"


# =============================================================================
# Additional Edge Cases
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsEdgeCases:
    """Additional edge case tests."""

    def test_cluster_patterns_threshold_boundary_exact_match(
        self,
    ) -> None:
        """Items with similarity exactly at threshold should cluster together."""
        # This is tricky to test exactly, but we can verify behavior around threshold
        features_a = make_features(item_id="a", keywords=("x",))
        features_b = make_features(item_id="b", keywords=("x",))

        # These should be very similar
        sim_result = compute_similarity(features_a, features_b)
        threshold = sim_result["similarity"]

        # At exact threshold, should cluster (>= threshold)
        result = cluster_patterns([features_a, features_b], threshold=threshold)
        assert len(result) == 1

        # Just above threshold, should NOT cluster
        result_higher = cluster_patterns(
            [features_a, features_b], threshold=threshold + 0.001
        )
        assert len(result_higher) == 2

    def test_cluster_patterns_uses_default_threshold(
        self,
    ) -> None:
        """Default threshold should be applied when not specified."""
        features = [make_features(item_id=f"item-{i}") for i in range(3)]

        # Should not raise and should use DEFAULT_CLUSTERING_THRESHOLD
        result = cluster_patterns(features)

        # Just verify it runs without error
        assert isinstance(result, list)

    def test_cluster_patterns_uses_default_weights(
        self,
    ) -> None:
        """Default weights should be applied when not specified."""
        features = [make_features(item_id=f"item-{i}") for i in range(2)]

        result = cluster_patterns(features, threshold=0.5)

        # Just verify it runs without error - default weights are used internally
        assert isinstance(result, list)

    def test_cluster_patterns_member_ids_sorted(
        self,
    ) -> None:
        """Member IDs within a cluster should be sorted."""
        features = [
            make_features(item_id="z"),
            make_features(item_id="a"),
            make_features(item_id="m"),
        ]

        # Low threshold to cluster all together
        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        member_ids = result[0]["member_ids"]

        # Verify sorted
        assert member_ids == tuple(sorted(member_ids))
        assert member_ids == ("a", "m", "z")
