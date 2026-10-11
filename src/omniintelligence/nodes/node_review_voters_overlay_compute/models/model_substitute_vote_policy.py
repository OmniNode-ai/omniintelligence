# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""When a timed-out voter's vote may come from an off-CI review receipt (OMN-20947).

A voter that times out casts no vote, and with two required voters one lost
vote is no quorum, so the gate fails closed. This policy lets a run accept,
in place of that one lost vote, clean review receipts from approved reviewers
that ran outside CI against the exact head commit. It is optional and absent
by default: an overlay without it accepts no receipt, so a fork's gate behaves
exactly as before. Which reviewers count and for how long a receipt is valid
are deployment facts, set by whoever supplies the overlay.
"""

from __future__ import annotations

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter import (
    VOTER_ID_PATTERN,
)

_ENV_NAME_PATTERN = r"^[A-Z][A-Z0-9_]{0,127}$"
_GITHUB_LOGIN_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?$"
_MAX_RECEIPT_AGE_SECONDS = 7 * 24 * 3600


class ModelSubstituteReviewer(BaseModel):
    """One off-CI reviewer whose clean receipt may stand in for a lost vote."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    reviewer_id: str = Field(
        pattern=VOTER_ID_PATTERN,
        description="Name the receipt carries, e.g. the reviewing tool's role.",
    )
    github_logins: tuple[str, ...] = Field(
        min_length=1,
        description="Accounts whose pull request reviews may carry this "
        "reviewer's receipts. A receipt posted by any other account is ignored.",
    )

    @model_validator(mode="after")
    def _validate_logins(self) -> Self:
        bad = [
            login
            for login in self.github_logins
            if not re.fullmatch(_GITHUB_LOGIN_PATTERN, login)
        ]
        if bad:
            raise ValueError(
                f"substitute reviewer {self.reviewer_id!r} names invalid "
                f"github_logins {bad}"
            )
        return self


class ModelSubstituteVotePolicy(BaseModel):
    """Which receipts may replace the vote of a voter that timed out."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    reviewers: tuple[ModelSubstituteReviewer, ...] = Field(
        min_length=1, description="The approved off-CI reviewers."
    )
    receipts_per_vote: int = Field(
        default=1,
        ge=1,
        description="How many DISTINCT approved reviewers must each post a clean "
        "receipt for the head commit before their receipts count as one vote.",
    )
    receipt_max_age_seconds: int = Field(
        gt=0,
        le=_MAX_RECEIPT_AGE_SECONDS,
        description="A receipt older than this when the gate runs is ignored.",
    )
    signing_key_env: str = Field(
        pattern=_ENV_NAME_PATTERN,
        description="Name of the environment variable that holds the shared "
        "key receipts are signed with. The key itself never appears here.",
    )

    @model_validator(mode="after")
    def _validate_policy(self) -> Self:
        ids = [r.reviewer_id for r in self.reviewers]
        duplicates = sorted({rid for rid in ids if ids.count(rid) > 1})
        if duplicates:
            raise ValueError(
                f"substitute reviewer ids must be unique, repeated: {duplicates}"
            )
        if self.receipts_per_vote > len(self.reviewers):
            raise ValueError(
                f"receipts_per_vote {self.receipts_per_vote} exceeds the "
                f"{len(self.reviewers)} approved reviewer(s)"
            )
        return self

    def reviewer(self, reviewer_id: str) -> ModelSubstituteReviewer | None:
        for reviewer in self.reviewers:
            if reviewer.reviewer_id == reviewer_id:
                return reviewer
        return None


__all__ = ["ModelSubstituteReviewer", "ModelSubstituteVotePolicy"]
