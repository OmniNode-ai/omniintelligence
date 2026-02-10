# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
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

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.enums import EnumHeuristicMethod
from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    ProtocolPatternRepository,
    compute_and_store_heuristics,
    record_session_outcome,
    update_effectiveness_scores,
    update_pattern_rolling_metrics,
)
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    _parse_update_count,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
)
from omniintelligence.nodes.node_pattern_feedback_effect.node import (
    NodePatternFeedbackEffect,
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

    Simulates the learned_patterns table columns relevant to rolling metrics
    and effectiveness scoring.
    """

    id: UUID
    injection_count_rolling_20: int = 0
    success_count_rolling_20: int = 0
    failure_count_rolling_20: int = 0
    failure_streak: int = 0
    quality_score: float = 0.5


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
    # Heuristic fields (OMN-1679)
    contribution_heuristic: str | None = None  # JSONB stored as string
    heuristic_method: str | None = None
    heuristic_confidence: float | None = None


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

        # Handle: Fetch effectiveness scores for patterns
        if (
            "quality_score" in query
            and "learned_patterns" in query
            and "SELECT" in query
        ):
            pattern_ids = args[0]
            results = []
            for pid in pattern_ids:
                if pid in self.patterns:
                    results.append(
                        MockRecord(
                            {
                                "id": pid,
                                "quality_score": self.patterns[pid].quality_score,
                            }
                        )
                    )
            return results

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
        if (
            "UPDATE learned_patterns" in query
            and "failure_streak = failure_streak + 1" in query
        ):
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

        # Handle: Update injection heuristics (OMN-1679)
        # SQL_UPDATE_INJECTION_HEURISTIC: UPDATE pattern_injections SET ... WHERE injection_id = $1 AND contribution_heuristic IS NULL
        if (
            "UPDATE pattern_injections" in query
            and "contribution_heuristic" in query
            and "heuristic_method" in query
        ):
            injection_id = args[0]
            weights_json = args[1]
            method = args[2]
            confidence = args[3]
            count = 0
            for inj in self.injections:
                if (
                    inj.injection_id == injection_id
                    and inj.contribution_heuristic is None
                ):
                    inj.contribution_heuristic = weights_json
                    inj.heuristic_method = method
                    inj.heuristic_confidence = confidence
                    count += 1
            return f"UPDATE {count}"

        # Handle: Update effectiveness scores (quality_score) from rolling metrics
        if (
            "UPDATE learned_patterns" in query
            and "quality_score" in query
            and "injection_count_rolling_20" in query
        ):
            pattern_ids = args[0]
            count = 0
            for pid in pattern_ids:
                if pid in self.patterns:
                    p = self.patterns[pid]
                    if p.injection_count_rolling_20 > 0:
                        p.quality_score = (
                            p.success_count_rolling_20 / p.injection_count_rolling_20
                        )
                    else:
                        p.quality_score = 0.5
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
                failure_reason=f"Failure {i + 1}",
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
        success_rate = (
            updated.success_count_rolling_20 / updated.injection_count_rolling_20
        )
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
        assert _parse_update_count(None) == 0

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


# =============================================================================
# Test Class: Error Handling Tests
# =============================================================================


class MockErrorRepository:
    """Mock repository that raises exceptions for testing error paths.

    This mock allows configuring whether fetch() or execute() should raise
    exceptions, enabling tests for error propagation in record_session_outcome.
    """

    def __init__(
        self,
        fetch_error: Exception | None = None,
        execute_error: Exception | None = None,
    ) -> None:
        """Initialize with optional errors to raise.

        Args:
            fetch_error: Exception to raise on fetch() calls, or None for success
            execute_error: Exception to raise on execute() calls, or None for success
        """
        self._fetch_error = fetch_error
        self._execute_error = execute_error
        self._fetch_results: list[MockRecord] = []

    def set_fetch_results(self, results: list[MockRecord]) -> None:
        """Set the results to return from fetch() if no error configured."""
        self._fetch_results = results

    async def fetch(self, _query: str, *_args: Any) -> list[MockRecord]:
        """Execute fetch, raising configured error if present."""
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._fetch_results

    async def execute(self, _query: str, *_args: Any) -> str:
        """Execute query, raising configured error if present."""
        if self._execute_error is not None:
            raise self._execute_error
        return "UPDATE 1"


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error propagation from repository failures.

    These tests verify that exceptions from the repository layer
    properly propagate through record_session_outcome().
    """

    @pytest.mark.asyncio
    async def test_repository_fetch_error_propagates(
        self,
        sample_session_id: UUID,
    ) -> None:
        """Repository fetch() exception propagates to caller.

        When the repository raises an exception during fetch(), the error
        should propagate up to the caller rather than being silently caught.
        """
        # Arrange: Repository that raises on fetch
        error_message = "Database connection failed"
        error_repo = MockErrorRepository(fetch_error=ConnectionError(error_message))

        # Act & Assert: Exception propagates
        with pytest.raises(ConnectionError, match=error_message):
            await record_session_outcome(
                session_id=sample_session_id,
                success=True,
                repository=error_repo,
            )

    @pytest.mark.asyncio
    async def test_repository_execute_error_propagates(
        self,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Repository execute() exception propagates to caller.

        When the repository raises an exception during execute() (after
        a successful fetch), the error should propagate up to the caller.
        """
        # Arrange: Repository that succeeds on fetch but raises on execute
        error_message = "Failed to update patterns"
        error_repo = MockErrorRepository(execute_error=RuntimeError(error_message))
        # Configure fetch to return injections so we proceed to execute
        error_repo.set_fetch_results(
            [
                MockRecord(
                    {
                        "injection_id": uuid4(),
                        "pattern_ids": [sample_pattern_id],
                    }
                )
            ]
        )

        # Act & Assert: Exception propagates
        with pytest.raises(RuntimeError, match=error_message):
            await record_session_outcome(
                session_id=sample_session_id,
                success=True,
                repository=error_repo,
            )


# =============================================================================
# Test Class: NodePatternFeedbackEffect Declarative Pattern Tests
# =============================================================================


@pytest.mark.unit
class TestNodePatternFeedbackEffect:
    """Tests verifying the NodePatternFeedbackEffect declarative pattern.

    With the ONEX declarative pattern (OMN-1757), the node class is a pure
    type anchor with no custom __init__ or execute() overrides. All business
    logic is in handlers which are invoked directly by callers/orchestrators.

    These tests verify:
    - Handler can be called directly with repository dependency
    - Handler properly propagates errors from repository
    - Handler returns correct results

    Note:
        The node is now a pure declarative shell - NO constructor-based DI.
        Callers invoke handlers directly with dependencies as parameters.
    """

    @pytest.mark.asyncio
    async def test_handler_with_repository_exception_propagates(
        self,
        sample_session_id: UUID,
    ) -> None:
        """Handler with failing repository propagates exception to caller.

        With declarative pattern, handlers receive dependencies as parameters.
        Exceptions from dependencies propagate to the caller.
        """
        # Arrange: Repository that raises on fetch
        error_message = "Database connection lost"
        error_repo = MockErrorRepository(fetch_error=ConnectionError(error_message))

        # Act & Assert: Call handler directly, exception propagates
        with pytest.raises(ConnectionError, match=error_message):
            await record_session_outcome(
                session_id=sample_session_id,
                success=True,
                repository=error_repo,
            )

    @pytest.mark.asyncio
    async def test_handler_success_with_repository(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Handler with working repository returns SUCCESS.

        With declarative pattern, callers invoke the handler directly
        with the repository as a parameter dependency.
        """
        # Arrange: Add pattern and injection to repository
        mock_repository.add_pattern(
            PatternState(
                id=sample_pattern_id,
                injection_count_rolling_20=5,
                success_count_rolling_20=3,
                failure_count_rolling_20=2,
            )
        )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: Call handler directly with repository dependency
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.session_id == sample_session_id
        assert result.patterns_updated == 1
        assert sample_pattern_id in result.pattern_ids
        assert result.error_message is None

    def test_node_is_pure_declarative_shell(self) -> None:
        """Verify node class is a pure type anchor with no custom code.

        The declarative pattern requires:
        - No __init__ override (uses base class only)
        - No execute() override (routing via contract.yaml)
        - Class body contains only docstring/comment
        """
        import inspect

        # Get the class source
        source = inspect.getsource(NodePatternFeedbackEffect)

        # Verify no __init__ definition
        assert "def __init__" not in source, "Node should not override __init__"

        # Verify no execute definition
        assert "def execute" not in source, "Node should not override execute"
        assert "async def execute" not in source, "Node should not override execute"

        # Verify it inherits from NodeEffect
        assert issubclass(NodePatternFeedbackEffect, NodeEffect)


# =============================================================================
# Test Class: Contribution Heuristics (OMN-1679)
# =============================================================================


@pytest.mark.unit
class TestContributionHeuristics:
    """Tests for contribution heuristic computation and storage.

    These tests verify OMN-1679 functionality:
    - Heuristics are computed at outcome recording time
    - Weights are stored in pattern_injections table
    - Different heuristic methods work correctly
    - Idempotency is maintained (only write if NULL)
    - Duplicate patterns across injections are handled correctly

    Reference:
        - OMN-1679: FEEDBACK-004 contribution heuristic for outcome attribution
    """

    @pytest.mark.asyncio
    async def test_heuristic_stored_on_outcome_recording(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Heuristics are computed and stored when recording outcome."""
        # Arrange
        injection_id = uuid4()
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.EQUAL_SPLIT,
        )

        # Assert: Heuristic was stored
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        assert injection.contribution_heuristic is not None
        assert injection.heuristic_method == "equal_split"
        assert injection.heuristic_confidence == 0.5

        # Verify weights JSON
        weights = json.loads(injection.contribution_heuristic)
        assert str(sample_pattern_id) in weights
        assert weights[str(sample_pattern_id)] == 1.0

    @pytest.mark.asyncio
    async def test_equal_split_with_multiple_patterns(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """EQUAL_SPLIT distributes weight equally among patterns."""
        # Arrange
        injection_id = uuid4()
        for pid in sample_pattern_ids:
            mock_repository.add_pattern(PatternState(id=pid))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=sample_pattern_ids,  # 3 patterns
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.EQUAL_SPLIT,
        )

        # Assert
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        weights = json.loads(injection.contribution_heuristic)

        # Each pattern gets 1/3
        expected = 1.0 / 3
        for pid in sample_pattern_ids:
            assert abs(weights[str(pid)] - expected) < 1e-9

    @pytest.mark.asyncio
    async def test_recency_weighted_later_patterns_get_more(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """RECENCY_WEIGHTED gives more weight to later patterns."""
        # Arrange
        injection_id = uuid4()
        for pid in sample_pattern_ids:
            mock_repository.add_pattern(PatternState(id=pid))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=sample_pattern_ids,  # 3 patterns in order
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.RECENCY_WEIGHTED,
        )

        # Assert
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        assert injection.heuristic_method == "recency_weighted"
        assert injection.heuristic_confidence == 0.4

        weights = json.loads(injection.contribution_heuristic)
        # Positions: 1, 2, 3. Sum = 6. Weights: 1/6, 2/6, 3/6
        assert abs(weights[str(sample_pattern_ids[0])] - 1.0 / 6) < 1e-9
        assert abs(weights[str(sample_pattern_ids[1])] - 2.0 / 6) < 1e-9
        assert abs(weights[str(sample_pattern_ids[2])] - 3.0 / 6) < 1e-9

    @pytest.mark.asyncio
    async def test_first_match_only_first_pattern(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """FIRST_MATCH gives all credit to first pattern."""
        # Arrange
        injection_id = uuid4()
        for pid in sample_pattern_ids:
            mock_repository.add_pattern(PatternState(id=pid))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=sample_pattern_ids,
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.FIRST_MATCH,
        )

        # Assert
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        assert injection.heuristic_method == "first_match"
        assert injection.heuristic_confidence == 0.3

        weights = json.loads(injection.contribution_heuristic)
        assert weights == {str(sample_pattern_ids[0]): 1.0}

    @pytest.mark.asyncio
    async def test_idempotency_heuristic_not_overwritten(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Heuristic is not overwritten on retry (idempotency).

        When contribution_heuristic is already set, the UPDATE should not
        modify it (WHERE contribution_heuristic IS NULL guards against this).
        """
        # Arrange: Injection with heuristic already set
        injection_id = uuid4()
        original_heuristic = json.dumps({str(sample_pattern_id): 0.99})
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
                contribution_heuristic=original_heuristic,  # Already set!
                heuristic_method="equal_split",
                heuristic_confidence=0.5,
            )
        )

        # Act: Try to compute heuristics again
        updated = await compute_and_store_heuristics(
            injection_rows=[
                MockRecord(
                    {
                        "injection_id": injection_id,
                        "pattern_ids": [sample_pattern_id],
                    }
                )
            ],
            heuristic_method=EnumHeuristicMethod.FIRST_MATCH,  # Different method
            repository=mock_repository,
        )

        # Assert: Should NOT have updated (idempotency)
        assert updated == 0

        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        # Original values preserved
        assert injection.contribution_heuristic == original_heuristic
        assert injection.heuristic_method == "equal_split"

    @pytest.mark.asyncio
    async def test_multiple_injections_same_session(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """Multiple injections in same session get same heuristic weights.

        When a session has multiple injections, all patterns across all
        injections are collected in order, and the same computed weights
        are stored on each injection row.
        """
        # Arrange: Two injections, each with different patterns
        injection_id_1 = uuid4()
        injection_id_2 = uuid4()

        for pid in sample_pattern_ids:
            mock_repository.add_pattern(PatternState(id=pid))

        # Injection 1: patterns A, B
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id_1,
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_ids[0], sample_pattern_ids[1]],
            )
        )
        # Injection 2: pattern C
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id_2,
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_ids[2]],
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.EQUAL_SPLIT,
        )

        # Assert: Both injections have the same weights
        inj1 = next(
            i for i in mock_repository.injections if i.injection_id == injection_id_1
        )
        inj2 = next(
            i for i in mock_repository.injections if i.injection_id == injection_id_2
        )

        # Both should have same weights (session-level computation)
        assert inj1.contribution_heuristic == inj2.contribution_heuristic
        assert inj1.heuristic_method == inj2.heuristic_method
        assert inj1.heuristic_confidence == inj2.heuristic_confidence

        # Weights: 3 patterns total, each gets 1/3
        weights = json.loads(inj1.contribution_heuristic)
        for pid in sample_pattern_ids:
            assert abs(weights[str(pid)] - 1.0 / 3) < 1e-9

    @pytest.mark.asyncio
    async def test_duplicate_patterns_across_injections_accumulated(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """Duplicate patterns across injections accumulate weight.

        If pattern A appears in both injection 1 and injection 2, its
        weight is accumulated (respecting order for RECENCY_WEIGHTED).
        """
        # Arrange: Two injections, pattern A appears in both
        injection_id_1 = uuid4()
        injection_id_2 = uuid4()
        pattern_a = sample_pattern_ids[0]
        pattern_b = sample_pattern_ids[1]

        for pid in [pattern_a, pattern_b]:
            mock_repository.add_pattern(PatternState(id=pid))

        # Injection 1: A, B
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id_1,
                session_id=sample_session_id,
                pattern_ids=[pattern_a, pattern_b],
            )
        )
        # Injection 2: A (duplicate)
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id_2,
                session_id=sample_session_id,
                pattern_ids=[pattern_a],
            )
        )

        # Act: Use RECENCY_WEIGHTED to see position-based accumulation
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            heuristic_method=EnumHeuristicMethod.RECENCY_WEIGHTED,
        )

        # Assert
        inj = next(
            i for i in mock_repository.injections if i.injection_id == injection_id_1
        )
        weights = json.loads(inj.contribution_heuristic)

        # Order: A(1), B(2), A(3). Sum = 6.
        # A: 1/6 + 3/6 = 4/6 = 2/3
        # B: 2/6 = 1/3
        assert abs(weights[str(pattern_a)] - 4.0 / 6) < 1e-9
        assert abs(weights[str(pattern_b)] - 2.0 / 6) < 1e-9

    @pytest.mark.asyncio
    async def test_default_heuristic_method_is_equal_split(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Default heuristic method is EQUAL_SPLIT when not specified."""
        # Arrange
        injection_id = uuid4()
        mock_repository.add_pattern(PatternState(id=sample_pattern_id))
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: No heuristic_method specified (use default)
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
            # heuristic_method not specified, should default to EQUAL_SPLIT
        )

        # Assert
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        assert injection.heuristic_method == "equal_split"
        assert injection.heuristic_confidence == 0.5

    @pytest.mark.asyncio
    async def test_empty_pattern_ids_no_heuristic(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
    ) -> None:
        """Injection with empty pattern_ids has no heuristic computed."""
        # Arrange: Injection with no patterns
        injection_id = uuid4()
        mock_repository.add_injection(
            InjectionState(
                injection_id=injection_id,
                session_id=sample_session_id,
                pattern_ids=[],  # Empty!
            )
        )

        # Act
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: No heuristic computed (nothing to attribute)
        injection = next(
            i for i in mock_repository.injections if i.injection_id == injection_id
        )
        # The heuristic should not be set (empty weights returns early)
        assert injection.contribution_heuristic is None


# =============================================================================
# Test Class: Effectiveness Score Tests (OMN-2077)
# =============================================================================


@pytest.mark.unit
class TestEffectivenessScore:
    """Tests for effectiveness score (quality_score) computation.

    These tests verify OMN-2077 functionality:
    - quality_score is recomputed from rolling metrics after each outcome
    - Formula: success_count_rolling_20 / injection_count_rolling_20
    - Default: 0.5 when no injections recorded
    - Score is returned in the handler result
    - Score is updated in the database

    Reference:
        - OMN-2077: Pattern feedback consumption + scoring
    """

    @pytest.mark.asyncio
    async def test_score_computed_on_success_outcome(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Effectiveness score is recomputed after recording a success outcome."""
        # Arrange: Pattern with 5 injections, 3 successes → after success: 6 inj, 4 suc
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            quality_score=0.5,  # stale score
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

        # Assert: Score recomputed from updated metrics (4/6 ≈ 0.667)
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert sample_pattern_id in result.effectiveness_scores
        expected_score = 4.0 / 6.0
        assert (
            abs(result.effectiveness_scores[sample_pattern_id] - expected_score) < 1e-9
        )

        # Also verify DB state
        assert (
            abs(
                mock_repository.patterns[sample_pattern_id].quality_score
                - expected_score
            )
            < 1e-9
        )

    @pytest.mark.asyncio
    async def test_score_computed_on_failure_outcome(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Effectiveness score is recomputed after recording a failure outcome."""
        # Arrange: Pattern with 5 injections, 3 successes → after failure: 6 inj, 3 suc
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            quality_score=0.5,
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

        # Assert: Score recomputed from updated metrics (3/6 = 0.5)
        expected_score = 3.0 / 6.0
        assert (
            abs(result.effectiveness_scores[sample_pattern_id] - expected_score) < 1e-9
        )
        assert (
            abs(
                mock_repository.patterns[sample_pattern_id].quality_score
                - expected_score
            )
            < 1e-9
        )

    @pytest.mark.asyncio
    async def test_score_perfect_after_all_successes(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Pattern with all successes gets score of 1.0."""
        # Arrange: Fresh pattern
        pattern = PatternState(id=sample_pattern_id)
        mock_repository.add_pattern(pattern)

        # Act: Record 5 consecutive successes
        for _ in range(5):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            result = await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=mock_repository,
            )

        # Assert: 5/5 = 1.0
        assert abs(result.effectiveness_scores[sample_pattern_id] - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_score_zero_after_all_failures(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Pattern with all failures gets score of 0.0."""
        # Arrange: Fresh pattern
        pattern = PatternState(id=sample_pattern_id)
        mock_repository.add_pattern(pattern)

        # Act: Record 5 consecutive failures
        for _ in range(5):
            session_id = uuid4()
            mock_repository.add_injection(
                InjectionState(
                    injection_id=uuid4(),
                    session_id=session_id,
                    pattern_ids=[sample_pattern_id],
                )
            )
            result = await record_session_outcome(
                session_id=session_id,
                success=False,
                repository=mock_repository,
            )

        # Assert: 0/5 = 0.0
        assert abs(result.effectiveness_scores[sample_pattern_id] - 0.0) < 1e-9

    @pytest.mark.asyncio
    async def test_score_at_cap_with_decay(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Score reflects decayed rolling metrics at cap (20 injections)."""
        # Arrange: At cap with 10/10 split
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=20,
            success_count_rolling_20=10,
            failure_count_rolling_20=10,
            quality_score=0.5,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Act: Success → success_count=11, failure_count=9 (decay), inj=20
        await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: 11/20 = 0.55
        expected_score = 11.0 / 20.0
        assert (
            abs(
                mock_repository.patterns[sample_pattern_id].quality_score
                - expected_score
            )
            < 1e-9
        )

    @pytest.mark.asyncio
    async def test_score_for_multiple_patterns(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_ids: list[UUID],
    ) -> None:
        """All patterns in a session get their scores updated."""
        # Arrange: 3 patterns with different starting metrics
        starting_counts = [(5, 3, 2), (10, 8, 2), (20, 15, 5)]
        for pid, (inj, suc, fail) in zip(
            sample_pattern_ids, starting_counts, strict=True
        ):
            mock_repository.add_pattern(
                PatternState(
                    id=pid,
                    injection_count_rolling_20=inj,
                    success_count_rolling_20=suc,
                    failure_count_rolling_20=fail,
                )
            )
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=sample_pattern_ids,
            )
        )

        # Act: Record success
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: All patterns have updated scores
        assert len(result.effectiveness_scores) == 3
        for pid in sample_pattern_ids:
            assert pid in result.effectiveness_scores
            p = mock_repository.patterns[pid]
            expected = p.success_count_rolling_20 / p.injection_count_rolling_20
            assert abs(result.effectiveness_scores[pid] - expected) < 1e-9

    @pytest.mark.asyncio
    async def test_score_empty_for_no_injections_found(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
    ) -> None:
        """No effectiveness scores returned when no injections found."""
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.effectiveness_scores == {}

    @pytest.mark.asyncio
    async def test_score_empty_for_already_recorded(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """No effectiveness scores returned when already recorded."""
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
                outcome_recorded=True,
            )
        )

        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        assert result.status == EnumOutcomeRecordingStatus.ALREADY_RECORDED
        assert result.effectiveness_scores == {}

    @pytest.mark.asyncio
    async def test_score_graceful_degradation_on_scoring_failure(
        self,
        mock_repository: MockPatternRepository,
        sample_session_id: UUID,
        sample_pattern_id: UUID,
    ) -> None:
        """Handler returns SUCCESS with None scores when scoring raises."""
        # Arrange: Pattern and injection in place
        pattern = PatternState(
            id=sample_pattern_id,
            injection_count_rolling_20=5,
            success_count_rolling_20=3,
            failure_count_rolling_20=2,
            quality_score=0.5,
        )
        mock_repository.add_pattern(pattern)
        mock_repository.add_injection(
            InjectionState(
                injection_id=uuid4(),
                session_id=sample_session_id,
                pattern_ids=[sample_pattern_id],
            )
        )

        # Patch update_effectiveness_scores to raise
        original_execute = mock_repository.execute

        call_count = 0

        async def failing_execute(query: str, *args: Any) -> str:
            nonlocal call_count
            # Let the first execute calls through (marking injections + rolling metrics)
            # Fail on the effectiveness score UPDATE (contains quality_score and injection_count_rolling_20)
            if (
                "UPDATE learned_patterns" in query
                and "quality_score" in query
                and "injection_count_rolling_20" in query
            ):
                raise RuntimeError("Simulated DB failure on effectiveness scoring")
            return await original_execute(query, *args)

        # Monkey-patch execute for fault-injection test; type mismatch is intentional (OMN-2077)
        mock_repository.execute = failing_execute  # type: ignore[assignment]

        # Act
        result = await record_session_outcome(
            session_id=sample_session_id,
            success=True,
            repository=mock_repository,
        )

        # Assert: Critical operations succeeded, scoring failure surfaced via None
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.effectiveness_scores is None
        assert result.patterns_updated > 0


# =============================================================================
# Test Class: update_effectiveness_scores Direct Tests (OMN-2077)
# =============================================================================


@pytest.mark.unit
class TestUpdateEffectivenessScores:
    """Direct tests for update_effectiveness_scores function.

    These tests verify the lower-level function independently of
    record_session_outcome.
    """

    @pytest.mark.asyncio
    async def test_empty_pattern_list_returns_empty(
        self,
        mock_repository: MockPatternRepository,
    ) -> None:
        """Empty pattern list returns empty dict."""
        result = await update_effectiveness_scores(
            pattern_ids=[],
            repository=mock_repository,
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_score_formula_success_ratio(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Score = success_count / injection_count."""
        mock_repository.add_pattern(
            PatternState(
                id=sample_pattern_id,
                injection_count_rolling_20=10,
                success_count_rolling_20=7,
                failure_count_rolling_20=3,
                quality_score=0.0,  # Stale
            )
        )

        scores = await update_effectiveness_scores(
            pattern_ids=[sample_pattern_id],
            repository=mock_repository,
        )

        assert abs(scores[sample_pattern_id] - 0.7) < 1e-9

    @pytest.mark.asyncio
    async def test_score_default_when_no_injections(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
    ) -> None:
        """Score defaults to 0.5 when injection_count is 0."""
        mock_repository.add_pattern(
            PatternState(
                id=sample_pattern_id,
                injection_count_rolling_20=0,
                success_count_rolling_20=0,
            )
        )

        scores = await update_effectiveness_scores(
            pattern_ids=[sample_pattern_id],
            repository=mock_repository,
        )

        assert abs(scores[sample_pattern_id] - 0.5) < 1e-9
