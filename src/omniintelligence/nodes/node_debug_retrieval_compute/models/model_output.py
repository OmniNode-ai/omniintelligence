# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for debug retrieval compute node."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelDebugRetrievalOutput(BaseModel):
    """Output for NodeDebugRetrievalCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    fix_records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Fix records annotated with time_decay_weight, ordered by recency.",
    )


__all__ = ["ModelDebugRetrievalOutput"]
