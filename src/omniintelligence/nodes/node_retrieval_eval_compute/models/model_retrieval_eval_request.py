# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for one offline retrieval eval run (OMN-21945)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelRetrievalEvalRequest(BaseModel):
    """One run of the harness over the committed replay corpus and golden set.

    The run is fully offline and reads only committed fixtures, so the request
    carries nothing but the correlation id that threads the run end to end.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation id threaded through the run for tracing.",
    )


__all__ = ["ModelRetrievalEvalRequest"]
