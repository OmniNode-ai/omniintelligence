# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Paginated response model for pattern queries.

Ticket: OMN-2253
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.api.model_pattern_query_response import ModelPatternQueryResponse


class ModelPatternQueryPage(BaseModel):
    """Paginated response for pattern queries.

    Wraps a list of pattern results with pagination metadata
    to support cursor-free offset-based pagination.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    patterns: list[ModelPatternQueryResponse] = Field(
        ...,
        description="List of patterns matching the query",
    )
    total_returned: int = Field(
        ...,
        ge=0,
        description=(
            "Number of patterns in this page. "
            "When total_returned < limit, this is the final page."
        ),
    )
    limit: int = Field(
        ...,
        ge=1,
        le=200,
        description="Maximum patterns per page (request parameter)",
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Number of patterns skipped (request parameter)",
    )


__all__ = ["ModelPatternQueryPage"]
