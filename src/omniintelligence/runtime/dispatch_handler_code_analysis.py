# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch handler for code analysis commands (OMN-6969, OMN-6967).

Processes ``code-analysis.v1`` command events from omniclaude's
IntelligenceEventClient. Parses ModelCodeAnalysisRequestPayload,
runs LLM-backed quality analysis (Qwen Coder-14B via
AdapterCodeAnalysisEnrichment) with heuristic fallback, and publishes
ModelCodeAnalysisCompletedPayload or ModelCodeAnalysisFailedPayload.

Architecture:
    - LLM adapter preferred; graceful degrade to heuristic on any failure
    - Actionable findings are republished as pattern.discovered events
      with ``pattern_type='code_analysis_pattern'`` to feed pattern extraction
    - Produces completed/failed response events to Kafka
    - Dispatch alias used by create_intelligence_dispatch_engine()
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)
from omniintelligence.models.events.model_code_analysis_completed import (
    ModelCodeAnalysisCompletedPayload,
)
from omniintelligence.models.events.model_code_analysis_failed import (
    ModelCodeAnalysisFailedPayload,
)
from omniintelligence.models.events.model_code_analysis_request import (
    ModelCodeAnalysisRequestPayload,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# Canonical topic strings (ONEX naming: .cmd. / .evt.)
_CANONICAL_CMD = "onex.cmd.omniintelligence.code-analysis.v1"  # noqa: topic-naming-lint
_CANONICAL_COMPLETED = "onex.evt.omniintelligence.code-analysis-completed.v1"  # noqa: topic-naming-lint
_CANONICAL_FAILED = "onex.evt.omniintelligence.code-analysis-failed.v1"  # noqa: topic-naming-lint

# Dispatch alias — derived from canonical topic via bridge conversion.
DISPATCH_ALIAS_CODE_ANALYSIS = canonical_topic_to_dispatch_alias(_CANONICAL_CMD)

# Default publish topics for response events
TOPIC_CODE_ANALYSIS_COMPLETED = _CANONICAL_COMPLETED
TOPIC_CODE_ANALYSIS_FAILED = _CANONICAL_FAILED

# Pattern.discovered topic for actionable findings feed (OMN-6967).
# Canonical multi-producer topic consumed by NodePatternStorageEffect.
TOPIC_PATTERN_DISCOVERED = "onex.evt.pattern.discovered.v1"  # noqa: topic-naming-lint

# Stable marker for patterns emitted from this handler.
_PATTERN_TYPE_CODE_ANALYSIS = "code_analysis_pattern"
# Confidence floor for LLM-derived findings — must be >= 0.5 to pass
# ModelPatternDiscoveredEvent validation and pattern storage governance.
_LLM_FINDING_CONFIDENCE = 0.75
_SOURCE_SYSTEM = "omniintelligence.code_analysis"


# =============================================================================
# LLM Adapter Protocol (structural — matches AdapterCodeAnalysisEnrichment)
# =============================================================================


class ProtocolCodeAnalysisLLM(Protocol):
    """Structural protocol for the LLM code-analysis adapter.

    Matches ``AdapterCodeAnalysisEnrichment.enrich`` from omnibase_infra.
    Declared here to avoid a hard import on the adapter module at type-check
    time and to keep the handler unit-testable with a fake.
    """

    async def enrich(self, prompt: str, context: str) -> Any: ...  # noqa: ANN401 — ContractEnrichmentResult structural duck


# =============================================================================
# LLM-Backed Analysis
# =============================================================================


# Regex for extracting bullet-style findings from the adapter's markdown
# response. The adapter prompt asks for sections with bulleted items under
# headings like "Potential Issues" and "Affected Functions / Methods".
_SECTION_HEADING_RE = re.compile(r"^##+\s*(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s*$", re.MULTILINE)

_ISSUE_SECTION_KEYWORDS = ("issue", "risk", "regression", "breaking")
_RECOMMENDATION_SECTION_KEYWORDS = ("recommend", "suggest", "improvement")


def _extract_findings(markdown: str) -> tuple[list[str], list[str]]:
    """Parse adapter markdown into issues and recommendations.

    The adapter produces a structured Markdown report with ``##`` section
    headings. We walk sections and classify each bullet by its heading.

    Returns:
        (issues, recommendations) — lists of plain-text finding strings.
    """
    issues: list[str] = []
    recommendations: list[str] = []

    # Split by heading boundaries; keep (heading, body) pairs.
    headings = list(_SECTION_HEADING_RE.finditer(markdown))
    if not headings:
        # No structured sections — treat every bullet as an issue.
        for m in _BULLET_RE.finditer(markdown):
            issues.append(m.group(1).strip())
        return issues, recommendations

    for idx, match in enumerate(headings):
        heading = match.group(1).lower()
        start = match.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(markdown)
        body = markdown[start:end]
        bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
        if not bullets:
            continue
        if any(kw in heading for kw in _RECOMMENDATION_SECTION_KEYWORDS):
            recommendations.extend(bullets)
        elif any(kw in heading for kw in _ISSUE_SECTION_KEYWORDS):
            issues.extend(bullets)
        # Other sections (Summary, Affected Functions) are informational.
    return issues, recommendations


async def _llm_quality_score(
    adapter: ProtocolCodeAnalysisLLM,
    content: str,
    language: str,
    operation_type: EnumAnalysisOperationType,
    source_path: str,
) -> ModelCodeAnalysisCompletedPayload:
    """Run LLM-backed analysis via ``AdapterCodeAnalysisEnrichment``.

    The adapter returns a ``ContractEnrichmentResult`` whose
    ``summary_markdown`` is parsed into structured issues and
    recommendations. Quality and maintainability scores are derived
    from issue density relative to file size.

    Raises:
        Any exception from the adapter — caller is responsible for
        falling back to heuristic scoring.
    """
    start = time.monotonic()
    prompt = (
        f"Analyze this {language} source file ({source_path or '<unknown>'}) "
        f"for quality issues, anti-patterns, and actionable recommendations. "
        f"Operation: {operation_type.value}."
    )
    result = await adapter.enrich(prompt=prompt, context=content)

    summary_markdown: str = getattr(result, "summary_markdown", "") or ""
    model_used: str = getattr(result, "model_used", "unknown")
    latency_ms: float = float(getattr(result, "latency_ms", 0.0))

    issues, recommendations = _extract_findings(summary_markdown)

    total_lines = max(1, len(content.splitlines()))
    issue_density = len(issues) / total_lines
    quality_score = max(0.0, min(1.0, 1.0 - issue_density * 5.0))
    # Complexity proxied from nesting depth (same as heuristic).
    max_indent = 0
    for line in content.splitlines():
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if language == "python":
                indent = indent // 4
            max_indent = max(max_indent, indent)
    complexity_score = max(0.0, min(1.0, 1.0 - (max_indent / 10.0)))

    processing_time_ms = (time.monotonic() - start) * 1000

    return ModelCodeAnalysisCompletedPayload(
        quality_score=round(quality_score, 3),
        issues_count=len(issues),
        recommendations_count=len(recommendations),
        processing_time_ms=round(processing_time_ms, 2),
        operation_type=operation_type,
        complexity_score=round(complexity_score, 3),
        maintainability_score=round((quality_score + complexity_score) / 2, 3),
        results_summary={
            "issues": issues[:20],
            "recommendations": recommendations[:10],
            "total_lines": total_lines,
            "max_nesting_depth": max_indent,
            "summary_markdown": summary_markdown,
            "model_used": model_used,
            "llm_latency_ms": latency_ms,
            "analysis_source": "llm",
        },
    )


def _build_pattern_discovered_events(
    *,
    issues: list[str],
    recommendations: list[str],
    source_path: str,
    language: str,
    correlation_id: UUID,
    session_id: UUID,
) -> list[dict[str, object]]:
    """Convert LLM findings to pattern.discovered event payloads.

    Each finding becomes a single event feeding the pattern extraction
    pipeline. ``pattern_type='code_analysis_pattern'`` is recorded in
    metadata so downstream consumers can classify the source.
    """
    now = datetime.now(UTC)
    events: list[dict[str, object]] = []

    def _make(finding: str, kind: str) -> dict[str, object]:
        signature = f"{kind}:{language}:{finding}"[:500]
        signature_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        return {
            "event_type": "PatternDiscovered",
            "discovery_id": str(uuid4()),
            "pattern_signature": signature,
            "signature_hash": signature_hash,
            "domain": "code_analysis",
            "confidence": _LLM_FINDING_CONFIDENCE,
            "source_session_id": str(session_id),
            "source_system": _SOURCE_SYSTEM,
            "source_agent": "adapter_code_analysis_enrichment",
            "correlation_id": str(correlation_id),
            "discovered_at": now.isoformat(),
            "metadata": {
                "pattern_type": _PATTERN_TYPE_CODE_ANALYSIS,
                "finding_kind": kind,
                "language": language,
                "source_path": source_path,
                "finding_text": finding,
            },
        }

    for issue in issues:
        if issue:
            events.append(_make(issue, "issue"))
    for rec in recommendations:
        if rec:
            events.append(_make(rec, "recommendation"))
    return events


# =============================================================================
# Heuristic Quality Scoring
# =============================================================================


def _heuristic_quality_score(
    content: str,
    language: str,
    operation_type: EnumAnalysisOperationType,
) -> ModelCodeAnalysisCompletedPayload:
    """Run heuristic quality scoring on source code content.

    This is a baseline implementation that checks for common code quality
    signals. Task 7 (OMN-6967) will upgrade this to LLM-powered analysis.

    Returns:
        ModelCodeAnalysisCompletedPayload with quality metrics.
    """
    start = time.monotonic()
    lines = content.splitlines()
    total_lines = len(lines)

    issues: list[str] = []
    recommendations: list[str] = []

    # Check for common issues
    if total_lines == 0:
        issues.append("Empty file")

    long_lines = sum(1 for line in lines if len(line) > 120)
    if long_lines > 0:
        issues.append(f"{long_lines} lines exceed 120 characters")

    # Check for common anti-patterns
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("# TODO") or stripped.startswith("# FIXME"):
            issues.append(f"Line {i}: unresolved {stripped.split()[1]}")
        if "import *" in stripped:
            issues.append(f"Line {i}: wildcard import")
        if "except:" in stripped and "except Exception" not in stripped:
            issues.append(f"Line {i}: bare except clause")
        if "print(" in stripped and language == "python":
            recommendations.append(f"Line {i}: consider using logging instead of print")

    # Calculate quality score
    issue_penalty = min(len(issues) * 0.1, 0.5)
    line_quality = 1.0 - (long_lines / max(total_lines, 1)) * 0.3
    quality_score = max(0.0, min(1.0, line_quality - issue_penalty))

    # Complexity heuristic: count nesting depth
    max_indent = 0
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if language == "python":
                indent = indent // 4
            max_indent = max(max_indent, indent)

    complexity_score = max(0.0, min(1.0, 1.0 - (max_indent / 10.0)))

    processing_time_ms = (time.monotonic() - start) * 1000

    return ModelCodeAnalysisCompletedPayload(
        quality_score=round(quality_score, 3),
        issues_count=len(issues),
        recommendations_count=len(recommendations),
        processing_time_ms=round(processing_time_ms, 2),
        operation_type=operation_type,
        complexity_score=round(complexity_score, 3),
        maintainability_score=round((quality_score + complexity_score) / 2, 3),
        results_summary={
            "issues": issues[:20],
            "recommendations": recommendations[:10],
            "total_lines": total_lines,
            "max_nesting_depth": max_indent,
        },
    )


# =============================================================================
# Dispatch Handler Factory
# =============================================================================


def create_code_analysis_dispatch_handler(
    *,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    llm_adapter: ProtocolCodeAnalysisLLM | None = None,
    publish_topic_completed: str | None = None,
    publish_topic_failed: str | None = None,
    publish_topic_pattern_discovered: str | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch handler for code-analysis command events.

    Args:
        kafka_producer: Optional Kafka publisher for response events.
        llm_adapter: Optional LLM adapter (``AdapterCodeAnalysisEnrichment``
            from omnibase_infra). When provided, the handler uses the adapter
            for semantic analysis and falls back to heuristic scoring on any
            failure. When ``None``, the handler is heuristic-only.
        publish_topic_completed: Topic for completed events.
        publish_topic_failed: Topic for failed events.
        publish_topic_pattern_discovered: Topic for pattern.discovered events
            emitted from LLM findings. Defaults to
            ``onex.evt.pattern.discovered.v1``.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """
    _topic_completed = publish_topic_completed or TOPIC_CODE_ANALYSIS_COMPLETED
    _topic_failed = publish_topic_failed or TOPIC_CODE_ANALYSIS_FAILED
    _topic_pattern_discovered = (
        publish_topic_pattern_discovered or TOPIC_PATTERN_DISCOVERED
    )

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> code analysis -> completed/failed."""
        raw_ctx_id = getattr(context, "correlation_id", None)
        if isinstance(raw_ctx_id, UUID):
            ctx_correlation_id = raw_ctx_id
        elif raw_ctx_id is not None:
            try:
                ctx_correlation_id = UUID(str(raw_ctx_id))
            except (ValueError, AttributeError):
                ctx_correlation_id = uuid4()
        else:
            ctx_correlation_id = uuid4()

        payload = envelope.payload
        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for code-analysis (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Parse request
        try:
            request = ModelCodeAnalysisRequestPayload(**payload)
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.warning(
                "Failed to parse code-analysis request: %s (correlation_id=%s)",
                sanitized,
                ctx_correlation_id,
            )
            # Publish failure event
            failed = ModelCodeAnalysisFailedPayload(
                correlation_id=ctx_correlation_id,
                error_code="INVALID_REQUEST",
                error_message=f"Payload parse error: {sanitized}",
                retry_allowed=False,
            )
            await _publish_event(
                kafka_producer, _topic_failed, failed, ctx_correlation_id
            )
            return "error:invalid_request"

        # Use request correlation_id if provided
        correlation_id = request.correlation_id or ctx_correlation_id
        safe_path = get_log_sanitizer().sanitize(request.source_path or "<no_path>")

        logger.info(
            "Processing code-analysis command "
            "(source_path=%s, operation=%s, language=%s, correlation_id=%s)",
            safe_path,
            request.operation_type.value,
            request.language,
            correlation_id,
        )

        try:
            analysis_source = "heuristic"
            result: ModelCodeAnalysisCompletedPayload | None = None
            if llm_adapter is not None:
                try:
                    result = await _llm_quality_score(
                        llm_adapter,
                        request.content,
                        request.language,
                        request.operation_type,
                        request.source_path or "",
                    )
                    analysis_source = "llm"
                except Exception:
                    # Graceful degradation — log and fall through to heuristic.
                    logger.warning(
                        "LLM code analysis failed; falling back to heuristic "
                        "(source_path=%s, correlation_id=%s)",
                        safe_path,
                        correlation_id,
                        exc_info=True,
                    )
                    result = None

            if result is None:
                result = _heuristic_quality_score(
                    request.content,
                    request.language,
                    request.operation_type,
                )

            # Attach context from request
            completed = result.model_copy(
                update={
                    "correlation_id": correlation_id,
                    "source_path": request.source_path or "",
                }
            )

            await _publish_event(
                kafka_producer, _topic_completed, completed, correlation_id
            )

            # Feed actionable LLM findings into pattern extraction.
            if analysis_source == "llm" and kafka_producer is not None:
                raw_issues = completed.results_summary.get("issues", [])
                raw_recs = completed.results_summary.get("recommendations", [])
                issues: list[str] = (
                    [str(i) for i in raw_issues if isinstance(i, str)]
                    if isinstance(raw_issues, list)
                    else []
                )
                recommendations: list[str] = (
                    [str(r) for r in raw_recs if isinstance(r, str)]
                    if isinstance(raw_recs, list)
                    else []
                )
                if issues or recommendations:
                    events = _build_pattern_discovered_events(
                        issues=issues,
                        recommendations=recommendations,
                        source_path=request.source_path or "",
                        language=request.language,
                        correlation_id=correlation_id,
                        session_id=correlation_id,
                    )
                    for evt in events:
                        try:
                            await kafka_producer.publish(
                                topic=_topic_pattern_discovered,
                                key=str(evt["discovery_id"]),
                                value=evt,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to publish pattern.discovered "
                                "(topic=%s, correlation_id=%s)",
                                _topic_pattern_discovered,
                                correlation_id,
                                exc_info=True,
                            )

            logger.info(
                "Code analysis completed "
                "(source_path=%s, source=%s, quality=%.3f, issues=%d, "
                "processing_ms=%.1f, correlation_id=%s)",
                safe_path,
                analysis_source,
                completed.quality_score,
                completed.issues_count,
                completed.processing_time_ms,
                correlation_id,
            )
            return "ok"

        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.exception(
                "Code analysis failed (source_path=%s, correlation_id=%s)",
                safe_path,
                correlation_id,
            )
            failed = ModelCodeAnalysisFailedPayload(
                correlation_id=correlation_id,
                error_code="ANALYSIS_ERROR",
                error_message=sanitized,
                operation_type=request.operation_type,
                source_path=request.source_path or "",
                retry_allowed=True,
            )
            await _publish_event(kafka_producer, _topic_failed, failed, correlation_id)
            return "error:analysis_failed"

    return _handle


async def _publish_event(
    producer: ProtocolKafkaPublisher | None,
    topic: str,
    payload: ModelCodeAnalysisCompletedPayload | ModelCodeAnalysisFailedPayload,
    correlation_id: UUID,
) -> None:
    """Publish a code analysis response event to Kafka."""
    if producer is None:
        logger.debug(
            "No Kafka producer — skipping publish to %s (correlation_id=%s)",
            topic,
            correlation_id,
        )
        return

    try:
        event_data = payload.model_dump(mode="json")
        await producer.publish(
            topic=topic,
            key=str(correlation_id),
            value=event_data,
        )
    except Exception:
        logger.exception(
            "Failed to publish to %s (correlation_id=%s)",
            topic,
            correlation_id,
        )
