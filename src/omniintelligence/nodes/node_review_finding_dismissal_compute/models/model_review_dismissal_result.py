# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Output of the review finding dismissal node (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_finding_dismissal_record import (
    ModelReviewFindingDismissalRecord,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_dismissal_assignment import (
    ModelDismissalAssignment,
)


class ModelReviewDismissalResult(BaseModel):
    """One record per dismissal, the keys it clears, and the judgements still to ask."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    records: tuple[ModelReviewFindingDismissalRecord, ...] = ()
    cleared_keys: tuple[str, ...] = Field(
        default=(),
        description="Blocking findings a second voter's confirmation cleared.",
    )
    assignments: tuple[ModelDismissalAssignment, ...] = Field(
        default=(),
        description="Dismissals put to a second voter; judged ones carry a record too.",
    )


__all__ = ["ModelReviewDismissalResult"]
