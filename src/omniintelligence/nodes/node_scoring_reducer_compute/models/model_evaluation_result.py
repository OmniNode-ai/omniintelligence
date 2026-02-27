# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""EvaluationResult model (OMN-2537).

The output of a single ScoringReducerCompute evaluation. Contains:
- passed: Whether all hard gates passed.
- score_vector: The shaped reward score (zero if any gate failed).
- failures: IDs of gates that failed (empty if passed=True).
- attribution_refs: EvidenceItem IDs that contributed to non-zero score dims.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_scoring_reducer_compute.models.model_score_vector import (
    ModelScoreVector,
)


class ModelEvaluationResult(BaseModel):
    """Result of evaluating an EvidenceBundle against an ObjectiveSpec.

    This model is frozen — no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    passed: bool = Field(
        description="True if all hard gates passed; False if any gate failed."
    )
    score_vector: ModelScoreVector = Field(
        description=(
            "Shaped reward ScoreVector. All-zero if passed=False. "
            "Non-zero values only when all gates passed."
        )
    )
    failures: tuple[str, ...] = Field(
        default=(),
        description=(
            "IDs of GateSpec gates that failed. Empty when passed=True. "
            "Non-empty only when passed=False."
        ),
    )
    attribution_refs: tuple[str, ...] = Field(
        default=(),
        description=(
            "EvidenceItem.item_id values that contributed to non-zero ScoreVector "
            "dimensions. Empty when passed=False."
        ),
    )


__all__ = ["ModelEvaluationResult"]
