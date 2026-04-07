# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for CalibrationScorer.

TDD: Tests written first for OMN-6168.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationFindingTuple,
    ModelFindingAlignment,
)


def _make_finding(source: str = "codex") -> ModelCalibrationFindingTuple:
    return ModelCalibrationFindingTuple(
        category="architecture",
        location="file.py",
        description="Issue",
        severity="error",
        source_model=source,
        finding_id=uuid4(),
        raw_finding=None,
    )


def _make_tp() -> ModelFindingAlignment:
    return ModelFindingAlignment(
        ground_truth=_make_finding("codex"),
        challenger=_make_finding("deepseek-r1"),
        similarity_score=0.9,
        aligned=True,
        alignment_type="true_positive",
        embedding_model_version="jaccard-v1",
    )


def _make_fp() -> ModelFindingAlignment:
    return ModelFindingAlignment(
        ground_truth=None,
        challenger=_make_finding("deepseek-r1"),
        similarity_score=0.0,
        aligned=False,
        alignment_type="false_positive",
        embedding_model_version="jaccard-v1",
    )


def _make_fn() -> ModelFindingAlignment:
    return ModelFindingAlignment(
        ground_truth=_make_finding("codex"),
        challenger=None,
        similarity_score=0.0,
        aligned=False,
        alignment_type="false_negative",
        embedding_model_version="jaccard-v1",
    )


@pytest.mark.unit
class TestCalibrationScorer:
    """Tests for CalibrationScorer."""

    def test_perfect_challenger(self) -> None:
        scorer = CalibrationScorer()
        alignments = [_make_tp(), _make_tp(), _make_tp()]
        metrics = scorer.score(alignments, "deepseek-r1")
        assert metrics.true_positives == 3
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.precision == pytest.approx(1.0)
        assert metrics.recall == pytest.approx(1.0)
        assert metrics.f1_score == pytest.approx(1.0)
        assert metrics.noise_ratio == pytest.approx(0.0)

    def test_noisy_challenger(self) -> None:
        scorer = CalibrationScorer()
        alignments = [_make_tp(), _make_fp(), _make_fp(), _make_fp()]
        metrics = scorer.score(alignments, "deepseek-r1")
        assert metrics.true_positives == 1
        assert metrics.false_positives == 3
        assert metrics.precision == pytest.approx(0.25)
        assert metrics.noise_ratio == pytest.approx(0.75)

    def test_empty_challenger(self) -> None:
        scorer = CalibrationScorer()
        alignments = [_make_fn(), _make_fn()]
        metrics = scorer.score(alignments, "deepseek-r1")
        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 2
        assert metrics.precision == pytest.approx(0.0)
        assert metrics.recall == pytest.approx(0.0)
        assert metrics.f1_score == pytest.approx(0.0)

    def test_mixed_results(self) -> None:
        scorer = CalibrationScorer()
        alignments = [
            _make_tp(),
            _make_tp(),
            _make_tp(),  # 3 TP
            _make_fp(),
            _make_fp(),  # 2 FP
            _make_fn(),  # 1 FN
        ]
        metrics = scorer.score(alignments, "deepseek-r1")
        assert metrics.true_positives == 3
        assert metrics.false_positives == 2
        assert metrics.false_negatives == 1
        assert metrics.precision == pytest.approx(3 / 5)
        assert metrics.recall == pytest.approx(3 / 4)
        assert metrics.noise_ratio == pytest.approx(2 / 5)

    def test_no_alignments(self) -> None:
        scorer = CalibrationScorer()
        metrics = scorer.score([], "deepseek-r1")
        assert metrics.true_positives == 0
        assert metrics.precision == pytest.approx(0.0)
        assert metrics.recall == pytest.approx(0.0)
        assert metrics.f1_score == pytest.approx(0.0)

    def test_model_name_set(self) -> None:
        scorer = CalibrationScorer()
        metrics = scorer.score([_make_tp()], "qwen3-coder")
        assert metrics.model == "qwen3-coder"
