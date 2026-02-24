# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Guardrail configuration models (OMN-2563).

All thresholds are loaded from ObjectiveSpec — zero hardcoded magic numbers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCorrelationPair(BaseModel):
    """A correlated metric pair to monitor for Goodhart's Law violations.

    When metric_a improves and metric_b degrades by more than the threshold,
    a GoodhartViolationAlert is emitted.
    """

    model_config = ConfigDict(frozen=True)

    metric_a: str = Field(description="First ScoreVector dimension (the one that may improve).")
    metric_b: str = Field(description="Second ScoreVector dimension (the correlated peer).")
    divergence_threshold: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "Maximum allowed divergence between metric_a improvement and metric_b degradation. "
            "Alert fires when abs(delta_a) + abs(delta_b) > threshold AND they move in "
            "opposite directions."
        ),
    )


class ModelGuardrailConfig(BaseModel):
    """Complete guardrail configuration loaded from ObjectiveSpec.

    All thresholds and parameters are loaded from ObjectiveSpec at runtime.
    """

    model_config = ConfigDict(frozen=True)

    objective_id: str = Field(description="ObjectiveSpec this config was sourced from.")

    # Goodhart's Law detection
    correlation_pairs: tuple[ModelCorrelationPair, ...] = Field(
        default=(),
        description="Correlated metric pairs to monitor for Goodhart violations.",
    )

    # Reward hacking detection
    reward_hacking_score_threshold: float = Field(
        default=0.1,
        gt=0.0,
        le=1.0,
        description=(
            "Minimum correctness improvement to trigger reward-hacking check. "
            "If correctness improves by > this AND acceptance rate doesn't improve, alert."
        ),
    )
    reward_hacking_acceptance_floor: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum expected acceptance rate improvement when correctness improves. "
            "If acceptance_rate_delta < this, fire alert."
        ),
    )

    # Distributional shift detection
    drift_threshold: float = Field(
        default=0.3,
        gt=0.0,
        description="KL-divergence threshold for distributional shift alert.",
    )
    baseline_window: int = Field(
        default=100,
        gt=0,
        description="Number of recent runs to use as baseline for drift detection.",
    )

    # Diversity constraint
    min_evidence_sources: int = Field(
        default=2,
        ge=1,
        description=(
            "Minimum number of distinct EvidenceItem source types required. "
            "Fewer than this causes DiversityConstraintViolation (veto)."
        ),
    )


__all__ = ["ModelCorrelationPair", "ModelGuardrailConfig"]
