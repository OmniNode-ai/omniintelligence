"""Adapter handler bridging omnibase_core pattern extraction models to local extractors.

This handler accepts the canonical ``ModelPatternExtractionInput`` /
``ModelPatternExtractionOutput`` from ``omnibase_core.models.intelligence`` and
delegates actual extraction to the existing local handlers.

Flow:
    1. Validate core input (session_ids or raw_events required)
    2. Convert raw_events -> local ModelSessionSnapshot(s)
    3. Filter by kinds / time window
    4. Run existing extractor pipeline
    5. Convert local ModelCodebaseInsight -> core ModelPatternRecord
    6. Build core ModelPatternExtractionOutput (patterns_by_kind)

Ticket: OMN-1594
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from omnibase_core.enums import EnumPatternKind
from omnibase_core.models.intelligence.model_pattern_error import ModelPatternError
from omnibase_core.models.intelligence.model_pattern_extraction_input import (
    ModelPatternExtractionInput as CoreInput,
)
from omnibase_core.models.intelligence.model_pattern_extraction_output import (
    ModelPatternExtractionOutput as CoreOutput,
)
from omnibase_core.models.intelligence.model_pattern_record import ModelPatternRecord
from omnibase_core.models.intelligence.model_pattern_warning import ModelPatternWarning
from omnibase_core.types.type_json import JsonType

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_architecture_patterns import (
    extract_architecture_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_converters import (
    convert_architecture_patterns,
    convert_error_patterns,
    convert_file_patterns,
    convert_tool_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_error_patterns import (
    extract_error_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_file_patterns import (
    extract_file_access_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
    extract_tool_failure_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_tool_patterns import (
    extract_tool_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.enum_insight_type import (
    EnumInsightType,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_input import (
    ModelSessionSnapshot,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_input import (
    ModelToolExecution as LocalToolExecution,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Insight type -> Pattern kind mapping
# ---------------------------------------------------------------------------
_INSIGHT_TO_KIND: dict[EnumInsightType, EnumPatternKind] = {
    EnumInsightType.FILE_ACCESS_PATTERN: EnumPatternKind.FILE_ACCESS,
    EnumInsightType.ENTRY_POINT_PATTERN: EnumPatternKind.FILE_ACCESS,
    EnumInsightType.MODIFICATION_CLUSTER: EnumPatternKind.FILE_ACCESS,
    EnumInsightType.ERROR_PATTERN: EnumPatternKind.ERROR,
    EnumInsightType.ARCHITECTURE_PATTERN: EnumPatternKind.ARCHITECTURE,
    EnumInsightType.TOOL_USAGE_PATTERN: EnumPatternKind.TOOL_USAGE,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def handle_pattern_extraction_core(input_data: CoreInput) -> CoreOutput:
    """Extract patterns using core models from omnibase_core.

    This handler bridges the canonical core input/output models to the existing
    local extraction pipeline.  It supports both ``session_ids`` (stub -- returns
    a warning) and ``raw_events`` (converts to local session snapshots).

    Args:
        input_data: Core ``ModelPatternExtractionInput`` with session_ids
            and/or raw_events.

    Returns:
        Core ``ModelPatternExtractionOutput`` with patterns_by_kind.
    """
    start_time = time.perf_counter()
    warnings: list[ModelPatternWarning] = []
    errors: list[ModelPatternError] = []

    try:
        # ------------------------------------------------------------------
        # 1. Build local session snapshots from raw_events
        # ------------------------------------------------------------------
        sessions: list[ModelSessionSnapshot] = []

        if input_data.raw_events:
            converted = _raw_events_to_sessions(input_data.raw_events)
            sessions.extend(converted)

        if input_data.session_ids:
            # session_ids require a data store lookup -- not available in pure
            # compute.  Record a warning and proceed with raw_events only.
            warnings.append(
                ModelPatternWarning(
                    code="SESSION_IDS_UNSUPPORTED",
                    message=(
                        "session_ids input mode requires a data store and is not "
                        "supported in the pure compute node.  Provide raw_events "
                        "for direct extraction."
                    ),
                    context={"session_ids_count": len(input_data.session_ids)},
                )
            )

        if not sessions:
            return _error_output(
                correlation_id=input_data.correlation_id,
                source_snapshot_id=input_data.source_snapshot_id,
                processing_time_ms=_elapsed_ms(start_time),
                errors=[
                    ModelPatternError(
                        code="NO_DATA",
                        message="No session data available for extraction",
                        recoverable=False,
                    ),
                ],
                warnings=warnings,
            )

        # ------------------------------------------------------------------
        # 2. Apply time window filter
        # ------------------------------------------------------------------
        sessions = _apply_time_window(
            sessions,
            input_data.time_window_start,
            input_data.time_window_end,
        )

        if not sessions:
            return _error_output(
                correlation_id=input_data.correlation_id,
                source_snapshot_id=input_data.source_snapshot_id,
                processing_time_ms=_elapsed_ms(start_time),
                errors=[
                    ModelPatternError(
                        code="NO_DATA_AFTER_FILTER",
                        message="No sessions remain after time window filter",
                        recoverable=False,
                    ),
                ],
                warnings=warnings,
            )

        # ------------------------------------------------------------------
        # 3. Determine which kinds to extract
        # ------------------------------------------------------------------
        kinds_to_extract = (
            set(input_data.kinds) if input_data.kinds else set(EnumPatternKind)
        )

        # ------------------------------------------------------------------
        # 4. Run extractors
        # ------------------------------------------------------------------
        min_occ = input_data.min_occurrences
        min_conf = input_data.min_confidence
        # Fixed uniform params for extractor signature
        min_distinct = 2
        max_results = 20

        all_insights: list[ModelCodebaseInsight] = []
        ref_time = _derive_reference_time(sessions)

        if EnumPatternKind.FILE_ACCESS in kinds_to_extract:
            results = extract_file_access_patterns(
                sessions, min_occ, min_conf, min_distinct, max_results
            )
            all_insights.extend(convert_file_patterns(results, ref_time))

        if EnumPatternKind.ERROR in kinds_to_extract:
            results_err = extract_error_patterns(
                sessions, min_occ, min_conf, min_distinct, max_results
            )
            all_insights.extend(convert_error_patterns(results_err, ref_time))

        if EnumPatternKind.ARCHITECTURE in kinds_to_extract:
            results_arch = extract_architecture_patterns(
                sessions, min_occ, min_conf, min_distinct, max_results
            )
            all_insights.extend(convert_architecture_patterns(results_arch, ref_time))

        if EnumPatternKind.TOOL_USAGE in kinds_to_extract:
            results_tool = extract_tool_patterns(
                sessions, min_occ, min_conf, min_distinct, max_results
            )
            all_insights.extend(convert_tool_patterns(results_tool, ref_time))

        tool_failure_insights: list[ModelCodebaseInsight] = []
        if EnumPatternKind.TOOL_FAILURE in kinds_to_extract:
            results_tf = extract_tool_failure_patterns(
                sessions, min_occ, min_conf, min_distinct, max_results
            )
            tool_failure_insights = convert_error_patterns(results_tf, ref_time)

        # ------------------------------------------------------------------
        # 5. Convert insights -> ModelPatternRecord, grouped by kind
        # ------------------------------------------------------------------
        patterns_by_kind = _insights_to_patterns_by_kind(all_insights)

        # Route tool-failure insights into the TOOL_FAILURE bucket explicitly
        if tool_failure_insights:
            tf_records = _insights_to_patterns_by_kind(
                tool_failure_insights,
                kind_override=EnumPatternKind.TOOL_FAILURE,
            )
            patterns_by_kind.setdefault(EnumPatternKind.TOOL_FAILURE, []).extend(
                tf_records.get(EnumPatternKind.TOOL_FAILURE, [])
            )

        # Ensure all kinds present (validator requires it)
        for kind in EnumPatternKind:
            patterns_by_kind.setdefault(kind, [])

        total = sum(len(v) for v in patterns_by_kind.values())
        deterministic = (
            input_data.raw_events is not None and len(input_data.session_ids) == 0
        )

        return CoreOutput(
            success=True,
            deterministic=deterministic,
            patterns_by_kind=patterns_by_kind,
            total_patterns_found=total,
            processing_time_ms=_elapsed_ms(start_time),
            sessions_analyzed=len(sessions),
            events_scanned=_count_events(sessions),
            warnings=warnings,
            errors=errors,
            correlation_id=input_data.correlation_id,
            source_snapshot_id=input_data.source_snapshot_id,
        )

    except Exception as e:
        logger.exception("Core pattern extraction failed: %s", e)
        return _error_output(
            correlation_id=input_data.correlation_id,
            source_snapshot_id=input_data.source_snapshot_id,
            processing_time_ms=_elapsed_ms(start_time),
            errors=[
                ModelPatternError(
                    code="EXTRACTION_FAILED",
                    message=f"Extraction failed: {e}",
                    recoverable=True,
                ),
            ],
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _raw_events_to_sessions(
    raw_events: list[JsonType],
) -> list[ModelSessionSnapshot]:
    """Convert raw JSON events into local ModelSessionSnapshot(s).

    Groups events by ``session_id`` field (falls back to a single synthetic
    session if no session_id is present).  Each event is expected to be a dict
    with tool execution fields.

    Args:
        raw_events: List of JSON-serializable event dicts.

    Returns:
        List of local ModelSessionSnapshot objects.
    """
    from datetime import UTC
    from datetime import datetime as dt_cls

    grouped: dict[str, list[dict[str, JsonType]]] = defaultdict(list)

    for event in raw_events:
        if not isinstance(event, dict):
            continue
        sid = str(event.get("session_id", "synthetic-session"))
        grouped[sid].append(event)

    sessions: list[ModelSessionSnapshot] = []
    now = dt_cls.now(UTC)

    for session_id, events in grouped.items():
        files_accessed: list[str] = []
        files_modified: list[str] = []
        tools_used: list[str] = []
        tool_executions: list[LocalToolExecution] = []
        errors_encountered: list[str] = []
        timestamps: list[dt_cls] = []
        outcome = "unknown"

        for ev in events:
            tool_name = ev.get("tool_name", "")
            if tool_name:
                tools_used.append(str(tool_name))

            file_path = ev.get("file_path")
            if file_path:
                files_accessed.append(str(file_path))

            success = ev.get("success", True)

            ts_raw = ev.get("timestamp")
            ts: dt_cls
            if isinstance(ts_raw, str):
                try:
                    ts = dt_cls.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = now
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
            elif isinstance(ts_raw, dt_cls):
                ts = ts_raw
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
            else:
                ts = now

            timestamps.append(ts)

            if tool_name:
                tool_executions.append(
                    LocalToolExecution(
                        tool_name=str(tool_name),
                        success=bool(success),
                        error_message=str(ev["error_message"])
                        if ev.get("error_message")
                        else None,
                        error_type=str(ev["error_type"])
                        if ev.get("error_type")
                        else None,
                        duration_ms=int(str(ev["duration_ms"]))
                        if ev.get("duration_ms") is not None
                        else None,
                        tool_parameters=ev.get("tool_parameters"),
                        timestamp=ts,
                    )
                )

            if not success:
                err_msg = ev.get("error_message")
                if err_msg:
                    errors_encountered.append(str(err_msg))
                if outcome != "failure":
                    outcome = "partial" if success else "failure"

        # Determine outcome from events
        all_success = all(ev.get("success", True) for ev in events)
        any_failure = any(not ev.get("success", True) for ev in events)
        if all_success:
            outcome = "success"
        elif any_failure and not all(not ev.get("success", True) for ev in events):
            outcome = "partial"
        elif any_failure:
            outcome = "failure"

        started_at = min(timestamps) if timestamps else now
        ended_at = max(timestamps) if timestamps else now

        sessions.append(
            ModelSessionSnapshot(
                session_id=session_id,
                working_directory=str(events[0].get("working_directory", "/unknown")),
                started_at=started_at,
                ended_at=ended_at,
                files_accessed=tuple(files_accessed),
                files_modified=tuple(files_modified),
                tools_used=tuple(tools_used),
                tool_executions=tuple(tool_executions),
                errors_encountered=tuple(errors_encountered),
                outcome=outcome,
            )
        )

    return sessions


def _apply_time_window(
    sessions: list[ModelSessionSnapshot],
    start: datetime | None,
    end: datetime | None,
) -> list[ModelSessionSnapshot]:
    """Filter sessions by time window bounds.

    Args:
        sessions: Sessions to filter.
        start: Inclusive start bound (None = no lower bound).
        end: Exclusive end bound (None = no upper bound).

    Returns:
        Filtered list of sessions.
    """
    if start is None and end is None:
        return sessions

    filtered: list[ModelSessionSnapshot] = []
    for s in sessions:
        session_time = s.ended_at or s.started_at
        if start is not None and session_time < start:
            continue
        if end is not None and session_time >= end:
            continue
        filtered.append(s)
    return filtered


def _derive_reference_time(sessions: Sequence[ModelSessionSnapshot]) -> datetime:
    """Derive reference time from sessions for insight timestamps.

    Args:
        sessions: Sessions to derive time from.

    Returns:
        Max ended_at or current UTC time.
    """
    from datetime import UTC

    ended = [s.ended_at for s in sessions if s.ended_at is not None]
    if ended:
        return max(ended)
    return datetime.now(UTC)


def _insights_to_patterns_by_kind(
    insights: list[ModelCodebaseInsight],
    *,
    kind_override: EnumPatternKind | None = None,
) -> dict[EnumPatternKind, list[ModelPatternRecord]]:
    """Convert local insights to core ModelPatternRecords grouped by kind.

    Args:
        insights: Local insight objects.
        kind_override: If provided, all insights are assigned this kind
            instead of using the ``_INSIGHT_TO_KIND`` mapping.

    Returns:
        Dict mapping EnumPatternKind to lists of ModelPatternRecord.
    """
    result: dict[EnumPatternKind, list[ModelPatternRecord]] = {}

    for insight in insights:
        kind = kind_override or _INSIGHT_TO_KIND.get(
            insight.insight_type, EnumPatternKind.FILE_ACCESS
        )

        record = ModelPatternRecord(
            pattern_id=_stable_uuid(insight.insight_id),
            kind=kind,
            confidence=insight.confidence,
            occurrences=insight.occurrence_count,
            description=insight.description,
            evidence=list(insight.evidence_files) + list(insight.evidence_session_ids),
            metadata={
                "insight_type": insight.insight_type.value,
                "working_directory": insight.working_directory or "",
            },
        )

        result.setdefault(kind, []).append(record)

    return result


def _stable_uuid(insight_id: str) -> UUID:
    """Convert an insight_id string to a UUID.

    If the string is already a valid UUID, parse it.  Otherwise generate
    a deterministic UUID5 from the string.

    Args:
        insight_id: String ID from insight.

    Returns:
        UUID object.
    """
    import uuid

    try:
        return UUID(insight_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_OID, insight_id)


def _count_events(sessions: Sequence[ModelSessionSnapshot]) -> int:
    """Count total tool executions across sessions.

    Args:
        sessions: Sessions to count events from.

    Returns:
        Total number of tool executions.
    """
    return sum(len(s.tool_executions) for s in sessions)


def _elapsed_ms(start: float) -> float:
    """Calculate elapsed milliseconds since start.

    Args:
        start: perf_counter start time.

    Returns:
        Elapsed milliseconds.
    """
    return (time.perf_counter() - start) * 1000


def _error_output(
    *,
    correlation_id: UUID | None,
    source_snapshot_id: UUID | None,
    processing_time_ms: float,
    errors: list[ModelPatternError],
    warnings: list[ModelPatternWarning] | None = None,
) -> CoreOutput:
    """Build a failed CoreOutput with stable shape.

    Args:
        correlation_id: Request correlation ID.
        source_snapshot_id: Snapshot ID for replay.
        processing_time_ms: Processing duration.
        errors: Structured errors.
        warnings: Structured warnings.

    Returns:
        CoreOutput with success=False and all kinds initialized to empty.
    """
    return CoreOutput(
        success=False,
        deterministic=False,
        patterns_by_kind={kind: [] for kind in EnumPatternKind},
        total_patterns_found=0,
        processing_time_ms=processing_time_ms,
        sessions_analyzed=0,
        events_scanned=0,
        warnings=warnings or [],
        errors=errors,
        correlation_id=correlation_id,
        source_snapshot_id=source_snapshot_id,
    )


__all__ = ["handle_pattern_extraction_core"]
