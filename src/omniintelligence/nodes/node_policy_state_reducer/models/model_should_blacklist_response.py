# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Whether this update should trigger a blacklist action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelShouldBlacklistResponse(BaseModel):
    """Whether this update should trigger a blacklist action."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    should_blacklist: bool
