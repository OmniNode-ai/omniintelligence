# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One recorded dismissal of a blocking review finding and its judgement (OMN-20910).

A pull request author who refutes a blocking Hostile Reviewer finding records a
dismissal of it, with evidence, for one head. A second voter judges the
dismissal against the finding and the evidence. This record is what the gate
writes to the pull request and emits as an event for every dismissal it read,
whatever the outcome.
"""

from __future__ import annotations

from enum import Enum, unique
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


@unique
class EnumReviewDismissalOutcome(str, Enum):
    """What became of one recorded dismissal."""

    CONFIRMED = "confirmed"
    """A second voter judged the evidence to refute the finding; it stops blocking."""

    REJECTED = "rejected"
    """The second voter did not confirm it, or could not be asked; it keeps blocking."""

    REFUSED = "refused"
    """The dismissal was not put to a voter at all (see ``refusal``); it keeps blocking."""


@unique
class EnumReviewDismissalRefusal(str, Enum):
    """Why a dismissal was refused before any voter judged it."""

    NO_EVIDENCE = "no_evidence"
    STALE_HEAD = "stale_head"
    UNKNOWN_FINDING = "unknown_finding"
    NOT_AUTHORIZED = "not_authorized"
    NO_SECOND_VOTER = "no_second_voter"


class ModelReviewFindingDismissalRecord(BaseModel):
    """The event for one dismissal: who dismissed what, on which head, and the outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    finding_key: str = Field(min_length=1, description="The dismissed finding's key.")
    head_sha: str = Field(description="The head the review ran on.")
    dismissal_head_sha: str = Field(description="The head the dismissal names.")
    author: str = Field(description="Who recorded the dismissal.")
    source: str = Field(description="Where it was read: a comment id or a file path.")
    evidence: str = Field(description="The evidence the author gave.")
    outcome: EnumReviewDismissalOutcome
    refusal: EnumReviewDismissalRefusal | None = None
    judge_voter: str | None = Field(
        default=None, description="The voter that judged it; None when refused."
    )
    judge_raised_finding: bool = Field(
        default=False,
        description=(
            "True when the judge was itself one of the voters that raised the "
            "finding: every succeeded voter raised it, and the first raiser was "
            "excluded."
        ),
    )
    judge_reason: str = Field(default="", description="The judge's stated reason.")
    file_path: str = Field(default="", description="The finding's path.")
    line_start: int = Field(default=0, description="The finding's line.")
    severity: str = Field(default="", description="The finding's severity.")
    rule: str = Field(default="", description="The finding's agreement key.")
    repo: str | None = None
    pr: int | None = None
    correlation_id: UUID | None = None


__all__ = [
    "EnumReviewDismissalOutcome",
    "EnumReviewDismissalRefusal",
    "ModelReviewFindingDismissalRecord",
]
