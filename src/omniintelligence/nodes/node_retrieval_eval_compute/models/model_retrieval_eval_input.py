# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the retrieval eval compute node."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelRetrievalEvalInput(BaseModel):
    """One request to run the offline retrieval eval over the frozen fixtures."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation id threaded through the handler's log lines.",
    )


__all__ = ["ModelRetrievalEvalInput"]
