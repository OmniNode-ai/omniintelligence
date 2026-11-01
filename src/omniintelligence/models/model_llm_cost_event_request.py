# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for the LLM cost telemetry emitter (OMN-6801)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelLlmCostEventRequest(BaseModel):
    """One LLM call's cost telemetry to publish.

    Attributes:
        model_id: LLM model identifier (e.g. "qwen3-14b").
        prompt_tokens: Number of prompt/input tokens.
        completion_tokens: Number of completion/output tokens.
        total_tokens: Total tokens (prompt + completion).
        estimated_cost_usd: Estimated cost in USD.
        session_id: Session ID for attribution.
        correlation_id: Correlation ID for tracing.
        endpoint_url: LLM endpoint URL.
        request_type: Request type (completion, chat, embedding).
        latency_ms: Request latency in milliseconds.
        repo_name: Optional repository name for cost attribution.
        machine_id: Optional machine identifier for cost attribution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    session_id: str
    correlation_id: str | UUID
    endpoint_url: str = ""
    request_type: str = "completion"
    latency_ms: int = 0
    repo_name: str | None = None
    machine_id: str | None = None


__all__ = ["ModelLlmCostEventRequest"]
