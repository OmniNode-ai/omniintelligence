# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for FewShotExtractor.

Covers:
- Empty runs → empty result
- Below min_runs_for_fewshot threshold → empty result
- TP examples ranked by similarity_score descending
- FP examples ranked by recurrence frequency descending
- Count limits respected
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.fewshot_extractor import FewShotExtractor
from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationConfig,
    ModelCalibrationFindingTuple,
    ModelCalibrationMetrics,
    ModelCalibrationRunResult,
    ModelFindingAlignment,
)


def _make_finding(
    *,
    category: str = "security",
    description: str = "test finding",
    source_model: str = "challenger-1",
    severity: str = "warning",
) -> ModelCalibrationFindingTuple:
    return ModelCalibrationFindingTuple(
        category=category,
        location="src/foo.py",
        description=description,
        severity=severity,
        source_model=source_model,
        finding_id=uuid4(),
    )


def _make_tp_alignment(
    *,
    similarity_score: float = 0.9,
    category: str = "security",
    description: str = "test finding",
) -> ModelFindingAlignment:
    return ModelFindingAlignment(
        ground_truth=_make_finding(
            source_model="codex", category=category, description=description
        ),
        challenger=_make_finding(category=category, description=description),
        similarity_score=similarity_score,
        aligned=True,
        alignment_type="true_positive",
    )


def _make_fp_alignment(
    *,
    category: str = "style",
    description: str = "noisy finding",
) -> ModelFindingAlignment:
    return ModelFindingAlignment(
        ground_truth=None,
        challenger=_make_finding(category=category, description=description),
        similarity_score=0.0,
        aligned=False,
        alignment_type="false_positive",
    )


def _make_run(
    *,
    alignments: list[ModelFindingAlignment],
    run_id: str | None = None,
) -> ModelCalibrationRunResult:
    tps = sum(1 for a in alignments if a.alignment_type == "true_positive")
    fps = sum(1 for a in alignments if a.alignment_type == "false_positive")
    fns = sum(1 for a in alignments if a.alignment_type == "false_negative")
    total = tps + fps
    precision = tps / total if total > 0 else 1.0
    recall_denom = tps + fns
    recall = tps / recall_denom if recall_denom > 0 else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    noise = fps / total if total > 0 else 0.0
    return ModelCalibrationRunResult(
        run_id=run_id or str(uuid4()),
        ground_truth_model="codex",
        challenger_model="challenger-1",
        alignments=alignments,
        metrics=ModelCalibrationMetrics(
            model="challenger-1",
            true_positives=tps,
            false_positives=fps,
            false_negatives=fns,
            precision=precision,
            recall=recall,
            f1_score=f1,
            noise_ratio=noise,
        ),
        prompt_version="v1",
        created_at=datetime.now(tz=timezone.utc),
    )


def _default_config(
    *,
    min_runs: int = 3,
    tp_count: int = 3,
    fp_count: int = 3,
) -> ModelCalibrationConfig:
    return ModelCalibrationConfig(
        ground_truth_model="codex",
        challenger_models=["challenger-1"],
        min_runs_for_fewshot=min_runs,
        fewshot_tp_count=tp_count,
        fewshot_fp_count=fp_count,
    )


@pytest.mark.unit
class TestFewShotExtractor:
    def test_empty_runs_returns_empty(self) -> None:
        extractor = FewShotExtractor()
        result = extractor.extract(runs=[], config=_default_config())
        assert result == []

    def test_below_threshold_returns_empty(self) -> None:
        extractor = FewShotExtractor()
        runs = [_make_run(alignments=[_make_tp_alignment()]) for _ in range(2)]
        config = _default_config(min_runs=5)
        result = extractor.extract(runs=runs, config=config)
        assert result == []

    def test_exact_threshold_returns_results(self) -> None:
        extractor = FewShotExtractor()
        runs = [
            _make_run(alignments=[_make_tp_alignment(similarity_score=0.8)])
            for _ in range(3)
        ]
        config = _default_config(min_runs=3)
        result = extractor.extract(runs=runs, config=config)
        assert len(result) > 0

    def test_tps_ranked_by_similarity_desc(self) -> None:
        extractor = FewShotExtractor()
        alignments = [
            _make_tp_alignment(similarity_score=0.7, description="low"),
            _make_tp_alignment(similarity_score=0.95, description="high"),
            _make_tp_alignment(similarity_score=0.85, description="mid"),
        ]
        runs = [_make_run(alignments=alignments) for _ in range(3)]
        config = _default_config(min_runs=3, tp_count=3, fp_count=0)
        result = extractor.extract(runs=runs, config=config)
        tp_examples = [e for e in result if e.example_type == "true_positive"]
        assert len(tp_examples) == 3
        assert "high" in tp_examples[0].description
        assert "mid" in tp_examples[1].description
        assert "low" in tp_examples[2].description

    def test_fps_ranked_by_frequency_desc(self) -> None:
        extractor = FewShotExtractor()
        # "common noise" appears in all 3 runs, "rare noise" in 1 run
        run1 = _make_run(
            alignments=[
                _make_fp_alignment(description="common noise"),
                _make_fp_alignment(description="rare noise"),
            ]
        )
        run2 = _make_run(
            alignments=[
                _make_fp_alignment(description="common noise"),
            ]
        )
        run3 = _make_run(
            alignments=[
                _make_fp_alignment(description="common noise"),
            ]
        )
        config = _default_config(min_runs=3, tp_count=0, fp_count=2)
        result = extractor.extract(runs=[run1, run2, run3], config=config)
        fp_examples = [e for e in result if e.example_type == "false_positive"]
        assert len(fp_examples) == 2
        assert "common noise" in fp_examples[0].description
        assert "rare noise" in fp_examples[1].description

    def test_count_limits_respected(self) -> None:
        extractor = FewShotExtractor()
        alignments = [
            _make_tp_alignment(similarity_score=0.9 + i * 0.01, description=f"tp-{i}")
            for i in range(10)
        ] + [_make_fp_alignment(description=f"fp-{i}") for i in range(10)]
        runs = [_make_run(alignments=alignments) for _ in range(3)]
        config = _default_config(min_runs=3, tp_count=2, fp_count=2)
        result = extractor.extract(runs=runs, config=config)
        tp_examples = [e for e in result if e.example_type == "true_positive"]
        fp_examples = [e for e in result if e.example_type == "false_positive"]
        assert len(tp_examples) == 2
        assert len(fp_examples) == 2

    def test_failed_runs_excluded(self) -> None:
        """Runs with error set and metrics=None should be excluded."""
        extractor = FewShotExtractor()
        good_runs = [_make_run(alignments=[_make_tp_alignment()]) for _ in range(3)]
        failed_run = ModelCalibrationRunResult(
            run_id="failed",
            ground_truth_model="codex",
            challenger_model="challenger-1",
            alignments=[],
            metrics=None,
            prompt_version="v1",
            error="transport failure",
            created_at=datetime.now(tz=timezone.utc),
        )
        config = _default_config(min_runs=4)
        # 3 good + 1 failed = only 3 valid, below threshold of 4
        result = extractor.extract(runs=good_runs + [failed_run], config=config)
        assert result == []

    def test_zero_counts_returns_empty(self) -> None:
        extractor = FewShotExtractor()
        runs = [
            _make_run(alignments=[_make_tp_alignment(), _make_fp_alignment()])
            for _ in range(3)
        ]
        config = _default_config(min_runs=3, tp_count=0, fp_count=0)
        result = extractor.extract(runs=runs, config=config)
        assert result == []
