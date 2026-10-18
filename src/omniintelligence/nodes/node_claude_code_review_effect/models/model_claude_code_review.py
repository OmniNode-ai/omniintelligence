# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Secret-free messages for Claude Code review (OMN-20910)."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelClaudeCodeReviewRequest(BaseModel):
    """Prompts and the overlay's exact model; credentials never enter a message."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    model: str = Field(min_length=1, pattern=r"^claude-[a-z0-9][a-z0-9.-]*$")
    system_prompt: str
    user_prompt: str
    timeout_seconds: float = Field(gt=0, le=1800)
    max_output_tokens: int = Field(default=4096, gt=0)


type ClaudeCodeReviewError = Literal[
    "claude_pool_unavailable",
    "claude_pool_all_limited",
    "claude_pool_invalid_response",
    "claude_pool_mark_failed",
    "claude_pool_rotation_stalled",
    "claude_code_unavailable",
    "claude_code_failed",
    "claude_code_invalid_response",
    "claude_code_timeout",
]


class ModelClaudeCodeReviewResult(BaseModel):
    """A review or a stable failure code, with no raw process diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID
    success: bool = False
    response: str = ""
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    error: ClaudeCodeReviewError | None = None
