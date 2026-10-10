# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Output of the review voters overlay node (OMN-20910)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_resolved_review_voter import (
    ModelResolvedReviewVoter,
)

if TYPE_CHECKING:
    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )


class ModelReviewVoterRoster(BaseModel):
    """Every voter of one overlay, resolved, in declaration order -- or why not.

    A refused overlay is data (``error`` set, ``voters`` empty), never a raise:
    the caller decides how loudly to fail, and every caller fails.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    overlay_source: str
    voters: tuple[ModelResolvedReviewVoter, ...] = ()
    error: str = Field(default="", description="Why the overlay was refused.")
    error_voter_id: str = Field(
        default="", description="The voter the refusal is about, when one is."
    )

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def error_message(self) -> str:
        prefix = (
            f"review voter {self.error_voter_id!r}: " if self.error_voter_id else ""
        )
        return f"{prefix}{self.error}"

    @property
    def voter_ids(self) -> list[str]:
        return [v.voter_id for v in self.voters]

    @property
    def required_ids(self) -> frozenset[str]:
        return frozenset(v.voter_id for v in self.voters if v.voter.required)

    def get(self, voter_id: str) -> ModelResolvedReviewVoter | None:
        for voter in self.voters:
            if voter.voter_id == voter_id:
                return voter
        return None

    def endpoint_configs(self) -> dict[str, ModelEndpointConfig]:
        return {v.voter_id: v.endpoint_config() for v in self.voters}


__all__ = ["ModelReviewVoterRoster"]
