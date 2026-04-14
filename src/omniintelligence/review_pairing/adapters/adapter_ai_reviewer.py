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
4. to_review_findings -- maps to canonical ModelReviewFindingObserved models

Reference: OMN-5790
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import urllib.parse
from typing import Any
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    PROBABILISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
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

_SEVERITY_MAP: dict[str, EnumFindingSeverity] = {
    "critical": EnumFindingSeverity.ERROR,
    "major": EnumFindingSeverity.WARNING,
    "minor": EnumFindingSeverity.INFO,
    "nit": EnumFindingSeverity.HINT,
}

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelEndpointConfig] = {
    "deepseek-r1": ModelEndpointConfig(
        env_var="LLM_DEEPSEEK_R1_URL",
        default_url="http://192.168.86.201:8001",
        kind="reasoning",
        timeout_seconds=300.0,
        api_model_id="Corianas/DeepSeek-R1-Distill-Qwen-14B-AWQ",
    ),
    "qwen3-coder": ModelEndpointConfig(
        env_var="LLM_CODER_URL",
        default_url="",
        kind="long_context",
        timeout_seconds=120.0,
        api_model_id="cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit",
    ),
    "qwen3-14b": ModelEndpointConfig(
        env_var="LLM_CODER_FAST_URL",
        default_url="",
        kind="fast_review",
        timeout_seconds=60.0,
        api_model_id="Qwen/Qwen3-14B-AWQ",
    ),
    "qwen3-next": ModelEndpointConfig(
        env_var="LLM_QWEN3_NEXT_URL",
        default_url="",
        kind="code_review",
        timeout_seconds=120.0,
        api_model_id="Qwen3-Next-80B-A3B",
    ),
    # --- API fallback models (reachable from cloud CI) ---
    "claude-api": ModelEndpointConfig(
        env_var="ANTHROPIC_API_BASE_URL",
        default_url="https://api.anthropic.com",
        kind="api_fallback",
        timeout_seconds=120.0,
        api_model_id="claude-sonnet-4-6",
    ),
}

_LOCAL_MODEL_KEYS: frozenset[str] = frozenset(
    {"deepseek-r1", "qwen3-coder", "qwen3-14b", "qwen3-next"}
)
_API_FALLBACK_KEYS: tuple[str, ...] = ("claude-api",)

_DEFAULT_MODEL_KEY: str = "deepseek-r1"

# Default max tokens for review response.
_DEFAULT_MAX_TOKENS: int = 4096

# Default temperature for consistent review output.
_DEFAULT_TEMPERATURE: float = 0.3

# TCP probe timeout for reachability checks (seconds).
_PROBE_TIMEOUT_SECONDS: float = 2.0


# ---------------------------------------------------------------------------
# Reachability probing
# ---------------------------------------------------------------------------


def _probe_tcp(host: str, port: int, timeout: float = _PROBE_TIMEOUT_SECONDS) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_local_reachability(model_keys: list[str]) -> dict[str, bool]:
    """TCP-probe reachability for each local model endpoint in model_keys."""
    results: dict[str, bool] = {}
    for key in model_keys:
        if key not in _LOCAL_MODEL_KEYS:
            continue
        config = MODEL_REGISTRY.get(key)
        if config is None:
            continue
        url = os.environ.get(config.env_var, config.default_url)
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            port = parsed.port or 80
        except Exception:  # noqa: BLE001
            results[key] = False
            continue
        results[key] = _probe_tcp(host, port)
    return results


def select_models_with_fallback(
    requested_keys: list[str],
) -> tuple[list[str], list[str]]:
    """Return (models_to_run, skipped) applying reachability probe and API fallback."""
    local_requested = [k for k in requested_keys if k in _LOCAL_MODEL_KEYS]
    non_local_requested = [k for k in requested_keys if k not in _LOCAL_MODEL_KEYS]

    if not local_requested:
        return list(requested_keys), []

    reachability = probe_local_reachability(local_requested)
    reachable_local = [k for k in local_requested if reachability.get(k, False)]
    unreachable_local = [k for k in local_requested if not reachability.get(k, False)]

    if reachable_local:
        return reachable_local + non_local_requested, unreachable_local

    return list(_API_FALLBACK_KEYS) + non_local_requested, unreachable_local


# ---------------------------------------------------------------------------
# Internal layers (independently testable)
# ---------------------------------------------------------------------------


def build_review_prompt(
    plan_content: str,
    *,
    review_type: str = "plan",
    system_prompt_prefix: str | None = None,
) -> tuple[str, str]:
    """Construct system and user prompts for adversarial review.

    Args:
        plan_content: Raw content to review (plan text or PR diff).
        review_type: "plan" for plan/design review, "pr" for PR diff review.
        system_prompt_prefix: Optional content to prepend to the system prompt.
            When provided (e.g., a persona), it is prepended with a separator.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    template = USER_PROMPT_TEMPLATE_PR if review_type == "pr" else USER_PROMPT_TEMPLATE
    user_prompt = template.format(plan_content=plan_content)
    if system_prompt_prefix:
        system_prompt = f"{system_prompt_prefix}\n\n---\n\n{SYSTEM_PROMPT}"
    else:
        system_prompt = SYSTEM_PROMPT
    return system_prompt, user_prompt


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
    url = os.environ.get(config.env_var, config.default_url)
    if not url:
        raise ValueError(
            f"LLM endpoint not configured for '{model_key}'. "
            f"Set the {config.env_var} environment variable."
        )
    return url


async def _call_claude_api(
    system_prompt: str,
    user_prompt: str,
    config: ModelEndpointConfig,
) -> str:
    """Call the Anthropic Claude API for api_fallback models. Requires ANTHROPIC_API_KEY."""
    import urllib.request as _urlreq

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "claude-api fallback requires ANTHROPIC_API_KEY environment variable"
        )
    payload = json.dumps(
        {
            "model": config.api_model_id or "claude-sonnet-4-6",
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    ).encode()
    req = _urlreq.Request(  # noqa: S310
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with _urlreq.urlopen(req, timeout=config.timeout_seconds) as resp:  # noqa: S310
            data = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(f"Claude API call failed: {exc}") from exc
    try:
        return str(data["content"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Claude API response shape: {data!r}") from exc


async def call_model(
    system_prompt: str,
    user_prompt: str,
    model_key: str = _DEFAULT_MODEL_KEY,
) -> str:
    """Invoke LLM via HandlerLlmOpenaiCompatible, or Claude API for api_fallback models.

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
    config = MODEL_REGISTRY.get(model_key)
    if config is None:
        valid = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{model_key}'. Valid: {valid}")

    if config.kind == "api_fallback":
        return await _call_claude_api(system_prompt, user_prompt, config)

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

    # Ensure HMAC secret is set. Local LLM endpoints do not verify
    # signatures, so a placeholder is sufficient for CLI use.
    if not os.environ.get("LOCAL_LLM_SHARED_SECRET"):
        os.environ["LOCAL_LLM_SHARED_SECRET"] = "cli-review-unsigned"  # noqa: S105  # pragma: allowlist secret

    base_url = os.environ.get(config.env_var, config.default_url)
    if not base_url:
        raise ValueError(
            f"LLM endpoint not configured for '{model_key}'. "
            f"Set the {config.env_var} environment variable."
        )

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
            return parsed
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
                return parsed
        except json.JSONDecodeError:
            logger.debug("Fenced block was not valid JSON, trying bracket extraction")

    # Try finding a JSON array anywhere in the text.
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        try:
            parsed = json.loads(bracket_match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            logger.debug("Bracket-extracted text was not valid JSON")

    logger.warning("Failed to extract JSON findings from model response")
    return []


def map_severity(raw_severity: str) -> EnumFindingSeverity:
    """Map a raw severity string to canonical EnumFindingSeverity.

    Args:
        raw_severity: Severity string from model output.

    Returns:
        Canonical EnumFindingSeverity enum value.
    """
    normalized = raw_severity.strip().lower()
    severity = _SEVERITY_MAP.get(normalized)
    if severity is not None:
        return severity
    logger.warning(
        "Unmapped severity '%s'; defaulting to INFO",
        raw_severity,
    )
    return EnumFindingSeverity.INFO


def to_review_findings(
    parsed: list[Any],
    model_key: str,
    *,
    repo: str = "plan-review",
    pr_id: int = 0,
    commit_sha: str = "0000000",
) -> list[ModelReviewFindingObserved]:
    """Convert parsed finding dicts to canonical ModelReviewFindingObserved models.

    Args:
        parsed: List of finding dictionaries from parse_review_response.
        model_key: Model key for rule_id construction.
        repo: Repository slug (default "plan-review" for plan reviews).
        pr_id: PR number (default 0 for non-PR contexts).
        commit_sha: Commit SHA (default placeholder for plan reviews).

    Returns:
        List of ModelReviewFindingObserved instances.
    """
    findings: list[ModelReviewFindingObserved] = []
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
            ModelReviewFindingObserved(
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
) -> list[ModelReviewFindingObserved]:
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
        List of ModelReviewFindingObserved instances.
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
    system_prompt_prefix: str | None = None,
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
        system_prompt_prefix: Optional content to prepend to the system prompt
            (e.g., persona content). When set, prepended with a separator.

    Returns:
        ModelExternalReviewResult with review findings or error.
    """
    try:
        # Validate model key.
        _resolve_model_url(model)
        system_prompt, user_prompt = build_review_prompt(
            plan_content,
            review_type=review_type,
            system_prompt_prefix=system_prompt_prefix,
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
