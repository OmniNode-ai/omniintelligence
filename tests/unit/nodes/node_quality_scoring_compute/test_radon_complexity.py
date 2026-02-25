"""Unit tests for radon-based complexity scoring (OMN-1452).

Tests the optional radon integration for accurate McCabe cyclomatic complexity
scoring in the quality_scoring_compute node. Covers:
  - _mccabe_to_score grade-band interpolation
  - _compute_radon_complexity_score with real radon output
  - radon_available() introspection helper
  - score_code_quality radon_complexity_enabled metadata field
  - Fallback behaviour when radon is patched away (simulates missing install)
"""

from __future__ import annotations

from typing import Final
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# Helpers / constants
# ============================================================================

_SIMPLE_CODE: Final[str] = """
def add(a: int, b: int) -> int:
    return a + b
"""

# Complexity ~4 per function (for, if, if, if = 4 branches)
_MODERATE_CODE: Final[str] = """
def process(data: list[int]) -> int:
    result = 0
    for item in data:
        if item > 0:
            if item < 100:
                result += item
    return result
"""

# High complexity — many branches per function
_COMPLEX_CODE: Final[str] = """
def evaluate(x: int) -> str:
    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    elif x < 10:
        if x % 2 == 0:
            return "small even"
        elif x % 3 == 0:
            return "small multiple of 3"
        else:
            return "small odd"
    elif x < 100:
        for i in range(x):
            if i % 7 == 0:
                return "multiple of 7 found"
        return "medium"
    else:
        try:
            result = x / (x - 50)
            if result > 2:
                return "large high ratio"
            return "large"
        except ZeroDivisionError:
            return "exactly 50"
"""


# ============================================================================
# _mccabe_to_score tests
# ============================================================================


class TestMccabeToScore:
    """Tests for _mccabe_to_score grade-band interpolation."""

    def test_complexity_1_returns_1(self) -> None:
        """Complexity of 1 (no branches) should yield perfect score 1.0."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _mccabe_to_score,
        )

        assert _mccabe_to_score(1.0) == 1.0

    def test_complexity_below_1_returns_1(self) -> None:
        """Complexity <= 1 is trivially simple — score is 1.0."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _mccabe_to_score,
        )

        assert _mccabe_to_score(0.5) == 1.0

    def test_grade_a_boundary_5_returns_grade_a_min(self) -> None:
        """Complexity 5 (top of grade A) should return RADON_GRADE_A_SCORE_MIN (0.8)."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            RADON_GRADE_A_SCORE_MIN,
            _mccabe_to_score,
        )

        score = _mccabe_to_score(5.0)
        assert abs(score - RADON_GRADE_A_SCORE_MIN) < 0.001

    def test_grade_b_boundary_10_returns_grade_b_min(self) -> None:
        """Complexity 10 (top of grade B) should return RADON_GRADE_B_SCORE_MIN (0.5)."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            RADON_GRADE_B_SCORE_MIN,
            _mccabe_to_score,
        )

        score = _mccabe_to_score(10.0)
        assert abs(score - RADON_GRADE_B_SCORE_MIN) < 0.001

    def test_grade_c_boundary_15_returns_grade_c_min(self) -> None:
        """Complexity 15 (top of grade C) should return RADON_GRADE_C_SCORE_MIN (0.2)."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            RADON_GRADE_C_SCORE_MIN,
            _mccabe_to_score,
        )

        score = _mccabe_to_score(15.0)
        assert abs(score - RADON_GRADE_C_SCORE_MIN) < 0.001

    def test_very_high_complexity_approaches_zero(self) -> None:
        """Very high complexity (30+) should return close to 0.0."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _mccabe_to_score,
        )

        score = _mccabe_to_score(30.0)
        assert score >= 0.0, "Score must not go negative"
        assert score <= 0.1, f"Complexity 30 should be near 0, got {score}"

    def test_score_is_monotonically_decreasing(self) -> None:
        """Higher complexity must always yield a lower or equal score."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _mccabe_to_score,
        )

        previous_score = 1.0
        for cc in range(1, 25):
            score = _mccabe_to_score(float(cc))
            assert score <= previous_score + 0.001, (
                f"Score increased from cc={cc - 1} to cc={cc}: "
                f"{previous_score:.4f} -> {score:.4f}"
            )
            previous_score = score

    def test_score_always_in_valid_range(self) -> None:
        """All scores must be in [0.0, 1.0]."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _mccabe_to_score,
        )

        for cc in [0.5, 1, 3, 5, 7, 10, 12, 15, 20, 25, 50]:
            score = _mccabe_to_score(float(cc))
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for cc={cc}"


# ============================================================================
# _compute_radon_complexity_score tests
# ============================================================================


class TestComputeRadonComplexityScore:
    """Tests for _compute_radon_complexity_score (requires radon installed)."""

    def test_simple_code_scores_near_1(self) -> None:
        """Single simple function should score close to 1.0."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _compute_radon_complexity_score,
        )

        score = _compute_radon_complexity_score(_SIMPLE_CODE)
        assert score >= 0.8, f"Simple code should score >= 0.8, got {score}"

    def test_complex_code_scores_lower_than_simple(self) -> None:
        """Complex code should score lower than simple code."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _compute_radon_complexity_score,
        )

        simple_score = _compute_radon_complexity_score(_SIMPLE_CODE)
        complex_score = _compute_radon_complexity_score(_COMPLEX_CODE)
        assert complex_score < simple_score, (
            f"Complex code ({complex_score:.4f}) should score lower "
            f"than simple code ({simple_score:.4f})"
        )

    def test_empty_code_returns_1(self) -> None:
        """Code with no functions returns perfect score (no complexity)."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _compute_radon_complexity_score,
        )

        score = _compute_radon_complexity_score("x = 1\ny = 2\n")
        assert score == 1.0

    def test_radon_exception_returns_neutral_score(self) -> None:
        """If radon raises unexpectedly, neutral score 0.5 is returned."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            NO_FUNCTIONS_NEUTRAL_SCORE,
            _compute_radon_complexity_score,
        )

        with patch(
            "omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring.cc_visit",
            side_effect=RuntimeError("radon internal error"),
        ):
            score = _compute_radon_complexity_score(_SIMPLE_CODE)
            assert score == NO_FUNCTIONS_NEUTRAL_SCORE

    def test_score_in_valid_range(self) -> None:
        """Score must always be in [0.0, 1.0]."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
            _compute_radon_complexity_score,
        )

        for code in [_SIMPLE_CODE, _MODERATE_CODE, _COMPLEX_CODE]:
            score = _compute_radon_complexity_score(code)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range"


# ============================================================================
# radon_available() introspection helper tests
# ============================================================================


class TestRadonAvailable:
    """Tests for the radon_available() public helper."""

    def test_returns_bool(self) -> None:
        """radon_available() always returns a bool."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            radon_available,
        )

        assert isinstance(radon_available(), bool)

    def test_returns_true_when_radon_installed(self) -> None:
        """In this test environment radon is installed — should return True."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            radon_available,
        )

        # radon is in the dev dependency group; it should be present in CI/CD
        assert radon_available() is True, (
            "radon is expected to be installed in the dev environment. "
            "If this fails, add 'radon' to [dependency-groups].dev in pyproject.toml."
        )

    def test_returns_false_when_radon_unavailable(self) -> None:
        """When _RADON_AVAILABLE is patched to False, radon_available() returns False."""
        import omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring as mod

        original = mod._RADON_AVAILABLE
        try:
            mod._RADON_AVAILABLE = False  # type: ignore[assignment]
            from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
                radon_available,
            )

            assert radon_available() is False
        finally:
            mod._RADON_AVAILABLE = original  # type: ignore[assignment]


# ============================================================================
# score_code_quality radon integration tests
# ============================================================================


class TestScoreCodeQualityRadonIntegration:
    """Tests for radon integration in score_code_quality."""

    def test_radon_complexity_enabled_key_present(self) -> None:
        """score_code_quality result includes radon_complexity_enabled key."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            score_code_quality,
        )

        result = score_code_quality("def foo(): pass", "python")
        assert "radon_complexity_enabled" in result

    def test_radon_complexity_enabled_is_bool(self) -> None:
        """radon_complexity_enabled must be a bool."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            score_code_quality,
        )

        result = score_code_quality("x = 1", "python")
        assert isinstance(result.get("radon_complexity_enabled"), bool)

    def test_radon_complexity_enabled_true_when_radon_present(self) -> None:
        """When radon is installed, radon_complexity_enabled should be True."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            score_code_quality,
        )

        result = score_code_quality("def foo(): pass", "python")
        assert result.get("radon_complexity_enabled") is True

    def test_radon_complexity_enabled_false_when_radon_absent(self) -> None:
        """When _RADON_AVAILABLE is False, radon_complexity_enabled is False."""
        import omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring as mod

        original = mod._RADON_AVAILABLE
        try:
            mod._RADON_AVAILABLE = False  # type: ignore[assignment]
            from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
                score_code_quality,
            )

            result = score_code_quality("def foo(): pass", "python")
            assert result.get("radon_complexity_enabled") is False
        finally:
            mod._RADON_AVAILABLE = original  # type: ignore[assignment]

    def test_complexity_score_higher_for_simple_code(self) -> None:
        """Simple code must score higher on complexity dimension than complex code."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            score_code_quality,
        )

        simple_result = score_code_quality(_SIMPLE_CODE, "python")
        complex_result = score_code_quality(_COMPLEX_CODE, "python")

        simple_score = simple_result["dimensions"]["complexity"]
        complex_score = complex_result["dimensions"]["complexity"]

        assert simple_score > complex_score, (
            f"Simple code complexity score ({simple_score:.4f}) must be "
            f"higher than complex code ({complex_score:.4f})"
        )

    def test_analysis_version_updated_to_1_2_0(self) -> None:
        """ANALYSIS_VERSION should reflect OMN-1452 radon integration (1.2.0)."""
        from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
            ANALYSIS_VERSION,
        )

        assert str(ANALYSIS_VERSION) == "1.2.0", (
            f"Expected ANALYSIS_VERSION 1.2.0 after OMN-1452, got {ANALYSIS_VERSION}"
        )
