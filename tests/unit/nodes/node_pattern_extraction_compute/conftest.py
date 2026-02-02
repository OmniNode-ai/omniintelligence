"""Shared fixtures for pattern_extraction_compute handler tests.

These fixtures provide realistic session data for testing the pure handler
functions that extract patterns from Claude Code session snapshots.
"""

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelSessionSnapshot,
    ModelToolExecution,
    EnumInsightType,
)


# =============================================================================
# Time Fixtures
# =============================================================================


@pytest.fixture
def reference_time() -> datetime:
    """Fixed reference time for deterministic test output."""
    return datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def base_time(reference_time: datetime) -> datetime:
    """Base time for session timestamps (1 hour before reference)."""
    return reference_time - timedelta(hours=1)


# =============================================================================
# Single Session Fixtures
# =============================================================================


@pytest.fixture
def sample_session(base_time: datetime, reference_time: datetime) -> ModelSessionSnapshot:
    """A single session snapshot with realistic data.

    This session represents a typical development session where:
    - Multiple files were accessed and modified together
    - Several tools were used in sequence
    - The session completed successfully
    """
    return ModelSessionSnapshot(
        session_id="session-001",
        working_directory="/project/src",
        started_at=base_time,
        ended_at=reference_time,
        files_accessed=(
            "src/api/routes.py",
            "src/api/handlers.py",
            "src/models/user.py",
            "tests/test_api.py",
        ),
        files_modified=(
            "src/api/routes.py",
            "src/api/handlers.py",
        ),
        tools_used=(
            "Read",
            "Read",
            "Edit",
            "Bash",
            "Read",
            "Edit",
        ),
        errors_encountered=(),
        outcome="success",
        metadata={"task_type": "feature_development"},
    )


# =============================================================================
# Multiple Session Fixtures
# =============================================================================


@pytest.fixture
def multiple_sessions(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Multiple sessions showing clear patterns.

    These sessions are designed to produce detectable patterns:
    - Co-access pattern: api/routes.py and api/handlers.py accessed together
    - Entry point: src/api/routes.py is commonly the first file
    - Modification cluster: api files modified together
    - Tool sequence: Read -> Edit -> Bash pattern
    """
    return (
        ModelSessionSnapshot(
            session_id="session-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
                "src/models/user.py",
            ),
            files_modified=(
                "src/api/routes.py",
                "src/api/handlers.py",
            ),
            tools_used=("Read", "Edit", "Bash", "Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="session-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=45),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
                "src/services/auth.py",
            ),
            files_modified=(
                "src/api/routes.py",
                "src/api/handlers.py",
            ),
            tools_used=("Read", "Edit", "Bash", "Read"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="session-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=20),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
                "tests/test_routes.py",
            ),
            files_modified=(
                "src/api/routes.py",
                "tests/test_routes.py",
            ),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="session-004",
            working_directory="/project",
            started_at=base_time + timedelta(hours=3),
            ended_at=base_time + timedelta(hours=3, minutes=15),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
            ),
            files_modified=(
                "src/api/handlers.py",
            ),
            tools_used=("Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
    )


@pytest.fixture
def sessions_with_diverse_tools(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with diverse tool usage for tool pattern detection.

    Designed to detect:
    - Tool sequences (bigrams and trigrams)
    - Tool preferences by file type
    - Success rates
    """
    return (
        ModelSessionSnapshot(
            session_id="tool-session-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=("src/module.py", "tests/test_module.py"),
            files_modified=("src/module.py",),
            tools_used=("Read", "Edit", "Bash", "Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="tool-session-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=25),
            files_accessed=("src/utils.py", "src/helpers.py"),
            files_modified=("src/utils.py",),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="tool-session-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=40),
            files_accessed=("config.yaml", "settings.json"),
            files_modified=("config.yaml",),
            tools_used=("Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="tool-session-004",
            working_directory="/project",
            started_at=base_time + timedelta(hours=3),
            ended_at=base_time + timedelta(hours=3, minutes=20),
            files_accessed=("src/api.py",),
            files_modified=("src/api.py",),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
    )


# =============================================================================
# Error Session Fixtures
# =============================================================================


@pytest.fixture
def sessions_with_errors(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with error data for error pattern detection.

    Designed to detect:
    - Error-prone files
    - Common error messages
    - Files associated with failures
    """
    return (
        ModelSessionSnapshot(
            session_id="error-session-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=15),
            files_accessed=("src/database/connection.py", "src/database/pool.py"),
            files_modified=("src/database/connection.py",),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(
                "ConnectionError: Failed to connect to database",
                "TimeoutError: Connection timed out after 30s",
            ),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="error-session-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=20),
            files_accessed=("src/database/connection.py", "src/api/routes.py"),
            files_modified=("src/database/connection.py",),
            tools_used=("Read", "Edit"),
            errors_encountered=("ConnectionError: Failed to connect to database",),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="error-session-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=30),
            files_accessed=("src/database/connection.py",),
            files_modified=(),
            tools_used=("Read", "Bash"),
            errors_encountered=("ConnectionError: Failed to connect to database",),
            outcome="failure",
        ),
        # A successful session to show contrast
        ModelSessionSnapshot(
            session_id="error-session-004",
            working_directory="/project",
            started_at=base_time + timedelta(hours=3),
            ended_at=base_time + timedelta(hours=3, minutes=25),
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            files_modified=("src/api/routes.py",),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
    )


# =============================================================================
# Edge Case Fixtures
# =============================================================================


@pytest.fixture
def empty_sessions() -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with minimal data for edge case testing.

    These sessions have minimal or empty data fields to test
    graceful handling of edge cases.
    """
    now = datetime.now(UTC)
    return (
        ModelSessionSnapshot(
            session_id="empty-001",
            working_directory="/project",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            files_accessed=(),
            files_modified=(),
            tools_used=(),
            errors_encountered=(),
            outcome="unknown",
        ),
        ModelSessionSnapshot(
            session_id="empty-002",
            working_directory="/project",
            started_at=now - timedelta(minutes=30),
            ended_at=now,
            files_accessed=("single_file.py",),
            files_modified=(),
            tools_used=("Read",),
            errors_encountered=(),
            outcome="success",
        ),
    )


@pytest.fixture
def sessions_below_threshold(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions that produce patterns below default thresholds.

    Designed to test that patterns below min_occurrences and min_confidence
    are properly filtered out.
    """
    return (
        # Only one occurrence of each pattern - below min_occurrences=2
        ModelSessionSnapshot(
            session_id="low-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=10),
            files_accessed=("unique_file_a.py", "unique_file_b.py"),
            files_modified=("unique_file_a.py",),
            tools_used=("Grep", "Write"),
            errors_encountered=(),
            outcome="success",
        ),
    )


# =============================================================================
# Architecture Session Fixtures
# =============================================================================


@pytest.fixture
def sessions_with_architecture_patterns(
    base_time: datetime,
) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions designed to produce architecture patterns.

    These sessions show clear directory structure patterns:
    - Module boundaries (src/api/* accessed together)
    - Layer patterns (src/, tests/, config/)
    """
    return (
        ModelSessionSnapshot(
            session_id="arch-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
                "src/api/middleware.py",
            ),
            files_modified=("src/api/routes.py",),
            tools_used=("Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="arch-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=25),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
                "src/models/user.py",
            ),
            files_modified=("src/api/handlers.py",),
            tools_used=("Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="arch-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=35),
            files_accessed=(
                "src/api/routes.py",
                "tests/api/test_routes.py",
            ),
            files_modified=("tests/api/test_routes.py",),
            tools_used=("Read", "Edit", "Bash"),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="arch-004",
            working_directory="/project",
            started_at=base_time + timedelta(hours=3),
            ended_at=base_time + timedelta(hours=3, minutes=20),
            files_accessed=(
                "src/api/routes.py",
                "src/api/handlers.py",
            ),
            files_modified=("src/api/routes.py",),
            tools_used=("Read", "Edit"),
            errors_encountered=(),
            outcome="success",
        ),
    )


# =============================================================================
# Existing Insights Fixture
# =============================================================================


@pytest.fixture
def existing_insights(reference_time: datetime) -> tuple[ModelCodebaseInsight, ...]:
    """Pre-existing insights for merge testing."""
    return (
        ModelCodebaseInsight(
            insight_id="existing-001",
            insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
            description="Files src/api/routes.py and src/api/handlers.py are frequently accessed together",
            confidence=0.7,
            evidence_files=("src/api/routes.py", "src/api/handlers.py"),
            evidence_session_ids=("old-session-001", "old-session-002"),
            occurrence_count=2,
            first_observed=reference_time - timedelta(days=7),
            last_observed=reference_time - timedelta(days=1),
        ),
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def default_config() -> ModelExtractionConfig:
    """Default extraction configuration."""
    return ModelExtractionConfig()


@pytest.fixture
def lenient_config() -> ModelExtractionConfig:
    """Lenient config with low thresholds for testing pattern detection."""
    return ModelExtractionConfig(
        min_pattern_occurrences=1,
        min_confidence=0.1,
        max_insights_per_type=100,
    )


@pytest.fixture
def strict_config() -> ModelExtractionConfig:
    """Strict config with high thresholds."""
    return ModelExtractionConfig(
        min_pattern_occurrences=5,
        min_confidence=0.9,
        max_insights_per_type=10,
    )


@pytest.fixture
def selective_config() -> ModelExtractionConfig:
    """Config with only file patterns enabled."""
    return ModelExtractionConfig(
        extract_file_patterns=True,
        extract_error_patterns=False,
        extract_architecture_patterns=False,
        extract_tool_patterns=False,
    )


# =============================================================================
# Full Input Fixtures
# =============================================================================


@pytest.fixture
def full_extraction_input(
    multiple_sessions: tuple[ModelSessionSnapshot, ...],
    default_config: ModelExtractionConfig,
    reference_time: datetime,
) -> ModelPatternExtractionInput:
    """Complete input for extract_all_patterns testing."""
    config_with_time = ModelExtractionConfig(
        **{
            **default_config.model_dump(),
            "reference_time": reference_time,
        }
    )
    return ModelPatternExtractionInput(
        session_snapshots=multiple_sessions,
        options=config_with_time,
        existing_insights=(),
        correlation_id="test-correlation-001",
    )


# =============================================================================
# Tool Execution Fixtures
# =============================================================================


@pytest.fixture
def tool_execution_success(base_time: datetime) -> ModelToolExecution:
    """Successful tool execution."""
    return ModelToolExecution(
        tool_name="Read",
        success=True,
        duration_ms=45,
        timestamp=base_time,
    )


@pytest.fixture
def tool_execution_failure(base_time: datetime) -> ModelToolExecution:
    """Failed tool execution."""
    return ModelToolExecution(
        tool_name="Read",
        success=False,
        error_message="File not found: /path/to/file.py",
        error_type="FileNotFoundError",
        duration_ms=12,
        tool_parameters={"file_path": "/path/to/file.py"},
        timestamp=base_time,
    )


# =============================================================================
# Tool Failure Pattern Session Fixtures
# =============================================================================


@pytest.fixture
def sessions_with_recurring_failures(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with same tool+error_type across multiple sessions (min 3).

    Designed to detect:
    - Recurring failure patterns: same tool + same error_type across sessions
    - Should trigger recurring_failure pattern detection when min_distinct_sessions >= 2
    """
    return (
        ModelSessionSnapshot(
            session_id="recurring-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=20),
            files_accessed=("src/config.py", "src/settings.py"),
            files_modified=(),
            tools_used=("Read", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=30,
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: /path/to/missing.py",
                    error_type="FileNotFoundError",
                    duration_ms=10,
                    tool_parameters={"file_path": "/path/to/missing.py"},
                    timestamp=base_time + timedelta(seconds=30),
                ),
            ),
            errors_encountered=("FileNotFoundError: /path/to/missing.py",),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="recurring-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=15),
            files_accessed=("src/main.py",),
            files_modified=(),
            tools_used=("Read", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=25,
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: /path/to/another.py",
                    error_type="FileNotFoundError",
                    duration_ms=8,
                    tool_parameters={"file_path": "/path/to/another.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=45),
                ),
            ),
            errors_encountered=("FileNotFoundError: /path/to/another.py",),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="recurring-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=25),
            files_accessed=("src/utils.py",),
            files_modified=(),
            tools_used=("Read", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=35,
                    timestamp=base_time + timedelta(hours=2),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: /path/to/third.py",
                    error_type="FileNotFoundError",
                    duration_ms=11,
                    tool_parameters={"file_path": "/path/to/third.py"},
                    timestamp=base_time + timedelta(hours=2, seconds=60),
                ),
            ),
            errors_encountered=("FileNotFoundError: /path/to/third.py",),
            outcome="failure",
        ),
    )


@pytest.fixture
def sessions_with_failure_sequence(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions where Read failure is followed by Edit failure (within 5 calls).

    Designed to detect:
    - Failure cascades: one tool failure leading to another
    - Sequence patterns where failure A often precedes failure B
    """
    return (
        ModelSessionSnapshot(
            session_id="sequence-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=("src/module.py",),
            files_modified=(),
            tools_used=("Read", "Edit", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: src/module.py",
                    error_type="FileNotFoundError",
                    duration_ms=10,
                    tool_parameters={"file_path": "src/module.py"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit non-existent file: src/module.py",
                    error_type="FileNotFoundError",
                    duration_ms=8,
                    tool_parameters={"file_path": "src/module.py"},
                    timestamp=base_time + timedelta(seconds=15),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=40,
                    timestamp=base_time + timedelta(seconds=30),
                ),
            ),
            errors_encountered=(
                "FileNotFoundError: src/module.py",
                "Cannot edit non-existent file",
            ),
            outcome="partial",
        ),
        ModelSessionSnapshot(
            session_id="sequence-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=25),
            files_accessed=("src/handler.py",),
            files_modified=(),
            tools_used=("Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: src/handler.py",
                    error_type="FileNotFoundError",
                    duration_ms=12,
                    tool_parameters={"file_path": "src/handler.py"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit non-existent file: src/handler.py",
                    error_type="FileNotFoundError",
                    duration_ms=9,
                    tool_parameters={"file_path": "src/handler.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=20),
                ),
            ),
            errors_encountered=(
                "FileNotFoundError: src/handler.py",
                "Cannot edit non-existent file",
            ),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="sequence-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=20),
            files_accessed=("src/service.py",),
            files_modified=(),
            tools_used=("Read", "Bash", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: src/service.py",
                    error_type="FileNotFoundError",
                    duration_ms=11,
                    tool_parameters={"file_path": "src/service.py"},
                    timestamp=base_time + timedelta(hours=2),
                ),
                ModelToolExecution(
                    tool_name="Bash",
                    success=True,
                    duration_ms=500,
                    timestamp=base_time + timedelta(hours=2, seconds=10),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit non-existent file: src/service.py",
                    error_type="FileNotFoundError",
                    duration_ms=7,
                    tool_parameters={"file_path": "src/service.py"},
                    timestamp=base_time + timedelta(hours=2, seconds=25),
                ),
            ),
            errors_encountered=(
                "FileNotFoundError: src/service.py",
                "Cannot edit non-existent file",
            ),
            outcome="failure",
        ),
    )


@pytest.fixture
def sessions_with_recovery_pattern(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with failure -> retry -> success pattern.

    Designed to detect:
    - Recovery patterns: same tool, same parameters, failure then success
    - Retry behavior indicating transient failures
    """
    return (
        ModelSessionSnapshot(
            session_id="recovery-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=15),
            files_accessed=("src/api/routes.py",),
            files_modified=("src/api/routes.py",),
            tools_used=("Read", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Permission denied: src/api/routes.py",
                    error_type="PermissionError",
                    duration_ms=5,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=45,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time + timedelta(seconds=10),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=30,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time + timedelta(seconds=25),
                ),
            ),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="recovery-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=20),
            files_accessed=("src/models/user.py",),
            files_modified=("src/models/user.py",),
            tools_used=("Read", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Permission denied: src/models/user.py",
                    error_type="PermissionError",
                    duration_ms=6,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=50,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=15),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=35,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=30),
                ),
            ),
            errors_encountered=(),
            outcome="success",
        ),
    )


@pytest.fixture
def sessions_with_directory_failures(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with failures concentrated in specific directory.

    Designed to detect:
    - Directory hotspots: directories with high failure rates
    - Multiple failures in same directory (e.g., /src/broken/)
    """
    return (
        ModelSessionSnapshot(
            session_id="hotspot-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=20),
            files_accessed=("src/broken/module_a.py", "src/broken/module_b.py"),
            files_modified=(),
            tools_used=("Read", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Syntax error in file: src/broken/module_a.py",
                    error_type="SyntaxError",
                    duration_ms=15,
                    tool_parameters={"file_path": "src/broken/module_a.py"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Encoding error: src/broken/module_b.py",
                    error_type="UnicodeDecodeError",
                    duration_ms=12,
                    tool_parameters={"file_path": "src/broken/module_b.py"},
                    timestamp=base_time + timedelta(seconds=20),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit file with errors: src/broken/module_a.py",
                    error_type="ValueError",
                    duration_ms=8,
                    tool_parameters={"file_path": "src/broken/module_a.py"},
                    timestamp=base_time + timedelta(seconds=40),
                ),
            ),
            errors_encountered=(
                "SyntaxError: src/broken/module_a.py",
                "UnicodeDecodeError: src/broken/module_b.py",
            ),
            outcome="failure",
        ),
        ModelSessionSnapshot(
            session_id="hotspot-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=25),
            files_accessed=("src/broken/module_c.py", "src/working/module.py"),
            files_modified=("src/working/module.py",),
            tools_used=("Read", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Import error in file: src/broken/module_c.py",
                    error_type="ImportError",
                    duration_ms=20,
                    tool_parameters={"file_path": "src/broken/module_c.py"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=40,
                    tool_parameters={"file_path": "src/working/module.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=25),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=30,
                    tool_parameters={"file_path": "src/working/module.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=50),
                ),
            ),
            errors_encountered=("ImportError: src/broken/module_c.py",),
            outcome="partial",
        ),
        ModelSessionSnapshot(
            session_id="hotspot-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=15),
            files_accessed=("src/broken/module_d.py",),
            files_modified=(),
            tools_used=("Read",),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File corrupted: src/broken/module_d.py",
                    error_type="IOError",
                    duration_ms=18,
                    tool_parameters={"file_path": "src/broken/module_d.py"},
                    timestamp=base_time + timedelta(hours=2),
                ),
            ),
            errors_encountered=("IOError: File corrupted",),
            outcome="failure",
        ),
    )


@pytest.fixture
def sessions_all_success(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with only successful tool executions (no failures).

    Designed to verify:
    - No failure patterns are detected when all executions succeed
    - Handler gracefully handles sessions without failures
    """
    return (
        ModelSessionSnapshot(
            session_id="success-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=("src/api/routes.py", "src/api/handlers.py"),
            files_modified=("src/api/routes.py",),
            tools_used=("Read", "Read", "Edit", "Bash"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=45,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=40,
                    tool_parameters={"file_path": "src/api/handlers.py"},
                    timestamp=base_time + timedelta(seconds=15),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=30,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time + timedelta(seconds=30),
                ),
                ModelToolExecution(
                    tool_name="Bash",
                    success=True,
                    duration_ms=500,
                    tool_parameters={"command": "pytest tests/"},
                    timestamp=base_time + timedelta(seconds=45),
                ),
            ),
            errors_encountered=(),
            outcome="success",
        ),
        ModelSessionSnapshot(
            session_id="success-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=25),
            files_accessed=("src/models/user.py", "tests/test_user.py"),
            files_modified=("src/models/user.py", "tests/test_user.py"),
            tools_used=("Read", "Edit", "Read", "Edit", "Bash"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=50,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=35,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=20),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=45,
                    tool_parameters={"file_path": "tests/test_user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=40),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=40,
                    tool_parameters={"file_path": "tests/test_user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=60),
                ),
                ModelToolExecution(
                    tool_name="Bash",
                    success=True,
                    duration_ms=800,
                    tool_parameters={"command": "pytest tests/test_user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=80),
                ),
            ),
            errors_encountered=(),
            outcome="success",
        ),
    )


@pytest.fixture
def single_failure_session(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Single session with one failure - should NOT create pattern.

    Designed to verify:
    - Single occurrences do not create patterns (min_distinct_sessions=2)
    - Handler correctly filters out non-patterns
    """
    return (
        ModelSessionSnapshot(
            session_id="single-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=15),
            files_accessed=("src/unique/file.py",),
            files_modified=(),
            tools_used=("Read", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=30,
                    tool_parameters={"file_path": "src/main.py"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Unique error that only happens once",
                    error_type="UniqueError",
                    duration_ms=10,
                    tool_parameters={"file_path": "src/unique/file.py"},
                    timestamp=base_time + timedelta(seconds=30),
                ),
            ),
            errors_encountered=("UniqueError: only happens once",),
            outcome="failure",
        ),
    )


@pytest.fixture
def sessions_with_extension_failures(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with failures concentrated on specific file extensions.

    Designed to detect:
    - Context failures: failures correlated with file extensions (e.g., .json files)
    - Triggers context_failure pattern detection when tool fails on same extension
      across multiple sessions

    This fixture creates 3 sessions where Read/Edit fails on .json files:
    - Session 1: Read fails on config.json, Edit fails on settings.json
    - Session 2: Read fails on package.json
    - Session 3: Read fails on data.json, Edit fails on schema.json

    Total: 5 failures on .json files across 3 sessions, plus some .py successes
    for contrast.
    """
    return (
        ModelSessionSnapshot(
            session_id="ext-failure-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=25),
            files_accessed=("config.json", "settings.json", "src/main.py"),
            files_modified=(),
            tools_used=("Read", "Read", "Edit", "Read"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="JSON parse error: unexpected token at line 42",
                    error_type="JSONDecodeError",
                    duration_ms=15,
                    tool_parameters={"file_path": "config.json"},
                    timestamp=base_time,
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=30,
                    tool_parameters={"file_path": "src/main.py"},
                    timestamp=base_time + timedelta(seconds=20),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Invalid JSON structure: missing closing brace",
                    error_type="JSONDecodeError",
                    duration_ms=12,
                    tool_parameters={"file_path": "settings.json"},
                    timestamp=base_time + timedelta(seconds=40),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=25,
                    tool_parameters={"file_path": "src/main.py"},
                    timestamp=base_time + timedelta(seconds=60),
                ),
            ),
            errors_encountered=(
                "JSONDecodeError: config.json",
                "JSONDecodeError: settings.json",
            ),
            outcome="partial",
        ),
        ModelSessionSnapshot(
            session_id="ext-failure-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=20),
            files_accessed=("package.json", "src/utils.py"),
            files_modified=("src/utils.py",),
            tools_used=("Read", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="JSON parse error: trailing comma not allowed",
                    error_type="JSONDecodeError",
                    duration_ms=18,
                    tool_parameters={"file_path": "package.json"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=35,
                    tool_parameters={"file_path": "src/utils.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=25),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=28,
                    tool_parameters={"file_path": "src/utils.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=50),
                ),
            ),
            errors_encountered=("JSONDecodeError: package.json",),
            outcome="partial",
        ),
        ModelSessionSnapshot(
            session_id="ext-failure-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=30),
            files_accessed=("data/data.json", "data/schema.json", "src/handler.py"),
            files_modified=("src/handler.py",),
            tools_used=("Read", "Edit", "Read", "Edit"),
            tool_executions=(
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="JSON parse error: invalid escape sequence",
                    error_type="JSONDecodeError",
                    duration_ms=14,
                    tool_parameters={"file_path": "data/data.json"},
                    timestamp=base_time + timedelta(hours=2),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit malformed JSON file",
                    error_type="JSONDecodeError",
                    duration_ms=10,
                    tool_parameters={"file_path": "data/schema.json"},
                    timestamp=base_time + timedelta(hours=2, seconds=30),
                ),
                ModelToolExecution(
                    tool_name="Read",
                    success=True,
                    duration_ms=40,
                    tool_parameters={"file_path": "src/handler.py"},
                    timestamp=base_time + timedelta(hours=2, seconds=60),
                ),
                ModelToolExecution(
                    tool_name="Edit",
                    success=True,
                    duration_ms=32,
                    tool_parameters={"file_path": "src/handler.py"},
                    timestamp=base_time + timedelta(hours=2, seconds=90),
                ),
            ),
            errors_encountered=(
                "JSONDecodeError: data/data.json",
                "JSONDecodeError: data/schema.json",
            ),
            outcome="partial",
        ),
    )


@pytest.fixture
def sessions_with_many_failure_patterns(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions designed to produce MULTIPLE patterns of EACH subtype.

    This fixture is specifically for testing max_results_per_type limiting.
    It creates enough failures across sessions to generate:
    - Multiple recurring_failure patterns (different tool+error_type combinations)
    - Multiple failure_sequence patterns (different A->B sequences)
    - Multiple context_failure patterns (different file extensions)
    - Multiple failure_hotspot patterns (different directories)

    Each pattern subtype should have MORE than 1 pattern so we can verify
    max_results_per_type=1 actually limits results.
    """
    return (
        # Session 1: Multiple recurring failures and sequences
        ModelSessionSnapshot(
            session_id="many-001",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=30),
            files_accessed=("src/api/routes.py", "config/settings.json", "data/file.csv"),
            files_modified=(),
            tools_used=("Read", "Read", "Edit", "Bash", "Read", "Edit"),
            tool_executions=(
                # Read failure on .py file (recurring pattern 1: Read+FileNotFoundError)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: src/api/routes.py",
                    error_type="FileNotFoundError",
                    duration_ms=10,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time,
                ),
                # Edit failure follows Read failure (sequence: Read->Edit)
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit: src/api/routes.py",
                    error_type="FileNotFoundError",
                    duration_ms=8,
                    tool_parameters={"file_path": "src/api/routes.py"},
                    timestamp=base_time + timedelta(seconds=10),
                ),
                # Read failure on .json file (recurring pattern 2: Read+JSONDecodeError)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Invalid JSON: config/settings.json",
                    error_type="JSONDecodeError",
                    duration_ms=12,
                    tool_parameters={"file_path": "config/settings.json"},
                    timestamp=base_time + timedelta(seconds=20),
                ),
                # Bash failure (recurring pattern 3: Bash+CommandError)
                ModelToolExecution(
                    tool_name="Bash",
                    success=False,
                    error_message="Command failed with exit code 1",
                    error_type="CommandError",
                    duration_ms=500,
                    tool_parameters={"command": "pytest tests/"},
                    timestamp=base_time + timedelta(seconds=30),
                ),
                # Read failure on .csv file (context_failure for .csv extension)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="CSV parse error: data/file.csv",
                    error_type="CSVError",
                    duration_ms=15,
                    tool_parameters={"file_path": "data/file.csv"},
                    timestamp=base_time + timedelta(seconds=40),
                ),
                # Edit failure follows Read failure (another Read->Edit sequence instance)
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit CSV: data/file.csv",
                    error_type="CSVError",
                    duration_ms=10,
                    tool_parameters={"file_path": "data/file.csv"},
                    timestamp=base_time + timedelta(seconds=50),
                ),
            ),
            errors_encountered=("FileNotFoundError", "JSONDecodeError", "CommandError"),
            outcome="failure",
        ),
        # Session 2: More patterns to ensure min_distinct_sessions is met
        ModelSessionSnapshot(
            session_id="many-002",
            working_directory="/project",
            started_at=base_time + timedelta(hours=1),
            ended_at=base_time + timedelta(hours=1, minutes=30),
            files_accessed=("src/models/user.py", "config/app.json", "data/export.csv"),
            files_modified=(),
            tools_used=("Read", "Edit", "Read", "Bash", "Read", "Edit"),
            tool_executions=(
                # Read failure on .py file (recurring pattern 1: Read+FileNotFoundError)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: src/models/user.py",
                    error_type="FileNotFoundError",
                    duration_ms=11,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1),
                ),
                # Edit failure follows Read (sequence: Read->Edit)
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit: src/models/user.py",
                    error_type="FileNotFoundError",
                    duration_ms=9,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=10),
                ),
                # Read failure on .json file (recurring pattern 2: Read+JSONDecodeError)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Invalid JSON: config/app.json",
                    error_type="JSONDecodeError",
                    duration_ms=13,
                    tool_parameters={"file_path": "config/app.json"},
                    timestamp=base_time + timedelta(hours=1, seconds=20),
                ),
                # Bash failure (recurring pattern 3: Bash+CommandError)
                ModelToolExecution(
                    tool_name="Bash",
                    success=False,
                    error_message="Command failed with exit code 2",
                    error_type="CommandError",
                    duration_ms=450,
                    tool_parameters={"command": "npm test"},
                    timestamp=base_time + timedelta(hours=1, seconds=30),
                ),
                # Read failure on .csv (context_failure for .csv)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="CSV parse error: data/export.csv",
                    error_type="CSVError",
                    duration_ms=14,
                    tool_parameters={"file_path": "data/export.csv"},
                    timestamp=base_time + timedelta(hours=1, seconds=40),
                ),
                # Bash->Edit sequence (new sequence type)
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Edit failed after bash",
                    error_type="EditError",
                    duration_ms=8,
                    tool_parameters={"file_path": "src/models/user.py"},
                    timestamp=base_time + timedelta(hours=1, seconds=50),
                ),
            ),
            errors_encountered=("FileNotFoundError", "JSONDecodeError", "CommandError"),
            outcome="failure",
        ),
        # Session 3: Additional patterns for variety
        ModelSessionSnapshot(
            session_id="many-003",
            working_directory="/project",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=30),
            files_accessed=("lib/helper.py", "config/db.json", "logs/error.log"),
            files_modified=(),
            tools_used=("Read", "Edit", "Read", "Bash", "Read"),
            tool_executions=(
                # Read failure on .py file (recurring pattern 1)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="File not found: lib/helper.py",
                    error_type="FileNotFoundError",
                    duration_ms=10,
                    tool_parameters={"file_path": "lib/helper.py"},
                    timestamp=base_time + timedelta(hours=2),
                ),
                # Edit failure follows Read (sequence: Read->Edit)
                ModelToolExecution(
                    tool_name="Edit",
                    success=False,
                    error_message="Cannot edit: lib/helper.py",
                    error_type="FileNotFoundError",
                    duration_ms=8,
                    tool_parameters={"file_path": "lib/helper.py"},
                    timestamp=base_time + timedelta(hours=2, seconds=10),
                ),
                # Read failure on .json (recurring pattern 2)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Invalid JSON: config/db.json",
                    error_type="JSONDecodeError",
                    duration_ms=12,
                    tool_parameters={"file_path": "config/db.json"},
                    timestamp=base_time + timedelta(hours=2, seconds=20),
                ),
                # Bash failure (recurring pattern 3)
                ModelToolExecution(
                    tool_name="Bash",
                    success=False,
                    error_message="Command failed with exit code 127",
                    error_type="CommandError",
                    duration_ms=100,
                    tool_parameters={"command": "make build"},
                    timestamp=base_time + timedelta(hours=2, seconds=30),
                ),
                # Read failure on .log (context_failure for .log extension)
                ModelToolExecution(
                    tool_name="Read",
                    success=False,
                    error_message="Cannot read log: logs/error.log",
                    error_type="PermissionError",
                    duration_ms=8,
                    tool_parameters={"file_path": "logs/error.log"},
                    timestamp=base_time + timedelta(hours=2, seconds=40),
                ),
            ),
            errors_encountered=("FileNotFoundError", "JSONDecodeError", "CommandError"),
            outcome="failure",
        ),
    )
