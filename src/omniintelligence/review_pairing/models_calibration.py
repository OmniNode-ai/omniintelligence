# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pydantic v2 data models for the Review Calibration Loop.

All models are frozen (immutable), use PEP 604 union syntax, and pass
``mypy --strict``.

Reference: OMN-6165 (epic OMN-6164)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from omniintelligence.review_pairing.models import ReviewFindingObserved


class CalibrationConfig(BaseModel, frozen=True):
    """Configuration for a calibration run."""

    ground_truth_model: str = Field(
        description="Model key used as the ground-truth reference.",
    )
    challenger_models: list[str] = Field(
        description="Model keys for challenger models to evaluate.",
    )
    similarity_threshold: float = Field(
        default=0.7,
        description="Minimum composite similarity score for alignment.",
    )
    min_runs_for_fewshot: int = Field(
        default=5,
        description="Minimum calibration runs before few-shot extraction is enabled.",
    )
    fewshot_tp_count: int = Field(
        default=3,
        description="Number of true-positive few-shot examples to extract.",
    )
    fewshot_fp_count: int = Field(
        default=3,
        description="Number of false-positive few-shot examples to extract.",
    )
    fewshot_fn_count: int = Field(
        default=3,
        description="Number of false-negative few-shot examples to extract.",
    )
    max_concurrent_challengers: int = Field(
        default=3,
        description="Maximum number of challenger models to run concurrently.",
    )
    category_families: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Maps family names to lists of related category strings "
            "for fuzzy category matching in the alignment engine."
        ),
    )


class CalibrationFindingTuple(BaseModel, frozen=True):
    """Normalized finding representation for alignment matching."""

    category: str = Field(
        description="Finding category (e.g. 'architecture', 'error-handling').",
    )
    location: str | None = Field(
        description="Finding location (task name, file path, or None).",
    )
    description: str = Field(
        description="Human-readable finding description.",
    )
    severity: str = Field(
        description="Severity level as a string.",
    )
    source_model: str = Field(
        description="Model key that produced this finding.",
    )
    finding_id: UUID = Field(
        default_factory=uuid4,
        description=(
            "Unique identifier. Reused from source for external review "
            "findings; generated UUID4 for R1-R6 findings."
        ),
    )
    raw_finding: ReviewFindingObserved | None = Field(
        default=None,
        description="Original ReviewFindingObserved if from external review, else None.",
    )


class FindingAlignment(BaseModel, frozen=True):
    """Pairing of a ground-truth finding to a challenger finding."""

    ground_truth: CalibrationFindingTuple | None = Field(
        description="Ground-truth finding, or None for false positives.",
    )
    challenger: CalibrationFindingTuple | None = Field(
        description="Challenger finding, or None for false negatives.",
    )
    similarity_score: float = Field(
        description="Composite similarity score between the two findings.",
    )
    aligned: bool = Field(
        description="Whether the pair exceeds the similarity threshold.",
    )
    alignment_type: Literal["true_positive", "false_negative", "false_positive"] = (
        Field(
            description="Classification of this alignment record.",
        )
    )
    embedding_model_version: str | None = Field(
        default=None,
        description=(
            "Embedding model identifier used for similarity, "
            "or 'jaccard-v1' for fallback string similarity."
        ),
    )

    @model_validator(mode="after")
    def _validate_alignment_consistency(self) -> FindingAlignment:
        """Validate that alignment_type is consistent with ground_truth/challenger presence."""
        if self.alignment_type == "true_positive":
            if self.ground_truth is None or self.challenger is None:
                raise ValueError(
                    "true_positive alignment must have both ground_truth and challenger"
                )
        elif self.alignment_type == "false_negative":
            if self.ground_truth is None or self.challenger is not None:
                raise ValueError(
                    "false_negative alignment must have ground_truth and no challenger"
                )
        elif self.alignment_type == "false_positive":
            if self.ground_truth is not None or self.challenger is None:
                raise ValueError(
                    "false_positive alignment must have challenger and no ground_truth"
                )
        return self


class CalibrationMetrics(BaseModel, frozen=True):
    """Per-model precision, recall, noise metrics from a calibration run."""

    model: str = Field(
        description="Challenger model key.",
    )
    true_positives: int = Field(
        description="Count of aligned true-positive pairs.",
    )
    false_positives: int = Field(
        description="Challenger findings with no ground-truth match.",
    )
    false_negatives: int = Field(
        description="Ground-truth findings the challenger missed.",
    )
    precision: float = Field(
        description="TP / (TP + FP), 0.0 if denominator is zero.",
    )
    recall: float = Field(
        description="TP / (TP + FN), 0.0 if denominator is zero.",
    )
    f1_score: float = Field(
        description="Harmonic mean of precision and recall.",
    )
    noise_ratio: float = Field(
        description="FP / challenger_count, 0.0 if challenger_count is zero.",
    )


class CalibrationRunResult(BaseModel, frozen=True):
    """Full result of one calibration run for a single challenger."""

    run_id: str = Field(
        description="UUID4 string identifying this calibration invocation.",
    )
    ground_truth_model: str = Field(
        description="Model key used as ground truth.",
    )
    challenger_model: str = Field(
        description="Challenger model key evaluated in this run.",
    )
    alignments: list[FindingAlignment] = Field(
        description="Full list of alignment records.",
    )
    metrics: CalibrationMetrics | None = Field(
        description="Computed metrics, or None if challenger failed.",
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
        description="Calibration config version identifier.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if challenger execution failed.",
    )
    created_at: datetime = Field(
        description="UTC timestamp of this calibration run.",
    )


class FewShotExample(BaseModel, frozen=True):
    """Extracted example for few-shot prompt injection."""

    example_type: Literal["true_positive", "false_positive", "false_negative"] = Field(
        description="Classification of this example.",
    )
    category: str = Field(
        description="Finding category.",
    )
    description: str = Field(
        description="Finding description text.",
    )
    evidence: str = Field(
        description="Evidence or context supporting the classification.",
    )
    ground_truth_present: bool = Field(
        description="Whether this finding was present in ground truth.",
    )
    explanation: str = Field(
        description="Human-readable explanation of why this is a TP/FP/FN.",
    )


class CalibrationOrchestrationResult(BaseModel, frozen=True):
    """Wrapper for orchestrator output."""

    success: bool = Field(
        description="Whether the calibration run completed successfully.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if ground-truth failed.",
    )
    ground_truth_findings: list[CalibrationFindingTuple] = Field(
        default_factory=list,
        description="Ground-truth findings produced by the reference model.",
    )
    challenger_results: list[CalibrationRunResult] = Field(
        default_factory=list,
        description="Per-challenger calibration results.",
    )
