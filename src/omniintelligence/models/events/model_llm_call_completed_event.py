# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for LLM call completion telemetry.

Published by LLM clients (e.g., EvalLLMClient) after each successful
LLM API call. Consumed by omnidash Cost Trends projection to display
token volume and latency trends.

Note:
    ``cost_usd`` starts at 0.0 — cost estimation via per-token lookup
    is a follow-up (OMN-5223). Until then, the Cost Trends page shows
    token volume trends, not dollar costs.

Reference: OMN-5184 (Dashboard Data Pipeline Gaps)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelLLMCallCompletedEvent(BaseModel):
    """Frozen event model for LLM call completion telemetry.

    Emitted after each successful LLM API call with token usage,
    latency, and routing metadata. Consumed by omnidash Cost Trends
    projection.

    Fields are intentionally flat (no nesting) to match the omnidash
    Drizzle table schema for direct projection mapping.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    model_id: str = Field(
        min_length=1, description="LLM model identifier, e.g. 'qwen3-coder-30b'"
    )
    endpoint_url: str = Field(
        min_length=1, description="LLM endpoint URL, e.g. 'http://192.168.86.201:8000'"
    )
    input_tokens: int = Field(
        ge=0, description="Prompt tokens from API response usage.prompt_tokens"
    )
    output_tokens: int = Field(
        ge=0, description="Completion tokens from API response usage.completion_tokens"
    )
    total_tokens: int = Field(ge=0, description="input_tokens + output_tokens")
    cost_usd: float = Field(
        ge=0.0,
        description="Estimated cost in USD. 0.0 until OMN-5223 wires cost lookup.",
    )
    latency_ms: int = Field(
        ge=0, description="Wall-clock time of the HTTP call in milliseconds"
    )
    request_type: str = Field(
        min_length=1,
        description="Type of LLM request: 'completion', 'classification', 'reasoning', or 'embedding'",
    )
    correlation_id: str = Field(
        min_length=1, description="Distributed tracing correlation ID"
    )
    session_id: str = Field(min_length=1, description="Session ID from request context")
    emitted_at: datetime = Field(description="UTC timestamp of event emission")

    @field_validator("emitted_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that emitted_at is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")
        return v


__all__ = ["ModelLLMCallCompletedEvent"]
