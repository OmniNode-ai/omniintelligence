"""Shared fixtures for pattern_extraction_compute handler tests.

These fixtures provide realistic session data for testing the pure handler
functions that extract patterns from Claude Code session snapshots.
"""

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelSessionSnapshot,
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
        config=config_with_time,
        existing_insights=(),
        correlation_id="test-correlation-001",
    )
