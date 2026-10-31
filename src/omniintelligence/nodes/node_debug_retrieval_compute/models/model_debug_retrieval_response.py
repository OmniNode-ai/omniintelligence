# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Response containing time-decayed CI fix records."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ModelDebugRetrievalResponse(BaseModel):
    """Fix records annotated with time-decay weights, ordered by recency."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    records: list[dict[str, Any]]


__all__ = ["ModelDebugRetrievalResponse"]
