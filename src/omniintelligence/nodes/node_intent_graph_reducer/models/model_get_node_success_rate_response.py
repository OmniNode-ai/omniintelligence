# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Success rate for the requested intent class."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelGetNodeSuccessRateResponse(BaseModel):
    """Success rate for the requested intent class."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    success_rate: float
