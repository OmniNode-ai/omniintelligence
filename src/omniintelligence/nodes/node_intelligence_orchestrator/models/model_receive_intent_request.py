# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Receive one reducer intent with optional tracing context."""

from __future__ import annotations

from uuid import UUID

from omnibase_core.models.reducer.model_intent import ModelIntent
from pydantic import BaseModel, ConfigDict


class ModelReceiveIntentRequest(BaseModel):
    """Receive one reducer intent with optional tracing context."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    intent: ModelIntent
    correlation_id: UUID | None = None


__all__ = ["ModelReceiveIntentRequest"]
