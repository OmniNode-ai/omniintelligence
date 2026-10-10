# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The review voters overlay document (OMN-20910)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter import (
    ModelReviewVoter,
)

REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION = "review_voters_overlay.v1"


class ModelReviewVotersOverlay(BaseModel):
    """The whole overlay file: a schema version, a backend overlay, the voters."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    schema_version: str = Field(min_length=1)
    backend_overlay: str | None = Field(
        default=None,
        description="File name, in the same directory, of the "
        "bifrost_lane_overlay.v3 file backend_id values resolve against.",
    )
    voters: tuple[ModelReviewVoter, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_overlay(self) -> Self:
        if self.schema_version != REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}"
            )
        ids = [voter.voter_id for voter in self.voters]
        duplicates = sorted({vid for vid in ids if ids.count(vid) > 1})
        if duplicates:
            raise ValueError(f"voter ids must be unique, repeated: {duplicates}")
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
        return self


__all__ = ["REVIEW_VOTERS_OVERLAY_SCHEMA_VERSION", "ModelReviewVotersOverlay"]
