# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the receipt issuing operation (OMN-20981)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.review_pairing.models import ModelReviewFindingObserved


class ModelIssueReceiptRequest(BaseModel):
    """An off-CI reviewer's findings on one head commit, and the key to sign with."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    invocation_id: UUID
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    reviewer_id: str = Field(min_length=1, max_length=63)
    findings: tuple[ModelReviewFindingObserved, ...] = ()
    issued_at: datetime = Field(description="The reviewer's clock, timezone-aware.")
    key: bytes = Field(min_length=1, description="The receipt signing key.")


__all__ = ["ModelIssueReceiptRequest"]
