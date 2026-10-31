# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input for resetting a failure streak on recovery."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelStreakResetRequest(BaseModel):
    """Input for resetting a failure streak on recovery."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
