# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input for reading the current failure streak."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelStreakQueryRequest(BaseModel):
    """Input for reading the current failure streak."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str
    branch: str
