# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for time-decayed retrieval of past CI fix records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelDebugRetrievalRequest(BaseModel):
    """A failure fingerprint, result limit, and optional reference time."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    failure_fingerprint: str
    limit: int = 10
    now: datetime | None = None


__all__ = ["ModelDebugRetrievalRequest"]
