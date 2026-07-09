# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output envelope models for external model review.

Provides structured result types for single-model and multi-model
adversarial review results. Used by both the LLM adapter and Codex
CLI adapter.

Reference: OMN-5790
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.review_pairing.models import ModelReviewFindingObserved


class ModelEndpointConfig(BaseModel, frozen=True):
    """Configuration for a model endpoint in the registry.

    Attributes:
        env_var: Environment variable name for the endpoint URL.
        default_url: Fallback URL when env var is not set.
        kind: Model capability category (reasoning, long_context, fast_review).
        timeout_seconds: Request timeout in seconds.
        api_model_id: Model identifier for the API (empty string for CLI-only models).
        enable_thinking: Whether the model is allowed to emit a reasoning
            preamble (Qwen3 chat_template_kwargs.enable_thinking). Declarative
            per-model toggle (OMN-14176) -- flipping reasoning off/on for a
            model is a config change here, not a code change in call_model().
    """

    env_var: str = Field(description="Environment variable name for the endpoint URL.")
    default_url: str = Field(description="Fallback URL when env var is not set.")
    kind: str = Field(
        description="Model capability category (reasoning, long_context, fast_review)."
    )
    timeout_seconds: float = Field(description="Request timeout in seconds.")
    api_model_id: str = Field(
        default="",
        description="Model identifier for the API (empty string for CLI-only models).",
    )
    enable_thinking: bool = Field(
        default=True,
        description=(
            "Whether the model may emit a reasoning preamble before its "
            "answer (Qwen3 chat_template_kwargs.enable_thinking). Additive: "
            "defaults to the pre-OMN-14176 behavior (thinking allowed) so "
            "existing entries that don't set it are unaffected."
        ),
    )


class ModelExternalReviewResult(BaseModel, frozen=True):
    """Top-level output envelope for a single external model review.

    Attributes:
        model: Model key (e.g. "deepseek-r1", "codex").
        prompt_version: Version of the adversarial prompt used.
        success: True if model returned usable output.
        error: Failure reason if success is False.
        findings: List of canonical review findings.
        result_count: Number of findings (explicit for fast scanning).
    """

    model: str = Field(description="Model key used for this review.")
    prompt_version: str = Field(description="Adversarial prompt version.")
    success: bool = Field(description="True if model returned usable output.")
    error: str | None = Field(
        default=None, description="Failure reason if success is False."
    )
    findings: list[ModelReviewFindingObserved] = Field(
        default_factory=list, description="Canonical review findings."
    )
    result_count: int = Field(
        default=0, description="Number of findings (len(findings))."
    )


class ModelMultiReviewResult(BaseModel, frozen=True):
    """Aggregated output from multiple model reviews.

    Attributes:
        models_attempted: List of model keys attempted.
        models_succeeded: List of models that returned success=True.
        models_failed: List of models that returned success=False.
        results: Per-model result envelopes.
        total_findings: Sum of findings across all successful models.
    """

    models_attempted: list[str] = Field(
        default_factory=list, description="Model keys attempted."
    )
    models_succeeded: list[str] = Field(
        default_factory=list, description="Models that succeeded."
    )
    models_failed: list[str] = Field(
        default_factory=list, description="Models that failed."
    )
    results: list[ModelExternalReviewResult] = Field(
        default_factory=list, description="Per-model result envelopes."
    )
    total_findings: int = Field(
        default=0, description="Sum of findings across all successful models."
    )
