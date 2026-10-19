# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The typed result of one review model call (OMN-20910).

The provider's stop reason travels with the text so the parser decides whether
the reply is a complete review. A bare string cannot say that it was cut off.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

NORMAL_STOP_REASONS: frozenset[str] = frozenset({"tool_use", "end_turn", "stop"})
"""Normal ends: Messages ``tool_use`` and ``end_turn``, OpenAI-compatible ``stop``."""


class ModelReviewCallResponse(BaseModel):
    """Content, stop reason, usage and served model of one call.

    Attributes:
        content: The reply text, reasoning stripped.
        stop_reason: The provider's stop or finish reason, None when the
            transport reports none (an unknown end is not a normal end).
        input_tokens: Prompt tokens billed, 0 when not reported.
        output_tokens: Completion tokens billed, 0 when not reported.
        served_model: The model the provider says it served, when it says.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(description="Reply text.")
    stop_reason: str | None = Field(default=None, description="Provider stop reason.")
    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens.")
    output_tokens: int = Field(default=0, ge=0, description="Completion tokens.")
    served_model: str | None = Field(default=None, description="Served model id.")

    @property
    def completed_normally(self) -> bool:
        """True only for a reported normal end; ``max_tokens``/``length``/None are not."""
        return self.stop_reason in NORMAL_STOP_REASONS


__all__ = ["NORMAL_STOP_REASONS", "ModelReviewCallResponse"]
