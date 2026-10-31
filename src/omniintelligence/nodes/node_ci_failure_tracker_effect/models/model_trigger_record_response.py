# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Trigger created when the failure streak meets the threshold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ModelTriggerRecordResponse(BaseModel):
    """Trigger created when the failure streak meets the threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    trigger: dict[str, Any] | None
