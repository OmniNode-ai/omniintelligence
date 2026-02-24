# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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
from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_clustering import (
    cluster_patterns,
    compute_similarity,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    ONEX_PATTERN_KEYWORDS,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
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
            assert result_forward[i]["cluster_id"] == result_scrambled[i]["cluster_id"]
            assert result_forward[i]["member_ids"] == result_scrambled[i]["member_ids"]


# =============================================================================
# cluster_patterns Tests - B Contract (Sort-Internally) Compliance
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsDeterminismContract:
    """Tests for B (sort-internally) contract compliance.

    The B contract guarantees that cluster_patterns produces canonical output
    regardless of input order. This ensures:
    - Identical clusters from any permutation of the same inputs
    - Cluster leaders are always the minimum member_id
    - Cluster list is ordered by cluster_id (assigned by leader)
    """

    def test_shuffled_input_produces_canonical_cluster_order(self) -> None:
        """Multiple random shuffles of input produce identical output.

        This test verifies that the cluster_patterns function is fully
        deterministic: the same set of features, regardless of input order,
        always produces the same output (cluster_ids, member_ids, centroids).
        """
        import random

        # Fixed seed for reproducibility
        random.seed(42)

        # Create 7 features with varying similarity characteristics
        # Group 1: Similar compute features (should cluster together)
        features_list = [
            make_features(
                item_id="compute-alpha",
                keywords=("def", "class", "typing"),
                pattern_indicators=("NodeCompute", "frozen"),
                labels=("compute", "pure"),
            ),
            make_features(
                item_id="compute-beta",
                keywords=("def", "class", "typing"),
                pattern_indicators=("NodeCompute",),
                labels=("compute", "pure"),
            ),
            make_features(
                item_id="compute-gamma",
                keywords=("def", "class", "typing"),
                pattern_indicators=("NodeCompute", "immutable"),
                labels=("compute",),
            ),
            # Group 2: Effect features (should cluster together)
            make_features(
                item_id="effect-delta",
                keywords=("async", "await", "httpx"),
                pattern_indicators=("NodeEffect", "async"),
                labels=("effect", "io"),
            ),
            make_features(
                item_id="effect-epsilon",
                keywords=("async", "await", "httpx"),
                pattern_indicators=("NodeEffect",),
                labels=("effect", "network"),
            ),
            # Standalone features (should be separate clusters)
            make_features(
                item_id="reducer-zeta",
                keywords=("state", "reduce", "aggregate"),
                pattern_indicators=("NodeReducer",),
                labels=("reducer",),
            ),
            make_features(
                item_id="orchestrator-eta",
                keywords=("workflow", "coordinate", "dispatch"),
                pattern_indicators=("NodeOrchestrator",),
                labels=("orchestrator",),
            ),
        ]

        # Get canonical result from sorted input
        canonical_result = cluster_patterns(
            sorted(features_list, key=lambda f: f["item_id"]),
            threshold=0.5,
        )

        # Run 10 iterations with random shuffles
        for iteration in range(10):
            shuffled_features = features_list.copy()
            random.shuffle(shuffled_features)

            shuffled_result = cluster_patterns(shuffled_features, threshold=0.5)

            # Assert same number of clusters
            assert len(shuffled_result) == len(canonical_result), (
                f"Iteration {iteration}: cluster count mismatch "
                f"({len(shuffled_result)} vs {len(canonical_result)})"
            )

            # Assert identical cluster structure
            for i in range(len(canonical_result)):
                assert (
                    shuffled_result[i]["cluster_id"]
                    == canonical_result[i]["cluster_id"]
                ), f"Iteration {iteration}, cluster {i}: cluster_id mismatch"
                assert (
                    shuffled_result[i]["member_ids"]
                    == canonical_result[i]["member_ids"]
                ), f"Iteration {iteration}, cluster {i}: member_ids mismatch"
                assert (
                    shuffled_result[i]["centroid_features"]["item_id"]
                    == canonical_result[i]["centroid_features"]["item_id"]
                ), f"Iteration {iteration}, cluster {i}: centroid mismatch"

    def test_cluster_leader_is_min_member_id_invariant(self) -> None:
        """Assert member_ids[0] == min(member_ids) for every cluster.

        The B contract specifies that the leader (first member) of each cluster
        must be the lexicographically smallest member_id. This invariant ensures
        deterministic cluster_id assignment.
        """
        # Create features that will form multiple clusters with varied item_ids
        features_list = [
            # Cluster 1: Similar features (zulu should NOT be leader despite being first)
            make_features(
                item_id="zulu-item",
                keywords=("shared", "common"),
                pattern_indicators=("TypeA",),
                labels=("group1",),
            ),
            make_features(
                item_id="alpha-item",
                keywords=("shared", "common"),
                pattern_indicators=("TypeA",),
                labels=("group1",),
            ),
            make_features(
                item_id="mike-item",
                keywords=("shared", "common"),
                pattern_indicators=("TypeA",),
                labels=("group1",),
            ),
            # Cluster 2: Different features
            make_features(
                item_id="yankee-diff",
                keywords=("unique", "different"),
                pattern_indicators=("TypeB",),
                labels=("group2",),
            ),
            make_features(
                item_id="bravo-diff",
                keywords=("unique", "different"),
                pattern_indicators=("TypeB",),
                labels=("group2",),
            ),
            # Cluster 3: Standalone
            make_features(
                item_id="oscar-solo",
                keywords=("standalone", "isolated"),
                pattern_indicators=("TypeC",),
                labels=("group3",),
            ),
        ]

        result = cluster_patterns(features_list, threshold=0.5)

        # Verify invariant for every cluster
        for cluster in result:
            member_ids = cluster["member_ids"]
            leader = member_ids[0]
            min_member = min(member_ids)

            assert leader == min_member, (
                f"Cluster {cluster['cluster_id']}: leader '{leader}' is not the "
                f"minimum member_id. Expected '{min_member}'. "
                f"Full member_ids: {member_ids}"
            )

    def test_cluster_list_ordered_by_leader(self) -> None:
        """Output clusters are ordered by cluster_id (which is assigned by leader).

        The B contract specifies that the output cluster list must be sorted
        by cluster_id. Since cluster_ids are assigned based on leader order
        (cluster-0001 for smallest leader, cluster-0002 for next, etc.),
        this ensures a deterministic, reproducible output order.
        """
        # Create features forming multiple distinct clusters
        features_list = [
            # Will form cluster with leader "zebra-..." (should be LAST)
            make_features(
                item_id="zebra-one",
                keywords=("z-group",),
                pattern_indicators=("ZType",),
                labels=("z-label",),
            ),
            make_features(
                item_id="zebra-two",
                keywords=("z-group",),
                pattern_indicators=("ZType",),
                labels=("z-label",),
            ),
            # Will form cluster with leader "alpha-..." (should be FIRST)
            make_features(
                item_id="alpha-first",
                keywords=("a-group",),
                pattern_indicators=("AType",),
                labels=("a-label",),
            ),
            make_features(
                item_id="alpha-second",
                keywords=("a-group",),
                pattern_indicators=("AType",),
                labels=("a-label",),
            ),
            # Will form cluster with leader "mid-..." (should be MIDDLE)
            make_features(
                item_id="mid-one",
                keywords=("m-group",),
                pattern_indicators=("MType",),
                labels=("m-label",),
            ),
            make_features(
                item_id="mid-two",
                keywords=("m-group",),
                pattern_indicators=("MType",),
                labels=("m-label",),
            ),
        ]

        result = cluster_patterns(features_list, threshold=0.5)

        # Verify clusters are ordered by cluster_id
        for i in range(len(result) - 1):
            current_id = result[i]["cluster_id"]
            next_id = result[i + 1]["cluster_id"]

            assert current_id < next_id, (
                f"Clusters not ordered by cluster_id: "
                f"result[{i}] has '{current_id}', result[{i + 1}] has '{next_id}'"
            )

        # Also verify the cluster_id sequence is contiguous (0001, 0002, 0003)
        for i, cluster in enumerate(result):
            expected_id = f"cluster-{i + 1:04d}"
            assert cluster["cluster_id"] == expected_id, (
                f"Cluster at index {i} has id '{cluster['cluster_id']}', "
                f"expected '{expected_id}'"
            )

        # Verify leaders are in ascending order (which determines cluster_id order)
        leaders = [cluster["member_ids"][0] for cluster in result]
        assert leaders == sorted(leaders), (
            f"Cluster leaders are not in ascending order: {leaders}"
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
        features_list = [make_features(item_id=f"item-{i}") for i in range(10)]

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
        features = [make_features(item_id=f"item-{i}") for i in range(5)]

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


# =============================================================================
# cluster_patterns Tests - Member Pattern Indicators (Parallel Tuple)
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsMemberPatternIndicators:
    """Tests for member_pattern_indicators field."""

    def test_member_pattern_indicators_parallel_to_member_ids(
        self,
    ) -> None:
        """member_pattern_indicators should have same length as member_ids."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute",)),
            make_features(item_id="b", pattern_indicators=("NodeEffect",)),
            make_features(item_id="c", pattern_indicators=("NodeReducer",)),
        ]

        # Low threshold to cluster all together
        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        cluster = result[0]
        assert len(cluster["member_pattern_indicators"]) == len(cluster["member_ids"])

    def test_member_pattern_indicators_order_matches_member_ids(
        self,
    ) -> None:
        """member_pattern_indicators[i] should correspond to member_ids[i]."""
        features = [
            make_features(item_id="c", pattern_indicators=("Indicator_C",)),
            make_features(item_id="a", pattern_indicators=("Indicator_A",)),
            make_features(item_id="b", pattern_indicators=("Indicator_B",)),
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        cluster = result[0]

        # member_ids should be sorted: ("a", "b", "c")
        assert cluster["member_ids"] == ("a", "b", "c")

        # member_pattern_indicators should match that order
        assert cluster["member_pattern_indicators"][0] == ("Indicator_A",)  # for "a"
        assert cluster["member_pattern_indicators"][1] == ("Indicator_B",)  # for "b"
        assert cluster["member_pattern_indicators"][2] == ("Indicator_C",)  # for "c"

    def test_member_pattern_indicators_preserves_tuple_structure(
        self,
    ) -> None:
        """pattern_indicators tuples should be preserved as-is."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute", "frozen")),
        ]

        result = cluster_patterns(features, threshold=0.99)

        assert len(result) == 1
        assert result[0]["member_pattern_indicators"][0] == ("NodeCompute", "frozen")

    def test_member_pattern_indicators_empty_tuple_preserved(
        self,
    ) -> None:
        """Empty pattern_indicators should be preserved as empty tuple."""
        features = [
            make_features(item_id="a", pattern_indicators=()),
        ]

        result = cluster_patterns(features)

        assert len(result) == 1
        assert result[0]["member_pattern_indicators"][0] == ()


# =============================================================================
# cluster_patterns Tests - Label Agreement
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsLabelAgreement:
    """Tests for label_agreement field."""

    def test_label_agreement_all_match(
        self,
    ) -> None:
        """label_agreement should be 1.0 when all members match dominant pattern_type."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute",)),
            make_features(item_id="b", pattern_indicators=("NodeCompute",)),
            make_features(item_id="c", pattern_indicators=("NodeCompute",)),
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        assert result[0]["pattern_type"] == "NodeCompute"
        assert result[0]["label_agreement"] == 1.0

    def test_label_agreement_partial_match(
        self,
    ) -> None:
        """label_agreement should reflect fraction of members matching."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute",)),
            make_features(item_id="b", pattern_indicators=("NodeCompute",)),
            make_features(item_id="c", pattern_indicators=("NodeEffect",)),  # different
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        # NodeCompute appears 2x, NodeEffect 1x -> dominant is NodeCompute
        # 2 of 3 members have NodeCompute in their indicators
        assert result[0]["pattern_type"] == "NodeCompute"
        assert result[0]["label_agreement"] == pytest.approx(2 / 3)

    def test_label_agreement_none_match(
        self,
    ) -> None:
        """label_agreement should be 0.0 when no members contain dominant pattern."""
        # Edge case: each member has different single indicator
        # Dominant is alphabetically first (tie-break), but none have it twice
        features = [
            make_features(item_id="a", pattern_indicators=("Alpha",)),
            make_features(item_id="b", pattern_indicators=("Beta",)),
            make_features(item_id="c", pattern_indicators=("Gamma",)),
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        # All have 1 count, alphabetically "Alpha" wins
        assert result[0]["pattern_type"] == "Alpha"
        # Only 1 of 3 has "Alpha"
        assert result[0]["label_agreement"] == pytest.approx(1 / 3)

    def test_label_agreement_unknown_pattern_type(
        self,
    ) -> None:
        """label_agreement should be 0.0 when pattern_type is 'unknown'."""
        features = [
            make_features(item_id="a", pattern_indicators=()),
            make_features(item_id="b", pattern_indicators=()),
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        assert result[0]["pattern_type"] == "unknown"
        assert result[0]["label_agreement"] == 0.0

    def test_label_agreement_single_member(
        self,
    ) -> None:
        """Single member cluster should have label_agreement based on its own indicators."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute",)),
        ]

        result = cluster_patterns(features)

        assert len(result) == 1
        assert result[0]["pattern_type"] == "NodeCompute"
        # The single member has "NodeCompute", so 1/1 = 1.0
        assert result[0]["label_agreement"] == 1.0

    def test_label_agreement_member_has_multiple_indicators(
        self,
    ) -> None:
        """Members with multiple indicators should match if any contains dominant."""
        features = [
            make_features(item_id="a", pattern_indicators=("NodeCompute", "frozen")),
            make_features(item_id="b", pattern_indicators=("NodeCompute",)),
            make_features(
                item_id="c", pattern_indicators=("frozen",)
            ),  # no NodeCompute
        ]

        result = cluster_patterns(features, threshold=0.0)

        assert len(result) == 1
        # NodeCompute appears 2x (in a and b), frozen appears 2x (in a and c)
        # Tie-break: NodeCompute < frozen alphabetically
        assert result[0]["pattern_type"] == "NodeCompute"
        # "a" has NodeCompute, "b" has NodeCompute, "c" doesn't -> 2/3
        assert result[0]["label_agreement"] == pytest.approx(2 / 3)


# =============================================================================
# cluster_patterns Tests - Invariants
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsInvariants:
    """Tests for cluster invariants."""

    def test_invariant_member_count_equals_member_ids_length(
        self,
    ) -> None:
        """member_count should equal len(member_ids)."""
        features = [make_features(item_id=f"item-{i}") for i in range(5)]

        result = cluster_patterns(features, threshold=0.0)

        for cluster in result:
            assert cluster["member_count"] == len(cluster["member_ids"])

    def test_invariant_pattern_indicators_length_equals_member_ids(
        self,
    ) -> None:
        """len(member_pattern_indicators) should equal len(member_ids)."""
        features = [make_features(item_id=f"item-{i}") for i in range(5)]

        result = cluster_patterns(features, threshold=0.0)

        for cluster in result:
            assert len(cluster["member_pattern_indicators"]) == len(
                cluster["member_ids"]
            )


# =============================================================================
# cluster_patterns Tests - Replay Artifact Invariants (Surgical Tests)
# =============================================================================


@pytest.mark.unit
class TestClusterPatternsReplayInvariants:
    """Surgical invariant tests for replay artifacts.

    These tests verify structural invariants of the replay artifacts
    rather than brittle JSON blob comparisons. Each test focuses on
    a specific invariant that must hold for correct clustering behavior.
    """

    def test_invariant_every_item_appears_exactly_once_in_assignment_map(
        self,
    ) -> None:
        """Every input item_id appears exactly once in cluster_assignment_map.

        Invariant: len(assignment_map) == len(input_features)
        Invariant: set(assignment_map.keys()) == {f["item_id"] for f in input_features}
        """
        # Create 6 features with various characteristics
        features = [
            make_features(
                item_id=f"feature-{i:03d}",
                keywords=("shared", "common") if i < 3 else ("unique", f"kw-{i}"),
                pattern_indicators=("NodeCompute",) if i < 3 else ("NodeEffect",),
                labels=("compute",) if i < 3 else ("effect",),
            )
            for i in range(6)
        ]

        emitter = MagicMock()
        cluster_patterns(features, threshold=0.5, replay_emitter=emitter)

        # Extract replay artifact payload
        emitter.emit.assert_called_once()
        payload = emitter.emit.call_args[0][1]
        assignment_map = payload["cluster_assignment_map"]

        # Invariant 1: Every input item appears in assignment_map
        input_item_ids = {f["item_id"] for f in features}
        assigned_item_ids = set(assignment_map.keys())

        assert len(assignment_map) == len(features), (
            f"Assignment map size {len(assignment_map)} != input size {len(features)}"
        )
        assert assigned_item_ids == input_item_ids, (
            f"Assignment map keys mismatch. "
            f"Missing: {input_item_ids - assigned_item_ids}, "
            f"Extra: {assigned_item_ids - input_item_ids}"
        )

        # Invariant 2: No duplicate item_ids (implicitly verified by dict keys)
        # But verify explicitly that each item_id maps to exactly one cluster
        assert len(list(assignment_map.keys())) == len(set(assignment_map.keys())), (
            "Duplicate item_ids detected in assignment_map"
        )

    def test_invariant_leaders_match_min_member_ids(
        self,
    ) -> None:
        """For each cluster, leader == min(member_ids for that cluster).

        This invariant ensures deterministic cluster_id assignment.
        The leader is always the lexicographically smallest member_id.
        """
        # Create features that will form distinct clusters with varied item_ids
        features = [
            # Group 1: Will cluster together (similar features)
            make_features(
                item_id="zulu-node-001",
                keywords=("group-alpha", "shared"),
                pattern_indicators=("NodeCompute",),
                labels=("compute",),
            ),
            make_features(
                item_id="alpha-node-002",
                keywords=("group-alpha", "shared"),
                pattern_indicators=("NodeCompute",),
                labels=("compute",),
            ),
            make_features(
                item_id="mike-node-003",
                keywords=("group-alpha", "shared"),
                pattern_indicators=("NodeCompute",),
                labels=("compute",),
            ),
            # Group 2: Will cluster together (different from group 1)
            make_features(
                item_id="yankee-effect-001",
                keywords=("group-beta", "network"),
                pattern_indicators=("NodeEffect",),
                labels=("effect",),
            ),
            make_features(
                item_id="bravo-effect-002",
                keywords=("group-beta", "network"),
                pattern_indicators=("NodeEffect",),
                labels=("effect",),
            ),
        ]

        emitter = MagicMock()
        cluster_patterns(features, threshold=0.5, replay_emitter=emitter)

        # Extract replay artifact
        payload = emitter.emit.call_args[0][1]
        assignment_map = payload["cluster_assignment_map"]
        cluster_leaders = payload["cluster_leaders"]

        # Invert assignment_map to get members per cluster
        members_by_cluster: dict[str, list[str]] = {}
        for item_id, cluster_id in assignment_map.items():
            if cluster_id not in members_by_cluster:
                members_by_cluster[cluster_id] = []
            members_by_cluster[cluster_id].append(item_id)

        # Verify invariant: leader == min(members) for each cluster
        for cluster_id, members in members_by_cluster.items():
            expected_leader = min(members)
            actual_leader = cluster_leaders[cluster_id]

            assert actual_leader == expected_leader, (
                f"Cluster {cluster_id}: leader '{actual_leader}' is not the "
                f"minimum member_id. Expected '{expected_leader}'. "
                f"Full members: {sorted(members)}"
            )

    def test_invariant_assignment_cluster_ids_exist_in_leaders(
        self,
    ) -> None:
        """All cluster_ids in assignment_map values exist as keys in leaders map.

        This invariant ensures referential integrity between the two maps.
        Every cluster referenced in assignment_map must have a corresponding
        leader defined in cluster_leaders.
        """
        # Create features with various clustering behavior
        features = [
            make_features(
                item_id=f"item-{i}",
                keywords=(f"unique-{i}",) if i % 2 == 0 else ("shared", "common"),
                pattern_indicators=("Type-A",) if i < 3 else ("Type-B",),
                labels=(f"label-{i % 3}",),
            )
            for i in range(8)
        ]

        emitter = MagicMock()
        cluster_patterns(features, threshold=0.5, replay_emitter=emitter)

        # Extract replay artifact
        payload = emitter.emit.call_args[0][1]
        assignment_map = payload["cluster_assignment_map"]
        cluster_leaders = payload["cluster_leaders"]

        # Collect all unique cluster_ids from assignment_map
        assigned_cluster_ids = set(assignment_map.values())

        # Collect all cluster_ids from leaders map
        leader_cluster_ids = set(cluster_leaders.keys())

        # Invariant: Every cluster_id in assignment_map exists in cluster_leaders
        assert assigned_cluster_ids == leader_cluster_ids, (
            f"Cluster ID mismatch. "
            f"In assignment but not in leaders: {assigned_cluster_ids - leader_cluster_ids}, "
            f"In leaders but not in assignment: {leader_cluster_ids - assigned_cluster_ids}"
        )

        # Additional verification: All cluster_ids follow the expected format
        for cluster_id in assigned_cluster_ids:
            assert cluster_id.startswith("cluster-"), (
                f"Invalid cluster_id format: '{cluster_id}'"
            )
            # Verify 4-digit padding: cluster-0001, cluster-0002, etc.
            suffix = cluster_id[8:]
            assert len(suffix) == 4 and suffix.isdigit(), (
                f"Cluster ID should have 4-digit suffix, got: '{cluster_id}'"
            )

    def test_golden_dataset_exact_assignment(
        self,
    ) -> None:
        """Golden input produces exact expected cluster assignments.

        This test uses a deterministic dataset with known similarity
        characteristics to verify exact clustering behavior:
        - "item-a" and "item-b" have identical features (should cluster together)
        - "item-c" has completely different features (should be separate)

        The exact cluster_ids depend on the leader sorting, so:
        - "item-a" < "item-b" means "item-a" is leader of their cluster
        - "item-c" is alone, so it is its own leader
        - Since "item-a" < "item-c", the cluster with "item-a" gets cluster-0001
        - The cluster with "item-c" gets cluster-0002
        """
        # Create deterministic features with known similarity
        # item-a and item-b: Identical features (will cluster together)
        features_a = make_features(
            item_id="item-a",
            keywords=("identical", "features", "pair"),
            pattern_indicators=("NodeCompute", "frozen"),
            labels=("compute", "pure"),
            class_count=2,
            function_count=5,
            max_nesting_depth=3,
            line_count=100,
            cyclomatic_complexity=8,
            has_type_hints=True,
            has_docstrings=True,
        )
        features_b = make_features(
            item_id="item-b",
            keywords=("identical", "features", "pair"),
            pattern_indicators=("NodeCompute", "frozen"),
            labels=("compute", "pure"),
            class_count=2,
            function_count=5,
            max_nesting_depth=3,
            line_count=100,
            cyclomatic_complexity=8,
            has_type_hints=True,
            has_docstrings=True,
        )

        # item-c: Completely different features (will be separate)
        features_c = make_features(
            item_id="item-c",
            keywords=("completely", "different", "keywords"),
            pattern_indicators=("NodeEffect", "async"),
            labels=("effect", "io"),
            class_count=0,
            function_count=15,
            max_nesting_depth=6,
            line_count=300,
            cyclomatic_complexity=20,
            has_type_hints=False,
            has_docstrings=False,
        )

        emitter = MagicMock()
        result = cluster_patterns(
            [features_a, features_b, features_c],
            threshold=0.5,
            replay_emitter=emitter,
        )

        # Verify we got 2 clusters
        assert len(result) == 2, f"Expected 2 clusters, got {len(result)}"

        # Extract replay artifact
        payload = emitter.emit.call_args[0][1]
        assignment_map = payload["cluster_assignment_map"]
        cluster_leaders = payload["cluster_leaders"]

        # Verify exact cluster_assignment_map
        # item-a and item-b should be in cluster-0001 (leader is "item-a")
        # item-c should be in cluster-0002 (leader is "item-c")
        expected_assignment_map = {
            "item-a": "cluster-0001",
            "item-b": "cluster-0001",
            "item-c": "cluster-0002",
        }

        assert assignment_map == expected_assignment_map, (
            f"Assignment map mismatch.\n"
            f"Expected: {expected_assignment_map}\n"
            f"Actual: {assignment_map}"
        )

        # Verify exact cluster_leaders
        expected_leaders = {
            "cluster-0001": "item-a",  # min("item-a", "item-b") = "item-a"
            "cluster-0002": "item-c",  # only member
        }

        assert cluster_leaders == expected_leaders, (
            f"Cluster leaders mismatch.\n"
            f"Expected: {expected_leaders}\n"
            f"Actual: {cluster_leaders}"
        )
