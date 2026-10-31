# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input for incrementing a failure streak."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelStreakIncrementRequest(BaseModel):
    """Input for incrementing a failure streak."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
    sha: str
