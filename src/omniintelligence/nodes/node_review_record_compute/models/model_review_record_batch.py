# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the review record node (OMN-20981)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_review_record_compute.models.model_review_recorded import (
    ModelReviewRecorded,
)


class ModelReviewRecordBatch(BaseModel):
    """The run's records: voters first in result order, then substitute votes."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    records: tuple[ModelReviewRecorded, ...] = ()


__all__ = ["ModelReviewRecordBatch"]
