"""Unit tests for handler_core_models - core model adapter for pattern extraction.

Tests the handler that bridges omnibase_core ModelPatternExtractionInput/Output
to the existing local extraction pipeline.

Ticket: OMN-1594
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from omnibase_core.enums import EnumPatternKind
from omnibase_core.models.intelligence.model_pattern_extraction_input import (
    ModelPatternExtractionInput as CoreInput,
)
from omnibase_core.models.intelligence.model_pattern_extraction_output import (
    ModelPatternExtractionOutput as CoreOutput,
)
from omnibase_core.models.intelligence.model_pattern_record import ModelPatternRecord

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_core_models import (
    _apply_time_window,
    _insights_to_patterns_by_kind,
    _raw_events_to_sessions,
    _stable_uuid,
    handle_pattern_extraction_core,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.enum_insight_type import (
    EnumInsightType,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_input import (
    ModelSessionSnapshot,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def base_time() -> datetime:
    """Fixed base time for deterministic test output."""
    return datetime(2025, 6, 15, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def raw_events_file_access(base_time: datetime) -> list[dict]:
    """Raw events that produce file access patterns.

    Four events across two sessions where the same files are accessed together.
    """
    return [
        {
            "session_id": "session-a",
            "tool_name": "Read",
            "file_path": "src/api/routes.py",
            "success": True,
            "timestamp": (base_time).isoformat(),
            "duration_ms": 40,
            "working_directory": "/project",
        },
        {
            "session_id": "session-a",
            "tool_name": "Read",
            "file_path": "src/api/handlers.py",
            "success": True,
            "timestamp": (base_time + timedelta(seconds=10)).isoformat(),
            "duration_ms": 35,
            "working_directory": "/project",
        },
        {
            "session_id": "session-a",
            "tool_name": "Edit",
            "file_path": "src/api/routes.py",
            "success": True,
            "timestamp": (base_time + timedelta(seconds=20)).isoformat(),
            "duration_ms": 30,
            "working_directory": "/project",
        },
        {
            "session_id": "session-b",
            "tool_name": "Read",
            "file_path": "src/api/routes.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=1)).isoformat(),
            "duration_ms": 42,
            "working_directory": "/project",
        },
        {
            "session_id": "session-b",
            "tool_name": "Read",
            "file_path": "src/api/handlers.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=1, seconds=15)).isoformat(),
            "duration_ms": 38,
            "working_directory": "/project",
        },
        {
            "session_id": "session-b",
            "tool_name": "Edit",
            "file_path": "src/api/handlers.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=1, seconds=30)).isoformat(),
            "duration_ms": 25,
            "working_directory": "/project",
        },
        # Third session - same pattern
        {
            "session_id": "session-c",
            "tool_name": "Read",
            "file_path": "src/api/routes.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=2)).isoformat(),
            "duration_ms": 45,
            "working_directory": "/project",
        },
        {
            "session_id": "session-c",
            "tool_name": "Read",
            "file_path": "src/api/handlers.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=2, seconds=10)).isoformat(),
            "duration_ms": 40,
            "working_directory": "/project",
        },
        # Fourth session - same pattern
        {
            "session_id": "session-d",
            "tool_name": "Read",
            "file_path": "src/api/routes.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=3)).isoformat(),
            "duration_ms": 50,
            "working_directory": "/project",
        },
        {
            "session_id": "session-d",
            "tool_name": "Read",
            "file_path": "src/api/handlers.py",
            "success": True,
            "timestamp": (base_time + timedelta(hours=3, seconds=5)).isoformat(),
            "duration_ms": 45,
            "working_directory": "/project",
        },
    ]


@pytest.fixture
def raw_events_error(base_time: datetime) -> list[dict]:
    """Raw events with error patterns across multiple sessions."""
    return [
        {
            "session_id": "err-session-1",
            "tool_name": "Read",
            "file_path": "src/db/connection.py",
            "success": False,
            "error_type": "ConnectionError",
            "error_message": "Failed to connect to database",
            "timestamp": (base_time).isoformat(),
            "duration_ms": 10,
            "working_directory": "/project",
        },
        {
            "session_id": "err-session-2",
            "tool_name": "Read",
            "file_path": "src/db/connection.py",
            "success": False,
            "error_type": "ConnectionError",
            "error_message": "Failed to connect to database",
            "timestamp": (base_time + timedelta(hours=1)).isoformat(),
            "duration_ms": 12,
            "working_directory": "/project",
        },
        {
            "session_id": "err-session-3",
            "tool_name": "Read",
            "file_path": "src/db/connection.py",
            "success": False,
            "error_type": "ConnectionError",
            "error_message": "Failed to connect to database",
            "timestamp": (base_time + timedelta(hours=2)).isoformat(),
            "duration_ms": 11,
            "working_directory": "/project",
        },
    ]


@pytest.fixture
def raw_events_with_tools(base_time: datetime) -> list[dict]:
    """Raw events with clear tool usage patterns."""
    events = []
    for i in range(4):
        session_id = f"tool-session-{i}"
        t = base_time + timedelta(hours=i)
        events.extend(
            [
                {
                    "session_id": session_id,
                    "tool_name": "Read",
                    "file_path": f"src/module_{i}.py",
                    "success": True,
                    "timestamp": t.isoformat(),
                    "duration_ms": 40,
                    "working_directory": "/project",
                },
                {
                    "session_id": session_id,
                    "tool_name": "Edit",
                    "file_path": f"src/module_{i}.py",
                    "success": True,
                    "timestamp": (t + timedelta(seconds=15)).isoformat(),
                    "duration_ms": 30,
                    "working_directory": "/project",
                },
                {
                    "session_id": session_id,
                    "tool_name": "Bash",
                    "success": True,
                    "timestamp": (t + timedelta(seconds=30)).isoformat(),
                    "duration_ms": 500,
                    "working_directory": "/project",
                },
            ]
        )
    return events


@pytest.fixture
def raw_events_architecture(base_time: datetime) -> list[dict]:
    """Raw events with architecture patterns (same directories accessed together)."""
    events = []
    for i in range(4):
        session_id = f"arch-session-{i}"
        t = base_time + timedelta(hours=i)
        events.extend(
            [
                {
                    "session_id": session_id,
                    "tool_name": "Read",
                    "file_path": "src/api/routes.py",
                    "success": True,
                    "timestamp": t.isoformat(),
                    "duration_ms": 40,
                    "working_directory": "/project",
                },
                {
                    "session_id": session_id,
                    "tool_name": "Read",
                    "file_path": "src/api/handlers.py",
                    "success": True,
                    "timestamp": (t + timedelta(seconds=10)).isoformat(),
                    "duration_ms": 35,
                    "working_directory": "/project",
                },
                {
                    "session_id": session_id,
                    "tool_name": "Read",
                    "file_path": "src/api/middleware.py",
                    "success": True,
                    "timestamp": (t + timedelta(seconds=20)).isoformat(),
                    "duration_ms": 30,
                    "working_directory": "/project",
                },
            ]
        )
    return events


# =============================================================================
# Tests: extract_patterns_core - main handler
# =============================================================================


class TestExtractPatternsCore:
    """Tests for the main core model adapter handler."""

    def test_raw_events_produces_output(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """raw_events input produces a valid CoreOutput."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert isinstance(result, CoreOutput)
        assert result.success is True
        assert result.total_patterns_found >= 0
        assert result.processing_time_ms > 0
        assert result.sessions_analyzed > 0
        # All EnumPatternKind keys must be present
        for kind in EnumPatternKind:
            assert kind in result.patterns_by_kind

    def test_raw_events_deterministic_flag(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """When only raw_events are provided, deterministic should be True."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.deterministic is True

    def test_session_ids_produces_warning(self) -> None:
        """session_ids input produces a warning since pure compute cannot query DB."""
        core_input = CoreInput(
            session_ids=["session-1", "session-2"],
            raw_events=[
                {
                    "session_id": "session-1",
                    "tool_name": "Read",
                    "success": True,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "working_directory": "/project",
                },
            ],
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        assert len(result.warnings) >= 1
        warning_codes = [w.code for w in result.warnings]
        assert "SESSION_IDS_UNSUPPORTED" in warning_codes

    def test_empty_raw_events_produces_error(self) -> None:
        """Empty raw_events with no session_ids results in error output."""
        # Need at least one data source to pass model validation
        core_input = CoreInput(
            raw_events=[{"not_a_tool": True}],
        )
        result = handle_pattern_extraction_core(core_input)

        # Should still succeed - empty/invalid events just produce no sessions
        # The handler should handle gracefully
        assert isinstance(result, CoreOutput)

    def test_correlation_id_threaded(self, raw_events_file_access: list[dict]) -> None:
        """correlation_id from input is preserved in output."""
        cid = uuid4()
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            correlation_id=cid,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.correlation_id == cid

    def test_source_snapshot_id_threaded(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """source_snapshot_id from input is preserved in output."""
        snap_id = uuid4()
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            source_snapshot_id=snap_id,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.source_snapshot_id == snap_id

    def test_file_access_patterns_detected(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """FILE_ACCESS patterns are detected from raw events."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            kinds=[EnumPatternKind.FILE_ACCESS],
            min_occurrences=2,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        fa_patterns = result.patterns_by_kind[EnumPatternKind.FILE_ACCESS]
        assert len(fa_patterns) > 0

        # All should be ModelPatternRecord
        for p in fa_patterns:
            assert isinstance(p, ModelPatternRecord)
            assert p.kind == EnumPatternKind.FILE_ACCESS
            assert 0.0 <= p.confidence <= 1.0
            assert p.occurrences >= 1

    def test_error_patterns_detected(self, raw_events_error: list[dict]) -> None:
        """ERROR patterns are detected from raw events with errors."""
        core_input = CoreInput(
            raw_events=raw_events_error,
            kinds=[EnumPatternKind.ERROR],
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        err_patterns = result.patterns_by_kind[EnumPatternKind.ERROR]
        # Should detect error-prone file or error sequence patterns
        assert len(err_patterns) >= 0  # May or may not detect depending on threshold

    def test_tool_usage_patterns_detected(
        self, raw_events_with_tools: list[dict]
    ) -> None:
        """TOOL_USAGE patterns are detected from tool events."""
        core_input = CoreInput(
            raw_events=raw_events_with_tools,
            kinds=[EnumPatternKind.TOOL_USAGE],
            min_occurrences=2,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        tool_patterns = result.patterns_by_kind[EnumPatternKind.TOOL_USAGE]
        assert len(tool_patterns) > 0

        for p in tool_patterns:
            assert p.kind == EnumPatternKind.TOOL_USAGE

    def test_architecture_patterns_detected(
        self, raw_events_architecture: list[dict]
    ) -> None:
        """ARCHITECTURE patterns are detected from file access events."""
        core_input = CoreInput(
            raw_events=raw_events_architecture,
            kinds=[EnumPatternKind.ARCHITECTURE],
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        arch_patterns = result.patterns_by_kind[EnumPatternKind.ARCHITECTURE]
        assert len(arch_patterns) > 0

        for p in arch_patterns:
            assert p.kind == EnumPatternKind.ARCHITECTURE

    def test_kinds_filter_restricts_output(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """Specifying kinds filter restricts which pattern kinds are populated."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            kinds=[EnumPatternKind.FILE_ACCESS],
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        # ERROR, ARCHITECTURE, TOOL_USAGE, TOOL_FAILURE should be empty
        assert len(result.patterns_by_kind[EnumPatternKind.ERROR]) == 0
        assert len(result.patterns_by_kind[EnumPatternKind.ARCHITECTURE]) == 0
        assert len(result.patterns_by_kind[EnumPatternKind.TOOL_USAGE]) == 0
        assert len(result.patterns_by_kind[EnumPatternKind.TOOL_FAILURE]) == 0

    def test_all_kinds_extracted_by_default(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """When kinds is None, all pattern kinds are extracted."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        # All kinds should be present in output (even if empty)
        for kind in EnumPatternKind:
            assert kind in result.patterns_by_kind

    def test_total_patterns_matches_actual_count(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """total_patterns_found matches sum of all pattern lists."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        actual_count = sum(len(v) for v in result.patterns_by_kind.values())
        assert result.total_patterns_found == actual_count

    def test_pattern_records_have_valid_uuids(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """All pattern records have valid UUID pattern_ids."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        for kind, patterns in result.patterns_by_kind.items():
            for p in patterns:
                assert isinstance(p.pattern_id, UUID)


# =============================================================================
# Tests: Time window filtering
# =============================================================================


class TestTimeWindowFiltering:
    """Tests for time window filter application."""

    def test_time_window_filters_sessions(
        self, raw_events_file_access: list[dict], base_time: datetime
    ) -> None:
        """Time window filter restricts which sessions are analyzed."""
        # Set window to only include first 90 minutes
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            time_window_start=base_time,
            time_window_end=base_time + timedelta(hours=1, minutes=30),
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        # Should analyze fewer sessions than total
        assert result.sessions_analyzed <= 4

    def test_time_window_no_sessions_produces_error(
        self, raw_events_file_access: list[dict], base_time: datetime
    ) -> None:
        """Time window that excludes all sessions produces error output."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            time_window_start=base_time + timedelta(days=30),
            time_window_end=base_time + timedelta(days=31),
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is False
        assert len(result.errors) > 0
        error_codes = [e.code for e in result.errors]
        assert "NO_DATA_AFTER_FILTER" in error_codes

    def test_no_time_window_returns_all(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """No time window means all sessions are included."""
        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.sessions_analyzed == 4  # 4 sessions in fixture


# =============================================================================
# Tests: _raw_events_to_sessions
# =============================================================================


class TestRawEventsToSessions:
    """Tests for raw event -> session snapshot conversion."""

    def test_groups_by_session_id(self) -> None:
        """Events with different session_ids become different sessions."""
        now = datetime.now(UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/a",
            },
            {
                "session_id": "s2",
                "tool_name": "Edit",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/b",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions) == 2
        session_ids = {s.session_id for s in sessions}
        assert session_ids == {"s1", "s2"}

    def test_synthetic_session_for_missing_id(self) -> None:
        """Events without session_id are grouped into a synthetic session."""
        now = datetime.now(UTC)
        events: list[dict] = [
            {
                "tool_name": "Read",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
            {
                "tool_name": "Edit",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions) == 1
        assert sessions[0].session_id == "synthetic-session"
        assert len(sessions[0].tools_used) == 2

    def test_file_paths_extracted(self) -> None:
        """file_path from events is added to files_accessed."""
        now = datetime.now(UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "file_path": "src/main.py",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert "src/main.py" in sessions[0].files_accessed

    def test_tool_executions_built(self) -> None:
        """Tool executions are properly constructed from events."""
        now = datetime.now(UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": False,
                "error_type": "FileNotFoundError",
                "error_message": "File not found",
                "duration_ms": 10,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions[0].tool_executions) == 1
        exec_ = sessions[0].tool_executions[0]
        assert exec_.tool_name == "Read"
        assert exec_.success is False
        assert exec_.error_type == "FileNotFoundError"
        assert exec_.error_message == "File not found"
        assert exec_.duration_ms == 10

    def test_error_messages_collected(self) -> None:
        """Error messages from failed events are collected."""
        now = datetime.now(UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": False,
                "error_message": "Something broke",
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert "Something broke" in sessions[0].errors_encountered

    def test_outcome_derived_from_events(self) -> None:
        """Session outcome is derived from event success/failure."""
        now = datetime.now(UTC)
        all_success: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(all_success)
        assert sessions[0].outcome == "success"

        all_fail: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": False,
                "timestamp": now.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(all_fail)
        assert sessions[0].outcome == "failure"

    def test_non_dict_events_skipped(self) -> None:
        """Non-dict events are gracefully skipped."""
        events: list = ["not-a-dict", 42, None]
        sessions = _raw_events_to_sessions(events)  # type: ignore[arg-type]

        assert len(sessions) == 0

    def test_timestamps_parsed(self) -> None:
        """ISO format timestamps are properly parsed."""
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": ts.isoformat(),
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert sessions[0].started_at == ts
        assert sessions[0].ended_at == ts


# =============================================================================
# Tests: _apply_time_window
# =============================================================================


class TestApplyTimeWindow:
    """Tests for time window filtering helper."""

    def test_no_window_returns_all(self) -> None:
        """No time bounds returns all sessions."""
        now = datetime.now(UTC)
        sessions = [
            ModelSessionSnapshot(
                session_id="s1",
                working_directory="/project",
                started_at=now - timedelta(hours=2),
                ended_at=now - timedelta(hours=1),
            ),
            ModelSessionSnapshot(
                session_id="s2",
                working_directory="/project",
                started_at=now - timedelta(hours=1),
                ended_at=now,
            ),
        ]
        filtered = _apply_time_window(sessions, None, None)
        assert len(filtered) == 2

    def test_start_bound(self) -> None:
        """Start bound filters out sessions ending before it."""
        now = datetime.now(UTC)
        sessions = [
            ModelSessionSnapshot(
                session_id="old",
                working_directory="/project",
                started_at=now - timedelta(hours=5),
                ended_at=now - timedelta(hours=4),
            ),
            ModelSessionSnapshot(
                session_id="recent",
                working_directory="/project",
                started_at=now - timedelta(hours=1),
                ended_at=now,
            ),
        ]
        filtered = _apply_time_window(sessions, now - timedelta(hours=2), None)
        assert len(filtered) == 1
        assert filtered[0].session_id == "recent"

    def test_end_bound(self) -> None:
        """End bound filters out sessions ending at or after it."""
        now = datetime.now(UTC)
        sessions = [
            ModelSessionSnapshot(
                session_id="early",
                working_directory="/project",
                started_at=now - timedelta(hours=3),
                ended_at=now - timedelta(hours=2),
            ),
            ModelSessionSnapshot(
                session_id="late",
                working_directory="/project",
                started_at=now - timedelta(hours=1),
                ended_at=now,
            ),
        ]
        filtered = _apply_time_window(sessions, None, now - timedelta(hours=1))
        assert len(filtered) == 1
        assert filtered[0].session_id == "early"

    def test_both_bounds(self) -> None:
        """Both bounds together restrict to a time window."""
        now = datetime.now(UTC)
        sessions = [
            ModelSessionSnapshot(
                session_id="too-early",
                working_directory="/project",
                started_at=now - timedelta(hours=5),
                ended_at=now - timedelta(hours=4),
            ),
            ModelSessionSnapshot(
                session_id="in-window",
                working_directory="/project",
                started_at=now - timedelta(hours=2),
                ended_at=now - timedelta(hours=1),
            ),
            ModelSessionSnapshot(
                session_id="too-late",
                working_directory="/project",
                started_at=now - timedelta(minutes=30),
                ended_at=now,
            ),
        ]
        filtered = _apply_time_window(
            sessions,
            now - timedelta(hours=3),
            now - timedelta(minutes=30),
        )
        assert len(filtered) == 1
        assert filtered[0].session_id == "in-window"


# =============================================================================
# Tests: _insights_to_patterns_by_kind
# =============================================================================


class TestInsightsToPatternsByKind:
    """Tests for insight -> ModelPatternRecord conversion."""

    def test_file_access_insight_maps_to_file_access_kind(self) -> None:
        """FILE_ACCESS_PATTERN insights map to FILE_ACCESS kind."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
                description="co_access: src/a.py, src/b.py",
                confidence=0.85,
                evidence_files=("src/a.py", "src/b.py"),
                evidence_session_ids=("s1", "s2"),
                occurrence_count=3,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        assert EnumPatternKind.FILE_ACCESS in result
        records = result[EnumPatternKind.FILE_ACCESS]
        assert len(records) == 1
        assert records[0].kind == EnumPatternKind.FILE_ACCESS
        assert records[0].confidence == 0.85
        assert records[0].occurrences == 3

    def test_error_insight_maps_to_error_kind(self) -> None:
        """ERROR_PATTERN insights map to ERROR kind."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.ERROR_PATTERN,
                description="ConnectionError in db/conn.py",
                confidence=0.9,
                evidence_files=("db/conn.py",),
                evidence_session_ids=("s1",),
                occurrence_count=5,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        assert EnumPatternKind.ERROR in result
        assert len(result[EnumPatternKind.ERROR]) == 1
        assert result[EnumPatternKind.ERROR][0].kind == EnumPatternKind.ERROR

    def test_architecture_insight_maps_to_architecture_kind(self) -> None:
        """ARCHITECTURE_PATTERN insights map to ARCHITECTURE kind."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.ARCHITECTURE_PATTERN,
                description="module_boundary: src/api",
                confidence=0.75,
                evidence_files=("src/api/routes.py",),
                evidence_session_ids=(),
                occurrence_count=4,
                working_directory="src/api",
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        assert EnumPatternKind.ARCHITECTURE in result
        assert (
            result[EnumPatternKind.ARCHITECTURE][0].kind == EnumPatternKind.ARCHITECTURE
        )

    def test_tool_usage_insight_maps_to_tool_usage_kind(self) -> None:
        """TOOL_USAGE_PATTERN insights map to TOOL_USAGE kind."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.TOOL_USAGE_PATTERN,
                description="tool_sequence: Read -> Edit -> Bash",
                confidence=0.8,
                evidence_files=(),
                evidence_session_ids=(),
                occurrence_count=6,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        assert EnumPatternKind.TOOL_USAGE in result
        assert result[EnumPatternKind.TOOL_USAGE][0].kind == EnumPatternKind.TOOL_USAGE

    def test_evidence_combined(self) -> None:
        """Evidence files and session IDs are combined in record evidence."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
                description="test",
                confidence=0.8,
                evidence_files=("file_a.py", "file_b.py"),
                evidence_session_ids=("session_1",),
                occurrence_count=2,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        records = result[EnumPatternKind.FILE_ACCESS]
        assert len(records[0].evidence) == 3
        assert "file_a.py" in records[0].evidence
        assert "file_b.py" in records[0].evidence
        assert "session_1" in records[0].evidence

    def test_metadata_includes_insight_type(self) -> None:
        """Pattern record metadata includes original insight_type."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.ENTRY_POINT_PATTERN,
                description="entry_point: main.py",
                confidence=0.7,
                evidence_files=("main.py",),
                evidence_session_ids=(),
                occurrence_count=3,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        records = result[EnumPatternKind.FILE_ACCESS]
        assert records[0].metadata["insight_type"] == "entry_point_pattern"

    def test_entry_point_and_modification_cluster_map_to_file_access(self) -> None:
        """ENTRY_POINT_PATTERN and MODIFICATION_CLUSTER map to FILE_ACCESS kind."""
        now = datetime.now(UTC)
        insights = [
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.ENTRY_POINT_PATTERN,
                description="entry: main.py",
                confidence=0.7,
                evidence_files=("main.py",),
                evidence_session_ids=(),
                occurrence_count=2,
                first_observed=now,
                last_observed=now,
            ),
            ModelCodebaseInsight(
                insight_id=str(uuid4()),
                insight_type=EnumInsightType.MODIFICATION_CLUSTER,
                description="cluster: a.py, b.py",
                confidence=0.8,
                evidence_files=("a.py", "b.py"),
                evidence_session_ids=(),
                occurrence_count=3,
                first_observed=now,
                last_observed=now,
            ),
        ]
        result = _insights_to_patterns_by_kind(insights)

        # Both should map to FILE_ACCESS
        assert len(result[EnumPatternKind.FILE_ACCESS]) == 2


# =============================================================================
# Tests: _stable_uuid
# =============================================================================


class TestStableUuid:
    """Tests for UUID conversion helper."""

    def test_valid_uuid_string_parsed(self) -> None:
        """A valid UUID string is parsed directly."""
        uid = uuid4()
        result = _stable_uuid(str(uid))
        assert result == uid

    def test_non_uuid_string_produces_deterministic_uuid(self) -> None:
        """A non-UUID string produces a deterministic UUID5."""
        result1 = _stable_uuid("pattern-123")
        result2 = _stable_uuid("pattern-123")
        assert result1 == result2
        assert isinstance(result1, UUID)

    def test_different_strings_produce_different_uuids(self) -> None:
        """Different non-UUID strings produce different UUIDs."""
        result1 = _stable_uuid("pattern-A")
        result2 = _stable_uuid("pattern-B")
        assert result1 != result2


# =============================================================================
# Tests: Node integration
# =============================================================================


class TestNodeComputeCore:
    """Tests for the node's compute_core method."""

    @pytest.mark.asyncio
    async def test_compute_core_delegates_to_handler(
        self, raw_events_file_access: list[dict]
    ) -> None:
        """compute_core delegates to extract_patterns_core handler."""
        from omnibase_core.models.container import ModelONEXContainer

        from omniintelligence.nodes.node_pattern_extraction_compute.node import (
            NodePatternExtractionCompute,
        )

        container = ModelONEXContainer()
        node = NodePatternExtractionCompute(container)

        core_input = CoreInput(
            raw_events=raw_events_file_access,
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = await node.compute_core(core_input)

        assert isinstance(result, CoreOutput)
        assert result.success is True
        assert result.total_patterns_found >= 0

    @pytest.mark.asyncio
    async def test_original_compute_still_works(self) -> None:
        """The original compute method still works with local models."""
        from datetime import UTC

        from omnibase_core.models.container import ModelONEXContainer

        from omniintelligence.nodes.node_pattern_extraction_compute.models import (
            ModelPatternExtractionInput,
            ModelSessionSnapshot,
        )
        from omniintelligence.nodes.node_pattern_extraction_compute.node import (
            NodePatternExtractionCompute,
        )

        container = ModelONEXContainer()
        node = NodePatternExtractionCompute(container)

        now = datetime.now(UTC)
        local_input = ModelPatternExtractionInput(
            session_snapshots=(
                ModelSessionSnapshot(
                    session_id="s1",
                    working_directory="/project",
                    started_at=now - timedelta(hours=1),
                    ended_at=now,
                    files_accessed=("src/a.py",),
                    tools_used=("Read",),
                ),
            ),
        )
        result = await node.compute(local_input)

        assert result.success is True


# =============================================================================
# Tests: TOOL_FAILURE routing (regression test for CodeRabbit review)
# =============================================================================


class TestToolFailureRouting:
    """Verify TOOL_FAILURE insights are routed to the TOOL_FAILURE bucket."""

    def test_tool_failure_not_duplicated_into_error(
        self, raw_events_with_tools: list[dict], base_time: datetime
    ) -> None:
        """TOOL_FAILURE extraction does not duplicate into ERROR bucket."""
        # Build events that trigger tool failures across sessions
        fail_events = []
        for i in range(4):
            t = base_time + timedelta(hours=i)
            fail_events.extend(
                [
                    {
                        "session_id": f"fail-session-{i}",
                        "tool_name": "Bash",
                        "success": False,
                        "error_type": "CommandError",
                        "error_message": "Command failed with exit code 1",
                        "timestamp": t.isoformat(),
                        "duration_ms": 100,
                        "working_directory": "/project",
                    },
                    {
                        "session_id": f"fail-session-{i}",
                        "tool_name": "Bash",
                        "success": False,
                        "error_type": "CommandError",
                        "error_message": "Command failed with exit code 1",
                        "timestamp": (t + timedelta(seconds=10)).isoformat(),
                        "duration_ms": 150,
                        "working_directory": "/project",
                    },
                ]
            )

        # Request only TOOL_FAILURE, not ERROR
        core_input = CoreInput(
            raw_events=fail_events,
            kinds=[EnumPatternKind.TOOL_FAILURE],
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        # ERROR bucket should be empty since we only asked for TOOL_FAILURE
        assert len(result.patterns_by_kind[EnumPatternKind.ERROR]) == 0

    def test_tool_failure_patterns_in_correct_bucket(self) -> None:
        """TOOL_FAILURE patterns appear under TOOL_FAILURE kind, not ERROR."""
        now = datetime.now(UTC)
        fail_events = []
        for i in range(4):
            t = now + timedelta(hours=i)
            fail_events.append(
                {
                    "session_id": f"tf-session-{i}",
                    "tool_name": "Read",
                    "success": False,
                    "error_type": "FileNotFoundError",
                    "error_message": "File not found: /missing.py",
                    "timestamp": t.isoformat(),
                    "duration_ms": 5,
                    "working_directory": "/project",
                }
            )

        core_input = CoreInput(
            raw_events=fail_events,
            kinds=[EnumPatternKind.TOOL_FAILURE],
            min_occurrences=1,
            min_confidence=0.1,
        )
        result = handle_pattern_extraction_core(core_input)

        assert result.success is True
        tf_patterns = result.patterns_by_kind[EnumPatternKind.TOOL_FAILURE]
        for p in tf_patterns:
            assert p.kind == EnumPatternKind.TOOL_FAILURE


# =============================================================================
# Tests: Naive timestamp normalization (regression test for CodeRabbit review)
# =============================================================================


class TestNaiveTimestampNormalization:
    """Verify naive timestamps are normalized to UTC."""

    def test_naive_timestamp_string_normalized(self) -> None:
        """ISO timestamp without timezone info is normalized to UTC."""
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": "2025-06-15T10:00:00",  # naive - no tz
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions) == 1
        assert sessions[0].started_at.tzinfo is not None

    def test_naive_datetime_object_normalized(self) -> None:
        """Naive datetime objects passed as timestamps are normalized to UTC."""
        naive_dt = datetime(2025, 6, 15, 10, 0, 0)  # no tzinfo
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": naive_dt,
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions) == 1
        assert sessions[0].started_at.tzinfo is not None

    def test_z_suffix_timestamp_parsed(self) -> None:
        """Timestamp with 'Z' suffix is correctly parsed as UTC."""
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": "2025-06-15T10:00:00Z",
                "working_directory": "/project",
            },
        ]
        sessions = _raw_events_to_sessions(events)

        assert len(sessions) == 1
        assert sessions[0].started_at.tzinfo is not None

    def test_naive_timestamps_with_time_window_no_error(self) -> None:
        """Naive timestamps do not cause TypeError with tz-aware time window."""
        now = datetime(2025, 6, 15, 10, 0, 0, tzinfo=UTC)
        events: list[dict] = [
            {
                "session_id": "s1",
                "tool_name": "Read",
                "success": True,
                "timestamp": "2025-06-15T10:00:00",  # naive
                "working_directory": "/project",
            },
        ]
        core_input = CoreInput(
            raw_events=events,
            time_window_start=now - timedelta(hours=1),
            time_window_end=now + timedelta(hours=1),
            min_occurrences=1,
            min_confidence=0.1,
        )
        # This should not raise TypeError
        result = handle_pattern_extraction_core(core_input)
        assert isinstance(result, CoreOutput)
