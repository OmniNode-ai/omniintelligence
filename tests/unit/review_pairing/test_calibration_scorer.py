# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Calibration Scorer.

Reference: OMN-6168 (epic OMN-6164)
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.models_calibration import (
    CalibrationFindingTuple,
    FindingAlignment,
)


def _make_finding(model: str = "codex") -> CalibrationFindingTuple:
    return CalibrationFindingTuple(
        category="architecture",
        location="Task 1",
        description="Test finding",
        severity="error",
        source_model=model,
    )


def _make_tp() -> FindingAlignment:
    return FindingAlignment(
        ground_truth=_make_finding("codex"),
        challenger=_make_finding("deepseek-r1"),
        similarity_score=0.9,
        aligned=True,
        alignment_type="true_positive",
    )


def _make_fn() -> FindingAlignment:
    return FindingAlignment(
        ground_truth=_make_finding("codex"),
        challenger=None,
        similarity_score=0.0,
        aligned=False,
        alignment_type="false_negative",
    )


def _make_fp() -> FindingAlignment:
    return FindingAlignment(
        ground_truth=None,
        challenger=_make_finding("deepseek-r1"),
        similarity_score=0.0,
        aligned=False,
        alignment_type="false_positive",
    )


@pytest.mark.unit
class TestCalibrationScorer:
    @pytest.fixture
    def scorer(self) -> CalibrationScorer:
        return CalibrationScorer()

    def test_perfect_challenger(self, scorer: CalibrationScorer) -> None:
        alignments = [_make_tp() for _ in range(10)]
        m = scorer.score(
            alignments, ground_truth_count=10, challenger_count=10, model="deepseek-r1"
        )
        assert m.true_positives == 10
        assert m.false_positives == 0
        assert m.false_negatives == 0
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1_score == 1.0
        assert m.noise_ratio == 0.0

    def test_noisy_challenger(self, scorer: CalibrationScorer) -> None:
        alignments = [_make_tp() for _ in range(3)] + [_make_fp() for _ in range(7)]
        m = scorer.score(
            alignments, ground_truth_count=5, challenger_count=10, model="deepseek-r1"
        )
        assert m.true_positives == 3
        assert m.false_positives == 7
        assert m.false_negatives == 2
        assert m.precision == pytest.approx(0.3, abs=0.01)
        assert m.noise_ratio == pytest.approx(0.7, abs=0.01)

    def test_empty_challenger(self, scorer: CalibrationScorer) -> None:
        m = scorer.score(
            [], ground_truth_count=5, challenger_count=0, model="deepseek-r1"
        )
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1_score == 0.0
        assert m.noise_ratio == 0.0

    def test_empty_ground_truth(self, scorer: CalibrationScorer) -> None:
        alignments = [_make_fp() for _ in range(5)]
        m = scorer.score(
            alignments, ground_truth_count=0, challenger_count=5, model="deepseek-r1"
        )
        assert m.true_positives == 0
        assert m.false_positives == 5
        assert m.precision == 0.0
        assert m.noise_ratio == 1.0

    def test_partial_coverage(self, scorer: CalibrationScorer) -> None:
        alignments = [_make_tp() for _ in range(5)] + [_make_fn() for _ in range(5)]
        m = scorer.score(
            alignments, ground_truth_count=10, challenger_count=5, model="deepseek-r1"
        )
        assert m.true_positives == 5
        assert m.false_negatives == 5
        assert m.recall == pytest.approx(0.5, abs=0.01)
        assert m.precision == 1.0
