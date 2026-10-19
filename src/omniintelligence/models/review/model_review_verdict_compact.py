# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A complete compact review verdict (OMN-20910)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_finding_compact import (
    ModelReviewFindingCompact,
)


class ModelReviewVerdictCompact(BaseModel):
    """One voter's verdict in the v2 wire format.

    Attributes:
        v: The defect-catalog version the voter was given.
        f: The findings. The cap (``max_findings``) is a roster value enforced by
            the verdict schema and by the strict parser, not by this model.
        more: True when the voter found more defects than it could list. A
            verdict with ``more`` true is never a complete review.
        done: Terminal marker, always true; a cut reply does not carry it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    v: str = Field(min_length=1, description="Catalog version the voter was given.")
    f: list[ModelReviewFindingCompact] = Field(description="The findings.")
    more: bool = Field(description="More defects than the voter could list.")
    done: Literal[True] = Field(description="Terminal marker.")


__all__ = ["ModelReviewVerdictCompact"]
