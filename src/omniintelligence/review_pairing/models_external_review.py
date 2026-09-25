# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output envelope models for external model review.

Provides structured result types for single-model and multi-model
adversarial review results. Used by both the LLM adapter and Codex
CLI adapter.

Reference: OMN-5790
"""

from __future__ import annotations

from enum import Enum, unique
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)


class ModelEndpointConfig(BaseModel, frozen=True):
    """Configuration for a model endpoint in the registry.

    Attributes:
        env_var: Environment variable name for the endpoint URL.
        default_url: Fallback URL when env var is not set.
        kind: Model capability category (reasoning, long_context, fast_review).
        timeout_seconds: Request timeout in seconds.
        api_model_id: Model identifier for the API. Empty for CLI-only models
            and for every ``model_id_source: served`` entry.
        model_id_source: ``declared`` (send ``api_model_id``) or ``served``
            (resolve the id at call time from the endpoint's ``/v1/models``).
            OMN-18623, under the operator ruling of 2026-09-17T19:54:09Z that
            the reviewer's model must not be a hardcoded literal. Defaults to
            ``declared`` so existing entries are unaffected.
        enable_thinking: Whether the model is allowed to emit a reasoning
            preamble (Qwen3 chat_template_kwargs.enable_thinking). Declarative
            per-model toggle (OMN-14176) -- flipping reasoning off/on for a
            model is a config change here, not a code change in call_model().
        max_retries: Optional per-model override for HTTP retry attempts
            (OMN-15115). ``None`` (default) means "no override" -- call_model
            leaves ``ModelLlmInferenceRequest.max_retries`` at its own default
            (3, matching the transport's historical hardcoded behavior).
            Set this for endpoints where retrying a timeout doesn't help
            (a systematically slow, not transiently-flaky, endpoint) --
            retrying just re-spends the same wall-clock budget for the same
            outcome, and on a single-concurrency-slot endpoint it also
            extends how long that slot is held by a doomed request.
    """

    env_var: str = Field(description="Environment variable name for the endpoint URL.")
    default_url: str = Field(description="Fallback URL when env var is not set.")
    kind: str = Field(
        description="Model capability category (reasoning, long_context, fast_review)."
    )
    timeout_seconds: float = Field(description="Request timeout in seconds.")
    api_model_id: str = Field(
        default="",
        description=(
            "Model identifier for the API. Empty for CLI-only models AND for "
            "every entry whose model_id_source is 'served' -- see that field."
        ),
    )
    model_id_source: str = Field(
        default="declared",
        description=(
            "Where the concrete model id comes from (OMN-18623). 'declared' "
            "(default, so every pre-existing entry is unaffected) means send "
            "api_model_id. 'served' means resolve it at call time from the "
            "routed endpoint's /v1/models, which is exact for a single-model "
            "endpoint such as vLLM and is what makes a served-model swap need "
            "no edit in any repository. An entry may not do both."
        ),
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
    max_retries: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description=(
            "Optional per-model override for HTTP retry attempts (OMN-15115). "
            "None means no override -- call_model leaves "
            "ModelLlmInferenceRequest.max_retries at its own default. "
            "Additive: existing entries that don't set it are unaffected."
        ),
    )

    @model_validator(mode="after")
    def _validate_model_id_source(self) -> ModelEndpointConfig:
        """Refuse a config that declares an id it will not send, or vice versa.

        OMN-18623. Without this, ``model_id_source: served`` alongside a
        leftover ``api_model_id`` would load cleanly and the literal would sit
        in the file looking authoritative while nothing read it -- which is how
        a stale value survives a repin. An unknown source is refused rather
        than defaulted, because silently treating a typo as ``declared`` would
        send an empty model id.
        """
        allowed = {"declared", "served"}
        if self.model_id_source not in allowed:
            raise ValueError(
                f"model_id_source must be one of {sorted(allowed)}, "
                f"got {self.model_id_source!r}"
            )
        if self.model_id_source == "served" and self.api_model_id:
            raise ValueError(
                "model_id_source 'served' resolves the id from the endpoint, "
                f"so api_model_id must be empty; got {self.api_model_id!r}. "
                "A declared id here would be dead text that reads as truth "
                "(OMN-18623)."
            )
        return self

    api_key_env: str | None = Field(
        default=None,
        description=(
            "Optional environment variable holding a Bearer API key for "
            "authenticated cloud endpoints (OMN-17492, e.g. the z.ai GLM "
            "Coding Plan). None (default) means an unauthenticated local "
            "endpoint -- existing entries are unaffected. When set, "
            "call_model reads the key from this env var at call time and "
            "fails that model's review (fail-closed) if it is unset or "
            "empty; the key VALUE never lives in the registry. The infra "
            "transport additionally requires the endpoint host to appear in "
            "LLM_CLOUD_ENDPOINT_HOST_ALLOWLIST over HTTPS."
        ),
    )
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description=(
            "Optional reasoning effort for a local model whose chat template "
            "reads chat_template_kwargs.reasoning_effort (gpt-oss, OMN-17492). "
            "None (default) sends nothing, so existing entries are unaffected. "
            "It shares max_tokens with the answer: measured 2026-09-25 on "
            "gpt-oss-120b, 'high' spent all 4096 tokens on reasoning and "
            "returned no answer on a 98-line diff. Refused on an authenticated "
            "cloud entry, whose API has no chat_template_kwargs surface."
        ),
    )

    @model_validator(mode="after")
    def _validate_reasoning_effort_surface(self) -> ModelEndpointConfig:
        """Refuse an effort the endpoint would never receive (OMN-17492)."""
        if self.reasoning_effort is not None and self.api_key_env is not None:
            raise ValueError(
                "reasoning_effort travels in chat_template_kwargs, which an "
                "authenticated cloud entry (api_key_env set) does not send; "
                "declaring it there would be dead text."
            )
        return self


@unique
class EnumQuorumVerdict(str, Enum):
    """Outcome of multi-model quorum aggregation over one review.

    Reference: OMN-18479.
    """

    PASSED = "passed"
    """Quorum was met and no finding reached the agreement threshold."""

    BLOCKED = "blocked"
    """At least one finding was raised by enough distinct models to block."""

    DEGRADED_QUORUM = "degraded_quorum"
    """Fewer models succeeded than the threshold requires -- NOT a verdict.

    No agreement can be established from a single opinion, so this state
    carries no pass and no block. Callers fail closed on it.
    """

    NO_MODELS = "no_models"
    """Every model failed; the review never happened."""


class ModelReviewQuorumPolicy(BaseModel, frozen=True):
    """Contract-declared rules for turning per-model findings into a verdict.

    Declared in ``model_registry.yaml`` under ``review_quorum`` so the
    threshold is a contract edit, not a code change and not a caller flag.
    A caller may RAISE ``min_agreeing_models`` for its own repository; the
    ``ge=2`` bound means neither a contract nor a caller can lower it to
    one, which would restore the single-model blocking this policy exists
    to remove.

    Attributes:
        min_agreeing_models: Distinct successful models that must raise a
            matching finding before it blocks. Also the minimum number of
            models that must succeed for the run to have a verdict at all.
        line_proximity_lines: How far apart two findings' resolved line
            numbers may be and still count as the same finding.
        blocking_severities: Severities eligible to block once the
            agreement threshold is met. Every other severity is reported
            as a warning regardless of agreement.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    min_agreeing_models: int = Field(
        default=2,
        ge=2,
        description=(
            "Distinct successful models that must raise a matching finding "
            "for it to block. Never lower than 2."
        ),
    )
    line_proximity_lines: int = Field(
        default=3,
        ge=0,
        description=(
            "Maximum line distance between two findings for them to be "
            "treated as the same finding."
        ),
    )
    blocking_severities: tuple[EnumFindingSeverity, ...] = Field(
        default=(EnumFindingSeverity.CRITICAL, EnumFindingSeverity.ERROR),
        description="Severities eligible to block once agreement is reached.",
    )


class ModelQuorumFinding(BaseModel, frozen=True):
    """One finding cluster after cross-model agreement is resolved.

    Attributes:
        file_path: Normalised path the cluster was reported against.
        line_start: Resolved line number for the cluster.
        severity: Severity carried by the cluster.
        rule: Normalised rule/category key the cluster agreed on. The raw
            ``rule_id`` is model-specific (``ai-reviewer:{model}:{category}``)
            and is never used directly.
        message: Representative normalised message from the first model
            that raised the finding.
        agreeing_models: Distinct successful models that raised it, in the
            order the models ran.
        agreement_count: ``len(agreeing_models)``, explicit for scanning.
        blocking: True when this cluster blocks under the active policy.
        finding_ids: Source finding identifiers, so a caller can post the
            underlying per-model findings without re-deriving the cluster.
    """

    file_path: str = Field(description="Normalised path for the cluster.")
    line_start: int = Field(description="Resolved line number for the cluster.")
    severity: EnumFindingSeverity = Field(description="Severity of the cluster.")
    rule: str = Field(description="Normalised rule/category agreement key.")
    message: str = Field(description="Representative normalised message.")
    agreeing_models: tuple[str, ...] = Field(
        description="Distinct successful models that raised this finding."
    )
    agreement_count: int = Field(description="Number of distinct agreeing models.")
    blocking: bool = Field(description="True when this cluster blocks.")
    finding_ids: tuple[str, ...] = Field(
        default=(), description="Source finding identifiers in the cluster."
    )


class ModelReviewQuorumSummary(BaseModel, frozen=True):
    """Verdict of quorum aggregation over one multi-model review.

    Attributes:
        verdict: Aggregate outcome. ``degraded_quorum`` and ``no_models``
            are explicitly NOT passes.
        quorum_threshold: Active ``min_agreeing_models`` for this run.
        models_succeeded: Successful model keys considered for agreement.
        quorum_met: True when enough models succeeded to establish
            agreement at all.
        blocking_count: Number of blocking clusters.
        warning_count: Number of non-blocking clusters.
        blocking_findings: Clusters that block.
        warning_findings: Clusters that do not block. Single-model findings
            live here: reported, never dropped, never blocking.
    """

    verdict: EnumQuorumVerdict = Field(description="Aggregate quorum outcome.")
    quorum_threshold: int = Field(description="Active agreement threshold.")
    models_succeeded: tuple[str, ...] = Field(
        default=(), description="Successful model keys."
    )
    quorum_met: bool = Field(description="True when enough models succeeded.")
    blocking_count: int = Field(default=0, description="Number of blocking clusters.")
    warning_count: int = Field(
        default=0, description="Number of non-blocking clusters."
    )
    blocking_findings: tuple[ModelQuorumFinding, ...] = Field(
        default=(), description="Clusters that block."
    )
    warning_findings: tuple[ModelQuorumFinding, ...] = Field(
        default=(), description="Clusters reported without blocking."
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
        skipped_reason: Set when no model review was attempted because there
            was nothing to review (e.g. an empty PR diff on a merge/ancestry
            commit). ``None`` means models were genuinely attempted -- the
            caller should read ``models_succeeded``/``models_failed`` as
            usual. This is distinct from every model failing: a skipped
            review is an honest "nothing to review" outcome, not a reviewer
            crash or model outage (OMN-18409).
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
    quorum: ModelReviewQuorumSummary | None = Field(
        default=None,
        description=(
            "Cross-model agreement verdict (OMN-18479). None on a raw "
            "pre-aggregation envelope; the CLI always populates it before "
            "emitting the document a caller reads."
        ),
    )
    skipped_reason: str | None = Field(
        default=None,
        description=(
            "Set when no model review was attempted because there was "
            "nothing to review (e.g. an empty PR diff). None means models "
            "were genuinely attempted (OMN-18409)."
        ),
    )
