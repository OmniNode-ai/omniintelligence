# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for file access pattern extraction."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_session_pattern_request import (
    ModelSessionPatternRequest,
)


class ModelFilePatternRequest(ModelSessionPatternRequest):
    """Request for file access pattern extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    min_occurrences: int = Field(default=5, description="Minimum pattern occurrences")


__all__ = ["ModelFilePatternRequest"]
