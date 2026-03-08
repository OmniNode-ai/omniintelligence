# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for debug retrieval compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelDebugRetrievalInput(BaseModel):
    """Input for NodeDebugRetrievalCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    failure_fingerprint: str = Field(
        description="SHA-256 hex fingerprint to look up past fixes for."
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of fix records to retrieve.",
    )


__all__ = ["ModelDebugRetrievalInput"]
