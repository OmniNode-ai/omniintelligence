# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM-backed AI reviewer adapter for adversarial plan review.

Replaces the stub with a concrete adapter that calls local LLMs via
HandlerLlmOpenaiCompatible to conduct adversarial reviews of technical
plans and design documents.

Four internal layers:
1. build_review_prompt -- constructs system + user prompt
2. call_model -- invokes LLM endpoint
3. parse_review_response -- extracts structured JSON from model output
4. to_review_findings -- maps to canonical ReviewFindingObserved models

Reference: OMN-5790
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    PROBABILISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelEndpointConfig,
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE_PR,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, FindingSeverity] = {
    "critical": FindingSeverity.ERROR,
    "major": FindingSeverity.WARNING,
    "minor": FindingSeverity.INFO,
    "nit": FindingSeverity.HINT,
}

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelEndpointConfig] = {
    "deepseek-r1": ModelEndpointConfig(
        env_var="LLM_DEEPSEEK_R1_URL",
        default_url="http://192.168.86.200:8101",
        kind="reasoning",
        timeout_seconds=300.0,
        api_model_id="mlx-community/DeepSeek-R1-Distill-Qwen-32B-bf16",
    ),
    "qwen3-coder": ModelEndpointConfig(
        env_var="LLM_CODER_URL",
        default_url="http://192.168.86.201:8000",
        kind="long_context",
        timeout_seconds=120.0,
        api_model_id="cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit",
    ),
    "qwen3-14b": ModelEndpointConfig(
        env_var="LLM_CODER_FAST_URL",
        default_url="http://192.168.86.201:8001",
        kind="fast_review",
        timeout_seconds=60.0,
        api_model_id="Qwen/Qwen3-14B-AWQ",
    ),
}

_DEFAULT_MODEL_KEY: str = "deepseek-r1"

# Default max tokens for review response.
_DEFAULT_MAX_TOKENS: int = 4096

# Default temperature for consistent review output.
_DEFAULT_TEMPERATURE: float = 0.3


# ---------------------------------------------------------------------------
# Internal layers (independently testable)
# ---------------------------------------------------------------------------


def build_review_prompt(
    plan_content: str,
    *,
    review_type: str = "plan",
) -> tuple[str, str]:
    """Construct system and user prompts for adversarial review.

    Args:
        plan_content: Raw content to review (plan text or PR diff).
        review_type: "plan" for plan/design review, "pr" for PR diff review.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    template = USER_PROMPT_TEMPLATE_PR if review_type == "pr" else USER_PROMPT_TEMPLATE
    user_prompt = template.format(plan_content=plan_content)
    return SYSTEM_PROMPT, user_prompt


def _resolve_model_url(model_key: str) -> str:
    """Resolve model endpoint URL from registry.

    Args:
        model_key: Key in MODEL_REGISTRY.

    Returns:
        Resolved URL string.

    Raises:
        ValueError: If model_key is not in the registry.
    """
    if model_key not in MODEL_REGISTRY:
        valid = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{model_key}'. Valid: {valid}")
    config = MODEL_REGISTRY[model_key]
    return os.environ.get(config.env_var, config.default_url)


async def call_model(
    system_prompt: str,
    user_prompt: str,
    model_key: str = _DEFAULT_MODEL_KEY,
) -> str:
    """Invoke LLM via HandlerLlmOpenaiCompatible.

    Uses infrastructure transport per ARCH-002. Sets a default
    LOCAL_LLM_SHARED_SECRET if not configured, since the local LLM
    endpoints do not verify HMAC signatures.

    Args:
        system_prompt: System prompt for the model.
        user_prompt: User prompt with plan content.
        model_key: Key in MODEL_REGISTRY for endpoint resolution.

    Returns:
        Raw text response from the model.

    Raises:
        ValueError: If model_key is not in the registry.
        RuntimeError: On LLM call failure.
    """
    from omnibase_infra.adapters.llm.adapter_llm_provider_openai import (
        TransportHolderLlmHttp,
    )
    from omnibase_infra.enums import EnumLlmOperationType
    from omnibase_infra.nodes.node_llm_inference_effect.handlers.handler_llm_openai_compatible import (
        HandlerLlmOpenaiCompatible,
    )
    from omnibase_infra.nodes.node_llm_inference_effect.models.model_llm_inference_request import (
        ModelLlmInferenceRequest,
    )

    config = MODEL_REGISTRY.get(model_key)
    if config is None:
        valid = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{model_key}'. Valid: {valid}")

    # Ensure HMAC secret is set. Local LLM endpoints do not verify
    # signatures, so a placeholder is sufficient for CLI use.
    if not os.environ.get("LOCAL_LLM_SHARED_SECRET"):
        os.environ["LOCAL_LLM_SHARED_SECRET"] = "cli-review-unsigned"  # noqa: S105  # pragma: allowlist secret

    base_url = os.environ.get(config.env_var, config.default_url)

    transport = TransportHolderLlmHttp(
        target_name=f"ai-reviewer-{model_key}",
        max_timeout_seconds=config.timeout_seconds + 30.0,
    )
    handler = HandlerLlmOpenaiCompatible(transport)

    request = ModelLlmInferenceRequest(
        base_url=base_url,
        operation_type=EnumLlmOperationType.CHAT_COMPLETION,
        model=config.api_model_id or model_key,
        messages=({"role": "user", "content": user_prompt},),
        system_prompt=system_prompt,
        max_tokens=_DEFAULT_MAX_TOKENS,
        temperature=_DEFAULT_TEMPERATURE,
        timeout_seconds=config.timeout_seconds,
    )

    response = await handler.handle(request)
    text = str(response.generated_text)

    # Qwen3 models emit <think>...</think> reasoning blocks before the
    # actual response. Strip them to get the JSON content.
    if "<think>" in text:
        import re as _re

        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()

    return text


def parse_review_response(raw_text: str) -> list[dict[str, Any]]:
    """Extract structured JSON findings from model response.

    Handles common model output patterns:
    - Raw JSON array
    - JSON wrapped in markdown fences
    - Leading/trailing commentary around JSON

    Args:
        raw_text: Raw text response from the model.

    Returns:
        List of finding dictionaries. Empty list on parse failure.
    """
    text = raw_text.strip()

    # Try direct JSON parse first.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed  # type: ignore[no-any-return]
        logger.warning("Parsed JSON is not a list; got %s", type(parsed).__name__)
        return []
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown fences.
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1).strip())
            if isinstance(parsed, list):
                return parsed  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.debug("Fenced block was not valid JSON, trying bracket extraction")

    # Try finding a JSON array anywhere in the text.
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        try:
            parsed = json.loads(bracket_match.group(0))
            if isinstance(parsed, list):
                return parsed  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.debug("Bracket-extracted text was not valid JSON")

    logger.warning("Failed to extract JSON findings from model response")
    return []


def map_severity(raw_severity: str) -> FindingSeverity:
    """Map a raw severity string to canonical FindingSeverity.

    Args:
        raw_severity: Severity string from model output.

    Returns:
        Canonical FindingSeverity enum value.
    """
    normalized = raw_severity.strip().lower()
    severity = _SEVERITY_MAP.get(normalized)
    if severity is not None:
        return severity
    logger.warning(
        "Unmapped severity '%s'; defaulting to INFO",
        raw_severity,
    )
    return FindingSeverity.INFO


def to_review_findings(
    parsed: list[dict[str, Any]],
    model_key: str,
    *,
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
) -> list[ReviewFindingObserved]:
    """Convert parsed finding dicts to canonical ReviewFindingObserved models.

    Args:
        parsed: List of finding dictionaries from parse_review_response.
        model_key: Model key for rule_id construction.
        repo: Repository slug (default "plan-review" for plan reviews).
        pr_id: PR number (default 0 for non-PR contexts).
        commit_sha: Commit SHA (default placeholder for plan reviews).

    Returns:
        List of ReviewFindingObserved instances.
    """
    findings: list[ReviewFindingObserved] = []
    now = utcnow()

    for item in parsed:
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict finding: %s", type(item).__name__)
            continue

        category = str(item.get("category", "unknown")).lower()
        raw_severity = str(item.get("severity", "info"))
        title = str(item.get("title", "Untitled finding"))
        description = str(item.get("description", ""))
        evidence = str(item.get("evidence", ""))
        proposed_fix = str(item.get("proposed_fix", ""))
        location = item.get("location")

        severity = map_severity(raw_severity)
        rule_id = f"ai-reviewer:{model_key}:{category}"

        # Compose raw message from available fields.
        raw_parts = [title]
        if description:
            raw_parts.append(description)
        if evidence:
            raw_parts.append(f"Evidence: {evidence}")
        if proposed_fix:
            raw_parts.append(f"Fix: {proposed_fix}")
        raw_message = " | ".join(raw_parts)

        # Truncate for normalization (adapter contract: 512 chars max).
        normalized = normalize_message(raw_message[:512], f"ai-reviewer:{model_key}")

        file_path = str(location) if location else "plan"

        findings.append(
            ReviewFindingObserved(
                finding_id=uuid4(),
                repo=repo,
                pr_id=max(pr_id, 1),
                rule_id=rule_id,
                severity=severity,
                file_path=file_path,
                line_start=1,
                line_end=None,
                tool_name=f"ai-reviewer:{model_key}",
                tool_version=PROMPT_VERSION,
                normalized_message=normalized if normalized else title[:512],
                raw_message=raw_message[:512],
                commit_sha_observed=commit_sha,
                observed_at=now,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def parse_raw(
    raw: str | dict[str, Any],
    *,
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
    model: str = _DEFAULT_MODEL_KEY,
    **kwargs: Any,
) -> list[ReviewFindingObserved]:
    """Parse raw model output into canonical review findings.

    This is the synchronous entry point for the adapter interface.
    For plan review, the raw input is the text response from the LLM.

    Args:
        raw: Raw model output (string or dict).
        repo: Repository slug.
        pr_id: Pull request number.
        commit_sha: Commit SHA.
        model: Model key for endpoint resolution and rule_id.
        **kwargs: Additional keyword arguments (ignored).

    Returns:
        List of ReviewFindingObserved instances.
    """
    # Validate model key.
    _resolve_model_url(model)

    text = raw if isinstance(raw, str) else json.dumps(raw)
    parsed = parse_review_response(text)
    return to_review_findings(
        parsed,
        model,
        repo=repo,
        pr_id=pr_id,
        commit_sha=commit_sha,
    )


async def async_parse_raw(
    plan_content: str,
    *,
    model: str = _DEFAULT_MODEL_KEY,
    review_type: str = "plan",
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
) -> ModelExternalReviewResult:
    """Full review transaction: prompt, call, parse, convert.

    This is the async entry point that performs the complete review cycle:
    1. Build prompts from the shared prompt module
    2. Call the model endpoint
    3. Parse the response
    4. Convert to canonical findings

    Args:
        plan_content: Raw content to review (plan text or PR diff).
        model: Model key for endpoint resolution.
        review_type: "plan" for plan review, "pr" for PR diff review.
        repo: Repository slug.
        pr_id: Pull request number.
        commit_sha: Commit SHA.

    Returns:
        ModelExternalReviewResult with review findings or error.
    """
    try:
        # Validate model key.
        _resolve_model_url(model)
        system_prompt, user_prompt = build_review_prompt(
            plan_content,
            review_type=review_type,
        )
        raw_text = await call_model(system_prompt, user_prompt, model_key=model)
        parsed = parse_review_response(raw_text)
        findings = to_review_findings(
            parsed,
            model,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
        )
        return ModelExternalReviewResult(
            model=model,
            prompt_version=PROMPT_VERSION,
            success=True,
            findings=findings,
            result_count=len(findings),
        )
    except Exception as exc:
        logger.warning("Review failed for model '%s': %s", model, exc)
        return ModelExternalReviewResult(
            model=model,
            prompt_version=PROMPT_VERSION,
            success=False,
            error=str(exc),
        )


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return PROBABILISTIC
