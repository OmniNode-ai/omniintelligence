# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Comprehensive unit tests for session outcome recording and rolling metric updates.

This module tests the pattern feedback loop handlers:
- `record_session_outcome()`: Main entry point for recording session results
- `update_pattern_rolling_metrics()`: Updates rolling window counters with decay

Test cases are organized by acceptance criteria from OMN-1678:
1. Normal increment tests (below cap)
2. Hit cap tests (reaching 20)
3. Decay on success (at cap)
4. Decay on failure (at cap)
5. Floor at zero (edge case)
6. Recovery from early failures
7. Idempotency tests
8. Multi-pattern session tests

Reference:
    - OMN-1678: Implement rolling window metric updates with decay approximation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    ProtocolPatternRepository,
    record_session_outcome,
    update_pattern_rolling_metrics,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    _parse_update_count,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
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
class PatternState:
    """In-memory state for a learned pattern.

    Simulates the learned_patterns table columns relevant to rolling metrics.
    """

    id: UUID
    injection_count_rolling_20: int = 0
    success_count_rolling_20: int = 0
    failure_count_rolling_20: int = 0
    failure_streak: int = 0


@dataclass
class InjectionState:
    """In-memory state for a pattern injection.

    Simulates the pattern_injections table.
    """

    injection_id: UUID
    session_id: UUID
    pattern_ids: list[UUID]
    outcome_recorded: bool = False
    outcome_success: bool | None = None
    outcome_failure_reason: str | None = None


class MockPatternRepository:
    """In-memory mock repository implementing ProtocolPatternRepository.

    This mock simulates asyncpg behavior including:
    - Query execution with positional parameters ($1, $2, etc.)
    - Returning list of Record-like objects for fetch()
    - Returning status strings like "UPDATE 5" for execute()
    - Simulating the actual SQL logic for rolling window updates

    The repository tracks query history for verification in tests.

    Example:
        repo = MockPatternRepository()
        repo.add_pattern(PatternState(id=uuid4(), injection_count_rolling_20=5))
        repo.add_injection(InjectionState(...))

        result = await record_session_outcome(session_id, True, repository=repo)

        assert repo.queries_executed == [...]  # Verify query sequence
    """

    def __init__(self) -> None:
        """Initialize empty repository state."""
        self.patterns: dict[UUID, PatternState] = {}
        self.injections: list[InjectionState] = []
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []

    def add_pattern(self, pattern: PatternState) -> None:
        """Add a pattern to the mock database."""
        self.patterns[pattern.id] = pattern

    def add_injection(self, injection: InjectionState) -> None:
        """Add an injection to the mock database."""
        self.injections.append(injection)

    async def fetch(self, query: str, *args: Any) -> list[MockRecord]:
        """Execute a query and return results as MockRecord objects.

        Simulates asyncpg fetch() behavior. Supports the specific queries
        used by the session outcome handlers.
        """
        self.queries_executed.append((query, args))

        # Handle: Find unrecorded injections for session
        if "pattern_injections" in query and "outcome_recorded = FALSE" in query:
            session_id = args[0]
            results = []
            for inj in self.injections:
                if inj.session_id == session_id and not inj.outcome_recorded:
                    results.append(
                        MockRecord(
                            {
                                "injection_id": inj.injection_id,
                                "pattern_ids": inj.pattern_ids,
                            }
                        )
                    )
            return results

        # Handle: Count total injections for session (idempotency check)
        if "COUNT(*)" in query and "pattern_injections" in query:
            session_id = args[0]
            count = sum(1 for inj in self.injections if inj.session_id == session_id)
            return [MockRecord({"count": count})]

        return []

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return status string.

        Simulates asyncpg execute() behavior. Implements the actual
        rolling window update logic from the SQL queries.
        """
        self.queries_executed.append((query, args))

        # Handle: Mark injections as recorded
        if "UPDATE pattern_injections" in query and "outcome_recorded = TRUE" in query:
            session_id = args[0]
            success = args[1]
            failure_reason = args[2]
            count = 0
            for inj in self.injections:
                if inj.session_id == session_id and not inj.outcome_recorded:
                    inj.outcome_recorded = True
                    inj.outcome_success = success
                    inj.outcome_failure_reason = failure_reason
                    count += 1
            return f"UPDATE {count}"

        # Handle: Update learned_patterns on SUCCESS
        if "UPDATE learned_patterns" in query and "failure_streak = 0" in query:
            pattern_ids = args[0]
            count = 0
            for pid in pattern_ids:
                if pid in self.patterns:
                    p = self.patterns[pid]
                    # Simulate SQL: LEAST(injection_count + 1, 20)
                    old_inj = p.injection_count_rolling_20
                    p.injection_count_rolling_20 = min(old_inj + 1, 20)
                    # Simulate SQL: LEAST(success_count + 1, 20)
                    p.success_count_rolling_20 = min(p.success_count_rolling_20 + 1, 20)
                    # Simulate SQL decay: only if at cap AND failure > 0
                    if old_inj >= 20 and p.failure_count_rolling_20 > 0:
                        p.failure_count_rolling_20 -= 1
                    # Reset failure streak
                    p.failure_streak = 0
                    count += 1
            return f"UPDATE {count}"

        # Handle: Update learned_patterns on FAILURE
        if "UPDATE learned_patterns" in query and "failure_streak = failure_streak + 1" in query:
            pattern_ids = args[0]
            count = 0
            for pid in pattern_ids:
                if pid in self.patterns:
                    p = self.patterns[pid]
                    # Simulate SQL: LEAST(injection_count + 1, 20)
                    old_inj = p.injection_count_rolling_20
                    p.injection_count_rolling_20 = min(old_inj + 1, 20)
                    # Simulate SQL: LEAST(failure_count + 1, 20)
                    p.failure_count_rolling_20 = min(p.failure_count_rolling_20 + 1, 20)
                    # Simulate SQL decay: only if at cap AND success > 0
                    if old_inj >= 20 and p.success_count_rolling_20 > 0:
                        p.success_count_rolling_20 -= 1
                    # Increment failure streak
                    p.failure_streak += 1
                    count += 1
            return f"UPDATE {count}"

        return "UPDATE 0"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MockPatternRepository:
    """Create a fresh mock repository for each test."""
    return MockPatternRepository()


@pytest.fixture
def sample_session_id() -> UUID:
    """Fixed session ID for deterministic tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Single pattern ID for simple tests."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_pattern_ids() -> list[UUID]:
    """Multiple pattern IDs for multi-pattern tests."""
    return [
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
    ]


# =============================================================================
# Test Class: Normal Increment Tests (Below Cap)
# =============================================================================


@pytest.mark.unit
class TestNormalIncrementBelowCap:
    """Tests for normal increments when injection_count < 20.

    These tests verify that when the rolling window hasn't reached capacity:
    - Success increments success_count and resets failure_streak
    - Failure increments failure_count and failure_streak
    - No decay occurs (decay only happens at cap)
    """

    @pytest.mark.asyncio
    async def test_success_increments_success_count_resets_failure_streak(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Success outcome increments success_count and resets failure_streak to 0."""
        # Arrange: Pattern with 5 injections, 3 successes, 2 failures, streak of 2
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            failure_streak=2,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.patterns_updated == 1

        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 6  # 5 + 1
        assert updated.success_count_rolling_20 == 4  # 3 + 1
        assert updated.failure_count_rolling_20 == 2  # No decay (not at cap)
        assert updated.failure_streak == 0  # Reset on success

    @pytest.mark.asyncio
    async def test_failure_increments_failure_count_and_streak(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Failure outcome increments failure_count and failure_streak."""
        # Arrange: Pattern with 5 injections, 3 successes, 2 failures, streak of 0
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=False,
            failure_reason="Test failure",
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.patterns_updated == 1

        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 6  # 5 + 1
        assert updated.success_count_rolling_20 == 3  # No decay (not at cap)
        assert updated.failure_count_rolling_20 == 3  # 2 + 1
        assert updated.failure_streak == 1  # 0 + 1

    @pytest.mark.asyncio
    async def test_multiple_consecutive_failures_increment_streak(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Multiple consecutive failures increment failure_streak each time."""
        # Arrange: Pattern starting at 0
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=0,
            success_count_rolling_20=0,
            failure_count_rolling_20=0,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)

        # Act: Record 3 consecutive failures
        for i in range(3):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=False,
                failure_reason=f"Failure {i+1}",
                repository=mock_repository,
            )

        # Assert
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 3
        assert updated.failure_count_rolling_20 == 3
        assert updated.failure_streak == 3  # Incremented each time


# =============================================================================
# Test Class: Hit Cap Tests (Reaching 20)
# =============================================================================


@pytest.mark.unit
class TestHitCap:
    """Tests for behavior when reaching the cap of 20 injections.

    Key insight: Decay starts on the 21st injection (when cap is already reached),
    NOT on the 20th injection (the one that reaches the cap).
    """

    @pytest.mark.asyncio
    async def test_transition_from_19_to_20_no_decay(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Transition from 19 to 20 injections does NOT trigger decay.

        Decay only occurs when injection_count is ALREADY at 20 before the update.
        """
        # Arrange: 19 injections, reaching cap with this injection
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=19,
            success_count_rolling_20=10,
            failure_count_rolling_20=9,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: Success on the 20th injection
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        # Reaches cap
        assert updated.injection_count_rolling_20 == 20
        # Incremented, no decay
        assert updated.success_count_rolling_20 == 11
        # NO decay - cap not yet reached when update started
        assert updated.failure_count_rolling_20 == 9

    @pytest.mark.asyncio
    async def test_21st_injection_triggers_decay(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """21st injection (when already at 20) triggers decay of opposite bucket."""
        # Arrange: Already at cap of 20
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: Success triggers decay of failure_count
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        # Stays at cap (LEAST function)
        assert updated.injection_count_rolling_20 == 20
        # Capped at 20, was already 10
        assert updated.success_count_rolling_20 == 11
        # Decayed by 1 (was 10, now 9)
        assert updated.failure_count_rolling_20 == 9


# =============================================================================
# Test Class: Decay on Success (At Cap)
# =============================================================================


@pytest.mark.unit
class TestDecayOnSuccess:
    """Tests for decay behavior when recording success at cap.

    When at cap (20 injections) and recording a success:
    - success_count increments (capped at 20)
    - failure_count decrements by 1 (if > 0)
    - failure_streak resets to 0
    """

    @pytest.mark.asyncio
    async def test_success_at_cap_decays_failure_count(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Success at cap: inj=20, suc=10, fail=10 -> success -> suc=11, fail=9."""
        # Arrange
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
            failure_streak=5,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20  # Stays at cap
        assert updated.success_count_rolling_20 == 11  # Incremented
        assert updated.failure_count_rolling_20 == 9  # Decayed
        assert updated.failure_streak == 0  # Reset


# =============================================================================
# Test Class: Decay on Failure (At Cap)
# =============================================================================


@pytest.mark.unit
class TestDecayOnFailure:
    """Tests for decay behavior when recording failure at cap.

    When at cap (20 injections) and recording a failure:
    - failure_count increments (capped at 20)
    - success_count decrements by 1 (if > 0)
    - failure_streak increments
    """

    @pytest.mark.asyncio
    async def test_failure_at_cap_decays_success_count(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Failure at cap: inj=20, suc=10, fail=10 -> failure -> suc=9, fail=11."""
        # Arrange
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=False,
            failure_reason="Test failure",
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20  # Stays at cap
        assert updated.success_count_rolling_20 == 9  # Decayed
        assert updated.failure_count_rolling_20 == 11  # Incremented
        assert updated.failure_streak == 1  # Incremented


# =============================================================================
# Test Class: Floor at Zero (Edge Cases)
# =============================================================================


@pytest.mark.unit
class TestFloorAtZero:
    """Tests for floor behavior when opposite count is already zero.

    The CASE statement in SQL ensures we don't decrement below zero:
    - WHEN ... AND failure_count_rolling_20 > 0 THEN failure_count - 1
    - ELSE failure_count_rolling_20 (no change)
    """

    @pytest.mark.asyncio
    async def test_failure_when_success_at_zero_no_underflow(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Failure at cap with suc=0: inj=20, suc=0, fail=20 -> failure -> suc=0, fail=20.

        Cannot decrement success below 0.
        """
        # Arrange
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=0,
            failure_count_rolling_20=20,
            failure_streak=10,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=False,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.success_count_rolling_20 == 0  # Floor at 0, not -1
        assert updated.failure_count_rolling_20 == 20  # Capped at 20
        assert updated.failure_streak == 11

    @pytest.mark.asyncio
    async def test_success_when_failure_at_zero_no_underflow(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Success at cap with fail=0: inj=20, suc=20, fail=0 -> success -> suc=20, fail=0.

        Cannot decrement failure below 0.
        """
        # Arrange
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=20,
            failure_count_rolling_20=0,
            failure_streak=0,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.success_count_rolling_20 == 20  # Capped at 20
        assert updated.failure_count_rolling_20 == 0  # Floor at 0, not -1


# =============================================================================
# Test Class: Recovery from Early Failures
# =============================================================================


@pytest.mark.unit
class TestRecoveryFromEarlyFailures:
    """Tests for recovery scenarios where patterns start with many failures.

    This tests the practical scenario where a pattern has a rough start
    (many early failures) but then starts succeeding consistently.
    """

    @pytest.mark.asyncio
    async def test_recovery_with_10_consecutive_successes(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Pattern starts with 18 failures, 2 successes. After 10 successes, verify recovery.

        Start: inj=20, suc=2, fail=18
        After 10 successes: success count should increase, failure count should decrease
        """
        # Arrange: Pattern with very poor initial performance
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=2,
            failure_count_rolling_20=18,
            failure_streak=5,
        )
        mock_repository.add_pattern(pattern)

        # Act: Record 10 consecutive successes
        for i in range(10):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=mock_repository,
            )

        # Assert: Significant improvement
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20  # Stays capped
        # Started at 2, gained 10, should be 12
        assert updated.success_count_rolling_20 == 12
        # Started at 18, lost 10, should be 8
        assert updated.failure_count_rolling_20 == 8
        # Reset by each success
        assert updated.failure_streak == 0

    @pytest.mark.asyncio
    async def test_full_recovery_from_all_failures(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Pattern starts with all failures. After 20 successes, verify full recovery.

        Start: inj=20, suc=0, fail=20
        After 20 successes: suc=20, fail=0
        """
        # Arrange: Pattern with 100% failure rate
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=0,
            failure_count_rolling_20=20,
            failure_streak=20,
        )
        mock_repository.add_pattern(pattern)

        # Act: Record 20 consecutive successes
        for _ in range(20):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=mock_repository,
            )

        # Assert: Full recovery
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20
        assert updated.success_count_rolling_20 == 20  # Full recovery
        assert updated.failure_count_rolling_20 == 0  # All failures decayed
        assert updated.failure_streak == 0


# =============================================================================
# Test Class: Idempotency Tests
# =============================================================================


@pytest.mark.unit
class TestIdempotency:
    """Tests for idempotency and edge case handling.

    These tests ensure:
    - Already recorded sessions return ALREADY_RECORDED
    - Sessions with no injections return NO_INJECTIONS_FOUND
    - The same session cannot be recorded twice
    """

    @pytest.mark.asyncio
    async def test_already_recorded_returns_already_recorded_status(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Session with outcome_recorded=TRUE returns ALREADY_RECORDED status."""
        # Arrange: Injection already recorded
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
                outcome_recorded=True,  # Already recorded
                outcome_success=True,
            )
        )
        mock_repository.add_pattern(
            PatternState(id=sample_pattern_id, injection_count_rolling_20=5)
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.ALREADY_RECORDED
        assert result.injections_updated == 0
        assert result.patterns_updated == 0
        assert result.pattern_ids == []

    @pytest.mark.asyncio
    async def test_no_injections_returns_no_injections_found_status(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
    ) -> None:
        """Session with no injections returns NO_INJECTIONS_FOUND status."""
        # Arrange: No injections for this session
        # (empty repository)

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.injections_updated == 0
        assert result.patterns_updated == 0

    @pytest.mark.asyncio
    async def test_recording_same_session_twice_returns_already_recorded(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Recording the same session twice returns ALREADY_RECORDED on second call."""
        # Arrange
        mock_repository.add_pattern(
            PatternState(id=sample_pattern_id, injection_count_rolling_20=5)
        )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: First recording
        result1 = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Act: Second recording of same session
        result2 = await record_session_outcome(
            session_id=sample_session_id,
            success=False,  # Different outcome, still should fail
            repository=mock_repository,
        )

        # Assert
        assert result1.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result2.status == EnumOutcomeRecordingStatus.ALREADY_RECORDED

    @pytest.mark.asyncio
    async def test_partial_recording_handles_mixed_states(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Session with some recorded and some unrecorded injections processes only unrecorded."""
        # Arrange: Two injections, one recorded, one not
        mock_repository.add_pattern(
            PatternState(id=sample_pattern_id, injection_count_rolling_20=5)
        )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
                outcome_recorded=True,  # Already recorded
            )
        )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
                outcome_recorded=False,  # Not yet recorded
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: Should process only the unrecorded injection
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.injections_updated == 1  # Only the unrecorded one


# =============================================================================
# Test Class: Multi-Pattern Session Tests
# =============================================================================


@pytest.mark.unit
class TestMultiPatternSession:
    """Tests for sessions that injected multiple patterns.

    A single session can inject multiple patterns. When recording the outcome,
    all patterns should be updated.
    """

    @pytest.mark.asyncio
    async def test_session_with_3_patterns_updates_all(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """Session with 3 patterns injected updates all 3 patterns."""
        # Arrange: 3 patterns, 1 injection with all 3
        for pid in sample_pattern_ids:
            mock_repository.add_pattern(
                PatternState(
                    id=pid,
                    injection_count_rolling_20=5,
                    success_count_rolling_20=3,
                    failure_count_rolling_20=2,
                    failure_streak=0,
                )
            )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=sample_pattern_ids,  # All 3 patterns
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.patterns_updated == 3
        assert len(result.pattern_ids) == 3

        # Verify all patterns were updated
        for pid in sample_pattern_ids:
            updated = mock_repository.patterns[pid]
            assert updated.injection_count_rolling_20 == 6
            assert updated.success_count_rolling_20 == 4
            assert updated.failure_streak == 0

    @pytest.mark.asyncio
    async def test_multiple_injections_with_overlapping_patterns(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """Multiple injections in same session with overlapping patterns.

        Pattern A appears in both injections, patterns B and C appear in one each.
        All should be updated exactly once (deduplicated).
        """
        # Arrange
        for pid in sample_pattern_ids:
            mock_repository.add_pattern(
                PatternState(
                    id=pid,
                    injection_count_rolling_20=10,
                    success_count_rolling_20=5,
                    failure_count_rolling_20=5,
                )
            )

        # Injection 1: Pattern A and B
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_ids[0], sample_pattern_ids[1]],
            )
        )
        # Injection 2: Pattern A and C (A overlaps)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_ids[0], sample_pattern_ids[2]],
            )
        )

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: All 3 unique patterns updated
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.patterns_updated == 3
        # Patterns are deduplicated
        assert len(result.pattern_ids) == 3
        assert set(result.pattern_ids) == set(sample_pattern_ids)


# =============================================================================
# Test Class: Update Pattern Rolling Metrics Direct Tests
# =============================================================================


@pytest.mark.unit
class TestUpdatePatternRollingMetrics:
    """Direct tests for update_pattern_rolling_metrics function.

    These tests verify the lower-level function independently of
    record_session_outcome.
    """

    @pytest.mark.asyncio
    async def test_empty_pattern_list_returns_zero(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Empty pattern list returns 0 updated."""
        result = await update_pattern_rolling_metrics(
            pattern_ids=[],
            success=True,
            repository=mock_repository,
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_nonexistent_patterns_returns_zero(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Patterns not in database returns 0 updated."""
        result = await update_pattern_rolling_metrics(
            pattern_ids=[uuid4(), uuid4()],
            success=True,
            repository=mock_repository,
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_success_uses_success_sql(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Success=True uses the success SQL query (failure_streak = 0)."""
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))

        await update_pattern_rolling_metrics(
            pattern_ids=[sample_pattern_id],
            success=True,
            repository=mock_repository,
        )

        # Verify the correct SQL was used
        queries = [q[0] for q in mock_repository.queries_executed]
        assert any("failure_streak = 0" in q for q in queries)

    @pytest.mark.asyncio
    async def test_failure_uses_failure_sql(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Success=False uses the failure SQL query (failure_streak + 1)."""
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))

        await update_pattern_rolling_metrics(
            pattern_ids=[sample_pattern_id],
            success=False,
            repository=mock_repository,
        )

        # Verify the correct SQL was used
        queries = [q[0] for q in mock_repository.queries_executed]
        assert any("failure_streak = failure_streak + 1" in q for q in queries)


# =============================================================================
# Test Class: Decay Approximation Algorithm Tests
# =============================================================================


@pytest.mark.unit
class TestDecayApproximation:
    """Focused tests on the decay approximation algorithm.

    The decay approximation ensures:
    1. Counters never exceed 20
    2. The ratio reflects recent performance (rolling window)
    3. Old outcomes are "forgotten" as new ones arrive
    """

    @pytest.mark.asyncio
    async def test_rolling_window_eventually_forgets_old_failures(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """After 20+ successes, early failures are completely forgotten.

        This tests the key property of the rolling window: old data decays away.
        """
        # Arrange: Start with 20 failures
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=0,
            failure_count_rolling_20=20,
            failure_streak=20,
        )
        mock_repository.add_pattern(pattern)

        # Act: Record 25 consecutive successes
        for _ in range(25):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=mock_repository,
            )

        # Assert: Original failures are forgotten
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20
        assert updated.success_count_rolling_20 == 20
        # All 20 failures decayed (limited by initial failure count of 20)
        assert updated.failure_count_rolling_20 == 0

    @pytest.mark.asyncio
    async def test_success_rate_reflects_recent_performance(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Success rate = success_count / injection_count reflects recent window."""
        # Arrange: Start at cap with 50/50 split
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
        )
        mock_repository.add_pattern(pattern)

        # Act: Record 5 successes (should shift ratio toward success)
        for _ in range(5):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=mock_repository,
            )

        # Assert: Ratio shifted
        updated = mock_repository.patterns[sample_pattern_id]
        success_rate = updated.success_count_rolling_20 / updated.injection_count_rolling_20
        # Started at 50%, after 5 successes should be ~75% (15/20)
        assert success_rate == 0.75

    @pytest.mark.asyncio
    async def test_alternating_outcomes_stabilize_at_50_percent(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Alternating success/failure should stabilize around 50/50."""
        # Arrange: Start at cap
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
        )
        mock_repository.add_pattern(pattern)

        # Act: Alternate 20 times (10 success, 10 failure)
        for i in range(20):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            await record_session_outcome(
                session_id=session_id,
                success=(i % 2 == 0),  # Alternating
                repository=mock_repository,
            )

        # Assert: Should remain close to 50/50
        updated = mock_repository.patterns[sample_pattern_id]
        assert updated.injection_count_rolling_20 == 20
        # With alternating pattern, should stay around 10
        # Actual value depends on starting point and sequence
        assert 8 <= updated.success_count_rolling_20 <= 12
        assert 8 <= updated.failure_count_rolling_20 <= 12


# =============================================================================
# Test Class: Protocol Compliance
# =============================================================================


@pytest.mark.unit
class TestProtocolCompliance:
    """Tests verifying MockPatternRepository implements ProtocolPatternRepository."""

    def test_mock_repository_is_protocol_compliant(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """MockPatternRepository satisfies ProtocolPatternRepository protocol."""
        assert isinstance(mock_repository, ProtocolPatternRepository)

    def test_mock_repository_has_fetch_method(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """MockPatternRepository has async fetch method."""
        assert hasattr(mock_repository, "fetch")
        assert callable(mock_repository.fetch)

    def test_mock_repository_has_execute_method(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """MockPatternRepository has async execute method."""
        assert hasattr(mock_repository, "execute")
        assert callable(mock_repository.execute)


# =============================================================================
# Test Class: Result Model Validation
# =============================================================================


@pytest.mark.unit
class TestResultModelValidation:
    """Tests verifying ModelSessionOutcomeResult contains correct data."""

    @pytest.mark.asyncio
    async def test_success_result_has_all_fields(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Successful recording returns result with all expected fields."""
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.session_id == sample_session_id
        assert result.injections_updated >= 1
        assert result.patterns_updated >= 1
        assert len(result.pattern_ids) >= 1
        assert result.recorded_at is not None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failure_reason_cleared_on_success(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """When success=True, failure_reason is not stored."""
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            failure_reason="This should be ignored",
            repository=mock_repository,
        )

        # Verify the injection was marked with success=True and no failure_reason
        injection = next(
            i for i in mock_repository.injections if i.session_id == sample_session_id
        )
        assert injection.outcome_success is True
        assert injection.outcome_failure_reason is None


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
        # The function signature says str, but we handle falsy values
        assert _parse_update_count(None) == 0  # type: ignore[arg-type]

    def test_single_word_returns_zero(self) -> None:
        """Single word (no count) returns 0."""
        assert _parse_update_count("UPDATE") == 0
        assert _parse_update_count("error") == 0

    def test_invalid_number_returns_zero(self) -> None:
        """Non-numeric count returns 0."""
        assert _parse_update_count("UPDATE abc") == 0
        assert _parse_update_count("UPDATE foo bar") == 0

    def test_whitespace_handling(self) -> None:
        """Handles various whitespace patterns."""
        assert _parse_update_count("  UPDATE  5  ") == 5
