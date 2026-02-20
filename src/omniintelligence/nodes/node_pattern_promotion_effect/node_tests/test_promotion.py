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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pydantic
import pytest

from omniintelligence.constants import TOPIC_PATTERN_LIFECYCLE_CMD_V1
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    MAX_FAILURE_STREAK,
    MIN_INJECTION_COUNT,
    MIN_SUCCESS_RATE,
    build_gate_snapshot,
    calculate_success_rate,
    check_and_promote_patterns,
    meets_promotion_criteria,
    promote_pattern,
)
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)
from omniintelligence.nodes.node_pattern_promotion_effect.registry.registry_pattern_promotion_effect import (
    RegistryPatternPromotionEffect,
    RegistryPromotionHandlers,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


class MockRecord(dict[str, Any]):
    """Dict-like object that mimics asyncpg.Record behavior.

    asyncpg.Record supports both dict-style access (record["column"]) and
    attribute access (record.column). This mock provides the same interface
    for testing. Extends ``dict[str, Any]`` so it satisfies
    ``Mapping[str, Any]`` as required by ``ProtocolPatternRepository``.
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
        self.queries_executed: list[tuple[str, tuple[object, ...]]] = []

    def add_pattern(self, pattern: PromotablePattern) -> None:
        """Add a pattern to the mock database."""
        self.patterns[pattern.id] = pattern

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        """Execute a query and return results as MockRecord objects.

        Simulates asyncpg fetch() behavior. Supports the specific queries
        used by the promotion handlers.
        """
        self.queries_executed.append((query, args))

        # Handle: Fetch provisional patterns eligible for promotion check
        if "learned_patterns" in query and "provisional" in query:
            results: list[Mapping[str, Any]] = []
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

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        """Execute a query and return first row, or None.

        Simulates asyncpg fetchrow() behavior.
        """
        results = await self.fetch(query, *args)
        return results[0] if results else None

    async def execute(self, query: str, *args: object) -> str:
        """Execute a query and return status string.

        Simulates asyncpg execute() behavior. Implements the actual
        promotion update logic.
        """
        self.queries_executed.append((query, args))

        # Handle: Promote a single pattern
        if "UPDATE learned_patterns" in query and "validated" in query:
            pattern_id = args[0]
            assert isinstance(pattern_id, UUID)
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 0,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_injection_count_below_minimum(self) -> None:
        """Pattern with 4 injections (below minimum 5) fails Gate 1."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 4,
                "success_count_rolling_20": 4,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_injection_count_at_minimum(self) -> None:
        """Pattern with exactly 5 injections (at minimum) passes Gate 1."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 5,
                "success_count_rolling_20": 4,  # 80% success rate
                "failure_count_rolling_20": 1,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_injection_count_above_minimum(self) -> None:
        """Pattern with 20 injections (above minimum) passes Gate 1."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 20,
                "success_count_rolling_20": 15,  # 75% success rate
                "failure_count_rolling_20": 5,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_handles_none_injection_count(self) -> None:
        """Pattern with None injection count is treated as 0."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": None,
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 5,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_success_rate_at_59_percent(self) -> None:
        """Pattern with ~59% success rate (just below 60%) fails Gate 2."""
        # 59.4% success rate: 19 successes, 13 failures (19/32 = 0.594)
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 32,
                "success_count_rolling_20": 19,
                "failure_count_rolling_20": 13,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_success_rate_at_60_percent(self) -> None:
        """Pattern with exactly 60% success rate passes Gate 2."""
        # Exactly 60%: 6 successes, 4 failures
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 6,
                "failure_count_rolling_20": 4,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_success_rate_above_60_percent(self) -> None:
        """Pattern with 80% success rate passes Gate 2."""
        # 80% success rate: 8 successes, 2 failures
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_100_percent_success_rate(self) -> None:
        """Pattern with 100% success rate passes Gate 2."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_fails_when_no_outcomes_recorded(self) -> None:
        """Pattern with 0 successes and 0 failures fails (division by zero protection)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 5,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_handles_none_success_count(self) -> None:
        """Pattern with None success count is treated as 0."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": None,
                "failure_count_rolling_20": 5,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_handles_none_failure_count(self) -> None:
        """Pattern with None failure count is treated as 0."""
        # 100% success rate with None failures treated as 0
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": None,
                "failure_streak": 0,
            }
        )
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,  # 70% success rate
                "failure_count_rolling_20": 3,
                "failure_streak": 3,  # At max
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_when_failure_streak_above_max(self) -> None:
        """Pattern with 5 consecutive failures (above max) fails Gate 3."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": 5,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_passes_when_failure_streak_below_max(self) -> None:
        """Pattern with 2 consecutive failures (below max) passes Gate 3."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": 2,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_failure_streak_is_zero(self) -> None:
        """Pattern with 0 consecutive failures passes Gate 3."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_passes_when_failure_streak_is_one(self) -> None:
        """Pattern with 1 consecutive failure passes Gate 3."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": 1,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_handles_none_failure_streak(self) -> None:
        """Pattern with None failure streak is treated as 0."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": None,
            }
        )
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 5,
                "success_count_rolling_20": 3,  # 60%: 3/(3+2)
                "failure_count_rolling_20": 2,
                "failure_streak": 2,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_meets_criteria_fails_first_gate_only(self) -> None:
        """Pattern fails only Gate 1 (injection count)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 4,  # Below minimum
                "success_count_rolling_20": 4,  # 100% success
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_second_gate_only(self) -> None:
        """Pattern fails only Gate 2 (success rate)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,  # Above minimum
                "success_count_rolling_20": 4,  # 40% success (below 60%)
                "failure_count_rolling_20": 6,
                "failure_streak": 0,  # No recent failures
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_third_gate_only(self) -> None:
        """Pattern fails only Gate 3 (failure streak)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,  # Above minimum
                "success_count_rolling_20": 8,  # 80% success (above 60%)
                "failure_count_rolling_20": 2,
                "failure_streak": 3,  # At max
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_meets_criteria_fails_all_gates(self) -> None:
        """Pattern fails all three gates."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 2,  # Below minimum
                "success_count_rolling_20": 1,  # 33% success (below 60%)
                "failure_count_rolling_20": 2,
                "failure_streak": 5,  # Above max
            }
        )
        assert meets_promotion_criteria(pattern) is False


# =============================================================================
# Test Class: calculate_success_rate Helper Function
# =============================================================================


@pytest.mark.unit
class TestCalculateSuccessRate:
    """Tests for the calculate_success_rate helper function."""

    def test_calculates_50_percent_rate(self) -> None:
        """Calculates 50% success rate correctly."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 5,
            }
        )
        assert calculate_success_rate(pattern) == 0.5

    def test_calculates_100_percent_rate(self) -> None:
        """Calculates 100% success rate correctly."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": 0,
            }
        )
        assert calculate_success_rate(pattern) == 1.0

    def test_calculates_0_percent_rate(self) -> None:
        """Calculates 0% success rate correctly."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 10,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_returns_zero_when_no_outcomes(self) -> None:
        """Returns 0.0 when no outcomes recorded (division by zero protection)."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_handles_none_values(self) -> None:
        """Handles None values by treating them as 0."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": None,
                "failure_count_rolling_20": None,
            }
        )
        assert calculate_success_rate(pattern) == 0.0


# =============================================================================
# Test Class: build_gate_snapshot Helper Function
# =============================================================================


@pytest.mark.unit
class TestBuildGateSnapshot:
    """Tests for the build_gate_snapshot helper function."""

    def test_builds_snapshot_with_all_fields(self) -> None:
        """Builds snapshot with all fields populated correctly."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 12,
                "failure_count_rolling_20": 3,
                "failure_streak": 1,
            }
        )

        snapshot = build_gate_snapshot(pattern)

        assert isinstance(snapshot, ModelGateSnapshot)
        assert snapshot.injection_count_rolling_20 == 15
        assert snapshot.failure_streak == 1
        assert snapshot.disabled is False  # Always False (filtered in SQL)
        assert abs(snapshot.success_rate_rolling_20 - 0.8) < 1e-9  # 12/15 = 0.8

    def test_snapshot_is_frozen_model(self) -> None:
        """Snapshot is immutable (frozen model)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )

        snapshot = build_gate_snapshot(pattern)

        # Pydantic frozen models raise ValidationError on mutation (frozen=True)
        with pytest.raises(pydantic.ValidationError):
            snapshot.success_rate_rolling_20 = 0.0


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
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
            dry_run=True,
        )

        # Assert: Only fetch query executed (no UPDATE)
        execute_queries = [
            q for q in mock_repository.queries_executed if "UPDATE" in q[0]
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
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
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
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
            dry_run=True,
        )

        # Assert
        assert result.patterns_checked == 3
        assert result.patterns_eligible == 2
        assert len(result.patterns_promoted) == 2


# =============================================================================
# Test Class: check_and_promote_patterns - Actual Promotion (Event-Driven)
# =============================================================================


@pytest.mark.unit
class TestActualPromotion:
    """Tests for check_and_promote_patterns with dry_run=False.

    **OMN-1805 Event-Driven Architecture:**
    When dry_run=False, the function now:
    - Does NOT execute database UPDATE directly
    - Publishes ModelPatternLifecycleEvent to Kafka for reducer processing
    - Returns results with promoted_at timestamps (request time, not completion time)

    The actual database update happens asynchronously via the reducer -> effect pipeline.
    """

    @pytest.mark.asyncio
    async def test_emits_lifecycle_event_for_eligible_patterns(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Eligible patterns trigger lifecycle event emission (not direct DB update).

        NOTE: With OMN-1805 event-driven architecture, the handler emits events
        to Kafka instead of directly updating the database. The mock repository
        status remains unchanged since no direct SQL UPDATE occurs.
        """
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
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        assert result.dry_run is False
        assert len(result.patterns_promoted) == 1
        assert result.patterns_promoted[0].dry_run is False
        # Event was emitted to Kafka for reducer processing
        assert len(mock_producer.published_events) == 1
        # NOTE: Database status unchanged - actual update happens via reducer/effect
        assert mock_repository.patterns[sample_pattern_id].status == "provisional"

    @pytest.mark.asyncio
    async def test_skips_ineligible_patterns(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 0
        assert len(result.patterns_promoted) == 0
        assert mock_repository.patterns[pattern_id].status == "provisional"

    @pytest.mark.asyncio
    async def test_publishes_lifecycle_event_for_each_promotion(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Kafka lifecycle event is published for each promoted pattern."""
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
    async def test_promotion_result_has_request_timestamp(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Promotion results have promoted_at timestamp set (request time)."""
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
            producer=mock_producer,
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
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Empty repository returns zero counts."""
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0
        assert len(result.patterns_promoted) == 0


# =============================================================================
# Test Class: Lifecycle Event Payload Verification (OMN-1805)
# =============================================================================


@pytest.mark.unit
class TestEventPayloadVerification:
    """Tests verifying the structure and content of emitted Kafka lifecycle events.

    OMN-1805: Events are now ModelPatternLifecycleEvent published to the
    pattern-lifecycle-transition command topic for reducer processing.
    """

    @pytest.mark.asyncio
    async def test_event_topic_uses_lifecycle_topic_constant(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event is published to the canonical lifecycle command topic constant."""
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
        topic, _key, _value = mock_producer.published_events[0]
        assert topic == TOPIC_PATTERN_LIFECYCLE_CMD_V1

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
    async def test_event_contains_gate_snapshot_as_dict(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains gate_snapshot with success_rate."""
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
        gate_snapshot = value["gate_snapshot"]
        assert abs(gate_snapshot["success_rate_rolling_20"] - 0.8) < 1e-9
        assert gate_snapshot["injection_count_rolling_20"] == 10
        assert gate_snapshot["failure_streak"] == 1

    @pytest.mark.asyncio
    async def test_event_contains_lifecycle_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains lifecycle-specific fields."""
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
        assert value["event_type"] == "PatternLifecycleEvent"
        assert value["trigger"] == "promote"
        assert value["actor"] == "promotion_handler"
        assert value["actor_type"] == "handler"
        assert "request_id" in value  # Idempotency key
        assert "occurred_at" in value

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
    async def test_event_reason_contains_gate_values(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event reason field contains human-readable gate values."""
        # Arrange
        mock_repository.add_pattern(
            PromotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
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
        reason = value["reason"]
        assert "Auto-promoted" in reason
        assert "success_rate=" in reason
        assert "injection_count=" in reason
        assert "failure_streak=" in reason


# =============================================================================
# Test Class: promote_pattern Direct Tests (OMN-1805 Event-Driven)
# =============================================================================


@pytest.mark.unit
class TestPromotePatternDirect:
    """Direct tests for the promote_pattern function.

    OMN-1805: promote_pattern now emits a ModelPatternLifecycleEvent to Kafka
    instead of directly updating the database. The actual status update happens
    asynchronously via the reducer -> effect pipeline.
    """

    @pytest.mark.asyncio
    async def test_promote_pattern_emits_lifecycle_event(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """promote_pattern emits lifecycle event to Kafka (not direct DB update)."""
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
        pattern_data = MockRecord(
            {
                "id": sample_pattern_id,
                "pattern_signature": "test_sig",
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )

        # Act
        result = await promote_pattern(
            producer=mock_producer,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
        )

        # Assert
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.dry_run is False
        # Event emitted to Kafka
        assert len(mock_producer.published_events) == 1
        # NOTE: Database status unchanged - actual update happens via reducer/effect
        assert mock_repository.patterns[sample_pattern_id].status == "provisional"

    @pytest.mark.asyncio
    async def test_promote_pattern_returns_gate_snapshot(
        self,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """promote_pattern result includes gate snapshot."""
        # Arrange
        pattern_data = MockRecord(
            {
                "id": sample_pattern_id,
                "pattern_signature": "test_sig",
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 12,
                "failure_count_rolling_20": 3,
                "failure_streak": 1,
            }
        )

        # Act
        result = await promote_pattern(
            producer=mock_producer,
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
# Test Class: RegistryPatternPromotionEffect Smoke Tests
# =============================================================================


@pytest.mark.unit
class TestRegistryPatternPromotionEffectSmoke:
    """Smoke tests for RegistryPatternPromotionEffect.create_registry.

    Verifies that create_registry succeeds with valid mock dependencies and
    returns a properly wired RegistryPromotionHandlers. These tests cover the
    happy path through the registry factory — the constructor-enforced producer
    requirement is validated by mypy at the type level, not at runtime.

    Note: None-argument rejection is enforced at the type level (mypy strict);
    no runtime guard exists. Runtime misuse manifests on first call, not at
    registry creation.
    """

    @pytest.fixture(autouse=True)
    def clear_registry(self) -> object:
        """Clear module-level registry state before and after each test."""
        RegistryPatternPromotionEffect.clear()
        yield
        RegistryPatternPromotionEffect.clear()

    def test_create_registry_succeeds_with_valid_dependencies(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """create_registry returns a RegistryPromotionHandlers with valid deps."""
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        assert isinstance(registry, RegistryPromotionHandlers)

    def test_create_registry_wires_check_and_promote_handler(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """check_and_promote attribute is a callable after create_registry."""
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        assert callable(registry.check_and_promote)

    def test_create_registry_handler_accessible_by_operation_name(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """get_handler('check_and_promote_patterns') returns a callable."""
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        handler = registry.get_handler("check_and_promote_patterns")
        assert handler is not None
        assert callable(handler)

    def test_create_registry_unknown_operation_returns_none(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """get_handler returns None for unknown operation names."""
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        assert registry.get_handler("nonexistent_operation") is None

    def test_create_registry_stored_in_module_level_state(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """create_registry stores the registry so get_registry() returns it."""
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        stored = RegistryPatternPromotionEffect.get_registry()
        assert stored is registry

    def test_registry_is_frozen_after_creation(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """RegistryPromotionHandlers is a frozen dataclass — mutation raises."""
        import dataclasses

        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=mock_producer,
        )

        with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
            registry.check_and_promote = lambda _: None  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_create_registry_with_none_producer_fails_at_use_time(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Passing None as producer binds silently but fails at use time with a structured error result, not a raised exception.

        This documents the runtime behavior honestly: create_registry accepts
        None (bypassing mypy with cast) without raising. None producer causes
        AttributeError inside promote_pattern which is caught by the per-pattern
        exception handler and recorded as a structured failure
        (patterns_failed > 0), not a raised exception.

        Note: None-argument rejection is enforced at the type level (mypy
        strict); no runtime guard exists.
        """
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=mock_repository,
            producer=cast(
                ProtocolKafkaPublisher, None
            ),  # cast used intentionally to bypass mypy for runtime behavior documentation — do not use cast(Protocol, None) in production code
        )

        # Registry creation succeeds silently — no error yet
        assert registry is not None
        assert callable(registry.check_and_promote)

        # Add a promotable pattern so the handler reaches the publish() call
        from omniintelligence.nodes.node_pattern_promotion_effect.models import (
            ModelPromotionCheckRequest,
        )

        mock_repository.add_pattern(
            PromotablePattern(
                id=uuid4(),
                injection_count_rolling_20=10,
                success_count_rolling_20=8,
                failure_count_rolling_20=2,
                failure_streak=0,
            )
        )

        request = ModelPromotionCheckRequest(dry_run=False)

        # Failure is recorded as a structured result — no exception raised
        result = await registry.check_and_promote(request)
        assert result.patterns_failed > 0
        assert (
            sum(1 for r in result.patterns_promoted if r.promoted_at is not None) == 0
        )

    @pytest.mark.asyncio
    async def test_create_registry_with_none_repository_fails_at_use_time(
        self,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Passing None as repository binds silently but fails at use time with a structured error result, not a raised exception.

        This documents the runtime behavior symmetrically with the None-producer
        test: create_registry accepts None (bypassing mypy with cast) without
        raising. The AttributeError from ``repository.fetch()`` is caught by
        the top-level fetch guard in ``check_and_promote_patterns``, which
        returns a structured result with an error_message rather than re-raising.

        Note: None-argument rejection is enforced at the type level (mypy
        strict); no runtime guard exists.
        """
        registry = RegistryPatternPromotionEffect.create_registry(
            repository=cast(ProtocolPatternRepository, None),
            producer=mock_producer,
        )

        # Registry creation succeeds silently — no error yet
        assert registry is not None
        assert callable(registry.check_and_promote)

        from omniintelligence.nodes.node_pattern_promotion_effect.models import (
            ModelPromotionCheckRequest,
        )

        request = ModelPromotionCheckRequest(dry_run=False)

        # Failure is recorded as a structured result — no exception raised
        result = await registry.check_and_promote(request)
        assert result.patterns_failed == 0  # fetch failed before any pattern loop
        assert result.patterns_promoted == []
        assert result.error_message is not None


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
        mock_producer: MockKafkaPublisher,
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

        # Act - Need producer for actual promotion (OMN-1805)
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
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
        mock_producer: MockKafkaPublisher,
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

        # Act - Need producer for actual promotion (OMN-1805)
        result = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=False,
        )

        # Assert
        promotion = result.patterns_promoted[0]
        assert isinstance(promotion, ModelPromotionResult)
        assert promotion.pattern_id == sample_pattern_id
        assert promotion.pattern_signature == signature
        assert promotion.from_status == "provisional"
        assert promotion.to_status == "validated"
        assert promotion.promoted_at is not None  # Request timestamp
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
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
            dry_run=False,
        )

        # Assert: Not found in provisional query
        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0

    @pytest.mark.asyncio
    async def test_non_current_pattern_not_checked(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
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
            producer=mock_producer,
            dry_run=False,
        )

        # Assert: Not found in query
        assert result.patterns_checked == 0

    @pytest.mark.asyncio
    async def test_large_batch_of_patterns(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Handles large batch of patterns correctly."""
        # Arrange: 100 patterns, 50 eligible
        for i in range(100):
            mock_repository.add_pattern(
                PromotablePattern(
                    id=uuid4(),
                    injection_count_rolling_20=10
                    if i % 2 == 0
                    else 3,  # Alternating eligibility
                    success_count_rolling_20=8 if i % 2 == 0 else 3,
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "extra_field": "ignored",
                "another_extra": 123,
            }
        )
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
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 7,
                "success_count_rolling_20": 6,  # 86% success rate
                "failure_count_rolling_20": 1,
                "failure_streak": 0,
            }
        )

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold
        assert (
            meets_promotion_criteria(
                pattern,
                min_injection_count=10,
            )
            is False
        )

    def test_custom_min_injection_count_more_lenient(self) -> None:
        """Pattern fails default threshold (5) but passes custom lenient threshold (2).

        A pattern with 3 injections:
        - Fails default: 3 < 5
        - Passes custom: 3 >= 2
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 3,
                "success_count_rolling_20": 3,  # 100% success rate
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert (
            meets_promotion_criteria(
                pattern,
                min_injection_count=2,
            )
            is True
        )

    def test_custom_min_success_rate_more_strict(self) -> None:
        """Pattern passes default threshold (0.6) but fails custom stricter threshold (0.8).

        A pattern with 65% success rate:
        - Passes default: 0.65 >= 0.6
        - Fails custom: 0.65 < 0.8
        """
        # 65% success rate: 13 successes, 7 failures (13/20 = 0.65)
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 20,
                "success_count_rolling_20": 13,
                "failure_count_rolling_20": 7,
                "failure_streak": 0,
            }
        )

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold
        assert (
            meets_promotion_criteria(
                pattern,
                min_success_rate=0.8,
            )
            is False
        )

    def test_custom_min_success_rate_more_lenient(self) -> None:
        """Pattern fails default threshold (0.6) but passes custom lenient threshold (0.4).

        A pattern with 50% success rate:
        - Fails default: 0.5 < 0.6
        - Passes custom: 0.5 >= 0.4
        """
        # 50% success rate: 5 successes, 5 failures
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 5,
                "failure_streak": 0,
            }
        )

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert (
            meets_promotion_criteria(
                pattern,
                min_success_rate=0.4,
            )
            is True
        )

    def test_custom_max_failure_streak_more_strict(self) -> None:
        """Pattern passes default threshold (3) but fails custom stricter threshold (2).

        A pattern with 2 consecutive failures:
        - Passes default: 2 < 3
        - Fails custom: 2 >= 2
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,  # 80% success rate
                "failure_count_rolling_20": 2,
                "failure_streak": 2,
            }
        )

        # Passes with default threshold
        assert meets_promotion_criteria(pattern) is True

        # Fails with stricter threshold (max_failure_streak=2 means 2+ fails)
        assert (
            meets_promotion_criteria(
                pattern,
                max_failure_streak=2,
            )
            is False
        )

    def test_custom_max_failure_streak_more_lenient(self) -> None:
        """Pattern fails default threshold (3) but passes custom lenient threshold (5).

        A pattern with 4 consecutive failures:
        - Fails default: 4 >= 3
        - Passes custom: 4 < 5
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,  # 70% success rate
                "failure_count_rolling_20": 3,
                "failure_streak": 4,
            }
        )

        # Fails with default threshold
        assert meets_promotion_criteria(pattern) is False

        # Passes with lenient threshold
        assert (
            meets_promotion_criteria(
                pattern,
                max_failure_streak=5,
            )
            is True
        )

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

        With default thresholds: 0 patterns eligible
        With lenient thresholds: 3 patterns eligible + 3 lifecycle events emitted

        NOTE (OMN-1805): Database status is NOT updated directly. The handler emits
        lifecycle events to Kafka, and the reducer/effect pipeline handles the update.
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

        # Act with DEFAULT thresholds - none should be eligible
        result_default = await check_and_promote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            dry_run=True,
        )

        # Assert: No patterns eligible with defaults
        assert result_default.patterns_checked == 3
        assert result_default.patterns_eligible == 0
        assert len(result_default.patterns_promoted) == 0

        # Act with LENIENT thresholds - all should be eligible and emit events
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
        # All lifecycle events emitted to Kafka
        assert len(mock_producer.published_events) == 3

        # NOTE: Database status remains 'provisional' - actual update is async via reducer
        assert mock_repository.patterns[pattern_1.id].status == "provisional"
        assert mock_repository.patterns[pattern_2.id].status == "provisional"
        assert mock_repository.patterns[pattern_3.id].status == "provisional"


# =============================================================================
# Test Class: Edge Cases - Numerical Robustness
# =============================================================================


@pytest.mark.unit
class TestEdgeCasesNumerical:
    """Tests for numerical edge cases and defensive handling.

    These tests verify that the promotion logic handles unusual or invalid
    input gracefully, including:
    - Negative values (defensive check)
    - Zero injection count with non-zero outcomes (data inconsistency)
    - Very precise boundary conditions
    - Large numbers (no overflow)
    """

    # -------------------------------------------------------------------------
    # Negative Value Tests (Defensive Checks)
    # -------------------------------------------------------------------------

    def test_negative_injection_count_fails_gate(self) -> None:
        """Pattern with negative injection count fails Gate 1.

        Negative values should not be possible in production, but if they
        somehow occur, the pattern should fail the injection count gate.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": -5,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )
        # -5 < 5 (minimum), so Gate 1 fails
        assert meets_promotion_criteria(pattern) is False

    def test_negative_success_count_affects_success_rate(self) -> None:
        """Pattern with negative success count produces invalid success rate.

        With negative success count, the calculated rate will be negative or
        otherwise invalid. The pattern should fail the success rate gate.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": -3,
                "failure_count_rolling_20": 10,
                "failure_streak": 0,
            }
        )
        # success_rate = -3 / (-3 + 10) = -3/7 ≈ -0.43 < 0.6, Gate 2 fails
        assert meets_promotion_criteria(pattern) is False

    def test_negative_failure_count_inflates_success_rate(self) -> None:
        """Pattern with negative failure count is clamped to valid range.

        With negative failure count, success_rate = success / (success + negative)
        would exceed 1.0 without defensive bounds checking. The function now
        clamps the result to [0.0, 1.0].
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": -2,
                "failure_streak": 0,
            }
        )
        # success_rate = 5 / (5 + -2) = 5/3 ≈ 1.67, but clamped to 1.0
        # Defensive bounds checking ensures invalid data cannot produce rates > 1.0
        rate = calculate_success_rate(pattern)
        assert rate == 1.0  # Clamped to maximum valid rate

    def test_negative_failure_streak_passes_gate(self) -> None:
        """Pattern with negative failure streak passes Gate 3.

        A negative failure streak (if somehow possible) would pass the
        failure_streak < max_failure_streak check.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": -1,
            }
        )
        # -1 < 3 (max), so Gate 3 passes
        assert meets_promotion_criteria(pattern) is True

    def test_all_negative_values_fails(self) -> None:
        """Pattern with all negative values fails promotion.

        Even with invalid data, the pattern should not be promoted.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": -10,
                "success_count_rolling_20": -5,
                "failure_count_rolling_20": -5,
                "failure_streak": -1,
            }
        )
        # Gate 1: -10 < 5 fails
        assert meets_promotion_criteria(pattern) is False

    # -------------------------------------------------------------------------
    # Data Inconsistency Tests
    # -------------------------------------------------------------------------

    def test_zero_injection_with_outcomes_fails_gate1(self) -> None:
        """Pattern with 0 injections but non-zero outcomes fails Gate 1.

        This is a data inconsistency: how can there be outcomes without
        injections? The pattern should still fail Gate 1.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 0,  # No injections
                "success_count_rolling_20": 5,  # But somehow has successes
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )
        # Gate 1: 0 < 5 fails (regardless of success rate)
        assert meets_promotion_criteria(pattern) is False

    def test_injections_without_outcomes_fails_gate2(self) -> None:
        """Pattern with injections but no outcomes fails Gate 2.

        This is the data inconsistency mentioned in the handler code at
        lines 389-403. The handler logs this as a potential issue.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,  # Sufficient injections
                "success_count_rolling_20": 0,  # No outcomes
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        # Gate 1: 10 >= 5 passes
        # Gate 2: total_outcomes = 0, returns False (division by zero protection)
        assert meets_promotion_criteria(pattern) is False

    def test_injection_count_greater_than_total_outcomes(self) -> None:
        """Pattern where injection count exceeds total outcomes.

        This could happen if some injections haven't been resolved yet.
        Should still pass if other gates are met.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 20,  # 20 injections
                "success_count_rolling_20": 6,  # Only 10 resolved
                "failure_count_rolling_20": 4,
                "failure_streak": 0,
            }
        )
        # Gate 1: 20 >= 5 passes
        # Gate 2: 6/(6+4) = 0.6 = 60% passes
        # Gate 3: 0 < 3 passes
        assert meets_promotion_criteria(pattern) is True

    # -------------------------------------------------------------------------
    # Precise Boundary Condition Tests
    # -------------------------------------------------------------------------

    def test_success_rate_exactly_at_boundary_float_precision(self) -> None:
        """Test success rate exactly at 60% boundary with float precision.

        Verifies that 60% (0.6) exactly passes the >= comparison.
        """
        # Exactly 60%: 3/5 = 0.6
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 5,
                "success_count_rolling_20": 3,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
            }
        )
        rate = calculate_success_rate(pattern)
        assert rate == 0.6  # Exact equality
        assert meets_promotion_criteria(pattern) is True

    def test_success_rate_just_below_boundary(self) -> None:
        """Test success rate infinitesimally below 60% fails.

        Uses values that produce a rate just under 0.6.
        """
        # 599/1000 = 0.599 (just below 0.6)
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 1000,
                "success_count_rolling_20": 599,
                "failure_count_rolling_20": 401,
                "failure_streak": 0,
            }
        )
        rate = calculate_success_rate(pattern)
        assert rate < 0.6
        assert meets_promotion_criteria(pattern) is False

    def test_success_rate_just_above_boundary(self) -> None:
        """Test success rate infinitesimally above 60% passes.

        Uses values that produce a rate just over 0.6.
        """
        # 601/1000 = 0.601 (just above 0.6)
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 1000,
                "success_count_rolling_20": 601,
                "failure_count_rolling_20": 399,
                "failure_streak": 0,
            }
        )
        rate = calculate_success_rate(pattern)
        assert rate > 0.6
        assert meets_promotion_criteria(pattern) is True

    def test_failure_streak_boundary_at_2_passes(self) -> None:
        """Pattern with failure_streak=2 passes Gate 3 (just below max=3)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 2,  # 2 < 3, passes
            }
        )
        assert meets_promotion_criteria(pattern) is True

    def test_failure_streak_boundary_at_3_fails(self) -> None:
        """Pattern with failure_streak=3 fails Gate 3 (exactly at max=3)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 3,  # 3 >= 3, fails
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_injection_count_boundary_at_4_fails(self) -> None:
        """Pattern with injection_count=4 fails Gate 1 (just below min=5)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 4,  # 4 < 5, fails
                "success_count_rolling_20": 4,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is False

    def test_injection_count_boundary_at_5_passes(self) -> None:
        """Pattern with injection_count=5 passes Gate 1 (exactly at min=5)."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 5,  # 5 >= 5, passes
                "success_count_rolling_20": 4,
                "failure_count_rolling_20": 1,
                "failure_streak": 0,
            }
        )
        assert meets_promotion_criteria(pattern) is True

    # -------------------------------------------------------------------------
    # Large Numbers Tests (Overflow Protection)
    # -------------------------------------------------------------------------

    def test_very_large_counts_handled_correctly(self) -> None:
        """Pattern with very large counts calculates correctly.

        Ensures no integer overflow issues with large values.
        """
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 1_000_000,
                "success_count_rolling_20": 800_000,
                "failure_count_rolling_20": 200_000,
                "failure_streak": 0,
            }
        )
        # success_rate = 800000 / 1000000 = 0.8
        rate = calculate_success_rate(pattern)
        assert abs(rate - 0.8) < 1e-9
        assert meets_promotion_criteria(pattern) is True

    def test_large_failure_streak_fails(self) -> None:
        """Pattern with very large failure streak fails Gate 3."""
        pattern = MockRecord(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 1_000_000,  # Very large streak
            }
        )
        # 1_000_000 >= 3, Gate 3 fails
        assert meets_promotion_criteria(pattern) is False


# =============================================================================
# Test Class: calculate_success_rate Edge Cases
# =============================================================================


@pytest.mark.unit
class TestCalculateSuccessRateEdgeCases:
    """Additional edge case tests specifically for calculate_success_rate()."""

    def test_division_by_zero_returns_zero(self) -> None:
        """Explicitly verify division by zero returns 0.0, not an exception."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
            }
        )
        # Should not raise ZeroDivisionError
        result = calculate_success_rate(pattern)
        assert result == 0.0

    def test_only_successes_returns_1(self) -> None:
        """Pattern with all successes returns 1.0."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 100,
                "failure_count_rolling_20": 0,
            }
        )
        assert calculate_success_rate(pattern) == 1.0

    def test_only_failures_returns_0(self) -> None:
        """Pattern with all failures returns 0.0."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 100,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_missing_success_key_treated_as_zero(self) -> None:
        """Missing success_count key is treated as 0."""
        pattern = MockRecord(
            {
                "failure_count_rolling_20": 10,
            }
        )
        # success = 0 (missing), failure = 10
        # rate = 0 / 10 = 0.0
        assert calculate_success_rate(pattern) == 0.0

    def test_missing_failure_key_treated_as_zero(self) -> None:
        """Missing failure_count key is treated as 0."""
        pattern = MockRecord(
            {
                "success_count_rolling_20": 10,
            }
        )
        # success = 10, failure = 0 (missing)
        # rate = 10 / 10 = 1.0
        assert calculate_success_rate(pattern) == 1.0

    def test_both_keys_missing_returns_zero(self) -> None:
        """Both keys missing returns 0.0 (division by zero protection)."""
        pattern = MockRecord({})
        assert calculate_success_rate(pattern) == 0.0

    def test_negative_total_from_negative_failure(self) -> None:
        """Verifies clamping when negative failure creates positive total < success.

        Without defensive bounds checking, this would produce rate > 1.0.
        The function now clamps to the valid [0.0, 1.0] range.
        """
        pattern = MockRecord(
            {
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": -5,
            }
        )
        # total = 10 + (-5) = 5
        # rate = 10 / 5 = 2.0, but clamped to 1.0
        result = calculate_success_rate(pattern)
        assert result == 1.0  # Clamped to maximum valid rate

    def test_equal_positive_and_negative_creates_zero_total(self) -> None:
        """When success and failure cancel out to zero total.

        success + failure = 0 triggers division by zero protection.
        """
        pattern = MockRecord(
            {
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": -5,
            }
        )
        # total = 5 + (-5) = 0
        # Division by zero protection returns 0.0
        result = calculate_success_rate(pattern)
        assert result == 0.0
