# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The review voters overlay document (OMN-20910)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter import (
    ModelReviewVoter,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_substitute_vote_policy import (
    ModelSubstituteVotePolicy,
)

REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION = "review_voters_overlay.v1"
REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION_V2 = "review_voters_overlay.v2"
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = (
    REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION,
    REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION_V2,
)


class ModelReviewVotersOverlay(BaseModel):
    """The whole overlay file: a schema version, a backend overlay, the voters."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: str = Field(min_length=1)
    backend_overlay: str | None = Field(
        default=None,
        description="File name, in the same directory, of the "
        "bifrost_lane_overlay.v3 file backend_id values resolve against.",
    )
    provider_endpoints: dict[str, str] = Field(
        default_factory=dict,
        description="Cloud provider base URLs supplied by the deployment overlay, keyed by provider.",
    )
    voters: tuple[ModelReviewVoter, ...] = Field(min_length=1)
    substitute_votes: ModelSubstituteVotePolicy | None = Field(
        default=None,
        description="Off-CI review receipts that may stand in for a voter that "
        "timed out (OMN-20947). Absent: no receipt is ever accepted.",
    )

    @model_validator(mode="after")
    def _validate_overlay(self) -> Self:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version must be one of {list(SUPPORTED_SCHEMA_VERSIONS)}, "
                f"got {self.schema_version!r}"
            )
        if self.schema_version == REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION:
            v2_only = [v.voter_id for v in self.voters if v.uses_v2_fields]
            if v2_only:
                raise ValueError(
                    f"voters {v2_only} use personas or claude_gateway, which need "
                    f"schema_version {REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION_V2!r}"
                )
        ids = [voter.voter_id for voter in self.voters]
        duplicates = sorted({vid for vid in ids if ids.count(vid) > 1})
        if duplicates:
            raise ValueError(f"voter ids must be unique, repeated: {duplicates}")
        persona_ids = [p.persona_id for v in self.voters for p in v.personas]
        repeated_personas = sorted(
            {pid for pid in persona_ids if persona_ids.count(pid) > 1}
        )
        if repeated_personas:
            raise ValueError(
                f"persona ids must be unique across voters, repeated: {repeated_personas}"
            )
        if not any(voter.required for voter in self.voters):
            raise ValueError("at least one voter must be required")
        if self.backend_overlay is not None and (
            "/" in self.backend_overlay or "\\" in self.backend_overlay
        ):
            raise ValueError(
                "backend_overlay is a file name in the overlay's own directory, "
                f"got {self.backend_overlay!r}"
            )
        uses_backend = [v.voter_id for v in self.voters if v.backend_id is not None]
        if uses_backend and self.backend_overlay is None:
            raise ValueError(
                f"voters {uses_backend} name a backend_id but the overlay "
                "declares no backend_overlay to resolve it against"
            )
        if self.substitute_votes is not None:
            clashes = sorted(
                {r.reviewer_id for r in self.substitute_votes.reviewers} & set(ids)
            )
            if clashes:
                raise ValueError(
                    f"substitute reviewer ids {clashes} are also voter ids; a "
                    "receipt must never read as the voter it stands in for"
                )
        return self


__all__ = [
    "REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION",
    "REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION_V2",
    "SUPPORTED_SCHEMA_VERSIONS",
    "ModelReviewVotersOverlay",
]
