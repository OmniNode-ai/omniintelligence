# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the review record node (OMN-20981)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelSubstituteVoteRecord,
)


class ModelReviewRecordRequest(BaseModel):
    """A run's voter results as the voters returned them, and its substitute votes.

    ``results`` are the voters' own results, before any substitute replaced a
    lost voter, so a lost voter is recorded as the failed run it was.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    invocation_id: UUID
    recorded_at: datetime = Field(description="The run's clock, timezone-aware.")
    review_type: Literal["pr", "plan"]
    repo: str | None = None
    pr: int | None = Field(default=None, gt=0)
    head_sha: str | None = None
    results: tuple[ModelExternalReviewResult, ...] = ()
    substitute_votes: tuple[ModelSubstituteVoteRecord, ...] = ()


__all__ = ["ModelReviewRecordRequest"]
