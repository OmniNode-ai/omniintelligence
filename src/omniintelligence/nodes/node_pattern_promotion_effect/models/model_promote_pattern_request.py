# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for emitting a single pattern promotion lifecycle event."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPromotePatternRequest(BaseModel):
    """Pattern data and trace context for a single promotion."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    pattern_id: UUID = Field(description="Identifier of the pattern to promote")
    pattern_data: Mapping[str, Any] = Field(
        description="Pattern record containing signature and promotion gate values"
    )
    correlation_id: UUID | None = Field(
        default=None, description="Optional correlation ID for tracing"
    )
