# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration test helpers for pattern feedback effect node (OMN-2077).

This module provides helper functions for integration tests that verify
session-outcome event consumption and effectiveness score updates against
a real PostgreSQL database.

Helpers included:
    - create_test_pattern: Insert a learned_pattern row with known metrics
    - create_test_injection: Insert a pattern_injection row for a session
    - fetch_pattern_score: Read current quality_score for a pattern
    - assert_score_updated: Verify quality_score matches expected value
    - create_feedback_scenario: Set up a complete scenario (patterns + injections)

Usage:
    from tests.integration.nodes.node_pattern_feedback_effect.helpers import (
        create_feedback_scenario,
        fetch_pattern_score,
        assert_score_updated,
    )

    async def test_effectiveness_score_with_real_db(db_conn):
        scenario = await create_feedback_scenario(
            conn=db_conn,
            pattern_count=2,
            injection_count=3,
            starting_success_count=8,
        )
        # ... invoke handler ...
        await assert_score_updated(db_conn, scenario.pattern_ids[0], expected=0.75)

Reference:
    - OMN-2077: Golden path pattern feedback consumption + scoring
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class FeedbackScenario:
    """Immutable description of a test scenario for pattern feedback.

    Contains all IDs and expected values needed to verify handler behavior.
    """

    pattern_ids: list[UUID]
    injection_ids: list[UUID]
    session_id: UUID
    domain_id: str = "testing"


# =============================================================================
# Pattern Helpers
# =============================================================================


async def create_test_pattern(
    conn: object,
    *,
    pattern_id: UUID | None = None,
    domain_id: str = "testing",
    injection_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    failure_streak: int = 0,
    quality_score: float = 0.5,
) -> UUID:
    """Insert a learned_pattern row with known rolling metrics.

    Args:
        conn: asyncpg connection (ProtocolPatternRepository-compatible).
        pattern_id: UUID for the pattern (auto-generated if None).
        domain_id: Domain taxonomy ID (must exist in domain_taxonomy table).
        injection_count: Initial injection_count_rolling_20.
        success_count: Initial success_count_rolling_20.
        failure_count: Initial failure_count_rolling_20.
        failure_streak: Initial failure_streak.
        quality_score: Initial quality_score.

    Returns:
        The UUID of the created pattern.
    """
    pid = pattern_id or uuid4()
    signature = f"test-signature-{pid}"
    signature_hash = (
        f"test_feedback_{hashlib.sha256(signature.encode()).hexdigest()[:32]}"
    )
    # conn typed as object for test genericity; runtime is always asyncpg.Connection (OMN-2077)
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO learned_patterns (
            id, pattern_signature, signature_hash, domain_id, domain_version,
            domain_candidates, confidence, status,
            source_session_ids, quality_score,
            injection_count_rolling_20, success_count_rolling_20,
            failure_count_rolling_20, failure_streak
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6::jsonb, $7, $8,
            $9, $10,
            $11, $12,
            $13, $14
        )
        """,
        pid,
        signature,
        signature_hash,
        domain_id,
        "1.0.0",
        "[]",
        0.8,
        "provisional",
        [uuid4()],
        quality_score,
        injection_count,
        success_count,
        failure_count,
        failure_streak,
    )
    return pid


# =============================================================================
# Injection Helpers
# =============================================================================


async def create_test_injection(
    conn: object,
    *,
    session_id: UUID,
    pattern_ids: list[UUID],
    injection_id: UUID | None = None,
    injection_context: str = "UserPromptSubmit",
    cohort: str = "treatment",
) -> UUID:
    """Insert a pattern_injection row for a given session.

    Args:
        conn: asyncpg connection.
        session_id: Claude Code session ID.
        pattern_ids: List of pattern UUIDs injected.
        injection_id: UUID for the injection (auto-generated if None).
        injection_context: Hook event context.
        cohort: A/B experiment cohort.

    Returns:
        The UUID of the created injection.
    """
    iid = injection_id or uuid4()
    # conn typed as object for test genericity; runtime is always asyncpg.Connection (OMN-2077)
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO pattern_injections (
            injection_id, session_id, pattern_ids,
            injection_context, cohort, assignment_seed
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        iid,
        session_id,
        pattern_ids,
        injection_context,
        cohort,
        42,
    )
    return iid


# =============================================================================
# Score Verification Helpers
# =============================================================================


async def fetch_pattern_score(conn: object, pattern_id: UUID) -> float:
    """Read the current quality_score for a pattern from the database.

    Args:
        conn: asyncpg connection.
        pattern_id: Pattern UUID to query.

    Returns:
        The current quality_score value.

    Raises:
        ValueError: If pattern not found.
    """
    # conn typed as object for test genericity; runtime is always asyncpg.Connection (OMN-2077)
    rows = await conn.fetch(  # type: ignore[union-attr]
        "SELECT quality_score FROM learned_patterns WHERE id = $1",
        pattern_id,
    )
    if not rows:
        raise ValueError(f"Pattern {pattern_id} not found")
    return float(rows[0]["quality_score"])


async def assert_score_updated(
    conn: object,
    pattern_id: UUID,
    expected: float,
    tolerance: float = 1e-6,
) -> None:
    """Assert that a pattern's quality_score matches the expected value.

    Args:
        conn: asyncpg connection.
        pattern_id: Pattern UUID to check.
        expected: Expected quality_score.
        tolerance: Floating point comparison tolerance.

    Raises:
        AssertionError: If score doesn't match within tolerance.
    """
    actual = await fetch_pattern_score(conn, pattern_id)
    assert (
        abs(actual - expected) < tolerance
    ), f"Pattern {pattern_id}: expected quality_score={expected}, got {actual}"


# =============================================================================
# Scenario Builder
# =============================================================================


async def create_feedback_scenario(
    conn: object,
    *,
    pattern_count: int = 1,
    injection_count: int = 1,
    starting_injection_count: int = 0,
    starting_success_count: int = 0,
    starting_failure_count: int = 0,
    domain_id: str = "testing",
) -> FeedbackScenario:
    """Create a complete feedback scenario with patterns and injections.

    Sets up the database state needed to test the full handler flow:
    patterns with known rolling metrics and unrecorded injections.

    Args:
        conn: asyncpg connection.
        pattern_count: Number of patterns to create.
        injection_count: Number of injections to create (all reference all patterns).
        starting_injection_count: Initial injection_count_rolling_20 for all patterns.
        starting_success_count: Initial success_count_rolling_20 for all patterns.
        starting_failure_count: Initial failure_count_rolling_20 for all patterns.
        domain_id: Domain taxonomy ID.

    Returns:
        FeedbackScenario with all created IDs.
    """
    session_id = uuid4()
    pattern_ids: list[UUID] = []
    injection_ids: list[UUID] = []

    # Create patterns
    for _ in range(pattern_count):
        pid = await create_test_pattern(
            conn,
            domain_id=domain_id,
            injection_count=starting_injection_count,
            success_count=starting_success_count,
            failure_count=starting_failure_count,
        )
        pattern_ids.append(pid)

    # Create injections
    for _ in range(injection_count):
        iid = await create_test_injection(
            conn,
            session_id=session_id,
            pattern_ids=pattern_ids,
        )
        injection_ids.append(iid)

    return FeedbackScenario(
        pattern_ids=pattern_ids,
        injection_ids=injection_ids,
        session_id=session_id,
        domain_id=domain_id,
    )


__all__ = [
    "FeedbackScenario",
    "assert_score_updated",
    "create_feedback_scenario",
    "create_test_injection",
    "create_test_pattern",
    "fetch_pattern_score",
]
