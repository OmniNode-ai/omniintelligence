# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Statistical significance result for a shadow variant."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelUpgradeReadyResponse(BaseModel):
    """Statistical significance result for a shadow variant."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    ready: bool = Field(
        description="Whether the shadow variant is ready for promotion."
    )


__all__ = ["ModelUpgradeReadyResponse"]
