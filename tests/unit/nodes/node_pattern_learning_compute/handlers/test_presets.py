# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for pattern learning preset constants.

This module tests the default configuration presets for pattern learning:
    - SIGNATURE_VERSION: Signature algorithm version
    - SIGNATURE_NORMALIZATION: Normalization method description
    - DEFAULT_SIMILARITY_WEIGHTS: 5-component similarity weights
    - Clustering and promotion thresholds
    - ONEX pattern detection constants
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_CLUSTERING_THRESHOLD,
    DEFAULT_DEDUPLICATION_THRESHOLD,
    DEFAULT_MIN_FREQUENCY,
    DEFAULT_PROMOTION_THRESHOLD,
    DEFAULT_SIMILARITY_WEIGHTS,
    NEAR_THRESHOLD_MARGIN,
    ONEX_BASE_CLASSES,
    ONEX_PATTERN_KEYWORDS,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
)


# =============================================================================
# Signature Versioning Tests
# =============================================================================


@pytest.mark.unit
class TestSignatureVersioning:
    """Tests for signature versioning constants."""

    def test_signature_version_is_string(self) -> None:
        """SIGNATURE_VERSION should be a string."""
        assert isinstance(SIGNATURE_VERSION, str)

    def test_signature_version_follows_semver_format(self) -> None:
        """SIGNATURE_VERSION should follow semantic versioning format."""
        import re

        # Pattern: vX.Y.Z where X, Y, Z are non-negative integers
        semver_pattern = r"^v\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, SIGNATURE_VERSION), \
            f"SIGNATURE_VERSION '{SIGNATURE_VERSION}' does not match vX.Y.Z format"

    def test_signature_version_is_v1(self) -> None:
        """Current SIGNATURE_VERSION should be v1.0.0."""
        assert SIGNATURE_VERSION == "v1.0.0"

    def test_signature_normalization_is_string(self) -> None:
        """SIGNATURE_NORMALIZATION should be a string."""
        assert isinstance(SIGNATURE_NORMALIZATION, str)

    def test_signature_normalization_describes_method(self) -> None:
        """SIGNATURE_NORMALIZATION should describe the normalization steps."""
        # Should contain key normalization terms
        assert "lowercase" in SIGNATURE_NORMALIZATION.lower()
        assert "sort" in SIGNATURE_NORMALIZATION.lower()
        assert "dedupe" in SIGNATURE_NORMALIZATION.lower()

    def test_signature_normalization_value(self) -> None:
        """SIGNATURE_NORMALIZATION should have expected value."""
        assert SIGNATURE_NORMALIZATION == "lowercase_sort_dedupe"


# =============================================================================
# Similarity Weights Tests
# =============================================================================


@pytest.mark.unit
class TestSimilarityWeights:
    """Tests for DEFAULT_SIMILARITY_WEIGHTS constant."""

    def test_weights_sum_to_one(self) -> None:
        """All similarity weights must sum to exactly 1.0."""
        total = sum(DEFAULT_SIMILARITY_WEIGHTS.values())
        assert total == pytest.approx(1.0), \
            f"Weights sum to {total}, expected 1.0"

    def test_has_all_required_keys(self) -> None:
        """DEFAULT_SIMILARITY_WEIGHTS should have all 5 component keys."""
        required_keys = {"keyword", "pattern", "structural", "label", "context"}
        assert set(DEFAULT_SIMILARITY_WEIGHTS.keys()) == required_keys

    def test_keyword_weight(self) -> None:
        """Keyword weight should be 0.30 (highest priority)."""
        assert DEFAULT_SIMILARITY_WEIGHTS["keyword"] == 0.30

    def test_pattern_weight(self) -> None:
        """Pattern weight should be 0.25."""
        assert DEFAULT_SIMILARITY_WEIGHTS["pattern"] == 0.25

    def test_structural_weight(self) -> None:
        """Structural weight should be 0.20."""
        assert DEFAULT_SIMILARITY_WEIGHTS["structural"] == 0.20

    def test_label_weight(self) -> None:
        """Label weight should be 0.15."""
        assert DEFAULT_SIMILARITY_WEIGHTS["label"] == 0.15

    def test_context_weight(self) -> None:
        """Context weight should be 0.10 (lowest priority)."""
        assert DEFAULT_SIMILARITY_WEIGHTS["context"] == 0.10

    def test_all_weights_positive(self) -> None:
        """All weights should be positive."""
        for key, weight in DEFAULT_SIMILARITY_WEIGHTS.items():
            assert weight > 0, f"Weight for '{key}' is not positive: {weight}"

    def test_all_weights_at_most_one(self) -> None:
        """All individual weights should be at most 1.0."""
        for key, weight in DEFAULT_SIMILARITY_WEIGHTS.items():
            assert weight <= 1.0, f"Weight for '{key}' exceeds 1.0: {weight}"

    def test_weights_are_floats(self) -> None:
        """All weights should be float values."""
        for key, weight in DEFAULT_SIMILARITY_WEIGHTS.items():
            assert isinstance(weight, float), \
                f"Weight for '{key}' is not float: {type(weight)}"

    def test_weights_dict_is_not_empty(self) -> None:
        """DEFAULT_SIMILARITY_WEIGHTS should not be empty."""
        assert len(DEFAULT_SIMILARITY_WEIGHTS) > 0

    def test_weight_priorities_make_sense(self) -> None:
        """Weights should follow expected priority order."""
        # keyword > pattern > structural > label > context
        assert DEFAULT_SIMILARITY_WEIGHTS["keyword"] > DEFAULT_SIMILARITY_WEIGHTS["pattern"]
        assert DEFAULT_SIMILARITY_WEIGHTS["pattern"] > DEFAULT_SIMILARITY_WEIGHTS["structural"]
        assert DEFAULT_SIMILARITY_WEIGHTS["structural"] > DEFAULT_SIMILARITY_WEIGHTS["label"]
        assert DEFAULT_SIMILARITY_WEIGHTS["label"] > DEFAULT_SIMILARITY_WEIGHTS["context"]


# =============================================================================
# Clustering Threshold Tests
# =============================================================================


@pytest.mark.unit
class TestClusteringThresholds:
    """Tests for clustering threshold constants."""

    def test_clustering_threshold_in_valid_range(self) -> None:
        """DEFAULT_CLUSTERING_THRESHOLD should be in [0.0, 1.0]."""
        assert 0.0 <= DEFAULT_CLUSTERING_THRESHOLD <= 1.0

    def test_clustering_threshold_value(self) -> None:
        """DEFAULT_CLUSTERING_THRESHOLD should be 0.70."""
        assert DEFAULT_CLUSTERING_THRESHOLD == 0.70

    def test_deduplication_threshold_in_valid_range(self) -> None:
        """DEFAULT_DEDUPLICATION_THRESHOLD should be in [0.0, 1.0]."""
        assert 0.0 <= DEFAULT_DEDUPLICATION_THRESHOLD <= 1.0

    def test_deduplication_threshold_value(self) -> None:
        """DEFAULT_DEDUPLICATION_THRESHOLD should be 0.85."""
        assert DEFAULT_DEDUPLICATION_THRESHOLD == 0.85

    def test_deduplication_higher_than_clustering(self) -> None:
        """Deduplication threshold should be higher than clustering threshold.

        This ensures conservative merging - items that cluster together
        are not automatically considered duplicates.
        """
        assert DEFAULT_DEDUPLICATION_THRESHOLD > DEFAULT_CLUSTERING_THRESHOLD

    def test_near_threshold_margin_in_valid_range(self) -> None:
        """NEAR_THRESHOLD_MARGIN should be a small positive value."""
        assert 0.0 < NEAR_THRESHOLD_MARGIN < 0.5

    def test_near_threshold_margin_value(self) -> None:
        """NEAR_THRESHOLD_MARGIN should be 0.05."""
        assert NEAR_THRESHOLD_MARGIN == 0.05


# =============================================================================
# Promotion Threshold Tests
# =============================================================================


@pytest.mark.unit
class TestPromotionThresholds:
    """Tests for pattern promotion threshold constants."""

    def test_promotion_threshold_in_valid_range(self) -> None:
        """DEFAULT_PROMOTION_THRESHOLD should be in [0.0, 1.0]."""
        assert 0.0 <= DEFAULT_PROMOTION_THRESHOLD <= 1.0

    def test_promotion_threshold_value(self) -> None:
        """DEFAULT_PROMOTION_THRESHOLD should be 0.70."""
        assert DEFAULT_PROMOTION_THRESHOLD == 0.70

    def test_min_frequency_is_positive_integer(self) -> None:
        """DEFAULT_MIN_FREQUENCY should be a positive integer."""
        assert isinstance(DEFAULT_MIN_FREQUENCY, int)
        assert DEFAULT_MIN_FREQUENCY > 0

    def test_min_frequency_value(self) -> None:
        """DEFAULT_MIN_FREQUENCY should be 5."""
        assert DEFAULT_MIN_FREQUENCY == 5

    def test_min_frequency_reasonable(self) -> None:
        """DEFAULT_MIN_FREQUENCY should be reasonable for statistical confidence."""
        # At least 2 for any statistical meaning, but not too high
        assert 2 <= DEFAULT_MIN_FREQUENCY <= 100


# =============================================================================
# ONEX Pattern Detection Tests
# =============================================================================


@pytest.mark.unit
class TestOnexBaseClasses:
    """Tests for ONEX_BASE_CLASSES constant."""

    def test_is_frozenset(self) -> None:
        """ONEX_BASE_CLASSES should be a frozenset (immutable)."""
        assert isinstance(ONEX_BASE_CLASSES, frozenset)

    def test_not_empty(self) -> None:
        """ONEX_BASE_CLASSES should not be empty."""
        assert len(ONEX_BASE_CLASSES) > 0

    def test_contains_node_types(self) -> None:
        """ONEX_BASE_CLASSES should contain all four ONEX node types."""
        assert "NodeCompute" in ONEX_BASE_CLASSES
        assert "NodeEffect" in ONEX_BASE_CLASSES
        assert "NodeReducer" in ONEX_BASE_CLASSES
        assert "NodeOrchestrator" in ONEX_BASE_CLASSES

    def test_contains_base_model(self) -> None:
        """ONEX_BASE_CLASSES should contain Pydantic BaseModel."""
        assert "BaseModel" in ONEX_BASE_CLASSES

    def test_all_elements_are_strings(self) -> None:
        """All elements in ONEX_BASE_CLASSES should be strings."""
        for item in ONEX_BASE_CLASSES:
            assert isinstance(item, str), f"Non-string element: {item}"

    def test_no_empty_strings(self) -> None:
        """ONEX_BASE_CLASSES should not contain empty strings."""
        assert "" not in ONEX_BASE_CLASSES

    def test_expected_size(self) -> None:
        """ONEX_BASE_CLASSES should have exactly 5 elements."""
        assert len(ONEX_BASE_CLASSES) == 5


@pytest.mark.unit
class TestOnexPatternKeywords:
    """Tests for ONEX_PATTERN_KEYWORDS constant."""

    def test_is_frozenset(self) -> None:
        """ONEX_PATTERN_KEYWORDS should be a frozenset (immutable)."""
        assert isinstance(ONEX_PATTERN_KEYWORDS, frozenset)

    def test_not_empty(self) -> None:
        """ONEX_PATTERN_KEYWORDS should not be empty."""
        assert len(ONEX_PATTERN_KEYWORDS) > 0

    def test_contains_pydantic_config_keywords(self) -> None:
        """ONEX_PATTERN_KEYWORDS should contain Pydantic config keywords."""
        assert "frozen" in ONEX_PATTERN_KEYWORDS
        assert "extra" in ONEX_PATTERN_KEYWORDS
        assert "forbid" in ONEX_PATTERN_KEYWORDS
        assert "model_config" in ONEX_PATTERN_KEYWORDS
        assert "Field" in ONEX_PATTERN_KEYWORDS

    def test_contains_typing_keywords(self) -> None:
        """ONEX_PATTERN_KEYWORDS should contain typing-related keywords."""
        assert "TypedDict" in ONEX_PATTERN_KEYWORDS
        assert "Protocol" in ONEX_PATTERN_KEYWORDS
        assert "Final" in ONEX_PATTERN_KEYWORDS
        assert "ClassVar" in ONEX_PATTERN_KEYWORDS

    def test_all_elements_are_strings(self) -> None:
        """All elements in ONEX_PATTERN_KEYWORDS should be strings."""
        for item in ONEX_PATTERN_KEYWORDS:
            assert isinstance(item, str), f"Non-string element: {item}"

    def test_no_empty_strings(self) -> None:
        """ONEX_PATTERN_KEYWORDS should not contain empty strings."""
        assert "" not in ONEX_PATTERN_KEYWORDS

    def test_expected_size(self) -> None:
        """ONEX_PATTERN_KEYWORDS should have exactly 9 elements."""
        assert len(ONEX_PATTERN_KEYWORDS) == 9


# =============================================================================
# Immutability Tests
# =============================================================================


@pytest.mark.unit
class TestImmutability:
    """Tests verifying that preset constants are properly immutable."""

    def test_onex_base_classes_immutable(self) -> None:
        """ONEX_BASE_CLASSES cannot be modified (frozenset)."""
        with pytest.raises(AttributeError):
            ONEX_BASE_CLASSES.add("NewClass")  # type: ignore[attr-defined]

    def test_onex_pattern_keywords_immutable(self) -> None:
        """ONEX_PATTERN_KEYWORDS cannot be modified (frozenset)."""
        with pytest.raises(AttributeError):
            ONEX_PATTERN_KEYWORDS.add("newkeyword")  # type: ignore[attr-defined]

    def test_similarity_weights_is_typed_dict(self) -> None:
        """DEFAULT_SIMILARITY_WEIGHTS should follow SimilarityWeightsDict protocol."""
        # Verify it has the expected structure
        assert "keyword" in DEFAULT_SIMILARITY_WEIGHTS
        assert "pattern" in DEFAULT_SIMILARITY_WEIGHTS
        assert "structural" in DEFAULT_SIMILARITY_WEIGHTS
        assert "label" in DEFAULT_SIMILARITY_WEIGHTS
        assert "context" in DEFAULT_SIMILARITY_WEIGHTS


# =============================================================================
# Type Annotation Tests
# =============================================================================


@pytest.mark.unit
class TestTypeAnnotations:
    """Tests verifying type annotations are correct."""

    def test_signature_version_type(self) -> None:
        """SIGNATURE_VERSION should be str."""
        assert isinstance(SIGNATURE_VERSION, str)

    def test_signature_normalization_type(self) -> None:
        """SIGNATURE_NORMALIZATION should be str."""
        assert isinstance(SIGNATURE_NORMALIZATION, str)

    def test_clustering_threshold_type(self) -> None:
        """DEFAULT_CLUSTERING_THRESHOLD should be float."""
        assert isinstance(DEFAULT_CLUSTERING_THRESHOLD, float)

    def test_deduplication_threshold_type(self) -> None:
        """DEFAULT_DEDUPLICATION_THRESHOLD should be float."""
        assert isinstance(DEFAULT_DEDUPLICATION_THRESHOLD, float)

    def test_near_threshold_margin_type(self) -> None:
        """NEAR_THRESHOLD_MARGIN should be float."""
        assert isinstance(NEAR_THRESHOLD_MARGIN, float)

    def test_promotion_threshold_type(self) -> None:
        """DEFAULT_PROMOTION_THRESHOLD should be float."""
        assert isinstance(DEFAULT_PROMOTION_THRESHOLD, float)

    def test_min_frequency_type(self) -> None:
        """DEFAULT_MIN_FREQUENCY should be int."""
        assert isinstance(DEFAULT_MIN_FREQUENCY, int)

    def test_base_classes_type(self) -> None:
        """ONEX_BASE_CLASSES should be frozenset[str]."""
        assert isinstance(ONEX_BASE_CLASSES, frozenset)

    def test_pattern_keywords_type(self) -> None:
        """ONEX_PATTERN_KEYWORDS should be frozenset[str]."""
        assert isinstance(ONEX_PATTERN_KEYWORDS, frozenset)


# =============================================================================
# Module __all__ Export Tests
# =============================================================================


@pytest.mark.unit
class TestModuleExports:
    """Tests verifying module exports all expected constants."""

    def test_all_constants_importable(self) -> None:
        """All documented constants should be importable."""
        from omniintelligence.nodes.node_pattern_learning_compute.handlers import presets

        expected_exports = [
            "DEFAULT_CLUSTERING_THRESHOLD",
            "DEFAULT_DEDUPLICATION_THRESHOLD",
            "DEFAULT_MIN_FREQUENCY",
            "DEFAULT_PROMOTION_THRESHOLD",
            "DEFAULT_SIMILARITY_WEIGHTS",
            "NEAR_THRESHOLD_MARGIN",
            "ONEX_BASE_CLASSES",
            "ONEX_PATTERN_KEYWORDS",
            "SIGNATURE_NORMALIZATION",
            "SIGNATURE_VERSION",
        ]

        for name in expected_exports:
            assert hasattr(presets, name), f"Missing export: {name}"

    def test_exports_match_all(self) -> None:
        """Module __all__ should include all documented constants."""
        from omniintelligence.nodes.node_pattern_learning_compute.handlers import presets

        expected_exports = {
            "DEFAULT_CLUSTERING_THRESHOLD",
            "DEFAULT_DEDUPLICATION_THRESHOLD",
            "DEFAULT_MIN_FREQUENCY",
            "DEFAULT_PROMOTION_THRESHOLD",
            "DEFAULT_SIMILARITY_WEIGHTS",
            "NEAR_THRESHOLD_MARGIN",
            "ONEX_BASE_CLASSES",
            "ONEX_PATTERN_KEYWORDS",
            "SIGNATURE_NORMALIZATION",
            "SIGNATURE_VERSION",
        }

        assert set(presets.__all__) == expected_exports
