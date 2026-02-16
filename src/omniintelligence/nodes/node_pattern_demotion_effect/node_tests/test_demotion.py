# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Comprehensive unit tests for pattern demotion gates and workflow.

This module tests the pattern demotion handler functions:
- `get_demotion_reason()`: Pure function checking demotion gates
- `check_and_demote_patterns()`: Main demotion workflow
- `demote_pattern()`: Single pattern demotion with event emission
- Helper functions: `calculate_success_rate`, `build_gate_snapshot`,
  `is_cooldown_active`, `build_effective_thresholds`, etc.

Test cases are organized by acceptance criteria from OMN-1681:
1. Gate 1: Minimum injection count for demotion eligibility (10)
2. Gate 2: Success rate gate (demote if < 40%)
3. Gate 3: Failure streak gate (demote if >= 5)
4. Gate 4: Manual disable gate (HARD TRIGGER - bypasses all)
5. Cooldown logic (anti-oscillation)
6. Threshold overrides with validation
7. Edge cases and boundary conditions
8. Handler tests with mocked repositories
9. Event payload verification

Reference:
    - OMN-1681: Auto-demote logic for patterns
    - OMN-1680: Auto-promote logic (reference implementation)
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pydantic
import pytest

from omniintelligence.nodes.node_pattern_demotion_effect.handlers.handler_demotion import (
    DEFAULT_COOLDOWN_HOURS,
    MAX_SUCCESS_RATE_FOR_DEMOTION,
    MIN_FAILURE_STREAK_FOR_DEMOTION,
    MIN_INJECTION_COUNT_FOR_DEMOTION,
    DemotionPatternRecord,
    _parse_update_count,
    build_effective_thresholds,
    build_gate_snapshot,
    calculate_hours_since_promotion,
    calculate_success_rate,
    check_and_demote_patterns,
    demote_pattern,
    get_demotion_reason,
    is_cooldown_active,
    validate_threshold_overrides,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models import (
    ModelDemotionCheckRequest,
    ModelDemotionCheckResult,
    ModelDemotionGateSnapshot,
    ModelDemotionResult,
    ModelEffectiveThresholds,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


def create_mock_record(data: dict[str, Any]) -> DemotionPatternRecord:
    """Create a DemotionPatternRecord from a plain dict.

    asyncpg.Record supports both dict-style access (record["column"]) and
    attribute access (record.column). For type-checking purposes, we cast
    the dict to DemotionPatternRecord so that handler functions accept it
    without mypy arg-type errors.

    At runtime, Python dicts support all the .get() calls that the handlers use,
    making this cast safe for testing.
    """
    return cast(DemotionPatternRecord, data)


# =============================================================================
# Mock Pattern Repository
# =============================================================================


@dataclass
class DemotablePattern:
    """In-memory state for a validated pattern eligible for demotion check.

    Simulates the learned_patterns table columns relevant to demotion,
    including the is_disabled flag from the LEFT JOIN with disabled_patterns_current.
    """

    id: UUID
    pattern_signature: str = "test_pattern_signature"
    status: str = "validated"
    is_current: bool = True
    promoted_at: datetime | None = None  # Set to datetime for cooldown tests
    injection_count_rolling_20: int = 0
    success_count_rolling_20: int = 0
    failure_count_rolling_20: int = 0
    failure_streak: int = 0
    is_disabled: bool = False


class MockPatternRepository:
    """In-memory mock repository implementing ProtocolPatternRepository.

    This mock simulates asyncpg behavior including:
    - Query execution with positional parameters ($1, $2, etc.)
    - Returning list of Record-like objects for fetch()
    - Returning status strings like "UPDATE 5" for execute()
    - Simulating the actual SQL logic for demotion

    The repository tracks query history for verification in tests.
    """

    def __init__(self) -> None:
        """Initialize empty repository state."""
        self.patterns: dict[UUID, DemotablePattern] = {}
        self.queries_executed: list[tuple[str, tuple[object, ...]]] = []

    def add_pattern(self, pattern: DemotablePattern) -> None:
        """Add a pattern to the mock database."""
        self.patterns[pattern.id] = pattern

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        """Execute a query and return results as record-like mappings.

        Simulates asyncpg fetch() behavior. Supports the specific queries
        used by the demotion handlers.
        """
        self.queries_executed.append((query, args))

        # Handle: Fetch validated patterns eligible for demotion check
        if "learned_patterns" in query and "validated" in query:
            results: list[Mapping[str, Any]] = []
            for p in self.patterns.values():
                if p.status == "validated" and p.is_current:
                    results.append(
                        create_mock_record(
                            {
                                "id": p.id,
                                "pattern_signature": p.pattern_signature,
                                "injection_count_rolling_20": p.injection_count_rolling_20,
                                "success_count_rolling_20": p.success_count_rolling_20,
                                "failure_count_rolling_20": p.failure_count_rolling_20,
                                "failure_streak": p.failure_streak,
                                "promoted_at": p.promoted_at,
                                "is_disabled": p.is_disabled,
                            }
                        )
                    )
            return results

        return []

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None:
        """Execute a query and return the first row, or None.

        Simulates asyncpg fetchrow() behavior. Required by the canonical
        ProtocolPatternRepository interface.
        """
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None

    async def execute(self, query: str, *args: object) -> str:
        """Execute a query and return status string.

        Simulates asyncpg execute() behavior. Implements the actual
        demotion update logic.
        """
        self.queries_executed.append((query, args))

        # Handle: Demote a single pattern
        if "UPDATE learned_patterns" in query and "deprecated" in query:
            pattern_id = cast(UUID, args[0])
            if pattern_id in self.patterns:
                p = self.patterns[pattern_id]
                if p.status == "validated":
                    p.status = "deprecated"
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
        self.published_events: list[tuple[str, str, dict[str, object]]] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
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


@pytest.fixture
def recently_promoted_pattern(sample_pattern_id: UUID) -> DemotablePattern:
    """Pattern promoted 12 hours ago (within default 24h cooldown)."""
    return DemotablePattern(
        id=sample_pattern_id,
        pattern_signature="recently_promoted",
        promoted_at=datetime.now(UTC) - timedelta(hours=12),
        injection_count_rolling_20=15,
        success_count_rolling_20=3,  # 20% success rate
        failure_count_rolling_20=12,
        failure_streak=6,
    )


@pytest.fixture
def old_promoted_pattern(sample_pattern_id: UUID) -> DemotablePattern:
    """Pattern promoted 48 hours ago (outside default 24h cooldown)."""
    return DemotablePattern(
        id=sample_pattern_id,
        pattern_signature="old_promoted",
        promoted_at=datetime.now(UTC) - timedelta(hours=48),
        injection_count_rolling_20=15,
        success_count_rolling_20=3,  # 20% success rate
        failure_count_rolling_20=12,
        failure_streak=6,
    )


@pytest.fixture
def default_request() -> ModelDemotionCheckRequest:
    """Default demotion check request with default thresholds."""
    return ModelDemotionCheckRequest(dry_run=False)


@pytest.fixture
def dry_run_request() -> ModelDemotionCheckRequest:
    """Dry run demotion check request."""
    return ModelDemotionCheckRequest(dry_run=True)


@pytest.fixture
def default_thresholds() -> ModelEffectiveThresholds:
    """Default effective thresholds for testing."""
    return ModelEffectiveThresholds(
        max_success_rate=MAX_SUCCESS_RATE_FOR_DEMOTION,
        min_failure_streak=MIN_FAILURE_STREAK_FOR_DEMOTION,
        min_injection_count=MIN_INJECTION_COUNT_FOR_DEMOTION,
        cooldown_hours=DEFAULT_COOLDOWN_HOURS,
        overrides_applied=False,
    )


# =============================================================================
# Test Class: Gate 1 - Minimum Injection Count
# =============================================================================


@pytest.mark.unit
class TestMinimumInjectionCount:
    """Tests for Gate 1: Minimum injection count requirement for demotion.

    A pattern must have injection_count_rolling_20 >= MIN_INJECTION_COUNT_FOR_DEMOTION (10)
    to be eligible for demotion based on success rate. This ensures sufficient sample size
    before making demotion decisions. Note: Failure streak gate can still trigger with
    fewer injections.
    """

    def test_fails_when_injection_count_below_minimum(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 9 injections and low success rate should NOT be demoted.

        The success rate gate requires minimum injection count. With only 9 injections
        (below the 10 minimum), the low success rate gate cannot trigger.
        """
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 9,
                "success_count_rolling_20": 2,  # 22% success rate (below 40%)
                "failure_count_rolling_20": 7,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        # Should NOT demote - insufficient data for success rate check
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_passes_when_injection_count_at_minimum(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with exactly 10 injections can be demoted for low success rate."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 3,  # 30% success rate (below 40%)
                "failure_count_rolling_20": 7,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason

    def test_passes_when_injection_count_above_minimum(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 20 injections and low success rate should be demoted."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 20,
                "success_count_rolling_20": 5,  # 25% success rate (below 40%)
                "failure_count_rolling_20": 15,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason

    def test_handles_none_injection_count(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with None injection count is treated as 0 (no demotion)."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": None,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 10,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None  # Cannot demote with insufficient data

    def test_min_injection_count_constant_is_ten(self) -> None:
        """Verify MIN_INJECTION_COUNT_FOR_DEMOTION constant is 10."""
        assert MIN_INJECTION_COUNT_FOR_DEMOTION == 10


# =============================================================================
# Test Class: Gate 2 - Success Rate Gate
# =============================================================================


@pytest.mark.unit
class TestSuccessRateGate:
    """Tests for Gate 2: Maximum success rate threshold for demotion.

    A pattern with success_rate < MAX_SUCCESS_RATE_FOR_DEMOTION (0.40 / 40%)
    is eligible for demotion. This only applies if the pattern has sufficient
    injection count (>= 10).
    """

    def test_demotes_when_success_rate_below_40_percent(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 30% success rate (below 40%) should be demoted."""
        # 30% success rate: 3 successes, 7 failures
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 3,
                "failure_count_rolling_20": 7,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason
        assert "30" in reason  # Should show 30.0%

    def test_does_not_demote_when_success_rate_at_40_percent(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with exactly 40% success rate should NOT be demoted.

        The gate uses < threshold, so exactly 40% does not trigger demotion.
        """
        # Exactly 40%: 4 successes, 6 failures
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 4,
                "failure_count_rolling_20": 6,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_does_not_demote_when_success_rate_above_40_percent(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 50% success rate should NOT be demoted."""
        # 50% success rate: 5 successes, 5 failures
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 5,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_requires_minimum_injection_count_for_rate_check(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Success rate check is skipped if injection count < 10."""
        # Low success rate but insufficient data
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 5,  # Below 10
                "success_count_rolling_20": 1,  # 20% success rate
                "failure_count_rolling_20": 4,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_max_success_rate_constant_is_0_4(self) -> None:
        """Verify MAX_SUCCESS_RATE_FOR_DEMOTION constant is 0.4."""
        assert MAX_SUCCESS_RATE_FOR_DEMOTION == 0.4


# =============================================================================
# Test Class: Gate 3 - Failure Streak Gate
# =============================================================================


@pytest.mark.unit
class TestFailureStreakGate:
    """Tests for Gate 3: Minimum failure streak threshold for demotion.

    A pattern with failure_streak >= MIN_FAILURE_STREAK_FOR_DEMOTION (5)
    is eligible for demotion regardless of success rate. This catches patterns
    in a persistent failure spiral.
    """

    def test_demotes_when_failure_streak_at_threshold(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with exactly 5 consecutive failures (at threshold) should be demoted."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,  # 70% success rate (good overall)
                "failure_count_rolling_20": 3,
                "failure_streak": 5,  # At threshold - demote
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason
        assert "5 consecutive" in reason

    def test_demotes_when_failure_streak_above_threshold(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 7 consecutive failures (above threshold) should be demoted."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 7,
                "failure_count_rolling_20": 3,
                "failure_streak": 7,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason
        assert "7 consecutive" in reason

    def test_does_not_demote_when_failure_streak_below_threshold(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with 4 consecutive failures (below threshold) should NOT be demoted."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,  # 80% success rate
                "failure_count_rolling_20": 2,
                "failure_streak": 4,  # Below threshold
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_handles_none_failure_streak(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with None failure streak is treated as 0."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": None,
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None  # 0 < 5, no failure streak demotion

    def test_min_failure_streak_constant_is_five(self) -> None:
        """Verify MIN_FAILURE_STREAK_FOR_DEMOTION constant is 5."""
        assert MIN_FAILURE_STREAK_FOR_DEMOTION == 5

    def test_failure_streak_does_not_require_minimum_injections(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Failure streak gate can trigger even with low injection count.

        Unlike the success rate gate, failure streak doesn't require minimum
        injection count - 5 consecutive failures is enough signal.
        """
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 5,  # Below 10
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 5,
                "failure_streak": 5,  # High streak
                "is_disabled": False,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason


# =============================================================================
# Test Class: Gate 4 - Manual Disable Gate (HARD TRIGGER)
# =============================================================================


@pytest.mark.unit
class TestManualDisableGate:
    """Tests for Gate 4: Manual disable gate (HARD TRIGGER).

    When a pattern exists in disabled_patterns_current table (is_disabled=True),
    it should be demoted immediately, bypassing all other gates including cooldown.
    """

    def test_demotes_when_pattern_is_disabled(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Disabled pattern should be demoted regardless of metrics."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 0,  # No data
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
                "failure_streak": 0,
                "is_disabled": True,  # HARD TRIGGER
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason == "manual_disable"

    def test_demotes_disabled_pattern_even_with_good_metrics(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Disabled pattern with excellent metrics should still be demoted."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 20,
                "success_count_rolling_20": 18,  # 90% success rate
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "is_disabled": True,  # HARD TRIGGER overrides everything
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason == "manual_disable"

    def test_disabled_sets_manual_disable_reason(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Disabled patterns get 'manual_disable' reason."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 2,  # Low success rate too
                "failure_count_rolling_20": 8,
                "failure_streak": 7,  # High streak too
                "is_disabled": True,
                "promoted_at": None,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        # Manual disable takes priority
        assert reason == "manual_disable"

    @pytest.mark.asyncio
    async def test_disabled_bypasses_cooldown(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Disabled pattern should be demoted even within cooldown period.

        This is a CRITICAL test: manual_disable must bypass cooldown.
        """
        # Pattern promoted just 1 hour ago (within 24h cooldown)
        pattern = DemotablePattern(
            id=uuid4(),
            pattern_signature="recently_disabled",
            promoted_at=datetime.now(UTC) - timedelta(hours=1),
            injection_count_rolling_20=10,
            success_count_rolling_20=3,
            failure_count_rolling_20=7,
            failure_streak=0,
            is_disabled=True,  # Manual disable
        )
        mock_repository.add_pattern(pattern)

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Should be demoted despite cooldown
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        assert len(result.patterns_demoted) == 1
        assert result.patterns_skipped_cooldown == 0  # NOT skipped
        assert result.patterns_demoted[0].reason == "manual_disable"


# =============================================================================
# Test Class: Cooldown Logic (Anti-Oscillation)
# =============================================================================


@pytest.mark.unit
class TestCooldownLogic:
    """Tests for cooldown logic preventing rapid oscillation.

    Patterns cannot be demoted until DEFAULT_COOLDOWN_HOURS (24) have passed
    since their promotion to validated status. Manual disable bypasses this.
    """

    @pytest.mark.asyncio
    async def test_skips_demotion_when_cooldown_active(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        recently_promoted_pattern: DemotablePattern,
    ) -> None:
        """Pattern promoted 12h ago (within 24h cooldown) should be skipped."""
        mock_repository.add_pattern(recently_promoted_pattern)

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Should be skipped due to cooldown
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1  # Pattern meets criteria
        assert len(result.patterns_demoted) == 0  # But not demoted
        assert result.patterns_skipped_cooldown == 1

    @pytest.mark.asyncio
    async def test_demotes_when_cooldown_expired(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        old_promoted_pattern: DemotablePattern,
    ) -> None:
        """Pattern promoted 48h ago (cooldown expired) should be demoted."""
        mock_repository.add_pattern(old_promoted_pattern)

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Should be demoted - cooldown expired
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        assert len(result.patterns_demoted) == 1
        assert result.patterns_skipped_cooldown == 0

    @pytest.mark.asyncio
    async def test_cooldown_with_null_promoted_at(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Pattern with None promoted_at has no cooldown protection."""
        pattern = DemotablePattern(
            id=uuid4(),
            pattern_signature="no_promotion_timestamp",
            promoted_at=None,  # No promotion timestamp
            injection_count_rolling_20=15,
            success_count_rolling_20=3,  # 20% success rate
            failure_count_rolling_20=12,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Should be demoted - no cooldown applies
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        assert len(result.patterns_demoted) == 1
        assert result.patterns_skipped_cooldown == 0

    @pytest.mark.asyncio
    async def test_custom_cooldown_hours(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Custom cooldown_hours override works correctly."""
        # Pattern promoted 6h ago - would be skipped with default 24h cooldown
        pattern = DemotablePattern(
            id=uuid4(),
            promoted_at=datetime.now(UTC) - timedelta(hours=6),
            injection_count_rolling_20=15,
            success_count_rolling_20=3,
            failure_count_rolling_20=12,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)

        # Use custom 4h cooldown (already expired)
        request = ModelDemotionCheckRequest(
            dry_run=False,
            cooldown_hours=4,
            allow_threshold_override=True,
        )
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Should be demoted - custom cooldown (4h) has expired
        assert len(result.patterns_demoted) == 1
        assert result.patterns_skipped_cooldown == 0

    @pytest.mark.asyncio
    async def test_manual_disable_bypasses_cooldown(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Manual disable should ALWAYS bypass cooldown (CRITICAL)."""
        # Pattern promoted just 1 hour ago with manual disable
        pattern = DemotablePattern(
            id=uuid4(),
            promoted_at=datetime.now(UTC) - timedelta(hours=1),
            injection_count_rolling_20=10,
            success_count_rolling_20=8,  # Good metrics
            failure_count_rolling_20=2,
            failure_streak=0,
            is_disabled=True,  # Manual disable
        )
        mock_repository.add_pattern(pattern)

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # Manual disable bypasses cooldown
        assert len(result.patterns_demoted) == 1
        assert result.patterns_demoted[0].reason == "manual_disable"
        assert result.patterns_skipped_cooldown == 0

    @pytest.mark.asyncio
    async def test_skipped_cooldown_count_tracked(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Skipped cooldown count is accurately tracked."""
        # Add 3 patterns: 2 within cooldown, 1 expired
        for i in range(2):
            mock_repository.add_pattern(
                DemotablePattern(
                    id=uuid4(),
                    pattern_signature=f"recent_{i}",
                    promoted_at=datetime.now(UTC)
                    - timedelta(hours=12),  # Within cooldown
                    injection_count_rolling_20=15,
                    success_count_rolling_20=3,
                    failure_count_rolling_20=12,
                    failure_streak=0,
                )
            )
        mock_repository.add_pattern(
            DemotablePattern(
                id=uuid4(),
                pattern_signature="old",
                promoted_at=datetime.now(UTC) - timedelta(hours=48),  # Expired
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        assert result.patterns_checked == 3
        assert result.patterns_eligible == 3
        assert len(result.patterns_demoted) == 1
        assert result.patterns_skipped_cooldown == 2

    def test_is_cooldown_active_true_when_within_period(self) -> None:
        """is_cooldown_active returns True when within cooldown period."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=12),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is True

    def test_is_cooldown_active_false_when_expired(self) -> None:
        """is_cooldown_active returns False when cooldown expired."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=48),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is False

    def test_is_cooldown_active_false_when_promoted_at_none(self) -> None:
        """is_cooldown_active returns False when promoted_at is None."""
        pattern = create_mock_record(
            {
                "promoted_at": None,
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is False

    def test_default_cooldown_hours_is_24(self) -> None:
        """Verify DEFAULT_COOLDOWN_HOURS constant is 24."""
        assert DEFAULT_COOLDOWN_HOURS == 24


# =============================================================================
# Test Class: Threshold Overrides
# =============================================================================


@pytest.mark.unit
class TestThresholdOverrides:
    """Tests for threshold override validation and application."""

    def test_rejects_overrides_without_allow_flag(self) -> None:
        """Threshold overrides require allow_threshold_override=True."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.30,  # Non-default
            allow_threshold_override=False,
        )
        with pytest.raises(ValueError) as exc_info:
            validate_threshold_overrides(request)
        assert "allow_threshold_override=False" in str(exc_info.value)

    def test_accepts_overrides_with_allow_flag(self) -> None:
        """Threshold overrides work with allow_threshold_override=True."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.30,
            min_failure_streak=7,
            min_injection_count=15,
            cooldown_hours=48,
            allow_threshold_override=True,
        )
        # Should not raise
        validate_threshold_overrides(request)

    def test_validates_success_rate_bounds_lower(self) -> None:
        """Success rate override below 0.10 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                max_success_rate=0.05,  # Below 0.10
                allow_threshold_override=True,
            )
        assert "greater than or equal to" in str(exc_info.value)

    def test_validates_success_rate_bounds_upper(self) -> None:
        """Success rate override above 0.60 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                max_success_rate=0.65,  # Above 0.60
                allow_threshold_override=True,
            )
        assert "less than or equal to" in str(exc_info.value)

    def test_validates_failure_streak_bounds_lower(self) -> None:
        """Failure streak override below 3 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                min_failure_streak=2,  # Below 3
                allow_threshold_override=True,
            )
        assert "greater than or equal to" in str(exc_info.value)

    def test_validates_failure_streak_bounds_upper(self) -> None:
        """Failure streak override above 20 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                min_failure_streak=25,  # Above 20
                allow_threshold_override=True,
            )
        assert "less than or equal to" in str(exc_info.value)

    def test_logs_effective_thresholds_in_result(self) -> None:
        """Effective thresholds are captured in result model."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.35,
            min_failure_streak=6,
            min_injection_count=12,
            cooldown_hours=48,
            allow_threshold_override=True,
        )
        thresholds = build_effective_thresholds(request)

        assert thresholds.max_success_rate == 0.35
        assert thresholds.min_failure_streak == 6
        assert thresholds.min_injection_count == 12
        assert thresholds.cooldown_hours == 48
        assert thresholds.overrides_applied is True

    def test_default_thresholds_not_flagged_as_override(self) -> None:
        """Default thresholds have overrides_applied=False."""
        request = ModelDemotionCheckRequest()  # All defaults
        thresholds = build_effective_thresholds(request)

        assert thresholds.overrides_applied is False

    def test_validates_min_injection_count_lower_bound(self) -> None:
        """min_injection_count below 1 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                min_injection_count=0,  # Below 1
                allow_threshold_override=True,
            )
        assert "greater than or equal to" in str(exc_info.value)

    def test_validates_cooldown_hours_lower_bound(self) -> None:
        """cooldown_hours below 0 is rejected at model creation.

        Pydantic validates bounds at model creation time, so we expect
        a ValidationError from Pydantic, not ValueError from our validator.
        """
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModelDemotionCheckRequest(
                cooldown_hours=-1,  # Below 0
                allow_threshold_override=True,
            )
        assert "greater than or equal to" in str(exc_info.value)


# =============================================================================
# Test Class: Dry Run Mode
# =============================================================================


@pytest.mark.unit
class TestDryRunMode:
    """Tests for check_and_demote_patterns in dry_run mode.

    When dry_run=True, the function should:
    - Return what WOULD be demoted
    - NOT execute any database mutations
    - NOT publish any Kafka events
    """

    @pytest.mark.asyncio
    async def test_dry_run_does_not_mutate_database(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Dry run does not call repository.execute() for demotion."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=True)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,
            request=request,
            topic_env_prefix="test",
        )

        # Only fetch query executed (no UPDATE)
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
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=True)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        # No events published
        assert len(mock_producer.published_events) == 0
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_dry_run_result_has_deprecated_at_none(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Dry run demotion results have deprecated_at=None."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=True)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        assert len(result.patterns_demoted) == 1
        demotion = result.patterns_demoted[0]
        assert demotion.dry_run is True
        assert demotion.deprecated_at is None

    @pytest.mark.asyncio
    async def test_dry_run_returns_correct_counts(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Dry run returns correct checked/eligible counts."""
        # 3 patterns - 2 eligible for demotion, 1 not
        mock_repository.add_pattern(
            DemotablePattern(
                id=uuid4(),
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,  # 20% - demote
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )
        mock_repository.add_pattern(
            DemotablePattern(
                id=uuid4(),
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=10,
                success_count_rolling_20=0,  # 0% - demote
                failure_count_rolling_20=10,
                failure_streak=5,
            )
        )
        mock_repository.add_pattern(
            DemotablePattern(
                id=uuid4(),
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=10,  # 67% - don't demote
                failure_count_rolling_20=5,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=True)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        assert result.patterns_checked == 3
        assert result.patterns_eligible == 2
        assert len(result.patterns_demoted) == 2


# =============================================================================
# Test Class: Actual Demotion
# =============================================================================


@pytest.mark.unit
class TestActualDemotion:
    """Tests for check_and_demote_patterns with dry_run=False.

    **OMN-1805 Event-Driven Architecture:**
    When dry_run=False, the function now:
    - Does NOT execute database UPDATE directly
    - Publishes ModelPatternLifecycleEvent to Kafka for reducer processing
    - Returns results with deprecated_at timestamps (request time, not completion time)

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
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        assert result.dry_run is False
        assert len(result.patterns_demoted) == 1
        assert result.patterns_demoted[0].dry_run is False
        # Event was emitted to Kafka for reducer processing
        assert len(mock_producer.published_events) == 1
        # NOTE: Database status unchanged - actual update happens via reducer/effect
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_without_producer_includes_result_with_kafka_unavailable_reason(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Without Kafka producer, demotion result is included with reason.

        OMN-1805: When Kafka is unavailable, the pattern IS included in
        patterns_demoted with reason='kafka_producer_unavailable'. The result
        is NOT dropped - it's recorded so callers know what happened.
        """
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,  # No Kafka producer
            request=request,
            topic_env_prefix="test",
        )

        # Pattern eligible and result IS included (not dropped)
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        # Result IS included with kafka_producer_unavailable reason
        assert len(result.patterns_demoted) == 1
        assert result.patterns_demoted[0].reason == "kafka_producer_unavailable"
        # No actual DB update occurred (deprecated_at is None)
        assert result.patterns_demoted[0].deprecated_at is None
        # Database status unchanged (event not sent to reducer)
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_skips_ineligible_patterns(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Ineligible patterns are not demoted."""
        pattern_id = uuid4()
        mock_repository.add_pattern(
            DemotablePattern(
                id=pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=10,  # 67% - above 40%
                failure_count_rolling_20=5,
                failure_streak=2,  # Below 5
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        assert result.patterns_checked == 1
        assert result.patterns_eligible == 0
        assert len(result.patterns_demoted) == 0
        assert mock_repository.patterns[pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_publishes_event_for_each_demotion(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
    ) -> None:
        """Kafka event is published for each demoted pattern."""
        id1, id2 = uuid4(), uuid4()
        mock_repository.add_pattern(
            DemotablePattern(
                id=id1,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )
        mock_repository.add_pattern(
            DemotablePattern(
                id=id2,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=10,
                success_count_rolling_20=2,
                failure_count_rolling_20=8,
                failure_streak=6,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        assert len(result.patterns_demoted) == 2
        assert len(mock_producer.published_events) == 2

    @pytest.mark.asyncio
    async def test_demotion_result_has_request_timestamp(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Demotion results have deprecated_at timestamp set (request time)."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        before = datetime.now(UTC)
        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )
        after = datetime.now(UTC)

        demotion = result.patterns_demoted[0]
        assert demotion.deprecated_at is not None  # Request timestamp
        assert before <= demotion.deprecated_at <= after

    @pytest.mark.asyncio
    async def test_empty_repository_returns_zero_counts(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Empty repository returns zero counts."""
        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0
        assert len(result.patterns_demoted) == 0


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
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="prod",
        )

        topic, _key, _value = mock_producer.published_events[0]
        assert topic.startswith("prod.")
        assert "pattern-lifecycle-transition" in topic

    @pytest.mark.asyncio
    async def test_event_key_is_pattern_id(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event key is the pattern ID for partitioning."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, key, _value = mock_producer.published_events[0]
        assert key == str(sample_pattern_id)

    @pytest.mark.asyncio
    async def test_event_contains_gate_snapshot(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains gate_snapshot with success_rate."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,  # 20% success rate
                failure_count_rolling_20=12,
                failure_streak=1,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, _key, value = mock_producer.published_events[0]
        assert "gate_snapshot" in value
        gate_snapshot = cast(dict[str, object], value["gate_snapshot"])
        assert abs(cast(float, gate_snapshot["success_rate_rolling_20"]) - 0.2) < 1e-9
        assert gate_snapshot["injection_count_rolling_20"] == 15
        assert gate_snapshot["failure_streak"] == 1

    @pytest.mark.asyncio
    async def test_event_contains_lifecycle_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains lifecycle-specific fields (OMN-1805).

        NOTE: effective_thresholds are no longer in the Kafka event payload.
        They're still in the ModelDemotionResult returned to the caller.
        """
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, _key, value = mock_producer.published_events[0]
        # Lifecycle event fields
        assert value["event_type"] == "PatternLifecycleEvent"
        assert value["trigger"] == "deprecate"
        assert value["actor"] == "demotion_handler"
        assert value["actor_type"] == "handler"
        assert "request_id" in value
        assert "occurred_at" in value

    @pytest.mark.asyncio
    async def test_event_contains_status_transition(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains from_status and to_status."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, _key, value = mock_producer.published_events[0]
        assert value["from_status"] == "validated"
        assert value["to_status"] == "deprecated"
        assert value["event_type"] == "PatternLifecycleEvent"
        assert value["trigger"] == "deprecate"
        assert value["actor"] == "demotion_handler"
        assert "request_id" in value  # Idempotency key

    @pytest.mark.asyncio
    async def test_event_contains_correlation_id(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
    ) -> None:
        """Event payload contains correlation_id when provided."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(
            dry_run=False,
            correlation_id=sample_correlation_id,
        )
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, _key, value = mock_producer.published_events[0]
        assert value["correlation_id"] == str(sample_correlation_id)

    @pytest.mark.asyncio
    async def test_event_contains_reason(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """Event payload contains demotion reason."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                pattern_signature="test_sig",
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,  # Low success rate
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        _topic, _key, value = mock_producer.published_events[0]
        assert "reason" in value
        assert "low_success_rate" in cast(str, value["reason"])
        # NOTE: pattern_signature is no longer in lifecycle events (OMN-1805)
        # It's in the gate_snapshot if needed for diagnostics


# =============================================================================
# Test Class: calculate_success_rate Helper Function
# =============================================================================


@pytest.mark.unit
class TestCalculateSuccessRate:
    """Tests for the calculate_success_rate helper function."""

    def test_calculates_50_percent_rate(self) -> None:
        """Calculates 50% success rate correctly."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": 5,
            }
        )
        assert calculate_success_rate(pattern) == 0.5

    def test_calculates_100_percent_rate(self) -> None:
        """Calculates 100% success rate correctly."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": 0,
            }
        )
        assert calculate_success_rate(pattern) == 1.0

    def test_calculates_0_percent_rate(self) -> None:
        """Calculates 0% success rate correctly."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 10,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_returns_zero_when_no_outcomes(self) -> None:
        """Returns 0.0 when no outcomes recorded (division by zero protection)."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 0,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_handles_none_values(self) -> None:
        """Handles None values by treating them as 0."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": None,
                "failure_count_rolling_20": None,
            }
        )
        assert calculate_success_rate(pattern) == 0.0

    def test_clamps_rate_to_max_1(self) -> None:
        """Success rate is clamped to maximum 1.0."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 10,
                "failure_count_rolling_20": -5,  # Negative would cause > 1.0
            }
        )
        assert calculate_success_rate(pattern) == 1.0

    def test_clamps_rate_to_min_0(self) -> None:
        """Success rate is clamped to minimum 0.0."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": -3,  # Negative success
                "failure_count_rolling_20": 10,
            }
        )
        result = calculate_success_rate(pattern)
        assert result >= 0.0


# =============================================================================
# Test Class: build_gate_snapshot Helper Function
# =============================================================================


@pytest.mark.unit
class TestBuildGateSnapshot:
    """Tests for the build_gate_snapshot helper function."""

    def test_builds_snapshot_with_all_fields(self) -> None:
        """Builds snapshot with all fields populated correctly."""
        promoted_at = datetime.now(UTC) - timedelta(hours=36)
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 12,
                "failure_count_rolling_20": 3,
                "failure_streak": 1,
                "is_disabled": False,
                "promoted_at": promoted_at,
            }
        )

        snapshot = build_gate_snapshot(pattern)

        assert isinstance(snapshot, ModelDemotionGateSnapshot)
        assert snapshot.injection_count_rolling_20 == 15
        assert snapshot.failure_streak == 1
        assert snapshot.disabled is False
        assert abs(snapshot.success_rate_rolling_20 - 0.8) < 1e-9  # 12/15 = 0.8
        assert snapshot.hours_since_promotion is not None
        assert abs(snapshot.hours_since_promotion - 36.0) < 0.1

    def test_hours_since_promotion_calculated_correctly(self) -> None:
        """hours_since_promotion is calculated correctly."""
        promoted_at = datetime.now(UTC) - timedelta(hours=24)
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": promoted_at,
            }
        )

        snapshot = build_gate_snapshot(pattern)
        assert snapshot.hours_since_promotion is not None
        assert abs(snapshot.hours_since_promotion - 24.0) < 0.1

    def test_hours_since_promotion_none_when_no_timestamp(self) -> None:
        """hours_since_promotion is None when promoted_at is None."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )

        snapshot = build_gate_snapshot(pattern)
        assert snapshot.hours_since_promotion is None

    def test_snapshot_is_frozen_model(self) -> None:
        """Snapshot is immutable (frozen model)."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )

        snapshot = build_gate_snapshot(pattern)

        # Pydantic frozen models raise ValidationError on mutation
        with pytest.raises(pydantic.ValidationError):
            snapshot.success_rate_rolling_20 = 0.0


# =============================================================================
# Test Class: build_effective_thresholds Helper Function
# =============================================================================


@pytest.mark.unit
class TestBuildEffectiveThresholds:
    """Tests for the build_effective_thresholds helper function."""

    def test_default_thresholds(self) -> None:
        """Default request produces default thresholds with overrides_applied=False."""
        request = ModelDemotionCheckRequest()
        thresholds = build_effective_thresholds(request)

        assert thresholds.max_success_rate == MAX_SUCCESS_RATE_FOR_DEMOTION
        assert thresholds.min_failure_streak == MIN_FAILURE_STREAK_FOR_DEMOTION
        assert thresholds.min_injection_count == MIN_INJECTION_COUNT_FOR_DEMOTION
        assert thresholds.cooldown_hours == DEFAULT_COOLDOWN_HOURS
        assert thresholds.overrides_applied is False

    def test_override_thresholds(self) -> None:
        """Non-default thresholds produce overrides_applied=True."""
        request = ModelDemotionCheckRequest(
            max_success_rate=0.35,
            min_failure_streak=6,
            min_injection_count=15,
            cooldown_hours=48,
            allow_threshold_override=True,
        )
        thresholds = build_effective_thresholds(request)

        assert thresholds.max_success_rate == 0.35
        assert thresholds.min_failure_streak == 6
        assert thresholds.min_injection_count == 15
        assert thresholds.cooldown_hours == 48
        assert thresholds.overrides_applied is True

    def test_partial_override_detected(self) -> None:
        """Any single non-default value triggers overrides_applied=True."""
        request = ModelDemotionCheckRequest(
            cooldown_hours=12,  # Only this is different
            allow_threshold_override=True,
        )
        thresholds = build_effective_thresholds(request)

        assert thresholds.overrides_applied is True


# =============================================================================
# Test Class: is_cooldown_active Helper Function
# =============================================================================


@pytest.mark.unit
class TestIsCooldownActive:
    """Tests for the is_cooldown_active helper function."""

    def test_true_when_within_cooldown_period(self) -> None:
        """Returns True when pattern was promoted within cooldown period."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=12),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is True

    def test_false_when_cooldown_expired(self) -> None:
        """Returns False when cooldown period has elapsed."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=48),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is False

    def test_false_when_promoted_at_is_none(self) -> None:
        """Returns False when promoted_at is None (no cooldown applies)."""
        pattern = create_mock_record(
            {
                "promoted_at": None,
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is False

    def test_boundary_just_before_expiry(self) -> None:
        """Returns True when just before cooldown expiry."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=23, minutes=59),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is True

    def test_boundary_just_after_expiry(self) -> None:
        """Returns False when just after cooldown expiry."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(hours=24, minutes=1),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=24) is False

    def test_zero_cooldown_hours(self) -> None:
        """Returns False when cooldown_hours is 0 (no cooldown)."""
        pattern = create_mock_record(
            {
                "promoted_at": datetime.now(UTC) - timedelta(minutes=1),
            }
        )
        assert is_cooldown_active(pattern, cooldown_hours=0) is False


# =============================================================================
# Test Class: get_demotion_reason Helper Function
# =============================================================================


@pytest.mark.unit
class TestGetDemotionReason:
    """Tests for the get_demotion_reason helper function.

    This function determines which demotion gate triggered, if any.
    Priority order: manual_disable > failure_streak > low_success_rate
    """

    def test_returns_manual_disable_for_disabled_patterns(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Returns 'manual_disable' for disabled patterns."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 0,
                "is_disabled": True,
            }
        )
        assert get_demotion_reason(pattern, default_thresholds) == "manual_disable"

    def test_returns_failure_streak_reason(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Returns failure streak reason when failure_streak >= threshold."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 6,
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason == "failure_streak: 6 consecutive failures"

    def test_returns_low_success_rate_reason(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Returns low success rate reason when rate < threshold."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 3,  # 20%
                "failure_count_rolling_20": 12,
                "failure_streak": 0,
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason
        assert "20" in reason

    def test_returns_none_when_no_criteria_met(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Returns None when pattern passes all gates."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 10,  # 67%
                "failure_count_rolling_20": 5,
                "failure_streak": 2,  # Below 5
                "is_disabled": False,
            }
        )
        assert get_demotion_reason(pattern, default_thresholds) is None

    def test_priority_manual_disable_over_failure_streak(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """manual_disable takes priority over failure_streak."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 10,
                "failure_streak": 10,  # Would trigger failure_streak
                "is_disabled": True,  # But manual_disable takes priority
            }
        )
        assert get_demotion_reason(pattern, default_thresholds) == "manual_disable"

    def test_priority_failure_streak_over_low_success_rate(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """failure_streak takes priority over low_success_rate."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 3,  # 20% - would trigger low_success_rate
                "failure_count_rolling_20": 12,
                "failure_streak": 7,  # But failure_streak takes priority
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason
        assert "low_success_rate" not in reason


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
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_pattern_already_deprecated_not_updated_again(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Pattern with status='deprecated' is not included in fetch results."""
        pattern_id = uuid4()
        mock_repository.add_pattern(
            DemotablePattern(
                id=pattern_id,
                status="deprecated",  # Already deprecated
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=6,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        # Not found in validated query
        assert result.patterns_checked == 0
        assert result.patterns_eligible == 0

    @pytest.mark.asyncio
    async def test_non_current_pattern_not_checked(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Pattern with is_current=False is not included in fetch results."""
        pattern_id = uuid4()
        mock_repository.add_pattern(
            DemotablePattern(
                id=pattern_id,
                is_current=False,  # Old version
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=6,
            )
        )

        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        # Not found in query
        assert result.patterns_checked == 0

    @pytest.mark.asyncio
    async def test_large_batch_of_patterns(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Handles large batch of patterns correctly."""
        # 100 patterns: 50 eligible (low success rate), 50 not
        for i in range(100):
            mock_repository.add_pattern(
                DemotablePattern(
                    id=uuid4(),
                    promoted_at=datetime.now(UTC) - timedelta(hours=48),
                    injection_count_rolling_20=15,
                    success_count_rolling_20=3 if i % 2 == 0 else 10,  # Alternating
                    failure_count_rolling_20=12 if i % 2 == 0 else 5,
                    failure_streak=0,
                )
            )

        request = ModelDemotionCheckRequest(dry_run=True)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            request=request,
            topic_env_prefix="test",
        )

        assert result.patterns_checked == 100
        assert result.patterns_eligible == 50

    def test_pattern_with_missing_keys_handled_gracefully(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern dict with missing keys is handled gracefully."""
        # Empty pattern dict - all values default to 0/False
        pattern = create_mock_record({})
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None  # No criteria met with defaults

    @pytest.mark.asyncio
    async def test_kafka_unavailable_includes_result_with_reason(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Demotion without Kafka includes result with reason (OMN-1805).

        This tests the scenario where:
        1. Pattern is fetched as 'validated' (eligible for demotion)
        2. Kafka producer is unavailable (None)
        3. Result IS included in patterns_demoted with reason='kafka_producer_unavailable'
        4. deprecated_at is None (no actual DB update)
        5. Database status remains unchanged

        NOTE: With OMN-1805, there is no "concurrent demotion" scenario because
        the handler no longer does direct SQL updates. The reducer handles
        idempotency via request_id tracking.
        """
        pattern_id = uuid4()
        mock_repository.add_pattern(
            DemotablePattern(
                id=pattern_id,
                status="validated",
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        # Act - No Kafka producer available
        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=None,  # Kafka unavailable
            request=request,
            topic_env_prefix="test",
        )

        # Pattern was checked and found eligible
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1

        # Result IS included with kafka_producer_unavailable reason
        assert len(result.patterns_demoted) == 1
        assert result.patterns_demoted[0].reason == "kafka_producer_unavailable"
        # No actual DB update occurred
        assert result.patterns_demoted[0].deprecated_at is None

        # Database status unchanged (event not sent to reducer)
        assert mock_repository.patterns[pattern_id].status == "validated"


# =============================================================================
# Test Class: Numerical Edge Cases
# =============================================================================


@pytest.mark.unit
class TestNumericalEdgeCases:
    """Tests for numerical edge cases and defensive handling."""

    def test_negative_injection_count(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Pattern with negative injection count cannot trigger success rate gate."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": -5,
                "success_count_rolling_20": 0,
                "failure_count_rolling_20": 10,
                "failure_streak": 0,
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None  # Cannot meet injection count requirement

    def test_negative_success_count(self) -> None:
        """Negative success count produces valid clamped rate."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": -3,
                "failure_count_rolling_20": 10,
            }
        )
        rate = calculate_success_rate(pattern)
        assert 0.0 <= rate <= 1.0

    def test_negative_failure_count_clamped(self) -> None:
        """Negative failure count is clamped to valid range."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 5,
                "failure_count_rolling_20": -2,
            }
        )
        rate = calculate_success_rate(pattern)
        assert rate == 1.0  # Clamped to max

    def test_very_large_counts(self) -> None:
        """Very large counts are handled correctly without overflow."""
        pattern = create_mock_record(
            {
                "success_count_rolling_20": 800_000,
                "failure_count_rolling_20": 200_000,
            }
        )
        rate = calculate_success_rate(pattern)
        assert abs(rate - 0.8) < 1e-9

    def test_boundary_success_rate_just_below_40(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Success rate at 39.9% triggers demotion."""
        # 399/1000 = 0.399 (just below 0.4)
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 1000,
                "success_count_rolling_20": 399,
                "failure_count_rolling_20": 601,
                "failure_streak": 0,
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "low_success_rate" in reason

    def test_boundary_success_rate_exactly_40(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Success rate at exactly 40% does NOT trigger demotion."""
        # 400/1000 = 0.400 (exactly at threshold)
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 1000,
                "success_count_rolling_20": 400,
                "failure_count_rolling_20": 600,
                "failure_streak": 0,
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_boundary_failure_streak_at_4(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Failure streak of 4 does NOT trigger demotion."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 4,  # Below 5
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is None

    def test_boundary_failure_streak_at_5(
        self, default_thresholds: ModelEffectiveThresholds
    ) -> None:
        """Failure streak of 5 DOES trigger demotion."""
        pattern = create_mock_record(
            {
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "failure_streak": 5,  # At threshold
                "is_disabled": False,
            }
        )
        reason = get_demotion_reason(pattern, default_thresholds)
        assert reason is not None
        assert "failure_streak" in reason


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
    async def test_demotion_check_result_has_all_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
    ) -> None:
        """ModelDemotionCheckResult contains all expected fields."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        # Act - Need producer for actual demotion (OMN-1805)
        request = ModelDemotionCheckRequest(
            dry_run=False,
            correlation_id=sample_correlation_id,
        )
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        assert isinstance(result, ModelDemotionCheckResult)
        assert result.dry_run is False
        assert result.patterns_checked == 1
        assert result.patterns_eligible == 1
        assert len(result.patterns_demoted) == 1
        assert result.correlation_id == sample_correlation_id

    @pytest.mark.asyncio
    async def test_demotion_result_has_all_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
    ) -> None:
        """ModelDemotionResult contains all expected fields."""
        signature = "test_signature"
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                pattern_signature=signature,
                promoted_at=datetime.now(UTC) - timedelta(hours=48),
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )

        # Act - Need producer for actual demotion (OMN-1805)
        request = ModelDemotionCheckRequest(dry_run=False)
        result = await check_and_demote_patterns(
            repository=mock_repository,
            producer=mock_producer,
            request=request,
            topic_env_prefix="test",
        )

        demotion = result.patterns_demoted[0]
        assert isinstance(demotion, ModelDemotionResult)
        assert demotion.pattern_id == sample_pattern_id
        assert demotion.pattern_signature == signature
        assert demotion.from_status == "validated"
        assert demotion.to_status == "deprecated"
        assert demotion.deprecated_at is not None  # Request timestamp
        assert "low_success_rate" in demotion.reason
        assert demotion.gate_snapshot is not None
        assert demotion.effective_thresholds is not None
        assert demotion.dry_run is False


# =============================================================================
# Test Class: calculate_hours_since_promotion Helper Function
# =============================================================================


@pytest.mark.unit
class TestCalculateHoursSincePromotion:
    """Tests for the calculate_hours_since_promotion helper function."""

    def test_calculates_correctly_for_recent_promotion(self) -> None:
        """Calculates hours correctly for recent promotion."""
        promoted_at = datetime.now(UTC) - timedelta(hours=24)
        hours = calculate_hours_since_promotion(promoted_at)
        assert hours is not None
        assert abs(hours - 24.0) < 0.1

    def test_calculates_correctly_for_old_promotion(self) -> None:
        """Calculates hours correctly for old promotion."""
        promoted_at = datetime.now(UTC) - timedelta(days=7)
        hours = calculate_hours_since_promotion(promoted_at)
        assert hours is not None
        assert abs(hours - (7 * 24)) < 0.1

    def test_returns_none_for_none_input(self) -> None:
        """Returns None when promoted_at is None."""
        hours = calculate_hours_since_promotion(None)
        assert hours is None

    def test_clamps_negative_to_zero(self) -> None:
        """Clamps result to non-negative (handles future timestamps)."""
        # Future timestamp (shouldn't happen, but defensive)
        promoted_at = datetime.now(UTC) + timedelta(hours=1)
        hours = calculate_hours_since_promotion(promoted_at)
        assert hours is not None
        assert hours >= 0.0

    def test_handles_naive_datetime(self) -> None:
        """Handles naive datetime without crashing.

        When a naive datetime is passed (without tzinfo), the function assumes UTC
        and processes it without raising an exception. The exact hour calculation
        may vary by timezone offset, so we just verify it returns a positive value.
        """
        # Naive datetime without tzinfo - create by subtracting from naive now()
        # then manually add UTC to make it behave like the handler does
        naive_time = datetime.now() - timedelta(hours=12)
        hours = calculate_hours_since_promotion(naive_time)
        assert hours is not None
        # The function adds UTC to naive datetimes and compares to datetime.now(UTC)
        # Result depends on local timezone offset, so just verify it's non-negative
        assert hours >= 0.0


# =============================================================================
# Test Class: demote_pattern Direct Tests
# =============================================================================


@pytest.mark.unit
class TestDemotePatternDirect:
    """Direct tests for the demote_pattern function.

    OMN-1805: demote_pattern now emits a ModelPatternLifecycleEvent to Kafka
    instead of directly updating the database. The actual status update happens
    asynchronously via the reducer -> effect pipeline.
    """

    @pytest.mark.asyncio
    async def test_demote_pattern_emits_lifecycle_event(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """demote_pattern emits lifecycle event to Kafka (not direct DB update)."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )
        pattern_data = create_mock_record(
            {
                "id": sample_pattern_id,
                "pattern_signature": "test_sig",
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 3,
                "failure_count_rolling_20": 12,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )

        result = await demote_pattern(
            repository=mock_repository,
            producer=mock_producer,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            topic_env_prefix="test",
        )

        assert result.from_status == "validated"
        assert result.to_status == "deprecated"
        assert result.dry_run is False
        # Event emitted to Kafka
        assert len(mock_producer.published_events) == 1
        # NOTE: Database status unchanged - actual update happens via reducer/effect
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_demote_pattern_without_producer_returns_skipped(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """demote_pattern with producer=None returns skipped result (OMN-1805).

        Kafka is REQUIRED for actual demotions. Without it, the handler cannot
        reach the reducer which is the single source of truth.
        """
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=0,
            )
        )
        pattern_data = create_mock_record(
            {
                "id": sample_pattern_id,
                "pattern_signature": "test_sig",
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 3,
                "failure_count_rolling_20": 12,
                "failure_streak": 0,
                "is_disabled": False,
                "promoted_at": None,
            }
        )

        result = await demote_pattern(
            repository=mock_repository,
            producer=None,  # No Kafka producer
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            topic_env_prefix="test",
        )

        # Demotion skipped, not silently executed
        assert result.to_status == "deprecated"  # Target status
        assert result.deprecated_at is None  # Indicates not actually deprecated
        assert result.reason == "kafka_producer_unavailable"
        # Database unchanged
        assert mock_repository.patterns[sample_pattern_id].status == "validated"

    @pytest.mark.asyncio
    async def test_demote_pattern_returns_gate_snapshot(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
        default_thresholds: ModelEffectiveThresholds,
    ) -> None:
        """demote_pattern result includes gate snapshot."""
        mock_repository.add_pattern(
            DemotablePattern(
                id=sample_pattern_id,
                injection_count_rolling_20=15,
                success_count_rolling_20=3,
                failure_count_rolling_20=12,
                failure_streak=1,
            )
        )
        pattern_data = create_mock_record(
            {
                "id": sample_pattern_id,
                "pattern_signature": "test_sig",
                "injection_count_rolling_20": 15,
                "success_count_rolling_20": 3,
                "failure_count_rolling_20": 12,
                "failure_streak": 1,
                "is_disabled": False,
                "promoted_at": None,
            }
        )

        result = await demote_pattern(
            repository=mock_repository,
            producer=None,
            pattern_id=sample_pattern_id,
            pattern_data=pattern_data,
            reason="low_success_rate: 20.0%",
            thresholds=default_thresholds,
            topic_env_prefix="test",
        )

        assert result.gate_snapshot is not None
        assert result.gate_snapshot.injection_count_rolling_20 == 15
        assert result.gate_snapshot.failure_streak == 1
        assert abs(result.gate_snapshot.success_rate_rolling_20 - 0.2) < 1e-9
