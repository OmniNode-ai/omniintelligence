# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Golden path verification for pattern feedback effectiveness scoring (OMN-2169).

These integration tests verify the complete feedback loop against a real
PostgreSQL database:

1. Outcome event is consumed and processed by the handler
2. Effectiveness score is updated correctly in learned_patterns
3. Score delta matches the expected change from known starting metrics

Each test runs inside a transaction that is rolled back on teardown,
ensuring zero pollution between tests or to production data.

Prerequisites:
    - PostgreSQL reachable at POSTGRES_HOST:POSTGRES_PORT (from .env)
    - POSTGRES_PASSWORD set in .env

Run with:
    pytest tests/integration/nodes/node_pattern_feedback_effect/test_golden_path_verification.py -v

Reference:
    - OMN-2169: Golden path pattern feedback verification
    - OMN-2077: Effectiveness score computation
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    ROLLING_WINDOW_SIZE,
    event_to_handler_args,
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
)
from tests.integration.conftest import TEST_DOMAIN_ID

from .helpers import (
    assert_score_updated,
    create_feedback_scenario,
    create_test_injection,
    create_test_pattern,
    fetch_pattern_score,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def txn_conn(db_conn: Any) -> AsyncGenerator[Any, None]:
    """Wrap db_conn in a transaction that auto-rolls back after each test.

    This provides complete test isolation: all INSERTs and UPDATEs made
    during the test are undone on teardown, leaving the database unchanged.

    Yields:
        The same asyncpg.Connection, but inside an active transaction.

    Note:
        Typed as ``Any`` because ``db_conn`` comes from the integration
        conftest where the concrete asyncpg type is unavailable at import
        time (the fixture may be skipped when PostgreSQL is unreachable).

        Exception safety: if ``transaction()`` or ``start()`` raises, the
        ``try``/``finally`` block is never entered, so ``rollback()`` is
        not called on an un-started transaction.  This is safe by Python
        generator semantics -- only exceptions after ``yield`` trigger
        the ``finally`` clause.
    """
    txn = db_conn.transaction()
    await txn.start()
    try:
        yield db_conn
    finally:
        await txn.rollback()


# =============================================================================
# Golden Path: Single Pattern SUCCESS (below cap)
# =============================================================================


class TestSinglePatternSuccessBelowCap:
    """Verify effectiveness score update for a single pattern SUCCESS outcome.

    Starting state: injection=10, success=8, failure=2 (below cap of 20)
    Action: Record SUCCESS outcome
    Expected: injection=11, success=9, failure=2 (no decay)
              quality_score = 9/11 ≈ 0.818182
    """

    @pytest.mark.integration
    async def test_handler_returns_success_status(self, txn_conn: Any) -> None:
        """Handler returns SUCCESS status after processing outcome event."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.injections_updated == 1
        assert result.patterns_updated == 1
        assert len(result.pattern_ids) == 1

    @pytest.mark.integration
    async def test_effectiveness_score_matches_expected(self, txn_conn: Any) -> None:
        """Effectiveness score = 9/11 after SUCCESS (below cap, no decay)."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        # Handler returns the new effectiveness scores
        expected_score = 9.0 / 11.0  # ≈ 0.818182
        assert result.effectiveness_scores is not None
        actual_score = result.effectiveness_scores[scenario.pattern_ids[0]]
        assert (
            abs(actual_score - expected_score) < 1e-6
        ), f"Expected {expected_score}, got {actual_score}"

    @pytest.mark.integration
    async def test_database_score_matches_handler_output(self, txn_conn: Any) -> None:
        """Database quality_score matches what the handler returned."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        # Verify the DB was actually updated (not just handler return value)
        expected_score = 9.0 / 11.0
        await assert_score_updated(txn_conn, scenario.pattern_ids[0], expected_score)

    @pytest.mark.integration
    async def test_score_delta_is_positive(self, txn_conn: Any) -> None:
        """Score delta after SUCCESS is positive (score improved)."""
        starting_quality = 0.5
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )
        # Explicitly set starting quality_score to decouple from helper default
        await txn_conn.execute(
            "UPDATE learned_patterns SET quality_score = $1 WHERE id = $2",
            starting_quality,
            scenario.pattern_ids[0],
        )

        score_before = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        assert abs(score_before - starting_quality) < 1e-6

        await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        score_after = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        delta = score_after - score_before

        # Starting quality_score=0.5, new=9/11≈0.818 → delta ≈ +0.318
        expected_delta = (9.0 / 11.0) - starting_quality
        assert (
            abs(delta - expected_delta) < 1e-6
        ), f"Expected delta {expected_delta}, got {delta}"


# =============================================================================
# Golden Path: Single Pattern FAILURE (below cap)
# =============================================================================


class TestSinglePatternFailureBelowCap:
    """Verify effectiveness score update for a single pattern FAILURE outcome.

    Starting state: injection=10, success=8, failure=2 (below cap of 20)
    Action: Record FAILURE outcome
    Expected: injection=11, success=8 (unchanged), failure=3
              quality_score = 8/11 ≈ 0.727273
    """

    @pytest.mark.integration
    async def test_effectiveness_score_after_failure(self, txn_conn: Any) -> None:
        """Effectiveness score = 8/11 after FAILURE (below cap, no decay)."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=False,
            failure_reason="test failure",
            repository=txn_conn,
        )

        expected_score = 8.0 / 11.0  # ≈ 0.727273
        assert result.effectiveness_scores is not None
        actual_score = result.effectiveness_scores[scenario.pattern_ids[0]]
        assert (
            abs(actual_score - expected_score) < 1e-6
        ), f"Expected {expected_score}, got {actual_score}"

    @pytest.mark.integration
    async def test_score_delta_matches_expected_after_failure(
        self, txn_conn: Any
    ) -> None:
        """Score delta after FAILURE matches the expected value from known metrics."""
        starting_quality = 0.5
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )
        # Explicitly set starting quality_score to decouple from helper default
        await txn_conn.execute(
            "UPDATE learned_patterns SET quality_score = $1 WHERE id = $2",
            starting_quality,
            scenario.pattern_ids[0],
        )

        score_before = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        assert abs(score_before - starting_quality) < 1e-6

        await record_session_outcome(
            session_id=scenario.session_id,
            success=False,
            failure_reason="test failure",
            repository=txn_conn,
        )

        score_after = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        delta = score_after - score_before

        # Starting quality_score=0.5, new=8/11≈0.727 → delta ≈ +0.227
        expected_delta = (8.0 / 11.0) - starting_quality
        assert (
            abs(delta - expected_delta) < 1e-6
        ), f"Expected delta {expected_delta}, got {delta}"

    @pytest.mark.integration
    async def test_database_score_matches_after_failure(self, txn_conn: Any) -> None:
        """Database quality_score matches expected value after FAILURE."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        await record_session_outcome(
            session_id=scenario.session_id,
            success=False,
            failure_reason="test failure",
            repository=txn_conn,
        )

        expected_score = 8.0 / 11.0
        await assert_score_updated(txn_conn, scenario.pattern_ids[0], expected_score)


# =============================================================================
# Golden Path: At-Cap With Decay
# =============================================================================


class TestAtCapWithDecay:
    """Verify decay approximation when at rolling window cap.

    Starting state: injection=20, success=15, failure=5 (AT cap)
    Action: Record SUCCESS outcome
    Expected: injection=20 (capped), success=16, failure=4 (decayed by 1)
              quality_score = 16/20 = 0.8
    """

    @pytest.mark.integration
    async def test_success_at_cap_triggers_failure_decay(self, txn_conn: Any) -> None:
        """SUCCESS at cap: failure counter decays, score = 16/20 = 0.8."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=ROLLING_WINDOW_SIZE,  # 20
            starting_success_count=15,
            starting_failure_count=5,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        # After SUCCESS at cap: success=16, failure=5-1=4, injection=20
        expected_score = 16.0 / 20.0  # = 0.8
        assert result.effectiveness_scores is not None
        actual_score = result.effectiveness_scores[scenario.pattern_ids[0]]
        assert (
            abs(actual_score - expected_score) < 1e-6
        ), f"Expected {expected_score}, got {actual_score}"
        await assert_score_updated(txn_conn, scenario.pattern_ids[0], expected_score)

    @pytest.mark.integration
    async def test_failure_at_cap_triggers_success_decay(self, txn_conn: Any) -> None:
        """FAILURE at cap: success counter decays, score = 14/20 = 0.7."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=ROLLING_WINDOW_SIZE,  # 20
            starting_success_count=15,
            starting_failure_count=5,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=False,
            failure_reason="test failure at cap",
            repository=txn_conn,
        )

        # After FAILURE at cap: success=15-1=14, failure=6, injection=20
        expected_score = 14.0 / 20.0  # = 0.7
        assert result.effectiveness_scores is not None
        actual_score = result.effectiveness_scores[scenario.pattern_ids[0]]
        assert (
            abs(actual_score - expected_score) < 1e-6
        ), f"Expected {expected_score}, got {actual_score}"
        await assert_score_updated(txn_conn, scenario.pattern_ids[0], expected_score)

    @pytest.mark.integration
    async def test_decay_delta_is_correct(self, txn_conn: Any) -> None:
        """Score delta at cap reflects both increment and decay."""
        starting_quality = 0.75  # = 15/20
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=ROLLING_WINDOW_SIZE,
            starting_success_count=15,
            starting_failure_count=5,
            domain_id=TEST_DOMAIN_ID,
        )
        # Override the starting quality_score to match actual ratio
        await txn_conn.execute(
            "UPDATE learned_patterns SET quality_score = $1 WHERE id = $2",
            starting_quality,
            scenario.pattern_ids[0],
        )

        score_before = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        assert abs(score_before - starting_quality) < 1e-6

        await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        score_after = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])
        # 16/20 - 15/20 = +0.05
        expected_delta = (16.0 / 20.0) - starting_quality
        actual_delta = score_after - score_before
        assert (
            abs(actual_delta - expected_delta) < 1e-6
        ), f"Expected delta {expected_delta}, got {actual_delta}"


# =============================================================================
# Golden Path: Multi-Pattern Session
# =============================================================================


class TestMultiPatternSession:
    """Verify effectiveness scores update for all patterns in a session.

    When a session references multiple patterns, all of them should have
    their rolling metrics and effectiveness scores updated.
    """

    @pytest.mark.integration
    async def test_all_patterns_updated(self, txn_conn: Any) -> None:
        """All patterns in the session receive metric updates."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=3,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=5,
            starting_failure_count=5,
            domain_id=TEST_DOMAIN_ID,
        )

        result = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )

        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.patterns_updated == 3
        assert result.effectiveness_scores is not None
        assert len(result.effectiveness_scores) == 3

        # All patterns had same starting metrics, so all get same new score
        # injection=11, success=6, failure=5 → score = 6/11 ≈ 0.545455
        expected_score = 6.0 / 11.0
        for pid in scenario.pattern_ids:
            actual = result.effectiveness_scores[pid]
            assert (
                abs(actual - expected_score) < 1e-6
            ), f"Pattern {pid}: expected {expected_score}, got {actual}"
            await assert_score_updated(txn_conn, pid, expected_score)

    @pytest.mark.integration
    async def test_multi_pattern_with_different_starting_metrics(
        self, txn_conn: Any
    ) -> None:
        """Patterns with different starting metrics get different scores."""
        session_id = uuid4()

        # Pattern A: healthy (8 successes, 2 failures out of 10)
        pattern_a = await create_test_pattern(
            txn_conn,
            domain_id=TEST_DOMAIN_ID,
            injection_count=10,
            success_count=8,
            failure_count=2,
        )

        # Pattern B: struggling (3 successes, 7 failures out of 10)
        pattern_b = await create_test_pattern(
            txn_conn,
            domain_id=TEST_DOMAIN_ID,
            injection_count=10,
            success_count=3,
            failure_count=7,
        )

        # Single injection referencing both patterns
        await create_test_injection(
            txn_conn,
            session_id=session_id,
            pattern_ids=[pattern_a, pattern_b],
        )

        result = await record_session_outcome(
            session_id=session_id,
            success=True,
            repository=txn_conn,
        )

        assert result.effectiveness_scores is not None

        # Pattern A: injection=11, success=9, failure=2 → 9/11 ≈ 0.818182
        expected_a = 9.0 / 11.0
        assert abs(result.effectiveness_scores[pattern_a] - expected_a) < 1e-6

        # Pattern B: injection=11, success=4, failure=7 → 4/11 ≈ 0.363636
        expected_b = 4.0 / 11.0
        assert abs(result.effectiveness_scores[pattern_b] - expected_b) < 1e-6


# =============================================================================
# Golden Path: Event-to-Handler Full Flow
# =============================================================================


class TestEventToHandlerFlow:
    """Verify the complete flow from ClaudeSessionOutcome event to DB update.

    This tests the boundary mapping (event → handler args) combined with
    the handler execution and DB verification in a single flow.
    """

    @pytest.mark.integration
    async def test_event_consumed_and_score_updated(self, txn_conn: Any) -> None:
        """Full flow: event → map → handler → DB update → score verification."""
        # Setup: pattern with known metrics
        session_id = uuid4()
        pattern_id = await create_test_pattern(
            txn_conn,
            domain_id=TEST_DOMAIN_ID,
            injection_count=10,
            success_count=7,
            failure_count=3,
        )
        await create_test_injection(
            txn_conn,
            session_id=session_id,
            pattern_ids=[pattern_id],
        )

        # Create the event (as if from Kafka)
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=uuid4(),
        )

        # Map event to handler args (boundary mapping)
        args = event_to_handler_args(event)

        # Invoke handler
        result = await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=txn_conn,
            correlation_id=args["correlation_id"],
        )

        # Verify handler result
        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.injections_updated == 1
        assert result.patterns_updated == 1

        # Verify effectiveness score
        # injection=11, success=8, failure=3 → 8/11 ≈ 0.727273
        expected_score = 8.0 / 11.0
        assert result.effectiveness_scores is not None
        assert abs(result.effectiveness_scores[pattern_id] - expected_score) < 1e-6

        # Verify DB state matches
        await assert_score_updated(txn_conn, pattern_id, expected_score)

    @pytest.mark.integration
    async def test_failed_event_updates_score_downward(self, txn_conn: Any) -> None:
        """FAILED event maps correctly and decreases effectiveness score."""
        session_id = uuid4()
        pattern_id = await create_test_pattern(
            txn_conn,
            domain_id=TEST_DOMAIN_ID,
            injection_count=10,
            success_count=7,
            failure_count=3,
            quality_score=7.0 / 10.0,  # Start at accurate ratio
        )
        await create_test_injection(
            txn_conn,
            session_id=session_id,
            pattern_ids=[pattern_id],
        )

        score_before = await fetch_pattern_score(txn_conn, pattern_id)

        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=None,
            correlation_id=uuid4(),
        )
        args = event_to_handler_args(event)

        await record_session_outcome(
            session_id=args["session_id"],
            success=args["success"],
            failure_reason=args["failure_reason"],
            repository=txn_conn,
            correlation_id=args["correlation_id"],
        )

        score_after = await fetch_pattern_score(txn_conn, pattern_id)

        # injection=11, success=7 (unchanged), failure=4 → 7/11 ≈ 0.636364
        expected_score = 7.0 / 11.0
        assert abs(score_after - expected_score) < 1e-6

        # Score decreased from 0.7 to ~0.636
        assert (
            score_after < score_before
        ), f"Expected score to decrease: before={score_before}, after={score_after}"


# =============================================================================
# Golden Path: Idempotent Replay (ALREADY_RECORDED)
# =============================================================================


class TestIdempotentReplay:
    """Verify that recording outcome twice returns ALREADY_RECORDED.

    The handler marks injections as recorded on the first call.
    Subsequent calls for the same session must return ALREADY_RECORDED
    without double-counting metrics or changing the effectiveness score.
    """

    @pytest.mark.integration
    async def test_second_call_returns_already_recorded(self, txn_conn: Any) -> None:
        """Second call with same session_id returns ALREADY_RECORDED status."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        # First call: should succeed
        result_1 = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )
        assert result_1.status == EnumOutcomeRecordingStatus.SUCCESS

        # Second call: same session_id, should be idempotent
        result_2 = await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )
        assert result_2.status == EnumOutcomeRecordingStatus.ALREADY_RECORDED
        assert result_2.injections_updated == 0
        assert result_2.patterns_updated == 0

    @pytest.mark.integration
    async def test_score_unchanged_after_replay(self, txn_conn: Any) -> None:
        """Effectiveness score does not change on idempotent replay."""
        scenario = await create_feedback_scenario(
            txn_conn,
            pattern_count=1,
            injection_count=1,
            starting_injection_count=10,
            starting_success_count=8,
            starting_failure_count=2,
            domain_id=TEST_DOMAIN_ID,
        )

        # First call: record outcome and capture resulting score
        await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )
        score_after_first = await fetch_pattern_score(txn_conn, scenario.pattern_ids[0])

        # Second call: replay
        await record_session_outcome(
            session_id=scenario.session_id,
            success=True,
            repository=txn_conn,
        )
        score_after_second = await fetch_pattern_score(
            txn_conn, scenario.pattern_ids[0]
        )

        # Score must be identical - no double-counting
        assert (
            abs(score_after_second - score_after_first) < 1e-6
        ), f"Score changed on replay: {score_after_first} → {score_after_second}"


# =============================================================================
# Edge Case: No Injections
# =============================================================================


class TestNoInjections:
    """Verify handler behavior when no injections exist for the session."""

    @pytest.mark.integration
    async def test_no_injections_returns_correct_status(self, txn_conn: Any) -> None:
        """Handler returns NO_INJECTIONS_FOUND when session has no injections."""
        result = await record_session_outcome(
            session_id=uuid4(),
            success=True,
            repository=txn_conn,
        )

        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.injections_updated == 0
        assert result.patterns_updated == 0
        assert result.effectiveness_scores == {}
