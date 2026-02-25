# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler: Gmail Intent Evaluator — full evaluation pipeline.

Implements all 10 steps of the Gmail intent evaluation flow:
  1. Compute evaluation_id via sha256
  2. Idempotency check against gmail_intent_evaluations table
  3. URL selection (tier-based domain preference)
  4. Fetch URL content (via clients.gmail_intent_http_client — ARCH-002 compliant)
  5. Query omnimemory for duplicate detection (Qdrant semantic search)
  6. Call DeepSeek R1 for verdict (SURFACE / WATCHLIST / SKIP)
  7. Validate + schema-check LLM response
  8. Rate-limited Slack post (5/hour via in-memory counter; Valkey optional)
  9. Emit downstream Kafka events via pending_events
 10. Write idempotency record to gmail_intent_evaluations table

Fallback behavior:
  - omnimemory unavailable → empty hits, error appended, no exception
  - DeepSeek unavailable → verdict=WATCHLIST, no exception
  - Slack fails → slack_sent=False, verdict unchanged
  - URL fetch fails → url_fetch_status=FAILED, body_text fallback
  - Idempotency store unavailable → log warning, proceed in degraded mode

ARCH-002 compliance:
  - Transport imports (httpx, asyncpg) are in omniintelligence.clients (excluded layer)
  - DB access goes through ProtocolPatternRepository (injected)
  - HTTP calls delegated to clients.gmail_intent_http_client

Reference:
    - OMN-2790: HandlerGmailIntentEvaluate implementation
    - OMN-2787: Gmail Intent Evaluator epic
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Any, Literal

from omnibase_infra.handlers.handler_slack_webhook import HandlerSlackWebhook
from omnibase_infra.handlers.models.model_slack_alert import (
    EnumAlertSeverity,
    ModelSlackAlert,
)

from omniintelligence.clients.gmail_intent_http_client import (
    call_deepseek_r1 as _http_call_deepseek_r1,
)
from omniintelligence.clients.gmail_intent_http_client import (
    fetch_embedding as _http_fetch_embedding,
)
from omniintelligence.clients.gmail_intent_http_client import (
    fetch_url_content as _http_fetch_url_content,
)
from omniintelligence.clients.gmail_intent_http_client import (
    make_asyncpg_repository as _make_asyncpg_repository,
)
from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluation_result import (
    ModelGmailIntentEvaluationResult,
    ModelMemoryHit,
)
from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models.model_gmail_intent_evaluator_config import (
    ModelGmailIntentEvaluatorConfig,
)
from omniintelligence.protocols import ProtocolPatternRepository

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

_RESOLVER_VERSION: str = "v1"
_MEMORY_QUERY_LIMIT: int = 5
_MEMORY_SIMILARITY_THRESHOLD: float = 0.65
_SLACK_MESSAGE_MAX_CHARS: int = 3000
_SLACK_RATE_LIMIT_PER_HOUR: int = 5

# Rate limiter: simple in-memory bucket keyed by hour
_slack_rate_buckets: dict[int, int] = {}
_slack_rate_lock = asyncio.Lock()

# =============================================================================
# URL Tier Classification
# =============================================================================

# Domain tier mapping (lower tier = higher preference)
_TIER_1_DOMAINS: frozenset[str] = frozenset(
    ["github.com", "arxiv.org", "huggingface.co", "paperswithcode.com"]
)
_TIER_2_DOMAINS: frozenset[str] = frozenset(["readthedocs.io", "docs.", ".dev", ".io"])
_TIER_3_DOMAINS: frozenset[str] = frozenset(
    ["substack.com", "medium.com", "ycombinator.com", "news.ycombinator.com"]
)
# Known tracking/redirect domains to deprioritize
_SKIP_DOMAINS: frozenset[str] = frozenset(
    ["c.gle", "bit.ly", "t.co", "ow.ly", "tinyurl.com", "goo.gl", "cli.ck"]
)
_SKIP_PARAMS: frozenset[str] = frozenset(["utm_source", "utm_medium", "utm_campaign"])


def _url_tier(url: str) -> int:
    """Return URL tier (1=best, 4=lowest, 99=skip)."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        query = parsed.query

        # Deprioritize tracking params
        if any(p in query for p in _SKIP_PARAMS):
            return 99

        # Known redirectors
        if any(d in domain for d in _SKIP_DOMAINS):
            return 99

        # Tier 1: GitHub, arxiv, huggingface, paperswithcode
        if any(d in domain for d in _TIER_1_DOMAINS):
            return 1

        # Tier 2: docs sites
        if any(d in domain for d in _TIER_2_DOMAINS):
            return 2

        # Tier 3: blogs
        if any(d in domain for d in _TIER_3_DOMAINS):
            return 3

        return 4
    except Exception:
        return 99


def _select_url(urls: list[str]) -> tuple[str | None, list[str]]:
    """Select best URL and return (selected_url, url_candidates).

    url_candidates contains Tier 1-3 URLs (up to 3).
    Returns (None, []) if all URLs are Tier 4+ or deprioritized.
    """
    if not urls:
        return None, []

    tiered = sorted(urls, key=_url_tier)
    candidates = [u for u in tiered if _url_tier(u) <= 3][:3]
    selected = tiered[0] if _url_tier(tiered[0]) <= 4 else None
    return selected, candidates


# =============================================================================
# PII Stripping
# =============================================================================

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


def _strip_pii(text: str, sender: str) -> str:
    """Strip email addresses (except sender domain) and phone numbers from text."""
    # Extract sender domain for preservation
    sender_domain = ""
    if "@" in sender:
        sender_domain = sender.split("@", 1)[1].lower()

    def _replace_email(m: re.Match[str]) -> str:
        email = m.group()
        if sender_domain and email.lower().endswith("@" + sender_domain):
            return f"[redacted]@{sender_domain}"
        return "[redacted@redacted.com]"

    text = _EMAIL_PATTERN.sub(_replace_email, text)
    text = _PHONE_PATTERN.sub("[redacted-phone]", text)
    return text


# =============================================================================
# URL Content Fetcher (delegates to clients layer — ARCH-002)
# =============================================================================


async def _fetch_url_content(url: str) -> tuple[str, Literal["OK", "FAILED"]]:
    """Fetch URL content with 512KB cap and HTML stripping.

    Delegates to omniintelligence.clients.gmail_intent_http_client.
    Returns (content, status).
    """
    content, status_str = await _http_fetch_url_content(url)
    status: Literal["OK", "FAILED"] = "OK" if status_str == "OK" else "FAILED"
    return content, status


# =============================================================================
# Omnimemory Query (Qdrant-based, embedding via clients layer)
# =============================================================================


async def _query_omnimemory(
    query_text: str,
    embedding_url: str,
) -> tuple[list[ModelMemoryHit], str | None]:
    """Query Qdrant via embedding for semantic duplicate detection.

    Returns (memory_hits, error_msg_or_None).
    """
    try:
        # Step 1: embed query text (via clients layer — ARCH-002 compliant)
        embedding = await _http_fetch_embedding(query_text, embedding_url)

        # Step 2: search Qdrant
        from qdrant_client import AsyncQdrantClient  # lazy — not a banned module

        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        collection_name = os.environ.get("OMNIMEMORY_COLLECTION", "omninode_memory")

        qdrant = AsyncQdrantClient(url=qdrant_url)
        try:
            query_result = await qdrant.query_points(
                collection_name=collection_name,
                query=embedding,
                limit=_MEMORY_QUERY_LIMIT,
                score_threshold=_MEMORY_SIMILARITY_THRESHOLD,
            )
        finally:
            await qdrant.close()

        hits = []
        for r in query_result.points:
            payload = r.payload or {}
            snippet = (
                payload.get("title", "")
                or payload.get("subject", "")
                or payload.get("tags", "")
                or ""
            )
            if isinstance(snippet, list):
                snippet = ", ".join(str(s) for s in snippet)
            hits.append(
                ModelMemoryHit(
                    item_id=str(payload.get("item_id", r.id)),
                    score=float(r.score),
                    snippet=str(snippet)[:120],
                )
            )
        return hits, None

    except Exception as exc:
        logger.warning("omnimemory query failed: %s", exc)
        return [], str(exc)


# =============================================================================
# LLM: DeepSeek R1 Call (delegates to clients layer — ARCH-002)
# =============================================================================

_SYSTEM_PROMPT = """You are an integration evaluator for OmniNode — an AI agent platform built on \
ONEX (Python, Kafka/Redpanda, PostgreSQL, Qdrant, Pydantic, asyncio).

Current stack: ONEX nodes (EFFECT/COMPUTE/REDUCER/ORCHESTRATOR), Kafka event bus, \
PostgreSQL, Qdrant vector store, Valkey cache, Consul, Infisical secrets, \
Redpanda, httpx async HTTP, omniintelligence (LLM evaluation), omnimemory \
(semantic retrieval), omniclaude (Claude Code agent plugin).

Active LLM tiers: Qwen3-Coder-30B (code/long context), Qwen3-14B (routing/mid), \
DeepSeek-R1-32B (reasoning), Qwen3-Embedding-8B (embeddings).

Evaluate: is this signal worth acting on for OmniNode?

Verdict rules:
- SURFACE: novel, useful, directly applicable — no equivalent in stack; or clear enhancement
- WATCHLIST: interesting but not immediately actionable, needs more context, or future relevance
- SKIP: noise, expired (webinar/social), clearly superseded, or duplicative with no enhancement

For LLMs/models: is it state-of-the-art for its class? Does it fill a gap in the model tier? \
Is it actually available (not just announced)?

Respond ONLY with valid JSON:
{"verdict":"SURFACE"|"WATCHLIST"|"SKIP","relevance_score":float,"reasoning":"2-3 sentences","initial_plan":"bullet points or null"}
initial_plan MUST be non-null when verdict=SURFACE."""


def _build_user_prompt(
    config: ModelGmailIntentEvaluatorConfig,
    selected_url: str | None,
    url_content: str,
    memory_hits: list[ModelMemoryHit],
    clean_body: str,
) -> str:
    """Build the LLM user prompt with duplicate hints."""
    # Memory hits summary
    if memory_hits:
        hits_summary = "\n".join(
            f"- {h.snippet or h.item_id} (score {h.score:.2f})" for h in memory_hits
        )
    else:
        hits_summary = "(no memory hits)"

    # Duplicate hint
    duplicate_hint = ""
    if memory_hits:
        top_score = memory_hits[0].score
        if top_score > 0.90:
            duplicate_hint = f"\nNOTE: top score {top_score:.2f} — strong duplicate signal; only SURFACE if clear enhancement"
        elif top_score >= 0.80:
            duplicate_hint = f"\nNOTE: top score {top_score:.2f} — partial overlap; bias WATCHLIST unless novel angle"

    prompt = (
        f"Subject: {config.subject}\n"
        f"Sender: {config.sender} | Received: {config.received_at}\n"
        f"URL: {selected_url or '(none)'}\n"
        f"\nBody:\n{clean_body[:2000]}\n"
        f"\nFetched content:\n{url_content[:2000]}\n"
        f"\nOmniNode memory hits:\n{hits_summary}"
        f"{duplicate_hint}"
    )
    return prompt


def _parse_llm_response(
    raw: str,
) -> tuple[dict[str, Any], Literal["OK", "RECOVERED", "FAILED"]]:
    """Parse LLM response with fallback recovery.

    Returns (parsed_dict, status).
    """
    # Attempt 1: strict parse
    try:
        return json.loads(raw), "OK"
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first {...} block
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group()), "RECOVERED"
        except json.JSONDecodeError:
            pass

    return {}, "FAILED"


def _validate_llm_dict(
    d: dict[str, Any],
    errors: list[str],
) -> tuple[Literal["SURFACE", "WATCHLIST", "SKIP"], float, str, str | None]:
    """Validate parsed LLM dict and return (verdict, score, reasoning, initial_plan)."""
    valid_verdicts: frozenset[str] = frozenset({"SURFACE", "WATCHLIST", "SKIP"})

    # Verdict
    raw_verdict = d.get("verdict", "WATCHLIST")
    if raw_verdict not in valid_verdicts:
        errors.append(
            f"LLM returned invalid verdict: {raw_verdict!r}; defaulting to WATCHLIST"
        )
        verdict: Literal["SURFACE", "WATCHLIST", "SKIP"] = "WATCHLIST"
    elif raw_verdict == "SURFACE":
        verdict = "SURFACE"
    elif raw_verdict == "SKIP":
        verdict = "SKIP"
    else:
        verdict = "WATCHLIST"

    # Relevance score
    raw_score = d.get("relevance_score", 0.5)
    try:
        score = float(raw_score)
        if score < 0.0:
            errors.append(f"relevance_score {score} < 0.0; clamped to 0.0")
            score = 0.0
        elif score > 1.0:
            errors.append(f"relevance_score {score} > 1.0; clamped to 1.0")
            score = 1.0
    except (ValueError, TypeError):
        errors.append(f"relevance_score not numeric: {raw_score!r}; defaulting to 0.5")
        score = 0.5

    # Reasoning
    reasoning = str(d.get("reasoning", "")) or "No reasoning provided"

    # Initial plan
    initial_plan: str | None = d.get("initial_plan") or None
    if verdict == "SURFACE" and not initial_plan:
        errors.append(
            "SURFACE verdict requires non-null initial_plan; demoting to WATCHLIST"
        )
        verdict = "WATCHLIST"

    return verdict, score, reasoning, initial_plan


async def _call_deepseek_r1(
    user_prompt: str,
    llm_url: str,
) -> tuple[dict[str, Any], Literal["OK", "RECOVERED", "FAILED"], list[str]]:
    """Call DeepSeek R1 and return (parsed_dict, parse_status, errors).

    Delegates to omniintelligence.clients.gmail_intent_http_client (ARCH-002).
    """
    errors: list[str] = []
    try:
        raw = await _http_call_deepseek_r1(_SYSTEM_PROMPT, user_prompt, llm_url)
        parsed, parse_status = _parse_llm_response(raw)
        return parsed, parse_status, errors

    except Exception as exc:
        logger.warning("DeepSeek R1 call failed: %s", exc)
        errors.append(f"LLM call failed: {exc}")
        return {}, "FAILED", errors


# =============================================================================
# Rate Limiter (in-memory, Valkey-optional)
# =============================================================================


async def _check_slack_rate_limit() -> bool:
    """Return True if posting is allowed (under 5/hour), False if rate-limited.

    Uses in-memory bucket keyed by hour. Valkey integration is an enhancement.
    """
    hour_bucket = int(time.time()) // 3600
    async with _slack_rate_lock:
        current = _slack_rate_buckets.get(hour_bucket, 0)
        if current >= _SLACK_RATE_LIMIT_PER_HOUR:
            return False
        _slack_rate_buckets[hour_bucket] = current + 1
        # Clean old buckets
        for old_key in [k for k in _slack_rate_buckets if k < hour_bucket - 1]:
            del _slack_rate_buckets[old_key]
        return True


# =============================================================================
# Slack Poster
# =============================================================================


async def _post_to_slack(
    config: ModelGmailIntentEvaluatorConfig,
    selected_url: str | None,
    reasoning: str,
    relevance_score: float,
    initial_plan: str | None,
    evaluation_id: str,
    errors: list[str],
) -> bool:
    """Post SURFACE notification to Slack. Returns True if sent."""
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    default_channel = os.environ.get("SLACK_DEFAULT_CHANNEL", "#ai-signals")

    url_label = f"<{selected_url}|{config.subject}>" if selected_url else config.subject

    message_body = (
        f"*New Technical Signal* — {url_label}\n\n"
        f"{reasoning}\n\n"
        f"*Verdict:* SURFACE  |  relevance: {relevance_score:.0%}\n"
        f"*From:* {config.sender}  |  *Received:* {config.received_at}\n"
    )

    if initial_plan:
        message_body += f"\n*Initial Plan:*\n{initial_plan}"

    message_body += f"\n\n_eval_id: {evaluation_id[:8]}_"

    # Cap message at 3000 chars
    if len(message_body) > _SLACK_MESSAGE_MAX_CHARS:
        message_body = message_body[: _SLACK_MESSAGE_MAX_CHARS - 3] + "..."

    if not bot_token:
        # Local mode: print to stdout
        print(f"[GMAIL SIGNAL] {message_body}")
        return False

    try:
        handler = HandlerSlackWebhook(
            bot_token=bot_token,
            default_channel=default_channel,
        )
        alert = ModelSlackAlert(
            severity=EnumAlertSeverity.INFO,
            message=message_body,
            title=f"Gmail Signal: {config.subject[:100]}",
            channel=default_channel,
        )
        result = await handler.handle(alert)
        if not result.success:
            errors.append(f"Slack delivery failed: {result.error_message}")
            return False
        return True
    except Exception as exc:
        errors.append(f"Slack delivery exception: {exc}")
        logger.warning("Slack delivery failed: %s", exc)
        return False


# =============================================================================
# Idempotency (uses ProtocolPatternRepository injection — ARCH-002 compliant)
# =============================================================================


async def _check_idempotency(
    evaluation_id: str,
    repository: ProtocolPatternRepository | None,
) -> tuple[bool, dict[str, Any] | None]:
    """Check if evaluation_id already exists. Returns (already_processed, prior_data)."""
    if repository is None:
        return False, None
    try:
        row = await repository.fetchrow(
            "SELECT verdict, relevance_score FROM gmail_intent_evaluations WHERE evaluation_id = $1",
            evaluation_id,
        )
        if row:
            return True, dict(row)
        return False, None
    except Exception as exc:
        logger.warning("Idempotency check failed (degraded mode): %s", exc)
        return False, None


async def _write_idempotency(
    evaluation_id: str,
    verdict: str,
    relevance_score: float,
    repository: ProtocolPatternRepository | None,
) -> None:
    """Write evaluation record to gmail_intent_evaluations (ON CONFLICT DO NOTHING)."""
    if repository is None:
        return
    try:
        await repository.execute(
            """
            INSERT INTO gmail_intent_evaluations (evaluation_id, verdict, relevance_score)
            VALUES ($1, $2, $3)
            ON CONFLICT (evaluation_id) DO NOTHING
            """,
            evaluation_id,
            verdict,
            relevance_score,
        )
    except Exception as exc:
        logger.warning("Failed to write idempotency record: %s", exc)


# =============================================================================
# Main Handler
# =============================================================================


async def handle_gmail_intent_evaluate(
    config: ModelGmailIntentEvaluatorConfig,
    *,
    repository: ProtocolPatternRepository | None = None,
    db_url: str | None = None,
    llm_url: str | None = None,
    embedding_url: str | None = None,
    _slack_rate_check: Callable[[], Any] | None = None,
) -> ModelGmailIntentEvaluationResult:
    """Evaluate a Gmail intent signal end-to-end.

    Args:
        config: Input model from gmail-intent-received.v1 event payload.
        repository: Pre-built DB repository for idempotency (preferred for tests).
            If None, falls back to creating one from db_url / OMNIBASE_INFRA_DB_URL.
        db_url: PostgreSQL DSN for idempotency table (fallback if repository is None).
            Defaults to OMNIBASE_INFRA_DB_URL env.
        llm_url: DeepSeek R1 endpoint. Defaults to LLM_DEEPSEEK_R1_URL env.
        embedding_url: Embedding endpoint. Defaults to LLM_EMBEDDING_URL env.
        _slack_rate_check: Override for rate limit check (testing).

    Returns:
        ModelGmailIntentEvaluationResult with verdict and all pipeline state.
    """
    errors: list[str] = []
    pending_events: list[Any] = []

    # Resolve config from environment
    resolved_llm_url = llm_url or os.environ.get(
        "LLM_DEEPSEEK_R1_URL", "http://192.168.86.200:8101"
    )
    resolved_embedding_url = embedding_url or os.environ.get(
        "LLM_EMBEDDING_URL", "http://192.168.86.200:8100"
    )
    rate_check_fn = _slack_rate_check or _check_slack_rate_limit

    # Resolve repository
    resolved_repository: ProtocolPatternRepository | None = repository
    if resolved_repository is None:
        resolved_db_url = db_url or os.environ.get("OMNIBASE_INFRA_DB_URL")
        resolved_repository = await _make_asyncpg_repository(resolved_db_url)

    # -------------------------------------------------------------------------
    # Step 1: Compute evaluation_id
    # -------------------------------------------------------------------------
    selected_url, url_candidates = _select_url(config.urls)
    evaluation_id = hashlib.sha256(
        f"{config.message_id}:{selected_url or ''}:{_RESOLVER_VERSION}".encode()
    ).hexdigest()

    logger.info(
        "gmail_intent_evaluate: message_id=%s evaluation_id=%s selected_url=%s",
        config.message_id,
        evaluation_id[:16],
        selected_url,
    )

    # -------------------------------------------------------------------------
    # Step 2: Idempotency check
    # -------------------------------------------------------------------------
    already_processed, prior_data = await _check_idempotency(
        evaluation_id, resolved_repository
    )
    if already_processed and prior_data:
        raw_verdict = prior_data.get("verdict", "WATCHLIST")
        valid_verdicts = {"SURFACE", "WATCHLIST", "SKIP"}
        idempotent_verdict: Literal["SURFACE", "WATCHLIST", "SKIP"] = (
            raw_verdict if raw_verdict in valid_verdicts else "WATCHLIST"
        )
        return ModelGmailIntentEvaluationResult(
            evaluation_id=evaluation_id,
            verdict=idempotent_verdict,
            reasoning="Idempotent: evaluation already processed",
            relevance_score=float(prior_data.get("relevance_score", 0.5)),
            initial_plan=None,
            selected_url=selected_url,
            url_candidates=url_candidates,
            url_fetch_status="SKIPPED",
            memory_hits=[],
            llm_parse_status="OK",
            slack_sent=False,
            rate_limited=False,
            errors=[],
            pending_events=[],
        )

    # -------------------------------------------------------------------------
    # Step 4: Fetch URL content
    # -------------------------------------------------------------------------
    url_content = ""
    url_fetch_status: Literal["OK", "FAILED", "SKIPPED"] = "SKIPPED"
    if selected_url:
        url_content, url_fetch_status = await _fetch_url_content(selected_url)

    # -------------------------------------------------------------------------
    # Step 5: Query omnimemory (Qdrant)
    # -------------------------------------------------------------------------
    memory_query = f"{config.subject} {selected_url or ''} {url_content[:500]}"
    memory_hits, memory_error = await _query_omnimemory(
        memory_query, resolved_embedding_url
    )
    if memory_error:
        errors.append(f"omnimemory query error: {memory_error}")

    # -------------------------------------------------------------------------
    # Step 6: PII strip + LLM call
    # -------------------------------------------------------------------------
    clean_body = _strip_pii(config.body_text, config.sender)
    user_prompt = _build_user_prompt(
        config, selected_url, url_content, memory_hits, clean_body
    )

    llm_dict, llm_parse_status, llm_errors = await _call_deepseek_r1(
        user_prompt, resolved_llm_url
    )
    errors.extend(llm_errors)

    # -------------------------------------------------------------------------
    # Step 7: Validate LLM response
    # -------------------------------------------------------------------------
    if llm_parse_status == "FAILED":
        verdict: Literal["SURFACE", "WATCHLIST", "SKIP"] = "WATCHLIST"
        relevance_score = 0.0
        reasoning = "LLM parse failed"
        initial_plan = None
    else:
        verdict, relevance_score, reasoning, initial_plan = _validate_llm_dict(
            llm_dict, errors
        )

    # -------------------------------------------------------------------------
    # Step 8: Rate-limited Slack post (SURFACE only)
    # -------------------------------------------------------------------------
    slack_sent = False
    rate_limited = False

    if verdict == "SURFACE":
        allowed = await rate_check_fn()
        if not allowed:
            rate_limited = True
            logger.info(
                "Slack rate limit reached for evaluation_id=%s", evaluation_id[:16]
            )
        else:
            slack_sent = await _post_to_slack(
                config=config,
                selected_url=selected_url,
                reasoning=reasoning,
                relevance_score=relevance_score,
                initial_plan=initial_plan,
                evaluation_id=evaluation_id,
                errors=errors,
            )

    # -------------------------------------------------------------------------
    # Step 9: Build downstream events
    # -------------------------------------------------------------------------
    evaluated_event: dict[str, Any] = {
        "event_type": "onex.evt.omniintelligence.gmail-intent-evaluated.v1",
        "evaluation_id": evaluation_id,
        "message_id": config.message_id,
        "verdict": verdict,
        "relevance_score": relevance_score,
        "selected_url": selected_url,
        "memory_hit_ids": [h.item_id for h in memory_hits],
        "llm_parse_status": llm_parse_status,
        "slack_sent": slack_sent,
    }
    pending_events.append(evaluated_event)

    if verdict == "SURFACE":
        surfaced_event: dict[str, Any] = {
            "event_type": "onex.evt.omniintelligence.gmail-intent-surfaced.v1",
            "evaluation_id": evaluation_id,
            "message_id": config.message_id,
            "subject": config.subject,
            "selected_url": selected_url,
            "initial_plan": initial_plan,
            "reasoning": reasoning,
        }
        pending_events.append(surfaced_event)

    # -------------------------------------------------------------------------
    # Step 10: Write idempotency record
    # -------------------------------------------------------------------------
    await _write_idempotency(
        evaluation_id, verdict, relevance_score, resolved_repository
    )

    return ModelGmailIntentEvaluationResult(
        evaluation_id=evaluation_id,
        verdict=verdict,
        reasoning=reasoning,
        relevance_score=relevance_score,
        initial_plan=initial_plan,
        selected_url=selected_url,
        url_candidates=url_candidates,
        url_fetch_status=url_fetch_status,
        memory_hits=memory_hits,
        llm_parse_status=llm_parse_status,
        slack_sent=slack_sent,
        rate_limited=rate_limited,
        errors=errors,
        pending_events=pending_events,
    )
