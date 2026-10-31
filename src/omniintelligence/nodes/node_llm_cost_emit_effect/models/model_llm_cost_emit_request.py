# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the LLM cost emitter (OMN-6801)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelLlmCostEmitRequest(BaseModel):
    """One LLM call's cost telemetry.

    Payload fields match the omnidash consumer's ``projectLlmCostEvent`` primary
    (snake_case) paths.

    Attributes:
        model_id: LLM model identifier.
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

    model_id: str = Field(description="LLM model identifier.")
    prompt_tokens: int = Field(description="Number of prompt/input tokens.")
    completion_tokens: int = Field(description="Number of completion/output tokens.")
    total_tokens: int = Field(description="Total tokens (prompt + completion).")
    estimated_cost_usd: float = Field(description="Estimated cost in USD.")
    session_id: str = Field(description="Session ID for attribution.")
    correlation_id: str | UUID = Field(description="Correlation ID for tracing.")
    endpoint_url: str = Field(default="", description="LLM endpoint URL.")
    request_type: str = Field(
        default="completion", description="Request type (completion, chat, embedding)."
    )
    latency_ms: int = Field(default=0, description="Request latency in milliseconds.")
    repo_name: str | None = Field(
        default=None, description="Repository name for cost attribution."
    )
    machine_id: str | None = Field(
        default=None, description="Machine identifier for cost attribution."
    )


__all__ = ["ModelLlmCostEmitRequest"]
