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
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any, TypedDict
from uuid import uuid4

from omniintelligence.review_pairing.adapters.base import (
    PROBABILISTIC,
    normalize_message,
    utcnow,
)
from omniintelligence.review_pairing.model_registry_loader import load_registry
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
)
from omniintelligence.review_pairing.served_model_resolver import (
    resolve_served_model_id,
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
        if not url:
            # Not configured (OMN-20930): nothing to probe, and a probe of an
            # empty host would be answered by whatever listens locally.
            results[key] = False
            continue
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

    Every voter is a local endpoint, so it is also probed for reachability like
    the registry's local keys. A voter id that names an existing registry key is
    refused: an overlay voter must never silently replace a registry entry, or
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
    _LOCAL_MODEL_KEYS = _LOCAL_MODEL_KEYS | frozenset(configs)


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


async def _call_claude_api(
    system_prompt: str,
    user_prompt: str,
    config: ModelEndpointConfig,
) -> str:
    """Call the Anthropic Claude API for api_fallback models.

    Per OMN-7835, ANTHROPIC_API_KEY is optional — Claude Code uses OAuth.
    If no key is available, this fallback is skipped (returns empty string).
    """
    import urllib.request as _urlreq

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning(
            "claude-api fallback skipped: ANTHROPIC_API_KEY not set "
            "(OAuth/SSO is the primary auth path per OMN-7835)"
        )
        return ""
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


def _build_extra_body(config: ModelEndpointConfig) -> dict[str, Any]:
    """Request-body keys the OpenAI-compatible effect merges in verbatim.

    ``chat_template_kwargs`` always (OMN-14176; ``reasoning_effort`` only when
    the registry declares it, OMN-17492). ``response_format`` only for an entry
    that sets ``constrain_findings_schema`` (OMN-20422), so every other entry
    sends exactly what it sent before.
    """
    template_kwargs: dict[str, Any] = {"enable_thinking": config.enable_thinking}
    if config.reasoning_effort is not None:
        template_kwargs["reasoning_effort"] = config.reasoning_effort
    extra_body: dict[str, Any] = {"chat_template_kwargs": template_kwargs}
    if config.constrain_findings_schema:
        extra_body["response_format"] = FINDINGS_RESPONSE_FORMAT
    return extra_body


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
    base_url = os.environ.get(config.env_var, config.default_url)
    if not base_url:
        raise ValueError(
            f"LLM endpoint not configured for '{model_key}'. "
            f"Set the {config.env_var} environment variable."
        )

    # OMN-14176 / OMN-12815: the OpenAI-compatible effect posts ``endpoint_url``
    # VERBATIM and performs no base_url + path construction. Registry URLs are
    # host:port only, so resolve the COMPLETE chat-completion URL here or the
    # transport raises "endpoint_url is required and must be the COMPLETE
    # contract endpoint URL" and every review DEGRADES with "all models failed".
    _normalized_url = base_url.rstrip("/")
    if _normalized_url.endswith("/chat/completions"):
        endpoint_url = _normalized_url
    else:
        endpoint_url = f"{_normalized_url}/v1/chat/completions"

    transport = TransportHolderLlmHttp(
        target_name=f"ai-reviewer-{model_key}",
        max_timeout_seconds=config.timeout_seconds + 30.0,
    )
    handler = HandlerLlmOpenaiCompatible(transport)

    # OMN-15115: max_retries is an OPTIONAL per-model registry override.
    # ``None`` means "no override" -- omit the kwarg entirely so
    # ModelLlmInferenceRequest applies its own default (3), which mirrors the
    # transport's historical hardcoded retry count. Only build an explicit
    # kwargs dict entry when the registry declares a real override, so models
    # that don't set it are provably unaffected by this change.
    _request_kwargs: _OptionalRequestKwargs = {}
    if config.max_retries is not None:
        _request_kwargs["max_retries"] = config.max_retries
    # OMN-20422: top_p is an OPTIONAL per-model registry override, sent only
    # when declared, so an entry that sets none sends what it always sent.
    if config.top_p is not None:
        _request_kwargs["top_p"] = config.top_p
    # OMN-20422: a per-model review focus extends the system prompt for that
    # voter only. Empty (the default) leaves the prompt byte-identical.
    if config.review_focus:
        system_prompt = f"{system_prompt}\n\n## Reviewer Focus\n\n{config.review_focus}"

    request = ModelLlmInferenceRequest(
        base_url=base_url,
        endpoint_url=endpoint_url,
        operation_type=EnumLlmOperationType.CHAT_COMPLETION,
        model=_resolve_api_model_id(model_key, config, base_url),
        messages=({"role": "user", "content": user_prompt},),
        system_prompt=system_prompt,
        max_tokens=_DEFAULT_MAX_TOKENS,
        temperature=(
            config.temperature
            if config.temperature is not None
            else _DEFAULT_TEMPERATURE
        ),
        timeout_seconds=config.timeout_seconds,
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
        # OMN-17492: gpt-oss reads reasoning_effort from the same
        # chat_template_kwargs; it is sent only when the registry declares it,
        # so every other entry sends exactly what it sent before. (The model
        # behind local-studio-planner has been Qwen3.6-35B-A3B since
        # 2026-10-08, OMN-17427; see its registry entry for what that does to
        # this field.) There is no cloud wire shape: private diffs go only to
        # lab models (2026-09-25).
        extra_body=_build_extra_body(config),
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

    return text


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
    _validate_model_key(model)

    text = raw if isinstance(raw, str) else json.dumps(raw)
    parsed, _dropped = split_self_negating(parse_review_response(text))
    return to_review_findings(
        parsed,
        model,
        repo=repo,
        pr_id=pr_id,
        commit_sha=commit_sha,
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
        _validate_model_key(model)
        system_prompt, user_prompt = build_review_prompt(
            plan_content,
            review_type=review_type,
            system_prompt_prefix=system_prompt_prefix,
        )
        raw_text = await call_model(system_prompt, user_prompt, model_key=model)
        parsed = try_parse_review_response(raw_text)
        if parsed is None:
            # OMN-20422: retry once with the same prompt, then fail the vote.
            logger.warning(
                "Model '%s' reply did not parse (%d chars); retrying once",
                model,
                len(raw_text),
            )
            first_length = len(raw_text)
            raw_text = await call_model(system_prompt, user_prompt, model_key=model)
            parsed = try_parse_review_response(raw_text)
            if parsed is None:
                return unparseable_reply_result(
                    model, len(raw_text), earlier_lengths=(first_length,)
                )
        # OMN-20422: a finding whose own text says there is no defect is
        # recorded as dropped and never reaches the quorum.
        parsed, dropped = split_self_negating(parsed)
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
            error=detail,
        )


def get_confidence_tier() -> str:
    """Return the confidence tier for this adapter."""
    return PROBABILISTIC
