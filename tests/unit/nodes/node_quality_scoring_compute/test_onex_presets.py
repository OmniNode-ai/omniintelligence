# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ONEX strictness preset functionality.

This module tests the preset system for ONEX compliance:
    - Preset weight configurations
    - Preset thresholds
    - Preset override behavior
    - Preset validation
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    DEFAULT_WEIGHTS,
    LENIENT_THRESHOLD,
    LENIENT_WEIGHTS,
    STANDARD_THRESHOLD,
    STANDARD_WEIGHTS,
    STRICT_THRESHOLD,
    STRICT_WEIGHTS,
    OnexStrictnessLevel,
    get_threshold_for_preset,
    get_weights_for_preset,
    score_code_quality,
)


class TestOnexPresets:
    """Tests for ONEX strictness preset functionality."""

    def test_strict_preset_uses_correct_weights(self) -> None:
        """STRICT preset should apply higher weights to documentation and patterns."""
        weights = get_weights_for_preset(OnexStrictnessLevel.STRICT)

        assert weights == STRICT_WEIGHTS
        assert weights["documentation"] == 0.20
        assert weights["patterns"] == 0.20
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_standard_preset_uses_correct_weights(self) -> None:
        """STANDARD preset should apply balanced weights."""
        weights = get_weights_for_preset(OnexStrictnessLevel.STANDARD)

        assert weights == STANDARD_WEIGHTS
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_lenient_preset_uses_correct_weights(self) -> None:
        """LENIENT preset should apply more forgiving weights."""
        weights = get_weights_for_preset(OnexStrictnessLevel.LENIENT)

        assert weights == LENIENT_WEIGHTS
        assert weights["complexity"] == 0.25  # Higher tolerance
        assert weights["documentation"] == 0.10  # Lower requirement
        assert weights["patterns"] == 0.10  # Lower requirement
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_strict_preset_uses_correct_threshold(self) -> None:
        """STRICT preset should use 0.8 threshold."""
        threshold = get_threshold_for_preset(OnexStrictnessLevel.STRICT)

        assert threshold == STRICT_THRESHOLD
        assert threshold == 0.8

    def test_standard_preset_uses_correct_threshold(self) -> None:
        """STANDARD preset should use 0.7 threshold."""
        threshold = get_threshold_for_preset(OnexStrictnessLevel.STANDARD)

        assert threshold == STANDARD_THRESHOLD
        assert threshold == 0.7

    def test_lenient_preset_uses_correct_threshold(self) -> None:
        """LENIENT preset should use 0.5 threshold."""
        threshold = get_threshold_for_preset(OnexStrictnessLevel.LENIENT)

        assert threshold == LENIENT_THRESHOLD
        assert threshold == 0.5

    def test_preset_overrides_manual_weights(self) -> None:
        """Preset should override manually provided weights."""
        code = "def process(): pass"

        # Custom weights that heavily favor documentation
        custom_weights = {
            "complexity": 0.05,
            "maintainability": 0.05,
            "documentation": 0.70,
            "temporal_relevance": 0.05,
            "patterns": 0.05,
            "architectural": 0.10,
        }

        # Without preset - uses custom weights
        result_custom = score_code_quality(code, "python", weights=custom_weights)

        # With preset - should override custom weights
        result_preset = score_code_quality(
            code, "python", weights=custom_weights, preset=OnexStrictnessLevel.STANDARD
        )

        # Scores should be different because preset overrides custom weights
        assert result_custom["quality_score"] != result_preset["quality_score"]

    def test_preset_overrides_manual_threshold(self) -> None:
        """Preset should override manually provided threshold."""
        # Medium quality code
        code = '''
class Example:
    """Example class."""
    def method(self) -> int:
        return 42
'''

        # With LENIENT preset (threshold 0.5) - should be compliant
        result_lenient = score_code_quality(
            code, "python", onex_threshold=0.95, preset=OnexStrictnessLevel.LENIENT
        )

        # With STRICT preset (threshold 0.8) - threshold from preset overrides 0.95
        result_strict = score_code_quality(
            code, "python", onex_threshold=0.1, preset=OnexStrictnessLevel.STRICT
        )

        # LENIENT uses 0.5 threshold regardless of onex_threshold=0.95
        # STRICT uses 0.8 threshold regardless of onex_threshold=0.1
        # Verify compliance is determined by preset thresholds (not manual overrides)
        assert result_lenient["onex_compliant"] == (
            result_lenient["quality_score"] >= 0.5
        )
        assert result_strict["onex_compliant"] == (
            result_strict["quality_score"] >= 0.8
        )

    def test_different_presets_produce_different_scores(self) -> None:
        """Same code should produce different scores with different presets."""
        # Code with decent structure but minimal documentation
        code = """
class DataProcessor:
    def process(self, data: dict) -> list:
        return list(data.values())
"""

        result_strict = score_code_quality(
            code, "python", preset=OnexStrictnessLevel.STRICT
        )
        result_standard = score_code_quality(
            code, "python", preset=OnexStrictnessLevel.STANDARD
        )
        result_lenient = score_code_quality(
            code, "python", preset=OnexStrictnessLevel.LENIENT
        )

        # Different presets have different weights, so scores should differ
        scores = {
            result_strict["quality_score"],
            result_standard["quality_score"],
            result_lenient["quality_score"],
        }

        # At least two presets should produce different scores for this code
        assert len(scores) >= 2

    def test_no_preset_uses_defaults(self) -> None:
        """Without preset, default weights and threshold should be used."""
        code = "x = 1"

        result_no_preset = score_code_quality(code, "python")
        result_explicit_default = score_code_quality(
            code, "python", weights=DEFAULT_WEIGHTS, onex_threshold=0.7
        )

        # Should produce identical results
        assert (
            result_no_preset["quality_score"]
            == result_explicit_default["quality_score"]
        )
        assert result_no_preset["dimensions"] == result_explicit_default["dimensions"]

    def test_preset_with_unsupported_language(self) -> None:
        """Preset should still work (for threshold) with unsupported languages."""
        code = 'fn main() { println!("Hello"); }'

        result_strict = score_code_quality(
            code, "rust", preset=OnexStrictnessLevel.STRICT
        )
        result_lenient = score_code_quality(
            code, "rust", preset=OnexStrictnessLevel.LENIENT
        )

        # Both get baseline 0.5 score for unsupported language
        assert result_strict["quality_score"] == 0.5
        assert result_lenient["quality_score"] == 0.5

        # But compliance differs based on preset threshold
        # STRICT threshold is 0.8, LENIENT is 0.5
        assert result_strict["onex_compliant"] is False  # 0.5 < 0.8
        assert result_lenient["onex_compliant"] is True  # 0.5 >= 0.5

    def test_preset_returns_copied_weights(self) -> None:
        """get_weights_for_preset should return a copy, not the original dict."""
        weights = get_weights_for_preset(OnexStrictnessLevel.STRICT)

        # Should be equal but not the same object
        assert weights == STRICT_WEIGHTS
        assert weights is not STRICT_WEIGHTS

    def test_all_preset_weights_sum_to_one(self) -> None:
        """All preset weight configurations must sum to exactly 1.0."""
        for level in OnexStrictnessLevel:
            weights = get_weights_for_preset(level)
            total = sum(weights.values())
            assert total == pytest.approx(1.0), f"{level.value} weights sum to {total}"

    def test_all_presets_have_valid_thresholds(self) -> None:
        """All preset thresholds must be in valid range [0.0, 1.0]."""
        for level in OnexStrictnessLevel:
            threshold = get_threshold_for_preset(level)
            assert 0.0 <= threshold <= 1.0, (
                f"{level.value} threshold {threshold} out of range"
            )

    def test_strictness_level_string_values(self) -> None:
        """OnexStrictnessLevel enum should have expected string values."""
        assert OnexStrictnessLevel.STRICT.value == "strict"
        assert OnexStrictnessLevel.STANDARD.value == "standard"
        assert OnexStrictnessLevel.LENIENT.value == "lenient"

    def test_preset_in_score_code_quality_signature(self) -> None:
        """score_code_quality should accept preset parameter."""
        # This should not raise any errors
        result = score_code_quality(
            content="x = 1",
            language="python",
            preset=OnexStrictnessLevel.STANDARD,
        )

        assert result["success"] is True
