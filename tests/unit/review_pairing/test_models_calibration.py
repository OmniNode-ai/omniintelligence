# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for calibration data models.

Reference: OMN-6165 (epic OMN-6164)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationFindingTuple,
    CalibrationMetrics,
    CalibrationOrchestrationResult,
    CalibrationRunResult,
    FewShotExample,
    FindingAlignment,
)


@pytest.mark.unit
class TestCalibrationConfig:
    def test_defaults(self) -> None:
        cfg = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
        )
        assert cfg.similarity_threshold == 0.7
        assert cfg.min_runs_for_fewshot == 5
        assert cfg.fewshot_tp_count == 3
        assert cfg.fewshot_fp_count == 3
        assert cfg.fewshot_fn_count == 3
        assert cfg.max_concurrent_challengers == 3
        assert cfg.category_families == {}

    def test_frozen(self) -> None:
        cfg = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
        )
        with pytest.raises(Exception):
            cfg.ground_truth_model = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        cfg = CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1", "qwen3-coder"],
            similarity_threshold=0.8,
            category_families={"architecture": ["design", "structure"]},
        )
        data = json.loads(cfg.model_dump_json())
        restored = CalibrationConfig.model_validate(data)
        assert restored == cfg


@pytest.mark.unit
class TestCalibrationFindingTuple:
    def test_basic_creation(self) -> None:
        fid = uuid4()
        t = CalibrationFindingTuple(
            category="architecture",
            location="Task 5",
            description="Missing error handling",
            severity="error",
            source_model="codex",
            finding_id=fid,
        )
        assert t.category == "architecture"
        assert t.finding_id == fid
        assert t.raw_finding is None

    def test_auto_uuid(self) -> None:
        t = CalibrationFindingTuple(
            category="design",
            location=None,
            description="Test",
            severity="warning",
            source_model="deepseek-r1",
        )
        assert t.finding_id is not None

    def test_frozen(self) -> None:
        t = CalibrationFindingTuple(
            category="design",
            location=None,
            description="Test",
            severity="warning",
            source_model="deepseek-r1",
        )
        with pytest.raises(Exception):
            t.category = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        t = CalibrationFindingTuple(
            category="design",
            location="Task 1",
            description="Missing validation",
            severity="error",
            source_model="codex",
        )
        data = json.loads(t.model_dump_json())
        restored = CalibrationFindingTuple.model_validate(data)
        assert restored.category == t.category
        assert restored.description == t.description


@pytest.mark.unit
class TestFindingAlignment:
    def _make_finding(self, model: str = "codex") -> CalibrationFindingTuple:
        return CalibrationFindingTuple(
            category="architecture",
            location="Task 1",
            description="Test finding",
            severity="error",
            source_model=model,
        )

    def test_true_positive(self) -> None:
        gt = self._make_finding("codex")
        ch = self._make_finding("deepseek-r1")
        a = FindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.9,
            aligned=True,
            alignment_type="true_positive",
        )
        assert a.aligned is True
        assert a.alignment_type == "true_positive"

    def test_false_negative(self) -> None:
        gt = self._make_finding("codex")
        a = FindingAlignment(
            ground_truth=gt,
            challenger=None,
            similarity_score=0.0,
            aligned=False,
            alignment_type="false_negative",
        )
        assert a.ground_truth is not None
        assert a.challenger is None

    def test_false_positive(self) -> None:
        ch = self._make_finding("deepseek-r1")
        a = FindingAlignment(
            ground_truth=None,
            challenger=ch,
            similarity_score=0.0,
            aligned=False,
            alignment_type="false_positive",
        )
        assert a.ground_truth is None
        assert a.challenger is not None

    def test_invalid_true_positive_missing_ground_truth(self) -> None:
        ch = self._make_finding("deepseek-r1")
        with pytest.raises(ValueError, match="true_positive"):
            FindingAlignment(
                ground_truth=None,
                challenger=ch,
                similarity_score=0.9,
                aligned=True,
                alignment_type="true_positive",
            )

    def test_invalid_true_positive_missing_challenger(self) -> None:
        gt = self._make_finding("codex")
        with pytest.raises(ValueError, match="true_positive"):
            FindingAlignment(
                ground_truth=gt,
                challenger=None,
                similarity_score=0.9,
                aligned=True,
                alignment_type="true_positive",
            )

    def test_invalid_false_negative_with_challenger(self) -> None:
        gt = self._make_finding("codex")
        ch = self._make_finding("deepseek-r1")
        with pytest.raises(ValueError, match="false_negative"):
            FindingAlignment(
                ground_truth=gt,
                challenger=ch,
                similarity_score=0.0,
                aligned=False,
                alignment_type="false_negative",
            )

    def test_invalid_false_positive_with_ground_truth(self) -> None:
        gt = self._make_finding("codex")
        ch = self._make_finding("deepseek-r1")
        with pytest.raises(ValueError, match="false_positive"):
            FindingAlignment(
                ground_truth=gt,
                challenger=ch,
                similarity_score=0.0,
                aligned=False,
                alignment_type="false_positive",
            )

    def test_round_trip_json(self) -> None:
        gt = self._make_finding("codex")
        ch = self._make_finding("deepseek-r1")
        a = FindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.85,
            aligned=True,
            alignment_type="true_positive",
            embedding_model_version="qwen3-embedding-8b",
        )
        data = json.loads(a.model_dump_json())
        restored = FindingAlignment.model_validate(data)
        assert restored.alignment_type == "true_positive"
        assert restored.similarity_score == 0.85


@pytest.mark.unit
class TestCalibrationMetrics:
    def test_perfect_challenger(self) -> None:
        m = CalibrationMetrics(
            model="deepseek-r1",
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            noise_ratio=0.0,
        )
        assert m.precision == 1.0
        assert m.noise_ratio == 0.0

    def test_frozen(self) -> None:
        m = CalibrationMetrics(
            model="deepseek-r1",
            true_positives=5,
            false_positives=3,
            false_negatives=2,
            precision=0.625,
            recall=0.714,
            f1_score=0.667,
            noise_ratio=0.375,
        )
        with pytest.raises(Exception):
            m.precision = 0.0  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        m = CalibrationMetrics(
            model="deepseek-r1",
            true_positives=5,
            false_positives=3,
            false_negatives=2,
            precision=0.625,
            recall=0.714,
            f1_score=0.667,
            noise_ratio=0.375,
        )
        data = json.loads(m.model_dump_json())
        restored = CalibrationMetrics.model_validate(data)
        assert restored == m


@pytest.mark.unit
class TestCalibrationRunResult:
    def test_successful_run(self) -> None:
        metrics = CalibrationMetrics(
            model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
        )
        result = CalibrationRunResult(
            run_id="test-run-1",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=metrics,
            prompt_version="1.1.0",
            created_at=datetime.now(timezone.utc),
        )
        assert result.error is None
        assert result.metrics is not None

    def test_failed_run(self) -> None:
        result = CalibrationRunResult(
            run_id="test-run-2",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            error="Connection timeout",
            created_at=datetime.now(timezone.utc),
        )
        assert result.metrics is None
        assert result.error == "Connection timeout"

    def test_round_trip_json(self) -> None:
        result = CalibrationRunResult(
            run_id="test-run-3",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            created_at=datetime.now(timezone.utc),
        )
        data = json.loads(result.model_dump_json())
        restored = CalibrationRunResult.model_validate(data)
        assert restored.run_id == result.run_id


@pytest.mark.unit
class TestFewShotExample:
    def test_creation(self) -> None:
        ex = FewShotExample(
            example_type="true_positive",
            category="architecture",
            description="Missing error handling in retry logic",
            evidence="Ground truth found this, challenger agreed",
            ground_truth_present=True,
            explanation="Both models identified the missing error handling.",
        )
        assert ex.example_type == "true_positive"
        assert ex.ground_truth_present is True

    def test_round_trip_json(self) -> None:
        ex = FewShotExample(
            example_type="false_positive",
            category="performance",
            description="Unnecessary async wrapper",
            evidence="Challenger flagged, ground truth did not",
            ground_truth_present=False,
            explanation="This is noise from the challenger model.",
        )
        data = json.loads(ex.model_dump_json())
        restored = FewShotExample.model_validate(data)
        assert restored == ex


@pytest.mark.unit
class TestCalibrationOrchestrationResult:
    def test_success(self) -> None:
        r = CalibrationOrchestrationResult(
            success=True,
            ground_truth_findings=[],
            challenger_results=[],
        )
        assert r.success is True
        assert r.error is None

    def test_failure(self) -> None:
        r = CalibrationOrchestrationResult(
            success=False,
            error="Ground truth model failed: timeout",
        )
        assert r.success is False
        assert r.error is not None

    def test_round_trip_json(self) -> None:
        r = CalibrationOrchestrationResult(
            success=True,
            ground_truth_findings=[],
            challenger_results=[],
        )
        data = json.loads(r.model_dump_json())
        restored = CalibrationOrchestrationResult.model_validate(data)
        assert restored == r
