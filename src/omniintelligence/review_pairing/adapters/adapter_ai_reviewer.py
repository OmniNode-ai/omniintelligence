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

import asyncio
import json
import logging
import os
import re
import socket
import sys
import time
import urllib.parse
from collections.abc import Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, TypedDict, Unpack
from uuid import uuid4

from omniintelligence.models.review.model_review_call_response import (
    ModelReviewCallResponse,
)
from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)
from omniintelligence.review_pairing.adapters.base import (
    PROBABILISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.model_registry_loader import (
    endpoint_not_configured_message,
    load_registry,
    resolve_endpoint_url,
)
from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelDroppedFinding,
    ModelEndpointConfig,
    ModelExternalReviewResult,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    FINDINGS_RESPONSE_FORMAT,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE_PR,
    render_standing_rules_section,
    render_standing_rules_section_v2,
    select_prompt,
)
from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    JSON_ONLY_RETRY as _JSON_ONLY_RETRY,
)
from omniintelligence.review_pairing.retry_budget import (
    compute_sequential_worst_case,
    resolve_live_max_retries_default,
)
from omniintelligence.review_pairing.served_model_resolver import (
    ServedModelResolutionError,
    resolve_served_model_id,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)
_ANTHROPIC_USAGE: ContextVar[list[int] | None] = ContextVar(
    "anthropic_review_usage", default=None
)

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
# Model registry (loaded from model_registry.yaml — OMN-7213)
# ---------------------------------------------------------------------------

_REGISTRY_CONTRACT = load_registry()

MODEL_REGISTRY: dict[str, ModelEndpointConfig] = dict(_REGISTRY_CONTRACT.models)

# OMN-18623: budget for the served-model metadata probe. Deliberately small and
# INDEPENDENT of the review timeout: /v1/models answers in milliseconds on a
# healthy endpoint, and spending review budget waiting on it would trade a
# review for nothing. An endpoint too slow to answer this is not one a review
# would have completed against either.
_SERVED_MODEL_PROBE_TIMEOUT_SECONDS: float = 15.0
_LOCAL_MODEL_KEYS: frozenset[str] = frozenset(_REGISTRY_CONTRACT.local_model_keys)
_API_FALLBACK_KEYS: tuple[str, ...] = tuple(_REGISTRY_CONTRACT.api_fallback_keys)
_DEFAULT_MODEL_KEY: str = _REGISTRY_CONTRACT.default_model_key

# Default max tokens for review response.
_DEFAULT_MAX_TOKENS: int = 4096

# Default retry budget. Larger reviews scale both caps together, up to
# _MAX_REVIEW_TOKENS initially and twice that on the JSON-only retry.
_RETRY_MAX_TOKENS: int = 2 * _DEFAULT_MAX_TOKENS

_MAX_REVIEW_TOKENS: int = 8192
_CONTEXT_MARGIN: int = 1024

# OMN-21289: a file starts at a unified-diff header or at a block of the
# files-API fallback target that cli_review builds for an oversized pull request.
_REVIEW_FILE_BOUNDARY = re.compile(
    r"(?=^diff --git |^--- \S.* \([a-z_]+, \+\d+/-\d+\) ---$)", re.MULTILINE
)

# Default temperature for consistent review output.
_DEFAULT_TEMPERATURE: float = 0.3

# TCP probe threshold for reachability checks — mirrors the CI reviewer endpoint
# preflight EXACTLY (omnimarket hostile-reviewer.yml, OMN-14176):
#   for attempt in 1 2 3; do timeout 5 ...; [ attempt -lt 3 ] && sleep 2; done
# The prior 2s single-shot lost the race against a live-but-slow endpoint under
# GPU load, fell back to codex (absent on CI), and produced a DEGRADED
# "Models succeeded: none" false-green while the job still reported success.
# Matching the preflight makes this probe a strict superset of the preflight's
# tolerance, so the reviewer never degrades on an endpoint the preflight cleared.
_PROBE_TIMEOUT_SECONDS: float = 5.0

# Number of TCP probe attempts before declaring an endpoint unreachable.
_PROBE_MAX_ATTEMPTS: int = 3

# Delay between probe attempts (seconds) — matches the preflight's `sleep 2`.
_PROBE_RETRY_DELAY_SECONDS: float = 2.0


# ---------------------------------------------------------------------------
# Reachability probing
# ---------------------------------------------------------------------------


def _probe_tcp(
    host: str,
    port: int,
    timeout: float = _PROBE_TIMEOUT_SECONDS,
    attempts: int = _PROBE_MAX_ATTEMPTS,
    retry_delay: float = _PROBE_RETRY_DELAY_SECONDS,
) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout.

    Retries up to ``attempts`` times, sleeping ``retry_delay`` seconds between
    attempts, mirroring the CI reviewer preflight probe (5s x 3). This gives a
    slow-but-live endpoint under load the same tolerance the workflow preflight
    uses, preventing a false "unreachable" -> codex-fallback -> DEGRADED
    false-green (OMN-14176).
    """
    for attempt in range(1, attempts + 1):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            if attempt < attempts:
                time.sleep(retry_delay)
    return False


def _probe_url(url: str) -> bool:
    """TCP-probe one endpoint URL; a URL that does not parse is unreachable."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 80
    except Exception:  # noqa: BLE001
        return False
    return _probe_tcp(host, port)


def probe_local_reachability(model_keys: list[str]) -> dict[str, bool]:
    """TCP-probe reachability for each local model endpoint in model_keys.

    A model with overflow endpoints is reachable when ANY of its endpoints is,
    primary first: an unreachable primary is exactly the case an overflow
    endpoint exists for, so it must not drop the voter before the call.
    """
    results: dict[str, bool] = {}
    for key in model_keys:
        if key not in _LOCAL_MODEL_KEYS:
            continue
        config = MODEL_REGISTRY.get(key)
        if config is None:
            continue
        url = resolve_endpoint_url(key, config)
        if not url:
            # Not configured (OMN-20936): nothing to probe, and a probe of an
            # empty host would be answered by whatever listens locally.
            results[key] = False
            continue
        results[key] = any(
            _probe_url(candidate) for candidate in (url, *config.overflow_urls)
        )
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

    def dedupe(keys: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    if reachable_local:
        return dedupe(reachable_local + non_local_requested), unreachable_local

    return dedupe(list(_API_FALLBACK_KEYS) + non_local_requested), unreachable_local


def register_review_voters(configs: Mapping[str, ModelEndpointConfig]) -> None:
    """Add overlay voters (OMN-20910) to the registry this adapter calls through.

    Local voters are probed for reachability like the registry's local keys.
    Anthropic voters go directly to the Messages API. A voter id that names an
    existing registry key is refused: an overlay voter must never silently replace a registry entry, or
    the same name would mean two different reviewers depending on the caller.

    Raises:
        ValueError: A voter id collides with a registry key that is not the
            identical config (re-registering the same roster is a no-op).
    """
    global _LOCAL_MODEL_KEYS
    for voter_id, config in configs.items():
        existing = MODEL_REGISTRY.get(voter_id)
        if existing is not None and existing != config:
            raise ValueError(
                f"review voter {voter_id!r}: the id is already a model_registry.yaml "
                "key; give the overlay voter a name of its own"
            )
    MODEL_REGISTRY.update(configs)
    _LOCAL_MODEL_KEYS = _LOCAL_MODEL_KEYS | frozenset(
        key for key, config in configs.items() if config.provider == "openai"
    )


# ---------------------------------------------------------------------------
# Internal layers (independently testable)
# ---------------------------------------------------------------------------


def build_review_prompt(
    plan_content: str,
    *,
    review_type: str = "plan",
    system_prompt_prefix: str | None = None,
    standing_rules: ModelReviewStandingRules | None = None,
    prompt_version: str = PROMPT_VERSION,
    catalog_section: str | None = None,
) -> tuple[str, str]:
    """Construct system and user prompts for adversarial review.

    Args:
        plan_content: Raw content to review (plan text or PR diff).
        review_type: "plan" for plan/design review, "pr" for PR diff review.
        system_prompt_prefix: Optional content to prepend to the system prompt.
            When provided (e.g., a persona), it is prepended with a separator.
        standing_rules: The reviewed repository's standing rules (OMN-20784).
            When provided, every rule is rendered into the system prompt by id.
        prompt_version: The reviewer prompt version. The default is the v1
            prompt; ``2.0.0`` selects the compact verdict prompt (OMN-20910).
        catalog_section: The rendered defect-catalog section, placed after the
            instructions. Used by the compact prompt only.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    if prompt_version != PROMPT_VERSION:
        selected = select_prompt(prompt_version)
        template = (
            selected.user_template_pr
            if review_type == "pr"
            else selected.user_template_plan
        )
        base_prompt = selected.system_prompt
        if catalog_section:
            base_prompt = f"{base_prompt}\n\n{catalog_section}"
        render_rules = (
            render_standing_rules_section_v2
            if selected.compact_output
            else render_standing_rules_section
        )
    else:
        template = (
            USER_PROMPT_TEMPLATE_PR if review_type == "pr" else USER_PROMPT_TEMPLATE
        )
        base_prompt = SYSTEM_PROMPT
        render_rules = render_standing_rules_section
    user_prompt = template.format(plan_content=plan_content)
    if system_prompt_prefix:
        system_prompt = f"{system_prompt_prefix}\n\n---\n\n{base_prompt}"
    else:
        system_prompt = base_prompt
    if standing_rules is not None:
        system_prompt = f"{system_prompt}\n\n{render_rules(standing_rules)}"
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
    url = resolve_endpoint_url(model_key, config)
    if not url:
        raise ValueError(endpoint_not_configured_message(model_key, config))
    return url


class _OptionalRequestKwargs(TypedDict, total=False):
    """Keyword arguments passed to ``ModelLlmInferenceRequest`` only when the
    registry declares a real override.

    A plain ``dict[str, object]`` unpacked with ``**`` tells the type checker
    that ANY keyword may arrive carrying ``object``, which since omnibase-infra
    0.38.22 conflicts with every narrowly-typed field on that model. A TypedDict
    states the one key that can actually be present, so the omit-when-unset
    behaviour (OMN-15115) survives without weakening the call site.
    """

    max_retries: int
    top_p: float


class _OutputBudgetKwargs(TypedDict, total=False):
    max_tokens: int
    json_only: bool
    budget_seconds: float
    # OMN-17427: share failed endpoints across chunks of one vote.
    failed_endpoints: set[str]


def _resolve_api_model_id(
    model_key: str,
    config: ModelEndpointConfig,
    base_url: str,
) -> str:
    """Return the wire ``model`` value for one review call.

    OMN-18623. ``declared`` entries send the id the contract names, exactly as
    before this change. ``served`` entries resolve it from the endpoint that is
    about to be POSTed to -- the SAME ``base_url``, so the probe target cannot
    diverge from the request target, which is the property that makes the
    answer trustworthy rather than merely fresh.

    Raises:
        ServedModelResolutionError: If a ``served`` entry's endpoint cannot be
            resolved to exactly one model. Deliberately not swallowed: a guess
            here is the defect this ticket exists to remove, and the caller
            already treats a raise as an ordinary per-model failure that leaves
            the rest of the roster reviewing.
    """
    if config.model_id_source == "served":
        return resolve_served_model_id(
            base_url, timeout_seconds=_SERVED_MODEL_PROBE_TIMEOUT_SECONDS
        )
    return config.api_model_id or model_key


def _validate_model_key(model_key: str) -> None:
    """Validate a model key without requiring an endpoint URL."""
    if model_key not in MODEL_REGISTRY:
        valid = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{model_key}'. Valid: {valid}")


def _claude_error_summary(response: httpx.Response) -> str:
    """Include only valid provider error fields, bounded to one line."""
    detail = f"Claude API call failed (HTTP {response.status_code})"
    try:
        data = response.json()
    except ValueError:
        return detail
    if not isinstance(data, dict):
        return detail
    error = data.get("error")
    if not isinstance(error, dict):
        return detail
    error_type = error.get("type")
    message = error.get("message")
    if not isinstance(error_type, str) or not isinstance(message, str):
        return detail
    suffix = " ".join(f"{error_type}: {message}".split())[:200]
    return f"{detail}: {suffix}"


async def _call_claude_api_response(
    system_prompt: str,
    user_prompt: str,
    config: ModelEndpointConfig,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> ModelReviewCallResponse:
    """Messages API call returning the typed response, stop reason included.

    A reply that stopped at ``max_tokens`` is returned as such, never raised or
    shortened: the strict parser decides that it is not a complete review
    (OMN-20910). Bounded retries. Only the named
    environment variable is read. Errors contain status and bounded provider
    error type/message fields, never headers or request text.
    """
    import httpx
    from omnibase_infra.handlers.models.model_retry_state import ModelRetryState

    key_env = config.api_key_env or "ANTHROPIC_API_KEY"
    api_key = os.environ.get(key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"Claude API key environment variable {key_env} is not set")
    if not config.api_model_id:
        raise ValueError("Claude API voter requires a declared model")
    if not config.default_url:
        raise ValueError(
            "Claude API voter requires a provider endpoint from its overlay"
        )
    payload: dict[str, Any] = {
        "model": config.api_model_id,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
    if config.top_p is not None:
        payload["top_p"] = config.top_p
    retries = config.max_retries
    if retries is None:
        retries = resolve_live_max_retries_default()
    state = ModelRetryState(max_attempts=1 + retries)
    async with httpx.AsyncClient(
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=config.timeout_seconds,
        follow_redirects=False,
    ) as client:
        while True:
            try:
                # wait_for bounds the whole attempt, including streamed reads;
                # httpx's socket timeouts alone would reset on each read.
                response = await asyncio.wait_for(
                    client.post(
                        f"{config.default_url.rstrip('/')}/v1/messages", json=payload
                    ),
                    timeout=config.timeout_seconds,
                )
            except (httpx.TransportError, TimeoutError) as exc:
                detail = f"Claude API transport failed ({type(exc).__name__})"
            else:
                if response.status_code == 200:
                    break
                detail = _claude_error_summary(response)
                if (
                    response.status_code not in {408, 409, 429}
                    and response.status_code < 500
                ):
                    raise RuntimeError(detail)
            state = state.next_attempt()
            if not state.is_retriable():
                raise RuntimeError(detail)
            await asyncio.sleep(state.delay_seconds)
    try:
        data = response.json()
        usage = data["usage"]
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
            raise ValueError("invalid usage")
        totals = _ANTHROPIC_USAGE.get()
        if totals is not None:
            totals[0] += input_tokens
            totals[1] += output_tokens
        stop_reason = data.get("stop_reason")
        if not isinstance(stop_reason, str):
            raise ValueError("missing stop reason")
        blocks = data["content"]
        if not isinstance(blocks, list):
            raise ValueError("invalid content")
        served_model = data.get("model")
        return ModelReviewCallResponse(
            content="".join(
                block["text"] for block in blocks if block["type"] == "text"
            ),
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            served_model=served_model if isinstance(served_model, str) else None,
        )
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError("Unexpected or incomplete Claude API response") from None


def _build_extra_body(
    config: ModelEndpointConfig, *, json_only: bool = False
) -> dict[str, Any]:
    """Request-body keys the OpenAI-compatible effect merges in verbatim.

    ``chat_template_kwargs`` always (OMN-14176; ``reasoning_effort`` only when
    the registry declares it, OMN-17492). ``response_format`` only for an entry
    that sets ``constrain_findings_schema`` (OMN-20422), so every other entry
    sends exactly what it sent before.
    """
    template_kwargs: dict[str, Any] = {
        "enable_thinking": False if json_only else config.enable_thinking
    }
    if config.reasoning_effort is not None:
        template_kwargs["reasoning_effort"] = (
            "low" if json_only else config.reasoning_effort
        )
    extra_body: dict[str, Any] = {"chat_template_kwargs": template_kwargs}
    if config.constrain_findings_schema:
        extra_body["response_format"] = FINDINGS_RESPONSE_FORMAT
    return extra_body


# The base URL each model key's most recent successful call was served by
# (OMN-20910 follow-up): the endpoint a vote came from, which differs from the
# resolved one when an overflow endpoint answered. Calls are sequential.
SERVED_BASE_URLS: dict[str, str] = {}


def _failover_errors() -> tuple[type[BaseException], ...]:
    """What moves a call to the next endpoint: full, unavailable or silent.

    A rejected request (400/422), an authentication failure or a malformed
    reply would fail the same way on the next endpoint, so they are not here.
    """
    from omnibase_infra.errors import (
        InfraConnectionError,
        InfraRateLimitedError,
        InfraTimeoutError,
        InfraUnavailableError,
    )

    return (
        InfraConnectionError,
        InfraRateLimitedError,
        InfraTimeoutError,
        InfraUnavailableError,
        ServedModelResolutionError,
    )


def _openai_call_response(text: str, response: Any) -> ModelReviewCallResponse:
    """Wrap an OpenAI-compatible reply with its finish reason, usage and model.

    The finish reason is the canonical enum's value (``stop``, ``length``, ...);
    a field the response does not carry stays unreported, never defaulted to a
    normal end.
    """
    finish = getattr(response, "finish_reason", None)
    usage = getattr(response, "usage", None)
    tokens_in = getattr(usage, "tokens_input", 0)
    tokens_out = getattr(usage, "tokens_output", 0)
    served = getattr(response, "model_used", None)
    return ModelReviewCallResponse(
        content=text,
        stop_reason=str(getattr(finish, "value", finish))
        if finish is not None
        else None,
        input_tokens=tokens_in if type(tokens_in) is int and tokens_in >= 0 else 0,
        output_tokens=tokens_out if type(tokens_out) is int and tokens_out >= 0 else 0,
        served_model=served if isinstance(served, str) and served else None,
    )


async def call_model(
    system_prompt: str,
    user_prompt: str,
    model_key: str = _DEFAULT_MODEL_KEY,
    *,
    repository: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    json_only: bool = False,
    budget_seconds: float | None = None,
    # OMN-17427: callers can retain failover state for one vote.
    failed_endpoints: set[str] | None = None,
) -> str:
    """The reply text of ``call_model_response`` (the v1 format's caller)."""
    response = await call_model_response(
        system_prompt,
        user_prompt,
        model_key,
        repository=repository,
        max_tokens=max_tokens,
        json_only=json_only,
        budget_seconds=budget_seconds,
        failed_endpoints=failed_endpoints,
        require_complete_reply=True,
    )
    return response.content


async def call_model_response(
    system_prompt: str,
    user_prompt: str,
    model_key: str = _DEFAULT_MODEL_KEY,
    *,
    repository: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    json_only: bool = False,
    budget_seconds: float | None = None,
    failed_endpoints: set[str] | None = None,
    require_complete_reply: bool = False,
) -> ModelReviewCallResponse:
    """Invoke LLM via HandlerLlmOpenaiCompatible, or Claude API for api_fallback models.

    Args:
        system_prompt: System prompt for the model.
        user_prompt: User prompt with plan content.
        model_key: Key in MODEL_REGISTRY for endpoint resolution.
        repository: The repository the reviewed content belongs to, sent as
            metadata.repository so a cloud voter can refuse a repository whose
            code never goes to a cloud model (OMN-20106). None sends no metadata.
        max_tokens: Most tokens the reply may hold.
        budget_seconds: This chunk's share of the whole-vote budget. When set,
            reserve time for every endpoint, with one attempt per endpoint.
        failed_endpoints: Endpoints of this vote that already failed over;
            skipped by later chunks. None keeps every endpoint.
        require_complete_reply: The v1 text contract: a Claude API reply that
            did not stop normally raises instead of being returned. The compact
            format leaves this False and reads the stop reason itself.

    Returns:
        The typed response: reply text, the provider's stop or finish reason,
        usage and the served model (OMN-20910). A reply cut at ``max_tokens``
        is returned with its stop reason, never shortened.

    Raises:
        ValueError: If model_key is not in the registry.
        RuntimeError: On LLM call failure.
    """
    config = MODEL_REGISTRY.get(model_key)
    if config is None:
        valid = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{model_key}'. Valid: {valid}")

    if config.provider in {"anthropic", "claude_code"} or config.kind == "api_fallback":
        repo = (repository or "").strip().rstrip("/").removesuffix(".git").casefold()
        if any(
            excluded.casefold() in {repo, repo.rsplit("/", 1)[-1]}
            for excluded in config.excluded_repositories
        ):
            raise ValueError("Cloud review is forbidden for this repository")
        if config.review_focus:
            system_prompt = (
                f"{system_prompt}\n\n## Reviewer Focus\n\n{config.review_focus}"
            )
        if config.provider == "claude_code":
            from omniintelligence.handlers.handler_claude_code_review_host import (
                handle,
            )
            from omniintelligence.nodes.node_claude_code_review_effect.models.model_claude_code_review import (
                ModelClaudeCodeReviewRequest,
            )

            result = await handle(
                ModelClaudeCodeReviewRequest(
                    model=config.api_model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_seconds=min(config.timeout_seconds, budget_seconds)
                    if budget_seconds is not None
                    else config.timeout_seconds,
                    max_output_tokens=max_tokens,
                )
            )
            if not result.success:
                raise RuntimeError(f"Claude Code voter {model_key}: {result.error}")
            usage = _ANTHROPIC_USAGE.get()
            if usage is not None:
                usage[0] += result.input_tokens
                usage[1] += result.output_tokens
            return ModelReviewCallResponse(
                content=result.response,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        claude_response = await _call_claude_api_response(
            system_prompt, user_prompt, config, max_tokens
        )
        if require_complete_reply and claude_response.stop_reason not in {
            "end_turn",
            "stop_sequence",
        }:
            raise RuntimeError("Unexpected or incomplete Claude API response")
        return claude_response
    if config.kind == "cli_fallback":
        raise ValueError(
            f"Model '{model_key}' is handled by its CLI adapter, not the LLM adapter."
        )

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

    # OMN-11008: LOCAL_LLM_SHARED_SECRET ownership lives in the LLM HTTP
    # transport (omnibase_infra.mixins.mixin_llm_http_transport). The
    # transport reads the secret from os.environ on every call and fails
    # closed (raises ProtocolConfigurationError) if absent. Callers (CLI
    # entry points and test fixtures) are responsible for setting the
    # secret in their own environment before invoking this path; the
    # adapter must not synthesize a placeholder.
    base_url = resolve_endpoint_url(model_key, config)
    if not base_url:
        raise ValueError(endpoint_not_configured_message(model_key, config))

    # OMN-20422: a per-model review focus extends the system prompt for that
    # voter only. Empty (the default) leaves the prompt byte-identical.
    if config.review_focus:
        system_prompt = f"{system_prompt}\n\n## Reviewer Focus\n\n{config.review_focus}"

    # Overflow (OMN-20910 follow-up): endpoints are tried in order. Every one
    # but the last gets one attempt of at most ``overflow_after_seconds``, so a
    # 503, a refused connection or a silent endpoint costs one attempt and the
    # next endpoint is the retry. The last endpoint keeps the model's own
    # timeout and ``max_retries``, and a model with no overflow has exactly one
    # endpoint, which is that last one: its behaviour is unchanged. A chunk's
    # explicit budget below can shorten these attempts to reserve later work.
    endpoints = (base_url, *config.overflow_urls)
    # OMN-17427: skip endpoints that already failed over during this vote.
    if failed_endpoints is not None:
        endpoints = (
            tuple(e for e in endpoints if e not in failed_endpoints) or endpoints[-1:]
        )
    call_deadline = (
        time.monotonic() + budget_seconds if budget_seconds is not None else None
    )
    giveup_seconds = min(
        config.timeout_seconds, config.overflow_after_seconds or config.timeout_seconds
    )

    async def _attempt(
        endpoint_base: str, timeout_seconds: float, max_retries: int | None
    ) -> ModelReviewCallResponse:
        # OMN-14176 / OMN-12815: the OpenAI-compatible effect posts ``endpoint_url``
        # VERBATIM and performs no base_url + path construction. Registry URLs are
        # host:port only, so resolve the COMPLETE chat-completion URL here or the
        # transport raises "endpoint_url is required and must be the COMPLETE
        # contract endpoint URL" and every review DEGRADES with "all models failed".
        _normalized_url = endpoint_base.rstrip("/")
        if _normalized_url.endswith("/chat/completions"):
            endpoint_url = _normalized_url
        else:
            endpoint_url = f"{_normalized_url}/v1/chat/completions"

        transport = TransportHolderLlmHttp(
            target_name=f"ai-reviewer-{model_key}",
            max_timeout_seconds=timeout_seconds + 30.0,
        )
        handler = HandlerLlmOpenaiCompatible(transport)

        _request_kwargs: _OptionalRequestKwargs = {}
        if max_retries is not None:
            _request_kwargs["max_retries"] = max_retries
        # OMN-20422: top_p is an OPTIONAL per-model registry override, sent only
        # when declared, so an entry that sets none sends what it always sent.
        if config.top_p is not None:
            _request_kwargs["top_p"] = config.top_p
        extra_body = _build_extra_body(config, json_only=json_only)
        if repository:
            extra_body["metadata"] = {"repository": repository}
        request = ModelLlmInferenceRequest(
            base_url=endpoint_base,
            endpoint_url=endpoint_url,
            operation_type=EnumLlmOperationType.CHAT_COMPLETION,
            model=await asyncio.to_thread(
                _resolve_api_model_id, model_key, config, endpoint_base
            ),
            messages=({"role": "user", "content": user_prompt},),
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=(
                config.temperature
                if config.temperature is not None
                else _DEFAULT_TEMPERATURE
            ),
            timeout_seconds=timeout_seconds,
            **_request_kwargs,
            # OMN-14176: enable_thinking is a DECLARATIVE per-model registry field
            # (model_registry.yaml), not a code-baked constant -- flipping it for
            # a model is a config edit, not a code change + redeploy. The
            # extra_body passthrough itself (OMN-12816) already exists on this
            # request model and is proven in production by node_generation_consumer
            # (omnimarket) for SEA generation determinism; this reads the same
            # config.enable_thinking the registry declares per model and threads
            # it through. When a thinking-capable model is allowed to reason
            # (enable_thinking=True), it can spend most of max_tokens on an
            # unwrapped reasoning preamble (observed live: 3496/4096 tokens, no
            # <think> opener but an unmatched </think> closer) that both defeats
            # the strip-think-tags step below (needs both tags) and, on slower
            # backends, risks consuming the full budget before an answer is ever
            # generated. qwen3-review and local-studio-planner are configured
            # enable_thinking: false in the registry; confirmed live on both
            # vLLM (5090) and llama.cpp (4090) that the toggle suppresses the
            # preamble entirely at generation time.
            #
            # OMN-17492: a local model whose chat template reads
            # reasoning_effort gets it from the same chat_template_kwargs; it is
            # sent only when the registry declares it, so every other entry
            # sends exactly what it sent before. (The model behind
            # local-studio-planner is Qwen3.8-27B since 2026-10-09, per the
            # delegation overlay; see its registry entry for what that does to
            # this field.) A voter is told the repository in metadata.repository;
            # a cloud voter's endpoint enforces the operator ruling of
            # 2026-10-13T20:50:03Z: one repository never goes to a cloud model.
            extra_body=extra_body,
        )

        response = await handler.handle(request)
        text = str(response.generated_text)

        # Qwen3 models emit <think>...</think> reasoning blocks before the
        # actual response. Strip through the LAST </think> to get the JSON
        # content. Some backends / chat templates emit only the CLOSING </think>
        # marker with no matching opener (observed live, OMN-14176) -- a paired-
        # tag regex cannot match that case, so this takes everything after the
        # last </think> regardless of whether an opener is present. Defense in
        # depth in case extra_body above is ever bypassed or a future model
        # reverts to emitting reasoning despite the toggle. A response with no
        # </think> at all (reasoning never closed, e.g. truncated at max_tokens)
        # has nothing to strip here -- that failure mode is addressed by
        # suppressing reasoning at request time (extra_body above), not by
        # post-hoc stripping.
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[1].strip()
        return _openai_call_response(text, response)

    failover_errors = _failover_errors()
    for index, endpoint_base in enumerate(endpoints):
        is_last = index == len(endpoints) - 1
        try:
            timeout = config.timeout_seconds if is_last else giveup_seconds
            if call_deadline is None:
                reply = await _attempt(
                    endpoint_base, timeout, config.max_retries if is_last else 0
                )
            else:
                # A primary that answers just inside its request timeout can
                # still consume several chunks' budgets. Give every endpoint
                # a share of this chunk's remaining time, rather than waiting
                # until the whole vote expires before trying overflow.
                remaining = call_deadline - time.monotonic()
                if remaining <= 0:
                    raise _budget_exhausted(model_key, budget_seconds or 0.0)
                # OMN-17427: the last endpoint has nowhere to fall to; only the
                # vote's deadline bounds it beyond the model's own timeout.
                if is_last:
                    reply = await _attempt(endpoint_base, timeout, 0)
                else:
                    endpoint_seconds = min(
                        timeout, remaining / (len(endpoints) - index)
                    )
                    try:
                        reply = await asyncio.wait_for(
                            # The request schema's minimum is one second. The
                            # enclosing wall-clock timeout still enforces smaller
                            # shares when a review is almost out of time.
                            _attempt(endpoint_base, max(1.0, endpoint_seconds), 0),
                            timeout=endpoint_seconds,
                        )
                    except TimeoutError as exc:
                        raise _budget_exhausted(model_key, endpoint_seconds) from exc
        except failover_errors as exc:
            if is_last:
                raise
            print(
                f"Model '{model_key}' endpoint {index + 1} of {len(endpoints)} "
                f"({endpoint_base}) is full or unavailable "
                f"({type(exc).__name__}); trying overflow endpoint "
                f"{endpoints[index + 1]}.",
                file=sys.stderr,
                flush=True,
            )
            # OMN-17427: a dead endpoint costs one chunk's share, not a share
            # of every later chunk in this vote.
            if failed_endpoints is not None:
                failed_endpoints.add(endpoint_base)
            continue
        SERVED_BASE_URLS[model_key] = endpoint_base
        # OMN-17427: filtering can place an overflow endpoint at index zero.
        if endpoint_base != base_url:
            print(
                f"Model '{model_key}' served by overflow endpoint "
                f"{index + 1} of {len(endpoints)} "
                f"({endpoint_base}).",
                file=sys.stderr,
                flush=True,
            )
        return reply
    raise AssertionError("unreachable: the last endpoint returns or raises")


def try_parse_review_response(raw_text: str) -> list[dict[str, Any]] | None:
    """Extract structured JSON findings from model response.

    Handles common model output patterns:
    - Raw JSON array
    - JSON wrapped in markdown fences
    - Leading/trailing commentary around JSON

    Args:
        raw_text: Raw text response from the model.

    Returns:
        List of finding dictionaries (empty for a reply that parsed as ``[]``),
        or None when nothing in the reply parsed as review JSON. OMN-20422:
        None and ``[]`` are different answers -- a clean review versus no
        review -- and callers must not fold one into the other.
    """
    text = raw_text.strip()

    # Try direct JSON parse first.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # OMN-14176: observed live with enable_thinking:false -- without a
            # reasoning scratchpad to plan the response shape, the model
            # sometimes emits a single well-formed finding object instead of
            # wrapping it in the array the system prompt requires. Treat a
            # single object as a one-element result rather than discarding a
            # real finding because of a missing wrapper.
            logger.warning(
                "Parsed JSON is a single object, not an array; treating as one finding"
            )
            return [parsed]
        logger.warning(
            "Parsed JSON is not a list or object; got %s", type(parsed).__name__
        )
        return None
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown fences.
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1).strip())
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
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
    return None


def parse_review_response(raw_text: str) -> list[dict[str, Any]]:
    """Like :func:`try_parse_review_response`, with an empty list on failure.

    For callers that only want findings. A caller deciding whether a model's
    vote counts must use :func:`try_parse_review_response`: this one cannot tell
    a clean review from an unparseable reply.
    """
    parsed = try_parse_review_response(raw_text)
    return parsed if parsed is not None else []


# OMN-20422: explicit statements that a finding is not a defect, as both lab
# voters wrote them ("No finding here", "Retracting this finding"). Narrow on
# purpose: "this is correct" and "is acceptable" also open sentences that go on
# to name a real gap, so they are not here.
_NO_DEFECT_STATEMENTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bno finding here\b", re.IGNORECASE),
    re.compile(r"\bretract(?:ing|ed|s)? (?:this|the) finding\b", re.IGNORECASE),
    re.compile(
        r"\bno (?:actual |real )?(?:defect|finding|bug)s? "
        r"(?:here|found|exists?|is present)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bno defect\s*[.;]", re.IGNORECASE),
    re.compile(r"\bthis is not a (?:finding|defect|bug)\b", re.IGNORECASE),
)
# A proposed fix that is only "no change": the statement ends at punctuation or
# at the end of the field. "No change needed in X; do Y" and "No action
# required unless ..." go on to ask for something, so they do not match.
_NO_CHANGE_FIX: re.Pattern[str] = re.compile(
    r"^\s*(?:no (?:code )?(?:change|fix|action)s? (?:is |are )?"
    r"(?:needed|required|necessary)|none (?:needed|required))\s*(?:[.;,:]|$)",
    re.IGNORECASE,
)
# Evidence quotes the diff, which can contain any of these words, so it is not
# read.
_SELF_NEGATION_FIELDS: tuple[str, ...] = ("title", "description", "proposed_fix")


def self_negation_reason(item: dict[str, Any]) -> str | None:
    """Return why a finding's own text says it is not a defect, or None.

    OMN-20422: both voters emitted critical findings whose text ended "No
    finding here ... No defect", and two of them in one place blocked a clean
    pull request. None means the finding stands as written.
    """
    for field in _SELF_NEGATION_FIELDS:
        text = str(item.get(field) or "")
        for pattern in _NO_DEFECT_STATEMENTS:
            match = pattern.search(text)
            if match is not None:
                return f"{field} says {match.group(0).strip()!r}"
    fix = str(item.get("proposed_fix") or "")
    match = _NO_CHANGE_FIX.match(fix)
    if match is not None:
        return f"proposed_fix says {match.group(0).strip()!r}"
    return None


def split_self_negating(
    parsed: list[Any],
) -> tuple[list[Any], list[ModelDroppedFinding]]:
    """Split parsed findings into kept ones and self-negating ones (OMN-20422).

    Order is preserved. Non-dict items are kept for ``to_review_findings`` to
    skip as before. Each drop is logged and returned with its reason, so the
    caller records it on the result instead of losing it.
    """
    kept: list[Any] = []
    dropped: list[ModelDroppedFinding] = []
    for item in parsed:
        reason = self_negation_reason(item) if isinstance(item, dict) else None
        if reason is None:
            kept.append(item)
            continue
        location = item.get("location")
        record = ModelDroppedFinding(
            title=str(item.get("title", "Untitled finding")),
            severity=str(item.get("severity", "")),
            category=str(item.get("category", "")),
            location=str(location) if location else None,
            reason=reason,
        )
        logger.warning(
            "Dropped %s finding %r: its own text states no defect (%s)",
            record.severity,
            record.title,
            reason,
        )
        dropped.append(record)
    return kept, dropped


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
    standing_rules: ModelReviewStandingRules | None = None,
) -> list[ModelReviewFindingObserved]:
    """Convert parsed finding dicts to canonical ModelReviewFindingObserved models.

    Args:
        parsed: List of finding dictionaries from parse_review_response.
        model_key: Model key for rule_id construction.
        repo: Repository slug (default "plan-review" for plan reviews).
        pr_id: PR number (default 0 for non-PR contexts).
        commit_sha: Commit SHA (default placeholder for plan reviews).
        standing_rules: The rules the model was handed (OMN-20784). A finding
            whose ``standing_rule_id`` names one of them is bound to it, and a
            violated mandatory rule is never below blocking severity. A
            citation of any other id binds nothing.

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

        standing_rule_id: str | None = None
        cited = item.get("standing_rule_id")
        if standing_rules is not None and isinstance(cited, str):
            standing_rule = standing_rules.rule(cited)
            if standing_rule is None:
                logger.warning(
                    "Model '%s' cited standing rule %r, which is not in the "
                    "supplied rules; the finding is not bound",
                    model_key,
                    cited,
                )
            else:
                standing_rule_id = standing_rule.id
                if standing_rule.mandatory:
                    severity = EnumFindingSeverity.ERROR

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
                standing_rule_id=standing_rule_id,
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
    standing_rules: ModelReviewStandingRules | None = None,
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
        standing_rules: The rules the model was handed (OMN-20784).
        **kwargs: Additional keyword arguments (ignored).

    Returns:
        List of ModelReviewFindingObserved instances.
    """
    _validate_model_key(model)

    text = raw if isinstance(raw, str) else json.dumps(raw)
    parsed, _dropped = split_self_negating(parse_review_response(text))
    return to_review_findings(
        parsed,
        model,
        repo=repo,
        pr_id=pr_id,
        commit_sha=commit_sha,
        standing_rules=standing_rules,
    )


def unparseable_reply_result(
    model: str,
    raw_reply_length: int,
    *,
    earlier_lengths: tuple[int, ...] = (),
) -> ModelExternalReviewResult:
    """Failed vote for a model whose reply never parsed as review JSON (OMN-20422).

    Records the failure and the reply length, never the reply text: the reply is
    model output over a private diff and has no business in a CI log.
    """
    lengths = ", ".join(str(n) for n in (*earlier_lengths, raw_reply_length))
    attempts = len(earlier_lengths) + 1
    logger.warning(
        "Model '%s' returned an unparseable reply on %d attempt(s); vote failed",
        model,
        attempts,
    )
    return ModelExternalReviewResult(
        model=model,
        prompt_version=PROMPT_VERSION,
        success=False,
        error=(
            f"unparseable reply: no review JSON in {attempts} attempt(s) "
            f"(reply lengths in chars: {lengths})"
        ),
        parse_failed=True,
        raw_reply_length=raw_reply_length,
    )


def _review_output_tokens(content: str, config: ModelEndpointConfig) -> int:
    """Scale output with evidence size, leaving room for a doubled retry."""
    sized = _DEFAULT_MAX_TOKENS + (len(content.encode()) // 8192) * 1024
    return min(sized, _MAX_REVIEW_TOKENS, config.context_window_tokens // 4)


def _try_parse_complete_review(raw_text: str) -> list[dict[str, Any]] | None:
    """JSON syntax alone is no vote: require the published finding fields.

    Keep the permissive extraction API for callers that parse historical data,
    but never turn an error object, scalar array or incomplete finding into a
    successful vote with zero findings.
    """
    # Do not extract an incidental [] from unfinished prose/reasoning and
    # count it as a clean review. The vote must be the complete answer.
    text = raw_text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return None
    item_schema = FINDINGS_RESPONSE_FORMAT["json_schema"]["schema"]["items"]
    # standing_rule_id (OMN-20784) is only meaningful when standing rules were
    # supplied, so a reply that omits it is still a complete finding.
    required = set(item_schema["required"]) - {"standing_rule_id"}
    for finding in parsed:
        if not isinstance(finding, dict) or not (
            required <= set(finding) <= set(item_schema["properties"])
        ):
            return None
        for name, value in finding.items():
            field = item_schema["properties"][name]
            if value is None and "null" in field["type"]:
                continue
            if not isinstance(value, str):
                return None
            if "enum" in field and value not in field["enum"]:
                return None
    return parsed


def _review_chunks(content: str, max_bytes: int) -> list[str]:
    """Pack whole files, splitting oversized files at hunk/line boundaries.

    The files-API fallback target (cli_review) carries no ``diff --git`` lines;
    it is split at its per-file ``--- name (status, +a/-d) ---`` blocks, so its
    preamble is not repeated as a header in every chunk (OMN-21289).

    UTF-8 bytes conservatively bound byte-tokenizer input without assuming an
    English characters-per-token ratio for code or non-ASCII text. No evidence
    is truncated. An indivisible line/header that cannot fit fails the vote.
    """
    if max_bytes <= 0:
        raise ValueError("review context cannot fit prompts and reserved output")
    if len(content.encode()) <= max_bytes:
        return [content]
    files = _REVIEW_FILE_BOUNDARY.split(content)
    parts: list[str] = []
    for file in files:
        if not file:
            continue
        if len(file.encode()) <= max_bytes:
            parts.append(file)
            continue
        # Repeat the file header and the current original hunk header in each
        # continuation, so every excerpt retains its path and diff coordinates.
        lines = file.splitlines(keepends=True)
        header_end = next(
            (i for i, line in enumerate(lines) if line.startswith("@@")), 0
        )
        header = "".join(lines[:header_end])
        continuation = ""
        if header:
            continuation = (
                "[File excerpt; repeated hunk header is original context, "
                "and this excerpt may continue that hunk.]\n"
            )
        prefix = continuation + header
        current = prefix
        hunk_header = ""
        for line in lines[header_end:]:
            if line.startswith("@@"):
                hunk_header = line
            if len((current + line).encode()) > max_bytes:
                if current == prefix:
                    raise ValueError("review context cannot fit a diff line and header")
                parts.append(current)
                current = prefix + (hunk_header if not line.startswith("@@") else "")
            if len((current + line).encode()) > max_bytes:
                raise ValueError("review context cannot fit a diff line and header")
            current += line
        if current != prefix:
            parts.append(current)
    batches: list[str] = []
    current = ""
    for part in parts:
        if current and len((current + part).encode()) > max_bytes:
            batches.append(current)
            current = ""
        current += part
    if current:
        batches.append(current)
    return batches


def _budget_exhausted(model: str, budget_seconds: float) -> Exception:
    """The voter ran out of its shared review budget: a timeout (OMN-19998).

    It carries the transport's timeout code, as a single call that ran past its
    timeout did before chunking, so the substitute-vote policy treats it as a
    voter that timed out rather than one that answered.
    """
    from omnibase_infra.enums import EnumInfraTransportType
    from omnibase_infra.errors import InfraTimeoutError, ModelTimeoutErrorContext

    return InfraTimeoutError(
        f"review budget exhausted; review is incomplete (model {model!r})",
        context=ModelTimeoutErrorContext(
            transport_type=EnumInfraTransportType.HTTP,
            operation="llm_review",
            timeout_seconds=budget_seconds,
        ),
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
    standing_rules: ModelReviewStandingRules | None = None,
    repository: str | None = None,
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
        standing_rules: The reviewed repository's standing rules (OMN-20784),
            rendered into the system prompt and used to bind cited findings.
        repository: Repository sent to the model as metadata.repository
            (OMN-20106). None sends no metadata.

    Returns:
        ModelExternalReviewResult with review findings or error.
    """
    usage_totals = [0, 0]
    # Each review owns its accumulator. Child wait_for tasks inherit its
    # reference, so parse retries and chunks report into the same receipt.
    usage_scope = _ANTHROPIC_USAGE.set(usage_totals)
    try:
        _validate_model_key(model)
        config = MODEL_REGISTRY[model]

        async def call_before_deadline(
            system: str,
            user: str,
            *,
            chunks_left: int,
            **kwargs: Unpack[_OutputBudgetKwargs],
        ) -> str:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _budget_exhausted(model, deadline_seconds)
            if config.provider == "claude_code" or (
                config.overflow_urls and len(chunks) > 1
            ):
                # All chunks must finish for a vote. A parse retry shares the
                # same remaining budget and must also leave time for them.
                kwargs["budget_seconds"] = remaining / chunks_left
                # OMN-17427: carry failover state across chunks, except through
                # the Claude Code call path, which only needs its time budget.
                if config.provider != "claude_code":
                    kwargs["failed_endpoints"] = failed_endpoints
            try:
                return await asyncio.wait_for(
                    call_model(
                        system, user, model_key=model, repository=repository, **kwargs
                    ),
                    timeout=remaining,
                )
            except TimeoutError as exc:
                raise _budget_exhausted(model, deadline_seconds) from exc

        system_prompt, empty_user_prompt = build_review_prompt(
            "",
            review_type=review_type,
            system_prompt_prefix=system_prompt_prefix,
            standing_rules=standing_rules,
        )
        # Reserve the largest possible retry output, focus, schema, chat framing
        # and chunk labels BEFORE batching. This also covers overflow endpoints:
        # the overlay's window is the smallest window of all its endpoints.
        overhead = len(
            (
                system_prompt
                + empty_user_prompt
                + _JSON_ONLY_RETRY
                + config.review_focus
                + "\n\n## Reviewer Focus\n\n"
            ).encode()
        )
        reserved_output = min(2 * _MAX_REVIEW_TOKENS, config.context_window_tokens // 2)
        chunks = _review_chunks(
            plan_content,
            config.context_window_tokens - reserved_output - overhead - _CONTEXT_MARGIN,
        )
        # The deadline never exceeds the budget the CI preflight reserves for
        # this voter. All calls and parse retries share it; an incomplete
        # review expires as a failed vote before the job is killed. With a
        # declared ceiling it scales with the chunk count (OMN-20910).
        budgets = compute_sequential_worst_case(
            [model], configs={model: config}, chunk_count=len(chunks)
        )
        deadline_seconds = (
            budgets[0].worst_case_seconds if budgets else config.timeout_seconds
        )
        deadline = time.monotonic() + deadline_seconds
        # OMN-17427: failover state belongs to this review, including retries.
        failed_endpoints: set[str] = set()
        if len(chunks) > 1:
            print(
                f"Model '{model}' reviewing {len(chunks)} chunks within a "
                f"{deadline_seconds:g}s review deadline.",
                file=sys.stderr,
                flush=True,
            )
        all_parsed: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, chunk in enumerate(chunks, 1):
            chunk_system, user_prompt = build_review_prompt(
                chunk,
                review_type=review_type,
                system_prompt_prefix=system_prompt_prefix,
                standing_rules=standing_rules,
            )
            if len(chunks) > 1:
                chunk_system += (
                    f"\nReview chunk {index}/{len(chunks)} of the same change. "
                    "Review every supplied change; other files are in other chunks. "
                    "Do not infer a missing implementation from an absent file."
                )
            output_tokens = _review_output_tokens(chunk, config)
            if len(chunks) > 1:
                print(
                    f"Model '{model}' reviewing chunk {index}/{len(chunks)} "
                    f"({len(chunk.encode())} input bytes, max_tokens={output_tokens}).",
                    file=sys.stderr,
                    flush=True,
                )
            budget_kwargs: _OutputBudgetKwargs = (
                {"max_tokens": output_tokens}
                if output_tokens != _DEFAULT_MAX_TOKENS
                else {}
            )
            raw_text = await call_before_deadline(
                chunk_system,
                user_prompt,
                chunks_left=len(chunks) - index + 1,
                **budget_kwargs,
            )
            parsed = _try_parse_complete_review(raw_text)
            if parsed is None:
                first_length = len(raw_text)
                retry_tokens = 2 * output_tokens
                logger.warning(
                    "Model '%s' chunk %d/%d reply did not parse (%d chars); "
                    "retrying once with JSON ONLY and max_tokens=%d",
                    model,
                    index,
                    len(chunks),
                    first_length,
                    retry_tokens,
                )
                raw_text = await call_before_deadline(
                    chunk_system + _JSON_ONLY_RETRY,
                    user_prompt,
                    chunks_left=len(chunks) - index + 1,
                    max_tokens=retry_tokens,
                    json_only=True,
                )
                parsed = _try_parse_complete_review(raw_text)
                if parsed is None:
                    failure = unparseable_reply_result(
                        model, len(raw_text), earlier_lengths=(first_length,)
                    )
                    if len(chunks) > 1:
                        failure = failure.model_copy(
                            update={
                                "error": f"chunk {index}/{len(chunks)}: {failure.error}"
                            }
                        )
                    return failure.model_copy(
                        update={
                            "input_tokens": usage_totals[0],
                            "output_tokens": usage_totals[1],
                        }
                    )
            for finding in parsed:
                key = json.dumps(finding, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    all_parsed.append(finding)
        # OMN-20422: a finding whose own text says there is no defect is
        # recorded as dropped and never reaches the quorum.
        parsed, dropped = split_self_negating(all_parsed)
        findings = to_review_findings(
            parsed,
            model,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
            standing_rules=standing_rules,
        )
        return ModelExternalReviewResult(
            model=model,
            prompt_version=PROMPT_VERSION,
            success=True,
            input_tokens=usage_totals[0],
            output_tokens=usage_totals[1],
            findings=findings,
            result_count=len(findings),
            dropped_findings=dropped,
        )
    except Exception as exc:
        # OMN-17293: the infra LLM transport builds request-rejection errors with
        # `response_body=<snippet>`, but str(exc) drops it -- so a 400 that the
        # endpoint explained ("input is longer than max_model_len", etc.) reached
        # the CI log as a bare "Request rejected (400)". That missing sentence is
        # why an oversized-payload defect read as generic GPU contention. Append
        # the body when the exception carries one.
        response_body = getattr(exc, "response_body", None)
        detail = (
            f"{exc} :: response_body={response_body}" if response_body else str(exc)
        )
        logger.warning("Review failed for model '%s': %s", model, detail)
        return ModelExternalReviewResult(
            model=model,
            prompt_version=PROMPT_VERSION,
            success=False,
            input_tokens=usage_totals[0],
            output_tokens=usage_totals[1],
            error=detail,
        )
    finally:
        _ANTHROPIC_USAGE.reset(usage_scope)


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return PROBABILISTIC
