# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Dispatch handler for pattern learning commands.

This module provides a bridge handler that processes PatternLearningRequested
commands emitted by handle_stop() in the Claude hook event handler. It:

1. Parses the session_id and correlation_id from the command envelope
2. Queries PostgreSQL (READ-ONLY) for session activity data
3. Runs the existing pure-compute extract_all_patterns() function
4. Transforms extracted insights into pattern-learned.v1 event payloads
5. Publishes pattern events to Kafka in batches for downstream storage

CRITICAL INVARIANT: This handler is DB READ-ONLY. All DB mutations happen
through ONEX DB Effect Nodes. This handler reads session data from PostgreSQL
but publishes pattern candidates to Kafka for downstream effect nodes to persist.

Architecture Decisions:
    - Split file: NOT in dispatch_handlers.py (already large)
    - Session data: DB first (query agent_actions/workflow_steps), synthetic fallback
    - Extraction volume: max_patterns_per_session=50, publish_batch_size=25
    - Domain taxonomy: domain_id='general' + insight_type in metadata
    - Kafka graceful degradation: no producer => extraction runs, no events emitted

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
    - OMN-2222: Wire intelligence pipeline end-to-end
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from asyncpg import InterfaceError as AsyncpgInterfaceError
from asyncpg import InternalClientError as AsyncpgInternalClientError
from asyncpg import PostgresConnectionError
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.exceptions import (
    PatternExtractionError,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_extract_all_patterns import (
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelSessionSnapshot,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_PATTERNS_PER_SESSION: int = 50
"""Hard cap on extracted patterns per session. Top-K by confidence if exceeded."""

PUBLISH_BATCH_SIZE: int = 25
"""Maximum patterns to publish per Kafka batch.

Note: Events are published one at a time within each batch (no transport-level
batch optimization). The batch grouping provides log grouping (batch_start/end
in warnings) and error isolation -- a failed event does not abort the remaining
events in the batch or subsequent batches."""

_SESSION_QUERY_TIMEOUT_SECONDS: float = 2.0
"""Hard timeout for session enrichment DB queries."""

_TAXONOMY_VERSION: str = "1.0.0"
"""Domain taxonomy version included in pattern metadata."""

_DEFAULT_DOMAIN_ID: str = "general"
"""Default domain_id for all patterns. Insight type stored in metadata for
later migration to a richer taxonomy."""

# =============================================================================
# SQL (READ-ONLY) for session enrichment
# =============================================================================
# These queries read from agent_actions and workflow_steps to build a
# ModelSessionSnapshot from the session's DB trail. They are bounded
# (LIMIT 500) and wrapped with asyncio.wait_for(_SESSION_QUERY_TIMEOUT_SECONDS)
# to prevent runaway queries.

_SQL_SESSION_ACTIONS = """\
SELECT
    action_type,
    tool_name,
    file_path,
    status,
    error_message,
    created_at
FROM agent_actions
WHERE session_id = $1
ORDER BY created_at ASC
LIMIT 500;
"""

_SQL_SESSION_WORKFLOW_STEPS = """\
SELECT
    step_name,
    status,
    error_message,
    started_at,
    completed_at
FROM workflow_steps
WHERE session_id = $1
ORDER BY started_at ASC
LIMIT 200;
"""


# =============================================================================
# Factory Function
# =============================================================================


def create_pattern_learning_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str,
    correlation_id: UUID | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch engine handler for pattern learning commands.

    Returns an async handler function compatible with MessageDispatchEngine's
    handler signature. The handler:
    1. Extracts session_id from the PatternLearningRequested payload
    2. Fetches session data from PostgreSQL (READ-ONLY, with timeout/fallback)
    3. Runs extract_all_patterns() (pure compute)
    4. Transforms insights into pattern-learned event payloads
    5. Publishes pattern events to Kafka in batches

    Args:
        repository: REQUIRED database repository for reading session data.
            Used READ-ONLY -- no mutations.
        kafka_producer: Optional Kafka producer (graceful degradation if absent).
        publish_topic: Full topic for pattern-learned events.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> pattern extraction -> Kafka publish."""
        start_time = time.perf_counter()

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for pattern-learning command "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Extract required session_id from PatternLearningRequested command
        raw_session_id = payload.get("session_id")
        if raw_session_id is None:
            msg = (
                f"Pattern learning payload missing required field 'session_id' "
                f"(correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        session_id = str(raw_session_id)

        # Override correlation_id from payload if present
        raw_payload_correlation = payload.get("correlation_id")
        if raw_payload_correlation is not None:
            try:
                ctx_correlation_id = UUID(str(raw_payload_correlation))
            except ValueError:
                logger.debug(
                    "Payload correlation_id is not a valid UUID, "
                    "using fallback (raw_value=%r, fallback_correlation_id=%s)",
                    raw_payload_correlation,
                    ctx_correlation_id,
                )

        logger.info(
            "Dispatching pattern-learning command via MessageDispatchEngine "
            "(session_id=%s, correlation_id=%s)",
            session_id,
            ctx_correlation_id,
        )

        # Step 1: Fetch session snapshot (DB READ-ONLY, with fallback)
        session_snapshot = await _fetch_session_snapshot(
            repository=repository,
            session_id=session_id,
            correlation_id=ctx_correlation_id,
        )

        # Step 2: Run pattern extraction (pure compute)
        extraction_input = ModelPatternExtractionInput(
            session_snapshots=(session_snapshot,),
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_distinct_sessions=1,
                min_confidence=0.5,
                max_insights_per_type=MAX_PATTERNS_PER_SESSION,
            ),
            existing_insights=(),
            correlation_id=str(ctx_correlation_id),
        )

        try:
            extraction_output = extract_all_patterns(extraction_input)
        except PatternExtractionError as exc:
            # PatternExtractionComputeError (and other PatternExtractionError
            # subclasses) indicate deterministic compute failures that will
            # never succeed on retry. Catch here to prevent the dispatch
            # engine from nacking and retrying the message infinitely.
            logger.warning(
                "Pattern extraction raised %s, returning early "
                "(session_id=%s, error=%s, correlation_id=%s)",
                type(exc).__name__,
                session_id,
                exc,
                ctx_correlation_id,
            )
            return ""

        if not extraction_output.success:
            logger.warning(
                "Pattern extraction returned success=False "
                "(session_id=%s, status=%s, message=%s, correlation_id=%s)",
                session_id,
                extraction_output.metadata.status,
                extraction_output.metadata.message,
                ctx_correlation_id,
            )
            return ""

        # Collect all insights (new + updated)
        all_insights: list[ModelCodebaseInsight] = [
            *extraction_output.new_insights,
            *extraction_output.updated_insights,
        ]

        # Step 3: Apply top-K cap by confidence if exceeds max
        truncated = False
        original_count = len(all_insights)
        if original_count > MAX_PATTERNS_PER_SESSION:
            all_insights = sorted(all_insights, key=lambda x: -x.confidence)[
                :MAX_PATTERNS_PER_SESSION
            ]
            truncated = True
            logger.info(
                "Truncated pattern extraction results from %d to %d "
                "(session_id=%s, correlation_id=%s)",
                original_count,
                MAX_PATTERNS_PER_SESSION,
                session_id,
                ctx_correlation_id,
            )

        # Step 4: Transform insights to pattern-learned event payloads
        # Use the deterministic session_id (uuid5-converted) from the snapshot
        # so that source_session_ids are consistent with evidence_session_ids
        # (which are already uuid5-converted by the extraction pipeline).
        pattern_events = _transform_insights_to_pattern_events(
            insights=all_insights,
            session_id=session_snapshot.session_id,
            correlation_id=ctx_correlation_id,
        )

        # Step 5: Batch publish to Kafka
        published_count = 0
        if kafka_producer is not None and pattern_events:
            published_count = await _batch_publish_patterns(
                producer=kafka_producer,
                topic=publish_topic,
                events=pattern_events,
                correlation_id=ctx_correlation_id,
            )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Pattern learning command processed via dispatch engine "
            "(session_id=%s, insights_extracted=%d, patterns_published=%d, "
            "truncated=%s, processing_time_ms=%.1f, correlation_id=%s)",
            session_id,
            len(all_insights),
            published_count,
            truncated,
            processing_time_ms,
            ctx_correlation_id,
        )

        return ""

    return _handle


# =============================================================================
# Session Enrichment (DB READ-ONLY)
# =============================================================================


async def _fetch_session_snapshot(
    *,
    repository: ProtocolPatternRepository,
    session_id: str,
    correlation_id: UUID,
) -> ModelSessionSnapshot:
    """Fetch session data from PostgreSQL to build a ModelSessionSnapshot.

    Queries agent_actions and workflow_steps tables for the given session_id.
    Returns a synthetic minimal snapshot on any failure (timeout, connection
    error, empty results).

    This function is DB READ-ONLY. No mutations.

    Args:
        repository: Database repository for reading session data.
        session_id: Session ID to query.
        correlation_id: Correlation ID for tracing.

    Returns:
        ModelSessionSnapshot built from DB data, or a minimal synthetic
        snapshot if DB query fails or returns no data.
    """
    now = datetime.now(UTC)
    # Convert string session_id to a deterministic UUID so downstream
    # source_session_ids are compatible with the UUID[] column in
    # learned_patterns. Same string always produces the same UUID.
    deterministic_session_id = str(uuid5(NAMESPACE_URL, session_id))

    try:
        # Query agent_actions for the session (bounded by asyncio timeout)
        try:
            actions = await asyncio.wait_for(
                repository.fetch(_SQL_SESSION_ACTIONS, session_id),
                timeout=_SESSION_QUERY_TIMEOUT_SECONDS,
            )
        except (
            TimeoutError,
            OSError,
            PostgresConnectionError,
            AsyncpgInterfaceError,
            AsyncpgInternalClientError,
        ):
            logger.warning(
                "Session actions query failed (timeout or connection error), "
                "using synthetic snapshot "
                "(session_id=%s, correlation_id=%s)",
                session_id,
                correlation_id,
            )
            return _create_synthetic_snapshot(session_id=deterministic_session_id, now=now)

        if not actions:
            logger.debug(
                "No agent_actions found for session, using synthetic snapshot "
                "(session_id=%s, correlation_id=%s)",
                session_id,
                correlation_id,
            )
            return _create_synthetic_snapshot(session_id=deterministic_session_id, now=now)

        # Extract files accessed and modified
        files_accessed: list[str] = []
        files_modified: list[str] = []
        tools_used: list[str] = []
        errors_encountered: list[str] = []
        earliest_at: datetime | None = None
        latest_at: datetime | None = None

        for action in actions:
            # Extract timestamps for session bounds
            action_time = action.get("created_at")
            if action_time is not None:
                if isinstance(action_time, datetime):
                    if earliest_at is None or action_time < earliest_at:
                        earliest_at = action_time
                    if latest_at is None or action_time > latest_at:
                        latest_at = action_time

            # Extract file paths
            file_path = action.get("file_path")
            if file_path and isinstance(file_path, str):
                files_accessed.append(file_path)
                action_type = action.get("action_type", "")
                if isinstance(action_type, str) and action_type in (
                    "write",
                    "edit",
                    "create",
                ):
                    files_modified.append(file_path)

            # Extract tool usage
            tool_name = action.get("tool_name")
            if tool_name and isinstance(tool_name, str):
                tools_used.append(tool_name)

            # Extract errors
            status = action.get("status", "")
            error_msg = action.get("error_message")
            if isinstance(status, str) and status == "error" and error_msg:
                errors_encountered.append(str(error_msg)[:200])

        # Determine outcome from workflow_steps (bounded by asyncio timeout)
        outcome = "unknown"
        try:
            steps = await asyncio.wait_for(
                repository.fetch(_SQL_SESSION_WORKFLOW_STEPS, session_id),
                timeout=_SESSION_QUERY_TIMEOUT_SECONDS,
            )
            if steps:
                last_step = steps[-1]
                step_status = last_step.get("status", "")
                if isinstance(step_status, str):
                    if step_status in ("completed", "success"):
                        outcome = "success"
                    elif step_status in ("failed", "error"):
                        outcome = "failure"
        except (
            TimeoutError,
            OSError,
            PostgresConnectionError,
            AsyncpgInterfaceError,
            AsyncpgInternalClientError,
        ):
            logger.debug(
                "Failed to query workflow_steps (timeout or connection error), "
                "using default outcome (session_id=%s, correlation_id=%s)",
                session_id,
                correlation_id,
            )

        # Deduplicate lists preserving order
        files_accessed = list(dict.fromkeys(files_accessed))
        files_modified = list(dict.fromkeys(files_modified))
        tools_used = list(dict.fromkeys(tools_used))

        return ModelSessionSnapshot(
            session_id=deterministic_session_id,
            working_directory="/unknown",
            started_at=earliest_at or now,
            ended_at=latest_at,
            files_accessed=tuple(files_accessed),
            files_modified=tuple(files_modified),
            tools_used=tuple(tools_used),
            errors_encountered=tuple(errors_encountered),
            outcome=outcome,
            metadata={"source": "postgresql", "action_count": len(actions)},
        )

    except Exception as e:
        logger.warning(
            "Failed to fetch session data from DB, using synthetic snapshot "
            "(session_id=%s, error=%s, correlation_id=%s)",
            session_id,
            type(e).__name__,
            correlation_id,
        )
        return _create_synthetic_snapshot(session_id=deterministic_session_id, now=now)


def _create_synthetic_snapshot(
    *,
    session_id: str,
    now: datetime,
) -> ModelSessionSnapshot:
    """Create a minimal synthetic snapshot when DB data is unavailable.

    Args:
        session_id: Session ID for the snapshot.
        now: Current UTC datetime.

    Returns:
        Minimal ModelSessionSnapshot with synthetic data.
    """
    return ModelSessionSnapshot(
        session_id=session_id,
        working_directory="/unknown",
        started_at=now,
        ended_at=now,
        files_accessed=(),
        files_modified=(),
        tools_used=(),
        errors_encountered=(),
        outcome="unknown",
        metadata={"source": "synthetic", "reason": "db_unavailable"},
    )


# =============================================================================
# Insight-to-Event Transformer
# =============================================================================


def _transform_insights_to_pattern_events(
    *,
    insights: Sequence[ModelCodebaseInsight],
    session_id: str,
    correlation_id: UUID,
) -> list[dict[str, object]]:
    """Transform ModelCodebaseInsight objects into pattern-learned.v1 event payloads.

    Produces payloads compatible with the pattern storage dispatch handler
    (create_pattern_storage_dispatch_handler) which expects:
    - pattern_id: UUID
    - signature: deterministic string from insight description + type
    - signature_hash: SHA256 hex digest of signature (NEVER empty)
    - domain_id: 'general' (with insight_type in metadata)
    - confidence: clamped to [0.5, 1.0]
    - version: 1
    - source_session_ids: from evidence_session_ids

    Args:
        insights: Extracted codebase insights to transform.
        session_id: Session ID that triggered extraction.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of pattern-learned event payload dicts.
    """
    events: list[dict[str, object]] = []
    now_iso = datetime.now(UTC).isoformat()

    for insight in insights:
        pattern_id = uuid4()

        # Build deterministic signature from insight type + description
        signature = f"{insight.insight_type.value}::{insight.description}"

        # SHA256 hash of signature -- NEVER empty
        signature_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()

        # Clamp confidence to [0.5, 1.0] for storage handler compatibility
        confidence = max(0.5, min(1.0, insight.confidence))

        # Build source_session_ids: evidence_session_ids + current session.
        # Both evidence_session_ids and session_id are already deterministic
        # UUID strings (uuid5-converted by _fetch_session_snapshot). No further
        # conversion needed -- just collect them directly.
        source_session_ids: list[str] = list(insight.evidence_session_ids)
        if session_id not in source_session_ids:
            source_session_ids.append(session_id)

        # Build metadata with insight_type for future taxonomy migration
        event_metadata: dict[str, object] = {
            "insight_type": insight.insight_type.value,
            "taxonomy_version": _TAXONOMY_VERSION,
            "insight_id": insight.insight_id,
            "occurrence_count": insight.occurrence_count,
        }

        # Include evidence files if present
        if insight.evidence_files:
            event_metadata["evidence_files"] = list(insight.evidence_files)

        # Include working directory if present
        if insight.working_directory:
            event_metadata["working_directory"] = insight.working_directory

        event_payload: dict[str, object] = {
            "event_type": "PatternLearned",
            "pattern_id": str(pattern_id),
            "signature": signature,
            "signature_hash": signature_hash,
            "domain_id": _DEFAULT_DOMAIN_ID,
            "domain_version": _TAXONOMY_VERSION,
            "confidence": confidence,
            "version": 1,
            "source_session_ids": source_session_ids,
            "correlation_id": str(correlation_id),
            "timestamp": now_iso,
            "metadata": event_metadata,
        }

        events.append(event_payload)

    return events


# =============================================================================
# Batch Publishing
# =============================================================================


async def _batch_publish_patterns(
    *,
    producer: ProtocolKafkaPublisher,
    topic: str,
    events: Sequence[dict[str, object]],
    correlation_id: UUID,
) -> int:
    """Publish pattern events to Kafka in batches.

    Publishes up to PUBLISH_BATCH_SIZE events per batch. Continues
    publishing remaining batches even if one batch fails (best-effort).

    Args:
        producer: Kafka publisher.
        topic: Target Kafka topic.
        events: Pattern event payloads to publish.
        correlation_id: Correlation ID for tracing.

    Returns:
        Number of events successfully published.
    """
    published = 0
    total = len(events)

    for batch_start in range(0, total, PUBLISH_BATCH_SIZE):
        batch_end = min(batch_start + PUBLISH_BATCH_SIZE, total)
        batch = events[batch_start:batch_end]

        for event in batch:
            try:
                # Use pattern_id as Kafka key for partitioning
                key = str(event.get("pattern_id", ""))
                # Ensure correlation_id is threaded through
                event_with_correlation: dict[str, object] = {
                    **event,
                    "correlation_id": str(correlation_id),
                }
                await producer.publish(
                    topic=topic,
                    key=key,
                    value=event_with_correlation,
                )
                published += 1
            except Exception:
                logger.warning(
                    "Failed to publish pattern event to Kafka "
                    "(pattern_id=%s, batch=%d-%d, correlation_id=%s)",
                    event.get("pattern_id"),
                    batch_start,
                    batch_end,
                    correlation_id,
                    exc_info=True,
                )
                # Continue with remaining events (best-effort)

    if published < total:
        logger.warning(
            "Partial pattern publish: %d/%d events published (correlation_id=%s)",
            published,
            total,
            correlation_id,
        )

    return published


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PATTERNS_PER_SESSION",
    "PUBLISH_BATCH_SIZE",
    "create_pattern_learning_dispatch_handler",
]
