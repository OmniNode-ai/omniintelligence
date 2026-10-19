# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One reviewer's recorded review of one target (OMN-20981).

Seam: this is the minimal local shape of the ``ModelReviewRecord`` in the
review-learning plan of 2026-10-18 (section 3.1). The plan's ticket 2 owns the final record, the
``ModelRecordedFinding`` envelope and the ``review-recorded`` topic; until it
merges, findings are carried as the canonical ``ModelReviewFindingObserved``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.review_pairing.models import ModelReviewFindingObserved

REVIEW_RECORDED_SCHEMA_VERSION: Final = "review_recorded.v1"

ArmKind = Literal["voter", "substitute", "receipt_reviewer"]


class ModelReviewRecorded(BaseModel):
    """What one arm said about one target, findings included."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: Literal["review_recorded.v1"] = REVIEW_RECORDED_SCHEMA_VERSION
    review_id: UUID = Field(description="Deterministic id of this arm's record.")
    invocation_id: UUID = Field(description="The run that produced the record.")
    arm: str = Field(
        min_length=1,
        description="Voter id, or the stand-in reviewers joined with '+'.",
    )
    arm_kind: ArmKind
    reviewer_identity: str | None = None
    prompt_version: str | None = None
    review_type: Literal["pr", "plan"]
    repo: str | None = None
    pr: int | None = Field(default=None, gt=0)
    head_sha: str | None = None
    execution_status: Literal["completed", "failed"]
    verdict: Literal["clean", "findings", "failed"]
    failure_reason: str | None = None
    findings: tuple[ModelReviewFindingObserved, ...] = ()
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    substitute_for: str | None = Field(
        default=None, description="The lost voter a substitute vote replaced."
    )
    substitute_reviewer_ids: tuple[str, ...] = ()
    substitute_review_authors: tuple[str, ...] = ()
    recorded_at: datetime

    @model_validator(mode="after")
    def _validate_record(self) -> Self:
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must carry a timezone")
        failed = self.execution_status == "failed"
        if failed != (self.verdict == "failed"):
            raise ValueError("verdict is 'failed' exactly when the run failed")
        if failed and self.findings:
            raise ValueError("a failed run records no findings")
        if self.verdict == "clean" and self.findings:
            raise ValueError("a clean verdict records no findings")
        if self.verdict == "findings" and not self.findings:
            raise ValueError("a findings verdict records at least one finding")
        return self


__all__ = ["REVIEW_RECORDED_SCHEMA_VERSION", "ArmKind", "ModelReviewRecorded"]
