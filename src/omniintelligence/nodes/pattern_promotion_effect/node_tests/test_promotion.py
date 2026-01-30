# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Comprehensive unit tests for pattern promotion gates and workflow.

This module tests the pattern promotion handler functions:
- `meets_promotion_criteria()`: Pure function checking promotion gates
- `check_and_promote_patterns()`: Main promotion workflow
- `promote_pattern()`: Single pattern promotion with event emission

Test cases are organized by acceptance criteria from OMN-1680:
1. Gate 1: Injection count gate (minimum 5 injections)
2. Gate 2: Success rate gate (minimum 60% success rate)
3. Gate 3: Failure streak gate (maximum 3 consecutive failures)
4. Edge cases and boundary conditions
5. Handler tests with mocked repositories
6. Event payload verification

Reference:
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pydantic
import pytest

from omniintelligence.nodes.pattern_promotion_effect.handlers.handler_promotion import (
    MAX_FAILURE_STREAK,
    MIN_INJECTION_COUNT,
    MIN_SUCCESS_RATE,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    _parse_update_count,
    build_gate_snapshot,
    calculate_success_rate,
    check_and_promote_patterns,
    meets_promotion_criteria,
    promote_pattern,
)
from omniintelligence.nodes.pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)


# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


class MockRecord(dict):
    """Dict-like object that mimics asyncpg.Record behavior.

    asyncpg.Record supports both dict-style access (record["column"]) and
    attribute access (record.column). This mock provides the same interface
    for testing.
    """

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to columns."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no column '{name}'")


# =============================================================================
# Mock Pattern Repository
# =============================================================================


@dataclass
class PromotablePattern:
    """In-memory state for a learned pattern eligible for promotion check.

    Simulates the learned_patterns table columns relevant to promotion.
    """

    id: UUID
    pattern_signature: str = "test_pattern_signature"
    status: str = "provisional"
    is_current: bool = True
    injection_count_rolling_20: int = 0
    success_count_rolling_20: int = 0
    failure_count_rolling_20: int = 0
    failure_streak: int = 0


class MockPatternRepository:
    """In-memory mock repository implementing ProtocolPatternRepository.

    This mock simulates asyncpg behavior including:
    - Query execution with positional parameters ($1, $2, etc.)
    - Returning list of Record-like objects for fetch()
    - Returning status strings like "UPDATE 5" for execute()
    - Simulating the actual SQL logic for promotion

    The repository tracks query history for verification in tests.
    """

    def __init__(self) -> None:
        """Initialize empty repository state."""
        self.patterns: dict[UUID, PromotablePattern] = {}
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []

    def add_pattern(self, pattern: PromotablePattern) -> None:
        """Add a pattern to the mock database."""
        self.patterns[pattern.id] = pattern

    async def fetch(self, query: str, *args: Any) -> list[MockRecord]:
        """Execute a query and return results as MockRecord objects.

        Simulates asyncpg fetch() behavior. Supports the specific queries
        used by the promotion handlers.
        """
        self.queries_executed.append((query, args))

        # Handle: Fetch provisional patterns eligible for promotion check
        if "learned_patterns" in query and "provisional" in query:
            results = []
            for p in self.patterns.values():
                if p.status == "provisional" and p.is_current:
                    results.append(
                        MockRecord(
                            {
                                "id": p.id,
                                "pattern_signature": p.pattern_signature,
                                "injection_count_rolling_20": p.injection_count_rolling_20,
                                "success_count_rolling_20": p.success_count_rolling_20,
                                "failure_count_rolling_20": p.failure_count_rolling_20,
                                "failure_streak": p.failure_streak,
                            }
                        )
                    )
            return results

        return []

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return status string.

        Simulates asyncpg execute() behavior. Implements the actual
        promotion update logic.
        """
        self.queries_executed.append((query, args))

        # Handle: Promote a single pattern
        if "UPDATE learned_patterns" in query and "validated" in query:
            pattern_id = args[0]
            if pattern_id in self.patterns:
                p = self.patterns[pattern_id]
                if p.status == "provisional":
                    p.status = "validated"
                    return "UPDATE 1"
            return "UPDATE 0"

        return "UPDATE 0"


# =============================================================================
# Mock Kafka Publisher
# =============================================================================


class MockKafkaPublisher:
    """Mock Kafka publisher for testing event emission.

    Tracks all published events for verification in tests.
    """

    def __init__(self) -> None:
        """Initialize with empty published events list."""
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Record the published event."""
        self.published_events.append((topic, key, value))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MockPatternRepository:
    """Create a fresh mock repository for each test."""
    return MockPatternRepository()


@pytest.fixture
def mock_producer() -> MockKafkaPublisher:
    """Create a fresh mock Kafka publisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Fixed pattern ID for deterministic tests."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


# =============================================================================
# Test Class: Gate 1 - Minimum Injection Count
# =============================================================================


@pytest.mark.unit
class TestGate1InjectionCount:
    """Tests for Gate 1: Minimum injection count requirement.

    A pattern must have injection_count_rolling_20 >= MIN_INJECTION_COUNT (5)
    to be eligible for promotion. This ensures sufficient sample size.
    """

    def test_meets_criteria_fails_when_injection_count_zero(self) -> None:
        """Pattern with 0 injections fails Gate 1."""
        pattern = MockRecord({
            "injection_count_rolling_20": 0,
            "success_count_rolling_20": 0,
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_injection_count_below_minimum(self) -> None:
        """Pattern with 4 injections (below minimum 5) fails Gate 1."""
        pattern = MockRecord({
            "injection_count_rolling_20": 4,
            "success_count_rolling_20": 4,
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_injection_count_at_minimum(self) -> None:
        """Pattern with exactly 5 injections (at minimum) passes Gate 1."""
        pattern = MockRecord({
            "injection_count_rolling_20": 5,
            "success_count_rolling_20": 4,  # 80% success rate
            "failure_count_rolling_20": 1,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_injection_count_above_minimum(self) -> None:
        """Pattern with 20 injections (above minimum) passes Gate 1."""
        pattern = MockRecord({
            "injection_count_rolling_20": 20,
            "success_count_rolling_20": 15,  # 75% success rate
            "failure_count_rolling_20": 5,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_handles_none_injection_count(self) -> None:
        """Pattern with None injection count is treated as 0."""
        pattern = MockRecord({
            "injection_count_rolling_20": None,
            "success_count_rolling_20": 5,
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_min_injection_count_constant_is_five(self) -> None:
        """Verify MIN_INJECTION_COUNT constant is 5."""
        assert MIN_INJECTION_COUNT == 5


# =============================================================================
# Test Class: Gate 2 - Minimum Success Rate
# =============================================================================


@pytest.mark.unit
class TestGate2SuccessRate:
    """Tests for Gate 2: Minimum success rate requirement.

    A pattern must have success_rate >= MIN_SUCCESS_RATE (0.6 / 60%)
    to be eligible for promotion. Success rate is calculated as:
    success_count / (success_count + failure_count)
    """

    def test_meets_criteria_fails_when_success_rate_below_60_percent(self) -> None:
        """Pattern with 50% success rate (below 60%) fails Gate 2."""
        # 50% success rate: 5 successes, 5 failures
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 5,
            "failure_count_rolling_20": 5,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_success_rate_at_59_percent(self) -> None:
        """Pattern with ~59% success rate (just below 60%) fails Gate 2."""
        # 59.4% success rate: 19 successes, 13 failures (19/32 = 0.594)
        pattern = MockRecord({
            "injection_count_rolling_20": 32,
            "success_count_rolling_20": 19,
            "failure_count_rolling_20": 13,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_success_rate_at_60_percent(self) -> None:
        """Pattern with exactly 60% success rate passes Gate 2."""
        # Exactly 60%: 6 successes, 4 failures
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 6,
            "failure_count_rolling_20": 4,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_success_rate_above_60_percent(self) -> None:
        """Pattern with 80% success rate passes Gate 2."""
        # 80% success rate: 8 successes, 2 failures
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,
            "failure_count_rolling_20": 2,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_100_percent_success_rate(self) -> None:
        """Pattern with 100% success rate passes Gate 2."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 10,
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_fails_when_no_outcomes_recorded(self) -> None:
        """Pattern with 0 successes and 0 failures fails (division by zero protection)."""
        pattern = MockRecord({
            "injection_count_rolling_20": 5,
            "success_count_rolling_20": 0,
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_handles_none_success_count(self) -> None:
        """Pattern with None success count is treated as 0."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": None,
            "failure_count_rolling_20": 5,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_handles_none_failure_count(self) -> None:
        """Pattern with None failure count is treated as 0."""
        # 100% success rate with None failures treated as 0
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 10,
            "failure_count_rolling_20": None,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_min_success_rate_constant_is_0_6(self) -> None:
        """Verify MIN_SUCCESS_RATE constant is 0.6."""
        assert MIN_SUCCESS_RATE == 0.6


# =============================================================================
# Test Class: Gate 3 - Maximum Failure Streak
# =============================================================================


@pytest.mark.unit
class TestGate3FailureStreak:
    """Tests for Gate 3: Maximum failure streak requirement.

    A pattern must have failure_streak < MAX_FAILURE_STREAK (3)
    to be eligible for promotion. This prevents promoting patterns
    that are currently in a failure spiral.
    """

    def test_meets_criteria_fails_when_failure_streak_at_max(self) -> None:
        """Pattern with exactly 3 consecutive failures (at max) fails Gate 3."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,  # 70% success rate
            "failure_count_rolling_20": 3,
            "failure_streak": 3,  # At max
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_failure_streak_above_max(self) -> None:
        """Pattern with 5 consecutive failures (above max) fails Gate 3."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,
            "failure_count_rolling_20": 3,
            "failure_streak": 5,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_failure_streak_below_max(self) -> None:
        """Pattern with 2 consecutive failures (below max) passes Gate 3."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,
            "failure_count_rolling_20": 3,
            "failure_streak": 2,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_failure_streak_is_zero(self) -> None:
        """Pattern with 0 consecutive failures passes Gate 3."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,
            "failure_count_rolling_20": 3,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_failure_streak_is_one(self) -> None:
        """Pattern with 1 consecutive failure passes Gate 3."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,
            "failure_count_rolling_20": 3,
            "failure_streak": 1,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_handles_none_failure_streak(self) -> None:
        """Pattern with None failure streak is treated as 0."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,
            "failure_count_rolling_20": 3,
            "failure_streak": None,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_max_failure_streak_constant_is_three(self) -> None:
        """Verify MAX_FAILURE_STREAK constant is 3."""
        assert MAX_FAILURE_STREAK == 3


# =============================================================================
# Test Class: All Gates Combined
# =============================================================================


@pytest.mark.unit
class TestAllGatesCombined:
    """Tests for scenarios where multiple gates interact.

    A pattern must pass ALL gates to be eligible for promotion.
    """

    def test_meets_criteria_passes_all_gates_minimum_values(self) -> None:
        """Pattern passes all gates with minimum acceptable values."""
        # Gate 1: 5 injections (minimum)
        # Gate 2: 60% success rate (minimum)
        # Gate 3: 2 failure streak (below max)
        pattern = MockRecord({
            "injection_count_rolling_20": 5,
            "success_count_rolling_20": 3,  # 60%: 3/(3+2)
            "failure_count_rolling_20": 2,
            "failure_streak": 2,
        })
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_fails_first_gate_only(self) -> None:
        """Pattern fails only Gate 1 (injection count)."""
        pattern = MockRecord({
            "injection_count_rolling_20": 4,  # Below minimum
            "success_count_rolling_20": 4,  # 100% success
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_second_gate_only(self) -> None:
        """Pattern fails only Gate 2 (success rate)."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,  # Above minimum
            "success_count_rolling_20": 4,  # 40% success (below 60%)
            "failure_count_rolling_20": 6,
            "failure_streak": 0,  # No recent failures
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_third_gate_only(self) -> None:
        """Pattern fails only Gate 3 (failure streak)."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,  # Above minimum
            "success_count_rolling_20": 8,  # 80% success (above 60%)
            "failure_count_rolling_20": 2,
            "failure_streak": 3,  # At max
        })
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_all_gates(self) -> None:
        """Pattern fails all three gates."""
        pattern = MockRecord({
            "injection_count_rolling_20": 2,  # Below minimum
            "success_count_rolling_20": 1,  # 33% success (below 60%)
            "failure_count_rolling_20": 2,
            "failure_streak": 5,  # Above max
        })
        assert meets_promotion_criteria(pattern) is False


# =============================================================================
# Test Class: calculate_success_rate Helper Function
# =============================================================================


@pytest.mark.unit
class TestCalculateSuccessRate:
    """Tests for the calculate_success_rate helper function."""

    def test_calculates_50_percent_rate(self) -> None:
        """Calculates 50% success rate correctly."""
        pattern = MockRecord({
            "success_count_rolling_20": 5,
            "failure_count_rolling_20": 5,
        })
        assert calculate_success_rate(pattern) == 0.5

    def test_calculates_100_percent_rate(self) -> None:
        """Calculates 100% success rate correctly."""
        pattern = MockRecord({
            "success_count_rolling_20": 10,
            "failure_count_rolling_20": 0,
        })
        assert calculate_success_rate(pattern) == 1.0

    def test_calculates_0_percent_rate(self) -> None:
        """Calculates 0% success rate correctly."""
        pattern = MockRecord({
            "success_count_rolling_20": 0,
            "failure_count_rolling_20": 10,
        })
        assert calculate_success_rate(pattern) == 0.0

    def test_returns_zero_when_no_outcomes(self) -> None:
        """Returns 0.0 when no outcomes recorded (division by zero protection)."""
        pattern = MockRecord({
            "success_count_rolling_20": 0,
            "failure_count_rolling_20": 0,
        })
        assert calculate_success_rate(pattern) == 0.0

    def test_handles_none_values(self) -> None:
        """Handles None values by treating them as 0."""
        pattern = MockRecord({
            "success_count_rolling_20": None,
            "failure_count_rolling_20": None,
        })
        assert calculate_success_rate(pattern) == 0.0


# =============================================================================
# Test Class: build_gate_snapshot Helper Function
# =============================================================================


@pytest.mark.unit
class TestBuildGateSnapshot:
    """Tests for the build_gate_snapshot helper function."""

    def test_builds_snapshot_with_all_fields(self) -> None:
        """Builds snapshot with all fields populated correctly."""
        pattern = MockRecord({
            "injection_count_rolling_20": 15,
            "success_count_rolling_20": 12,
            "failure_count_rolling_20": 3,
            "failure_streak": 1,
        })

        snapshot = build_gate_snapshot(pattern)

        assert isinstance(snapshot, ModelGateSnapshot)
        assert snapshot.injection_count_rolling_20 == 15
        assert snapshot.failure_streak == 1
        assert snapshot.disabled is False  # Always False (filtered in SQL)
        assert abs(snapshot.success_rate_rolling_20 - 0.8) < 1e-9  # 12/15 = 0.8

    def test_snapshot_is_frozen_model(self) -> None:
        """Snapshot is immutable (frozen model)."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,
            "failure_count_rolling_20": 2,
            "failure_streak": 0,
        })

        snapshot = build_gate_snapshot(pattern)

        # Pydantic frozen models raise ValidationError on mutation (frozen=True)
        with pytest.raises(pydantic.ValidationError):
            snapshot.success_rate_rolling_20 = 0.0


# =============================================================================
# Test Class: _parse_update_count Helper Function
# =============================================================================


@pytest.mark.unit
class TestParseUpdateCount:
    """Tests for the _parse_update_count helper function.

    This function parses PostgreSQL status strings like "UPDATE 5" to extract
    the affected row count.
    """

    def test_parses_update_status(self) -> None:
        """Parses 'UPDATE N' format correctly."""
        assert _parse_update_count("UPDATE 5") == 5
        assert _parse_update_count("UPDATE 0") == 0
        assert _parse_update_count("UPDATE 100") == 100

    def test_parses_insert_status(self) -> None:
        """Parses 'INSERT oid N' format correctly (takes last number)."""
        assert _parse_update_count("INSERT 0 1") == 1
        assert _parse_update_count("INSERT 0 5") == 5

    def test_parses_delete_status(self) -> None:
        """Parses 'DELETE N' format correctly."""
        assert _parse_update_count("DELETE 3") == 3
        assert _parse_update_count("DELETE 0") == 0

    def test_empty_string_returns_zero(self) -> None:
        """Empty string returns 0."""
        assert _parse_update_count("") == 0

    def test_none_returns_zero(self) -> None:
        """None value returns 0."""
        assert _parse_update_count(None) == 0

    def test_single_word_returns_zero(self) -> None:
        """Single word (no count) returns 0."""
        assert _parse_update_count("UPDATE") == 0
        assert _parse_update_count("error") == 0

    def test_invalid_number_returns_zero(self) -> None:
        """Non-numeric count returns 0."""
        assert _parse_update_count("UPDATE abc") == 0
        assert _parse_update_count("UPDATE foo bar") == 0


# =============================================================================
# Test Class: check_and_promote_patterns - Dry Run Mode
# =============================================================================


@pytest.mark.unit
class TestDryRunMode:
    """Tests for check_and_promote_patterns in dry_run mode.

    When dry_run=True, the function should:
    - Return what WOULD be promoted
    - NOT execute any database mutations
    - NOT publish any Kafka events
    """

    @pytest.mark.asyncio
    async def test_dry_run_does_not_mutate_database(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Dry run does not call repository.execute() for promotion."""
        # Arrange: One eligible pattern
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=None,
            dry_run=True,
        )

        # Assert: Only fetch query executed (no UPDATE)
        execute_queries = [
            q for q in mock_repository.queries_executed
            if "UPDATE" in q[0]
        ]
        assert len(execute_queries) == 0
        assert result.dry_run is True
        assert result.patterns_eligible == 1

    @pytest.mark.asyncio
    async def test_dry_run_does_not_publish_events(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Dry run does not call producer.publish()."""
        # Arrange: One eligible pattern
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=True,
        )

        # Assert: No events published
        assert len(mock_producer.published_events) == 0
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_dry_run_result_has_promoted_at_none(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Dry run promotion results have promoted_at=None."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=True,
        )

        # Assert
        assert len(result.patterns_promoted) == 1
        promotion = result.patterns_promoted[0]
        assert promotion.dry_run is True
        assert promotion.promoted_at is None

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_counts(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Dry run returns correct checked/eligible counts."""
        # Arrange: 3 patterns - 2 eligible, 1 not
        mock_repository.add_pattern(
            PromotablePattern(
                id=uuid4(),
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )
        mock_repository.add_pattern(
            PromotablePattern(
                id=uuid4(),
                injection_count_rolling_20=10,
                success_count_rolling_20=7,
                failure_count_rolling_20=3,
                failure_streak=1,
            )
        )
        mock_repository.add_pattern(
            PromotablePattern(
                id=uuid4(),
                injection_count_rolling_20=3,  # Below minimum
                success_count_rolling_20=3,
                failure_count_rolling_20=0,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=True,
        )

        # Assert
        assert result.patterns_checked == 3
        assert result.patterns_eligible == 2
        assert len(result.patterns_promoted) == 2


# =============================================================================
# Test Class: check_and_promote_patterns - Actual Promotion
# =============================================================================


@pytest.mark.unit
class TestActualPromotion:
    """Tests for check_and_promote_patterns with dry_run=False.

    When dry_run=False, the function should:
    - Execute database UPDATE for each eligible pattern
    - Publish Kafka events for each promotion
    - Return results with promoted_at timestamps
    """

    @pytest.mark.asyncio
    async def test_promotes_eligible_patterns(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Eligible patterns are promoted in the database."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=None,
            dry_run=False,
        )

        # Assert
        assert result.dry_run is False
        assert result.patterns_promoted[0].dry_run is False
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_skips_ineligible_patterns(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Ineligible patterns are not promoted."""
        # Arrange: Pattern fails success rate gate
        pattern_id = uuid4()
        mock_repository.add_pattern(
            PromotablePattern(
                id=pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=4,  # 40% - below 60%
                failure_count_rolling_20=6,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )

        # Assert
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 0
        assert len(result.patterns_promoted) == 0
        assert mock_repository.patterns[pattern_id].status == "provisional"

    @pytest.mark.asyncio
    async def test_publishes_event_for_each_promotion(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Kafka event is published for each promoted pattern."""
        # Arrange: 2 eligible patterns
        id1, id2 = uuid4(), uuid4()
        mock_repository.add_pattern(
            PromotablePattern(
                id=id1,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )
        mock_repository.add_pattern(
            PromotablePattern(
                id=id2,
                injection_count_rolling_20=15,
                success_count_rolling_20=12,
                failure_count_rolling_20=3,
                failure_streak=1,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        assert len(result.patterns_promoted) == 2
        assert len(mock_producer.published_events) == 2

    @pytest.mark.asyncio
    async def test_promotion_result_has_timestamp(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Promotion results have promoted_at timestamp set."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        before = datetime.now(UTC)
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )
        after = datetime.now(UTC)

        # Assert
        promotion = result.patterns_promoted[0]
        assert promotion.promoted_at is not None
        assert before <= promotion.promoted_at <= after

    @pytest.mark.asyncio
    async def test_empty_repository_returns_zero_counts(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Empty repository returns zero counts."""
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )

        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0
        assert len(result.patterns_promoted) == 0


# =============================================================================
# Test Class: Event Payload Verification
# =============================================================================


@pytest.mark.unit
class TestEventPayloadVerification:
    """Tests verifying the structure and content of emitted Kafka events."""

    @pytest.mark.asyncio
    async def test_event_topic_uses_env_prefix(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event is published to topic with correct environment prefix."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            topic_env_prefix="prod",
            dry_run=False,
        )

        # Assert
        topic, _key, _value = mock_producer.published_events[0]
        assert topic.startswith("prod.")
        assert "pattern-promoted" in topic

    @pytest.mark.asyncio
    async def test_event_key_is_pattern_id(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event key is the pattern ID for partitioning."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        _topic, key, _value = mock_producer.published_events[0]
        assert key == str(sample_pattern_id)

    @pytest.mark.asyncio
    async def test_event_contains_gate_snapshot(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains success_rate_rolling_20 from gate snapshot."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,  # 80% success rate
                failure_count_rolling_20=2,
                failure_streak=1,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        _topic, _key, value = mock_producer.published_events[0]
        assert abs(value["success_rate_rolling_20"] - 0.8) < 1e-9

    @pytest.mark.asyncio
    async def test_event_contains_status_transition(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains from_status and to_status."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        _topic, _key, value = mock_producer.published_events[0]
        assert value["from_status"] == "provisional"
        assert value["to_status"] == "validated"
        assert value["event_type"] == "PatternPromoted"

    @pytest.mark.asyncio
    async def test_event_contains_correlation_id(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
    ) -> None:
        """Event payload contains correlation_id when provided."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            correlation_id=sample_correlation_id,
            dry_run=False,
        )

        # Assert
        _topic, _key, value = mock_producer.published_events[0]
        assert value["correlation_id"] == str(sample_correlation_id)

    @pytest.mark.asyncio
    async def test_event_contains_pattern_signature(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains pattern_signature."""
        # Arrange
        signature = "test_agent::action::context"
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                pattern_signature=signature,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        _topic, _key, value = mock_producer.published_events[0]
        assert value["pattern_signature"] == signature


# =============================================================================
# Test Class: promote_pattern Direct Tests
# =============================================================================


@pytest.mark.unit
class TestPromotePatternDirect:
    """Direct tests for the promote_pattern function."""

    @pytest.mark.asyncio
    async def test_promote_pattern_updates_database(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """promote_pattern executes UPDATE query."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )
        pattern_data = MockRecord({
            "id": sample_pattern_id,
            "pattern_signature": "test_sig",
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,
            "failure_count_rolling_20": 2,
            "failure_streak": 0,
        })

        # Act
        result = await promote_pattern(
            repository=mock_repository,
            producer=None,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
        )

        # Assert
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.dry_run is False
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_promote_pattern_without_producer_skips_event(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """promote_pattern with producer=None does not emit event."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )
        pattern_data = MockRecord({
            "id": sample_pattern_id,
            "pattern_signature": "test_sig",
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,
            "failure_count_rolling_20": 2,
            "failure_streak": 0,
        })

        # Act - No exception should be raised
        result = await promote_pattern(
            repository=mock_repository,
            producer=None,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
        )

        # Assert
        assert result.to_status == "validated"

    @pytest.mark.asyncio
    async def test_promote_pattern_returns_gate_snapshot(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """promote_pattern result includes gate snapshot."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=15,
                success_count_rolling_20=12,
                failure_count_rolling_20=3,
                failure_streak=1,
            )
        )
        pattern_data = MockRecord({
            "id": sample_pattern_id,
            "pattern_signature": "test_sig",
            "injection_count_rolling_20": 15,
            "success_count_rolling_20": 12,
            "failure_count_rolling_20": 3,
            "failure_streak": 1,
        })

        # Act
        result = await promote_pattern(
            repository=mock_repository,
            producer=None,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
        )

        # Assert
        assert result.gate_snapshot is not None
        assert result.gate_snapshot.injection_count_rolling_20 == 15
        assert result.gate_snapshot.failure_streak == 1
        assert abs(result.gate_snapshot.success_rate_rolling_20 - 0.8) < 1e-9


# =============================================================================
# Test Class: Protocol Compliance
# =============================================================================


@pytest.mark.unit
class TestProtocolCompliance:
    """Tests verifying mock implementations satisfy protocols."""

    def test_mock_repository_is_protocol_compliant(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """MockPatternRepository satisfies ProtocolPatternRepository protocol."""
        assert isinstance(mock_repository, ProtocolPatternRepository)

    def test_mock_producer_is_protocol_compliant(
        self,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """MockKafkaPublisher satisfies ProtocolKafkaPublisher protocol."""
        assert isinstance(mock_producer, ProtocolKafkaPublisher)


# =============================================================================
# Test Class: Result Model Validation
# =============================================================================


@pytest.mark.unit
class TestResultModelValidation:
    """Tests verifying result models contain correct data."""

    @pytest.mark.asyncio
    async def test_promotion_check_result_has_all_fields(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelPromotionCheckResult contains all expected fields."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            correlation_id=sample_correlation_id,
            dry_run=False,
        )

        # Assert
        assert isinstance(result, ModelPromotionCheckResult)
        assert result.dry_run is False
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        assert len(result.patterns_promoted) == 1
        assert result.correlation_id == sample_correlation_id

    @pytest.mark.asyncio
    async def test_promotion_result_has_all_fields(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """ModelPromotionResult contains all expected fields."""
        # Arrange
        signature = "test_signature"
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                pattern_signature=signature,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )

        # Assert
        promotion = result.patterns_promoted[0]
        assert isinstance(promotion, ModelPromotionResult)
        assert promotion.pattern_id == sample_pattern_id
        assert promotion.pattern_signature == signature
        assert promotion.from_status == "provisional"
        assert promotion.to_status == "validated"
        assert promotion.promoted_at is not None
        assert promotion.reason == "auto_promote_rolling_window"
        assert promotion.gate_snapshot is not None
        assert promotion.dry_run is False


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_pattern_already_promoted_not_updated_again(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Pattern with status='validated' is not included in fetch results."""
        # Arrange: Pattern already validated
        pattern_id = uuid4()
        mock_repository.add_pattern(
            PromotablePattern(
                id=pattern_id,
                status="validated",  # Already promoted
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )

        # Assert: Not found in provisional query
        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0

    @pytest.mark.asyncio
    async def test_non_current_pattern_not_checked(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Pattern with is_current=False is not included in fetch results."""
        # Arrange: Pattern not current version
        pattern_id = uuid4()
        mock_repository.add_pattern(
            PromotablePattern(
                id=pattern_id,
                is_current=False,  # Old version
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=False,
        )

        # Assert: Not found in query
        assert result.patterns_checked == 0

    @pytest.mark.asyncio
    async def test_large_batch_of_patterns(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Handles large batch of patterns correctly."""
        # Arrange: 100 patterns, 50 eligible
        for i in range(100):
            mock_repository.add_pattern(
                PromotablePattern(
                    id=uuid4(),
                    injection_count_rolling_20=10 if i % 2 == 0 else 3,  # Alternating eligibility
                    success_count_rolling_20=8 if i % 2 == 0 else 3,
                    failure_count_rolling_20=2,
                    failure_streak=0,
                )
            )

        # Act
        result = await check_and_promote_patterns(
            repository=mock_repository,
            dry_run=True,
        )

        # Assert
        assert result.patterns_checked == 100
        assert result.patterns_eligible == 50

    def test_pattern_with_missing_keys_handled_gracefully(self) -> None:
        """Pattern dict with missing keys is handled gracefully."""
        # Empty pattern dict - all values default to 0
        pattern = MockRecord({})
        assert meets_promotion_criteria(pattern) is False

    def test_pattern_with_extra_keys_handled_gracefully(self) -> None:
        """Pattern dict with extra keys is handled correctly."""
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,
            "failure_count_rolling_20": 2,
            "failure_streak": 0,
            "extra_field": "ignored",
            "another_extra": 123,
        })
        assert meets_promotion_criteria(pattern) is True


# =============================================================================
# Test Class: Configurable Thresholds
# =============================================================================


@pytest.mark.unit
class TestConfigurableThresholds:
    """Tests for configurable promotion thresholds.

    The handler functions accept optional threshold parameters that override
    the default constants:
    - min_injection_count (default: 5)
    - min_success_rate (default: 0.6)
    - max_failure_streak (default: 3)

    These tests verify that custom thresholds work correctly for both
    stricter and more lenient configurations.
    """

    def test_custom_min_injection_count_more_strict(self) -> None:
        """Pattern passes default threshold (5) but fails custom stricter threshold (10).

        A pattern with 7 injections:
        - Passes default: 7 >= 5
        - Fails custom: 7 < 10
        """
        pattern = MockRecord({
            "injection_count_rolling_20": 7,
            "success_count_rolling_20": 6,  # 86% success rate
            "failure_count_rolling_20": 1,
            "failure_streak": 0,
        })

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold
        assert meets_promotion_criteria(
            pattern,
            min_injection_count=10,
        ) is False

    def test_custom_min_injection_count_more_lenient(self) -> None:
        """Pattern fails default threshold (5) but passes custom lenient threshold (2).

        A pattern with 3 injections:
        - Fails default: 3 < 5
        - Passes custom: 3 >= 2
        """
        pattern = MockRecord({
            "injection_count_rolling_20": 3,
            "success_count_rolling_20": 3,  # 100% success rate
            "failure_count_rolling_20": 0,
            "failure_streak": 0,
        })

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert meets_promotion_criteria(
            pattern,
            min_injection_count=2,
        ) is True

    def test_custom_min_success_rate_more_strict(self) -> None:
        """Pattern passes default threshold (0.6) but fails custom stricter threshold (0.8).

        A pattern with 65% success rate:
        - Passes default: 0.65 >= 0.6
        - Fails custom: 0.65 < 0.8
        """
        # 65% success rate: 13 successes, 7 failures (13/20 = 0.65)
        pattern = MockRecord({
            "injection_count_rolling_20": 20,
            "success_count_rolling_20": 13,
            "failure_count_rolling_20": 7,
            "failure_streak": 0,
        })

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold
        assert meets_promotion_criteria(
            pattern,
            min_success_rate=0.8,
        ) is False

    def test_custom_min_success_rate_more_lenient(self) -> None:
        """Pattern fails default threshold (0.6) but passes custom lenient threshold (0.4).

        A pattern with 50% success rate:
        - Fails default: 0.5 < 0.6
        - Passes custom: 0.5 >= 0.4
        """
        # 50% success rate: 5 successes, 5 failures
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 5,
            "failure_count_rolling_20": 5,
            "failure_streak": 0,
        })

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert meets_promotion_criteria(
            pattern,
            min_success_rate=0.4,
        ) is True

    def test_custom_max_failure_streak_more_strict(self) -> None:
        """Pattern passes default threshold (3) but fails custom stricter threshold (2).

        A pattern with 2 consecutive failures:
        - Passes default: 2 < 3
        - Fails custom: 2 >= 2
        """
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 8,  # 80% success rate
            "failure_count_rolling_20": 2,
            "failure_streak": 2,
        })

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold (max_failure_streak=2 means 2+ fails)
        assert meets_promotion_criteria(
            pattern,
            max_failure_streak=2,
        ) is False

    def test_custom_max_failure_streak_more_lenient(self) -> None:
        """Pattern fails default threshold (3) but passes custom lenient threshold (5).

        A pattern with 4 consecutive failures:
        - Fails default: 4 >= 3
        - Passes custom: 4 < 5
        """
        pattern = MockRecord({
            "injection_count_rolling_20": 10,
            "success_count_rolling_20": 7,  # 70% success rate
            "failure_count_rolling_20": 3,
            "failure_streak": 4,
        })

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert meets_promotion_criteria(
            pattern,
            max_failure_streak=5,
        ) is True

    @pytest.mark.asyncio
    async def test_check_and_promote_with_custom_thresholds(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Patterns NOT promoted with defaults ARE promoted with lenient thresholds.

        Sets up patterns that fail default thresholds but pass lenient ones:
        - Pattern 1: 3 injections (fails default 5, passes custom 2)
        - Pattern 2: 50% success (fails default 0.6, passes custom 0.4)
        - Pattern 3: 4 failure streak (fails default 3, passes custom 5)

        With default thresholds: 0 patterns promoted
        With lenient thresholds: 3 patterns promoted
        """
        # Pattern 1: Low injection count (fails default, passes lenient)
        pattern_1 = PromotablePattern(
            id=uuid4(),
            pattern_signature="low_injection_pattern",
            injection_count_rolling_20=3,  # < 5 (default), >= 2 (lenient)
            success_count_rolling_20=3,  # 100% success rate
            failure_count_rolling_20=0,
            failure_streak=0,
        )

        # Pattern 2: Low success rate (fails default, passes lenient)
        pattern_2 = PromotablePattern(
            id=uuid4(),
            pattern_signature="low_success_pattern",
            injection_count_rolling_20=10,  # >= 2
            success_count_rolling_20=5,  # 50% < 0.6, >= 0.4
            failure_count_rolling_20=5,
            failure_streak=0,
        )

        # Pattern 3: High failure streak (fails default, passes lenient)
        pattern_3 = PromotablePattern(
            id=uuid4(),
            pattern_signature="high_streak_pattern",
            injection_count_rolling_20=10,  # >= 2
            success_count_rolling_20=7,  # 70% >= 0.4
            failure_count_rolling_20=3,
            failure_streak=4,  # >= 3 (default), < 5 (lenient)
        )

        mock_repository.add_pattern(pattern_1)
        mock_repository.add_pattern(pattern_2)
        mock_repository.add_pattern(pattern_3)

        # Act with DEFAULT thresholds - none should be promoted
        result_default = await check_and_promote_patterns(
            repository=mock_repository,
            producer=None,
            dry_run=True,
        )

        # Assert: No patterns eligible with defaults
        assert result_default.patterns_checked == 3
        assert result_default.patterns_eligible == 0
        assert len(result_default.patterns_promoted) == 0

        # Act with LENIENT thresholds - all should be promoted
        result_lenient = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
            min_injection_count=2,
            min_success_rate=0.4,
            max_failure_streak=5,
        )

        # Assert: All patterns eligible with lenient thresholds
        assert result_lenient.patterns_checked == 3
        assert result_lenient.patterns_eligible == 3
        assert len(result_lenient.patterns_promoted) == 3
        assert len(mock_producer.published_events) == 3

        # Verify all patterns were actually promoted in the repository
        assert mock_repository.patterns[pattern_1.id].status == "validated"
        assert mock_repository.patterns[pattern_2.id].status == "validated"
        assert mock_repository.patterns[pattern_3.id].status == "validated"
