# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the review receipt substitute node (OMN-20947)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.review_pairing.models_external_review import (
    ModelSubstituteVoteRecord,
)


class ModelSubstituteDecision(BaseModel):
    """Which lost voters valid receipts stand in for, and every refusal."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    records: tuple[ModelSubstituteVoteRecord, ...] = ()
    refusals: tuple[str, ...] = ()


__all__ = ["ModelSubstituteDecision"]
