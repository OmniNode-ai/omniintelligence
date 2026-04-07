# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for calibration data models.

TDD: Tests written first for OMN-6165.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationConfig,
    ModelCalibrationFindingTuple,
    ModelCalibrationMetrics,
    ModelCalibrationOrchestrationResult,
    ModelCalibrationRunCompletedEvent,
    ModelCalibrationRunResult,
    ModelFewShotExample,
    ModelFindingAlignment,
)


@pytest.mark.unit
class TestCalibrationConfig:
    """Tests for ModelCalibrationConfig model."""

    def test_default_values(self) -> None:
        config = ModelCalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1", "qwen3-coder"],
        )
        assert config.ground_truth_model == "codex"
        assert config.challenger_models == ["deepseek-r1", "qwen3-coder"]
        assert config.similarity_threshold == 0.7
        assert config.min_runs_for_fewshot == 5
        assert config.fewshot_tp_count == 3
        assert config.fewshot_fp_count == 3
        assert config.fewshot_fn_count == 3
        assert config.max_concurrent_challengers == 3
        assert config.category_families == {}

    def test_custom_values(self) -> None:
        config = ModelCalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
            similarity_threshold=0.8,
            min_runs_for_fewshot=10,
            fewshot_tp_count=5,
            fewshot_fp_count=2,
            fewshot_fn_count=4,
            max_concurrent_challengers=2,
            category_families={"design": ["architecture", "structure"]},
        )
        assert config.similarity_threshold == 0.8
        assert config.min_runs_for_fewshot == 10
        assert config.category_families == {"design": ["architecture", "structure"]}

    def test_frozen(self) -> None:
        config = ModelCalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
        )
        with pytest.raises(ValidationError):
            config.ground_truth_model = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        config = ModelCalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1", "qwen3-coder"],
            category_families={"design": ["architecture"]},
        )
        json_str = config.model_dump_json()
        restored = ModelCalibrationConfig.model_validate_json(json_str)
        assert restored == config

    def test_empty_challenger_models_allowed(self) -> None:
        config = ModelCalibrationConfig(
            ground_truth_model="codex",
            challenger_models=[],
        )
        assert config.challenger_models == []


@pytest.mark.unit
class TestCalibrationFindingTuple:
    """Tests for ModelCalibrationFindingTuple model."""

    def test_basic_creation(self) -> None:
        fid = uuid4()
        finding = ModelCalibrationFindingTuple(
            category="architecture",
            location="src/main.py:42",
            description="Missing error handling",
            severity="error",
            source_model="codex",
            finding_id=fid,
            raw_finding=None,
        )
        assert finding.category == "architecture"
        assert finding.location == "src/main.py:42"
        assert finding.finding_id == fid
        assert finding.raw_finding is None

    def test_none_location(self) -> None:
        finding = ModelCalibrationFindingTuple(
            category="design",
            location=None,
            description="Poor abstraction",
            severity="warning",
            source_model="deepseek-r1",
            finding_id=uuid4(),
            raw_finding=None,
        )
        assert finding.location is None

    def test_frozen(self) -> None:
        finding = ModelCalibrationFindingTuple(
            category="design",
            location=None,
            description="Test",
            severity="warning",
            source_model="test",
            finding_id=uuid4(),
            raw_finding=None,
        )
        with pytest.raises(ValidationError):
            finding.category = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        finding = ModelCalibrationFindingTuple(
            category="architecture",
            location="file.py",
            description="Issue found",
            severity="error",
            source_model="codex",
            finding_id=uuid4(),
            raw_finding=None,
        )
        json_str = finding.model_dump_json()
        restored = ModelCalibrationFindingTuple.model_validate_json(json_str)
        assert restored == finding


@pytest.mark.unit
class TestFindingAlignment:
    """Tests for ModelFindingAlignment model."""

    def _make_finding(self, source: str = "codex") -> ModelCalibrationFindingTuple:
        return ModelCalibrationFindingTuple(
            category="architecture",
            location="file.py",
            description="Issue",
            severity="error",
            source_model=source,
            finding_id=uuid4(),
            raw_finding=None,
        )

    def test_true_positive(self) -> None:
        gt = self._make_finding("codex")
        ch = self._make_finding("deepseek-r1")
        alignment = ModelFindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.95,
            aligned=True,
            alignment_type="true_positive",
            embedding_model_version="qwen3-embedding-8b",
        )
        assert alignment.aligned is True
        assert alignment.alignment_type == "true_positive"

    def test_false_negative(self) -> None:
        gt = self._make_finding("codex")
        alignment = ModelFindingAlignment(
            ground_truth=gt,
            challenger=None,
            similarity_score=0.0,
            aligned=False,
            alignment_type="false_negative",
            embedding_model_version=None,
        )
        assert alignment.challenger is None
        assert alignment.alignment_type == "false_negative"

    def test_false_positive(self) -> None:
        ch = self._make_finding("deepseek-r1")
        alignment = ModelFindingAlignment(
            ground_truth=None,
            challenger=ch,
            similarity_score=0.0,
            aligned=False,
            alignment_type="false_positive",
            embedding_model_version="jaccard-v1",
        )
        assert alignment.ground_truth is None
        assert alignment.alignment_type == "false_positive"

    def test_frozen(self) -> None:
        gt = self._make_finding()
        ch = self._make_finding("deepseek-r1")
        alignment = ModelFindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.9,
            aligned=True,
            alignment_type="true_positive",
            embedding_model_version=None,
        )
        with pytest.raises(ValidationError):
            alignment.aligned = False  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        gt = self._make_finding()
        ch = self._make_finding("deepseek-r1")
        alignment = ModelFindingAlignment(
            ground_truth=gt,
            challenger=ch,
            similarity_score=0.85,
            aligned=True,
            alignment_type="true_positive",
            embedding_model_version="qwen3-embedding-8b",
        )
        json_str = alignment.model_dump_json()
        restored = ModelFindingAlignment.model_validate_json(json_str)
        assert restored == alignment


@pytest.mark.unit
class TestCalibrationMetrics:
    """Tests for ModelCalibrationMetrics model."""

    def test_basic_metrics(self) -> None:
        metrics = ModelCalibrationMetrics(
            model="deepseek-r1",
            true_positives=8,
            false_positives=2,
            false_negatives=3,
            precision=0.8,
            recall=0.727,
            f1_score=0.762,
            noise_ratio=0.2,
        )
        assert metrics.model == "deepseek-r1"
        assert metrics.true_positives == 8
        assert metrics.precision == 0.8

    def test_frozen(self) -> None:
        metrics = ModelCalibrationMetrics(
            model="test",
            true_positives=1,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            noise_ratio=0.0,
        )
        with pytest.raises(ValidationError):
            metrics.model = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        metrics = ModelCalibrationMetrics(
            model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
        )
        json_str = metrics.model_dump_json()
        restored = ModelCalibrationMetrics.model_validate_json(json_str)
        assert restored == metrics


@pytest.mark.unit
class TestCalibrationRunResult:
    """Tests for ModelCalibrationRunResult model."""

    def test_successful_run(self) -> None:
        metrics = ModelCalibrationMetrics(
            model="deepseek-r1",
            true_positives=5,
            false_positives=2,
            false_negatives=1,
            precision=0.714,
            recall=0.833,
            f1_score=0.769,
            noise_ratio=0.286,
        )
        now = datetime.now(tz=timezone.utc)
        result = ModelCalibrationRunResult(
            run_id="run-001",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=metrics,
            prompt_version="1.1.0",
            embedding_model_version="qwen3-embedding-8b",
            config_version="v1",
            error=None,
            created_at=now,
        )
        assert result.run_id == "run-001"
        assert result.metrics is not None
        assert result.error is None

    def test_failed_run(self) -> None:
        now = datetime.now(tz=timezone.utc)
        result = ModelCalibrationRunResult(
            run_id="run-002",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            error="Connection timeout",
            created_at=now,
        )
        assert result.metrics is None
        assert result.error == "Connection timeout"

    def test_frozen(self) -> None:
        now = datetime.now(tz=timezone.utc)
        result = ModelCalibrationRunResult(
            run_id="run-003",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            created_at=now,
        )
        with pytest.raises(ValidationError):
            result.run_id = "changed"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        now = datetime.now(tz=timezone.utc)
        result = ModelCalibrationRunResult(
            run_id="run-004",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=None,
            prompt_version="1.1.0",
            embedding_model_version=None,
            config_version="v1",
            error=None,
            created_at=now,
        )
        json_str = result.model_dump_json()
        restored = ModelCalibrationRunResult.model_validate_json(json_str)
        assert restored == result


@pytest.mark.unit
class TestFewShotExample:
    """Tests for ModelFewShotExample model."""

    def test_true_positive_example(self) -> None:
        example = ModelFewShotExample(
            example_type="true_positive",
            category="architecture",
            description="Missing error handling in API endpoint",
            evidence="Both ground truth and challenger found this issue",
            ground_truth_present=True,
            explanation="High-value finding confirmed by reference model",
        )
        assert example.example_type == "true_positive"
        assert example.ground_truth_present is True

    def test_false_positive_example(self) -> None:
        example = ModelFewShotExample(
            example_type="false_positive",
            category="style",
            description="Variable naming convention",
            evidence="Challenger flagged but ground truth did not",
            ground_truth_present=False,
            explanation="Noise: style preference not a real issue",
        )
        assert example.example_type == "false_positive"
        assert example.ground_truth_present is False

    def test_frozen(self) -> None:
        example = ModelFewShotExample(
            example_type="false_negative",
            category="security",
            description="SQL injection risk",
            evidence="Ground truth found but challenger missed",
            ground_truth_present=True,
            explanation="Challenger missed critical security finding",
        )
        with pytest.raises(ValidationError):
            example.category = "other"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        example = ModelFewShotExample(
            example_type="true_positive",
            category="architecture",
            description="Test description",
            evidence="Test evidence",
            ground_truth_present=True,
            explanation="Test explanation",
        )
        json_str = example.model_dump_json()
        restored = ModelFewShotExample.model_validate_json(json_str)
        assert restored == example


@pytest.mark.unit
class TestCalibrationOrchestrationResult:
    """Tests for ModelCalibrationOrchestrationResult model."""

    def test_successful_orchestration(self) -> None:
        finding = ModelCalibrationFindingTuple(
            category="architecture",
            location="file.py",
            description="Issue",
            severity="error",
            source_model="codex",
            finding_id=uuid4(),
            raw_finding=None,
        )
        now = datetime.now(tz=timezone.utc)
        run_result = ModelCalibrationRunResult(
            run_id="run-001",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            alignments=[],
            metrics=ModelCalibrationMetrics(
                model="deepseek-r1",
                true_positives=1,
                false_positives=0,
                false_negatives=0,
                precision=1.0,
                recall=1.0,
                f1_score=1.0,
                noise_ratio=0.0,
            ),
            prompt_version="1.1.0",
            created_at=now,
        )
        result = ModelCalibrationOrchestrationResult(
            success=True,
            error=None,
            ground_truth_findings=[finding],
            challenger_results=[run_result],
        )
        assert result.success is True
        assert len(result.ground_truth_findings) == 1
        assert len(result.challenger_results) == 1

    def test_failed_orchestration(self) -> None:
        result = ModelCalibrationOrchestrationResult(
            success=False,
            error="No ground truth findings available",
            ground_truth_findings=[],
            challenger_results=[],
        )
        assert result.success is False
        assert result.error is not None

    def test_frozen(self) -> None:
        result = ModelCalibrationOrchestrationResult(
            success=True,
            error=None,
            ground_truth_findings=[],
            challenger_results=[],
        )
        with pytest.raises(ValidationError):
            result.success = False  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        result = ModelCalibrationOrchestrationResult(
            success=True,
            error=None,
            ground_truth_findings=[],
            challenger_results=[],
        )
        json_str = result.model_dump_json()
        restored = ModelCalibrationOrchestrationResult.model_validate_json(json_str)
        assert restored == result


@pytest.mark.unit
class TestCalibrationRunCompletedEvent:
    """Tests for ModelCalibrationRunCompletedEvent model."""

    def test_event_creation(self) -> None:
        now = datetime.now(tz=timezone.utc)
        event = ModelCalibrationRunCompletedEvent(
            event_id=uuid4(),
            run_id="run-001",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            precision=0.8,
            recall=0.75,
            f1_score=0.774,
            noise_ratio=0.2,
            finding_count=10,
            prompt_version="1.1.0",
            created_at=now,
        )
        assert event.run_id == "run-001"
        assert event.precision == 0.8

    def test_frozen(self) -> None:
        now = datetime.now(tz=timezone.utc)
        event = ModelCalibrationRunCompletedEvent(
            event_id=uuid4(),
            run_id="run-001",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            precision=0.8,
            recall=0.75,
            f1_score=0.774,
            noise_ratio=0.2,
            finding_count=10,
            prompt_version="1.1.0",
            created_at=now,
        )
        with pytest.raises(ValidationError):
            event.run_id = "changed"  # type: ignore[misc]

    def test_round_trip_json(self) -> None:
        now = datetime.now(tz=timezone.utc)
        event = ModelCalibrationRunCompletedEvent(
            event_id=uuid4(),
            run_id="run-001",
            ground_truth_model="codex",
            challenger_model="deepseek-r1",
            precision=0.8,
            recall=0.75,
            f1_score=0.774,
            noise_ratio=0.2,
            finding_count=10,
            prompt_version="1.1.0",
            created_at=now,
        )
        json_str = event.model_dump_json()
        restored = ModelCalibrationRunCompletedEvent.model_validate_json(json_str)
        assert restored == event
