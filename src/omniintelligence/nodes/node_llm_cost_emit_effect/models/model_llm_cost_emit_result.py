# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the LLM cost emitter (OMN-6801)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelLlmCostEmitResult(BaseModel):
    """Whether the cost event reached the producer.

    Attributes:
        emitted: True if the event was published; False when there was no
            producer or publishing failed (both are fail-open, never raised).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    emitted: bool = Field(description="True if the cost event was published.")


__all__ = ["ModelLlmCostEmitResult"]
