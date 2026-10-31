# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for session pattern extraction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_session_snapshot import (
    ModelSessionSnapshot,
)


class ModelSessionPatternRequest(BaseModel):
    """Request for session pattern extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    sessions: tuple[ModelSessionSnapshot, ...] = Field(
        description="Session snapshots to analyze"
    )
    min_occurrences: int = Field(default=2, description="Minimum pattern occurrences")
    min_confidence: float = Field(default=0.6, description="Minimum pattern confidence")
    min_distinct_sessions: int = Field(
        default=2, description="Minimum distinct sessions containing a pattern"
    )
    max_results_per_type: int = Field(
        default=20, description="Maximum results per pattern type"
    )


__all__ = ["ModelSessionPatternRequest"]
