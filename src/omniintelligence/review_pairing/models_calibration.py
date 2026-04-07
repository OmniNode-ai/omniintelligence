# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration data models for the Review Calibration Loop.

All models use PEP 604 union syntax, are frozen (immutable), and pass mypy --strict.

ONEX Compliance:
    Naming follows Model{Domain}{Purpose} convention where applicable.
    All models inherit from pydantic.BaseModel with frozen=True.

Reference: OMN-6165
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.review_pairing.models import ModelReviewFindingObserved


class ModelCalibrationConfig(BaseModel, frozen=True):
    """Configuration for a calibration run.

    Attributes:
        ground_truth_model: Model key used as the reference (e.g. "codex").
        challenger_models: List of model keys to calibrate against ground truth.
        similarity_threshold: Minimum composite similarity score for alignment.
        min_runs_for_fewshot: Minimum calibration runs before few-shot extraction.
        fewshot_tp_count: Number of true-positive examples to extract per run.
        fewshot_fp_count: Number of false-positive examples to extract per run.
        fewshot_fn_count: Number of false-negative examples to extract per run.
        max_concurrent_challengers: Max challengers to run in parallel.
        category_families: Maps family names to lists of related category strings
            for fuzzy category matching in the alignment engine.
    """

    ground_truth_model: str = Field(
        description="Model key used as the reference (e.g. 'codex').",
    )
    challenger_models: list[str] = Field(
        description="List of model keys to calibrate against ground truth.",
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum composite similarity score for alignment.",
        ge=0.0,
        le=1.0,
    )
    min_runs_for_fewshot: int = Field(
        default=5,
        description="Minimum calibration runs before few-shot extraction.",
        ge=1,
    )
    fewshot_tp_count: int = Field(
        default=3,
        description="Number of true-positive examples to extract per run.",
        ge=0,
    )
    fewshot_fp_count: int = Field(
        default=3,
        description="Number of false-positive examples to extract per run.",
        ge=0,
    )
    fewshot_fn_count: int = Field(
        default=3,
        description="Number of false-negative examples to extract per run.",
        ge=0,
    )
    max_concurrent_challengers: int = Field(
        default=3,
        description="Max challengers to run in parallel.",
        ge=1,
    )
    category_families: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Maps family names to lists of related category strings "
            "for fuzzy category matching in the alignment engine."
        ),
    )


class ModelCalibrationFindingTuple(BaseModel, frozen=True):
    """Normalized finding representation for calibration alignment.

    Attributes:
        category: Finding category (e.g. "architecture", "security").
        location: File path or section reference. None for findings without location.
        description: Human-readable description of the finding.
        severity: Severity level as string (e.g. "error", "warning").
        source_model: Model key that produced this finding.
        finding_id: Unique identifier for this finding instance.
        raw_finding: Original ModelReviewFindingObserved if available, None for R1-R6 findings.
    """

    category: str = Field(
        description="Finding category (e.g. 'architecture', 'security').",
    )
    location: str | None = Field(
        description="File path or section reference. None for findings without location.",
    )
    description: str = Field(
        description="Human-readable description of the finding.",
    )
    severity: str = Field(
        description="Severity level as string (e.g. 'error', 'warning').",
    )
    source_model: str = Field(
        description="Model key that produced this finding.",
    )
    finding_id: UUID = Field(
        description="Unique identifier for this finding instance.",
    )
    raw_finding: ModelReviewFindingObserved | None = Field(
        default=None,
        description=(
            "Original ModelReviewFindingObserved if available. None for R1-R6 findings."
        ),
    )


class ModelFindingAlignment(BaseModel, frozen=True):
    """Alignment record pairing a ground-truth finding with a challenger finding.

    Bidirectional:
    - ground_truth=None: unmatched challenger finding (false positive)
    - challenger=None: unmatched ground-truth finding (false negative)
    - Both non-None with aligned=True: true positive

    Attributes:
        ground_truth: Ground-truth finding, or None for false positives.
        challenger: Challenger finding, or None for false negatives.
        similarity_score: Composite similarity score from the alignment engine.
        aligned: Whether this pair was matched above the similarity threshold.
        alignment_type: Classification of the alignment result.
        embedding_model_version: Embedding model used for similarity, or
            "jaccard-v1" for fallback string similarity.
    """

    ground_truth: ModelCalibrationFindingTuple | None = Field(
        description="Ground-truth finding, or None for false positives.",
    )
    challenger: ModelCalibrationFindingTuple | None = Field(
        description="Challenger finding, or None for false negatives.",
    )
    similarity_score: float = Field(
        description="Composite similarity score from the alignment engine.",
        ge=0.0,
    )
    aligned: bool = Field(
        description="Whether this pair was matched above the similarity threshold.",
    )
    alignment_type: Literal["true_positive", "false_negative", "false_positive"] = (
        Field(
            description="Classification of the alignment result.",
        )
    )
    embedding_model_version: str | None = Field(
        default=None,
        description=(
            "Embedding model used for similarity, or "
            "'jaccard-v1' for fallback string similarity."
        ),
    )


class ModelCalibrationMetrics(BaseModel, frozen=True):
    """Per-model precision, recall, and noise metrics from a calibration run.

    Attributes:
        model: Model key these metrics apply to.
        true_positives: Count of findings matched to ground truth.
        false_positives: Count of challenger findings not in ground truth.
        false_negatives: Count of ground-truth findings missed by challenger.
        precision: TP / (TP + FP).
        recall: TP / (TP + FN).
        f1_score: Harmonic mean of precision and recall.
        noise_ratio: FP / (TP + FP). Proportion of challenger findings that are noise.
    """

    model: str = Field(
        description="Model key these metrics apply to.",
    )
    true_positives: int = Field(
        description="Count of findings matched to ground truth.",
        ge=0,
    )
    false_positives: int = Field(
        description="Count of challenger findings not in ground truth.",
        ge=0,
    )
    false_negatives: int = Field(
        description="Count of ground-truth findings missed by challenger.",
        ge=0,
    )
    precision: float = Field(
        description="TP / (TP + FP).",
        ge=0.0,
        le=1.0,
    )
    recall: float = Field(
        description="TP / (TP + FN).",
        ge=0.0,
        le=1.0,
    )
    f1_score: float = Field(
        description="Harmonic mean of precision and recall.",
        ge=0.0,
        le=1.0,
    )
    noise_ratio: float = Field(
        description="FP / (TP + FP). Proportion of noise in challenger findings.",
        ge=0.0,
        le=1.0,
    )


class ModelCalibrationRunResult(BaseModel, frozen=True):
    """Full result of one calibration run for a single challenger model.

    Results with error != None and metrics == None represent transport/execution
    failures and are excluded from persistence and EMA updates.

    Attributes:
        run_id: Unique identifier for this calibration run.
        ground_truth_model: Model key used as reference.
        challenger_model: Model key being calibrated.
        alignments: List of finding alignments from the alignment engine.
        metrics: Computed metrics, or None on failure.
        prompt_version: Version of the adversarial reviewer prompt used.
        embedding_model_version: Embedding model used for similarity computation.
        config_version: Version identifier for the calibration config used.
        error: Error message if the run failed, None on success.
        created_at: UTC datetime when the run was executed.
    """

    run_id: str = Field(
        description="Unique identifier for this calibration run.",
    )
    ground_truth_model: str = Field(
        description="Model key used as reference.",
    )
    challenger_model: str = Field(
        description="Model key being calibrated.",
    )
    alignments: list[ModelFindingAlignment] = Field(
        description="List of finding alignments from the alignment engine.",
    )
    metrics: ModelCalibrationMetrics | None = Field(
        default=None,
        description="Computed metrics, or None on failure.",
    )
    prompt_version: str = Field(
        description="Version of the adversarial reviewer prompt used.",
    )
    embedding_model_version: str | None = Field(
        default=None,
        description="Embedding model used for similarity computation.",
    )
    config_version: str = Field(
        default="",
        description="Version identifier for the calibration config used.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if the run failed, None on success.",
    )
    created_at: datetime = Field(
        description="UTC datetime when the run was executed.",
    )


class ModelFewShotExample(BaseModel, frozen=True):
    """A single few-shot example extracted from calibration results.

    Used to inject high-value examples into adversarial reviewer prompts.

    Attributes:
        example_type: Whether this is a TP, FP, or FN example.
        category: Finding category this example belongs to.
        description: Description of the finding.
        evidence: Evidence supporting the classification.
        ground_truth_present: Whether the ground-truth model found this issue.
        explanation: Human-readable explanation of why this is a good example.
    """

    example_type: Literal["true_positive", "false_positive", "false_negative"] = Field(
        description="Whether this is a TP, FP, or FN example.",
    )
    category: str = Field(
        description="Finding category this example belongs to.",
    )
    description: str = Field(
        description="Description of the finding.",
    )
    evidence: str = Field(
        description="Evidence supporting the classification.",
    )
    ground_truth_present: bool = Field(
        description="Whether the ground-truth model found this issue.",
    )
    explanation: str = Field(
        description="Human-readable explanation of why this is a good example.",
    )


class ModelCalibrationOrchestrationResult(BaseModel, frozen=True):
    """Wrapper for the calibration orchestrator output.

    Attributes:
        success: Whether the orchestration completed without fatal errors.
        error: Error message if orchestration failed, None on success.
        ground_truth_findings: Findings from the ground-truth model.
        challenger_results: Per-challenger calibration run results.
    """

    success: bool = Field(
        description="Whether the orchestration completed without fatal errors.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if orchestration failed, None on success.",
    )
    ground_truth_findings: list[ModelCalibrationFindingTuple] = Field(
        description="Findings from the ground-truth model.",
    )
    challenger_results: list[ModelCalibrationRunResult] = Field(
        description="Per-challenger calibration run results.",
    )


class ModelCalibrationRunCompletedEvent(BaseModel, frozen=True):
    """Kafka event emitted when a calibration run completes.

    Published to ``onex.evt.review-pairing.calibration-run-completed.v1``.

    Attributes:
        event_id: Unique event identifier.
        run_id: Calibration run identifier.
        ground_truth_model: Reference model key.
        challenger_model: Challenger model key.
        precision: Computed precision metric.
        recall: Computed recall metric.
        f1_score: Computed F1 score.
        noise_ratio: Computed noise ratio.
        finding_count: Total number of findings aligned.
        prompt_version: Prompt version used for the run.
        created_at: UTC datetime of event creation.
    """

    event_id: UUID = Field(
        description="Unique event identifier.",
    )
    run_id: str = Field(
        description="Calibration run identifier.",
    )
    ground_truth_model: str = Field(
        description="Reference model key.",
    )
    challenger_model: str = Field(
        description="Challenger model key.",
    )
    precision: float = Field(
        description="Computed precision metric.",
        ge=0.0,
        le=1.0,
    )
    recall: float = Field(
        description="Computed recall metric.",
        ge=0.0,
        le=1.0,
    )
    f1_score: float = Field(
        description="Computed F1 score.",
        ge=0.0,
        le=1.0,
    )
    noise_ratio: float = Field(
        description="Computed noise ratio.",
        ge=0.0,
        le=1.0,
    )
    finding_count: int = Field(
        description="Total number of findings aligned.",
        ge=0,
    )
    prompt_version: str = Field(
        description="Prompt version used for the run.",
    )
    created_at: datetime = Field(
        description="UTC datetime of event creation.",
    )
