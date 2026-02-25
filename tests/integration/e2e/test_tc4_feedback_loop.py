# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""TC4: Feedback loop updates - E2E integration tests for OMN-1800.

This module tests the feedback loop that updates pattern metrics (rolling_20 window)
based on session outcomes. The feedback loop is critical for pattern lifecycle
management: successful sessions increase success metrics and reset failure streaks,
while failed sessions increase failure metrics and increment failure streaks.

Test Coverage:
    - Success outcome increments success_count_rolling_20
    - Failure outcome increments failure_count_rolling_20
    - Success resets failure_streak to 0
    - Failure increments failure_streak

Infrastructure Requirements:
    - PostgreSQL: localhost:5432 (database: omniintelligence)
    - Tables: learned_patterns, pattern_injections

Safety Measures:
    The cleanup_test_data helper implements 7-layer defense-in-depth to prevent
    accidental deletion of production patterns:

    1. TYPE ENFORCEMENT - pattern_ids must be list of UUID objects (not strings)
    2. WHITELIST APPROACH - only explicitly provided IDs can be deleted
    3. EXISTENCE VERIFICATION - all IDs must exist in database
    4. NULL REJECTION - patterns with NULL signature_hash are flagged
    5. PREFIX VERIFICATION - signature_hash must start with 'test_e2e_'
    6. DUAL-CONDITION DELETE - DELETE query re-validates both ID AND prefix
    7. POST-DELETE VERIFICATION - confirms exact count match (detects race conditions)

    TOCTOU (Time-of-Check to Time-of-Use) mitigation is provided by Layer 6:
    even if a pattern's signature_hash is modified between verification and
    deletion, the DELETE query itself requires the E2E prefix, so production
    patterns cannot be deleted.

    Any violation raises ValueError/TypeError and aborts cleanup without
    deleting anything. A count mismatch after deletion also raises ValueError.

    Note: Tests primarily use the e2e_db_conn fixture from conftest.py which has
    automatic cleanup. The cleanup_test_data helper is for manual/explicit cleanup
    when needed.

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - OMN-1678: Rolling window metric updates with decay approximation
    - OMN-1677: Pattern feedback effect node foundation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from tests.integration.conftest import requires_postgres
from tests.integration.e2e.conftest import (
    E2E_DOMAIN,
    E2E_SIGNATURE_PREFIX,
    _check_signature_hash_column_exists,
    create_e2e_signature_hash,
    requires_e2e_postgres,
)
from tests.integration.e2e.fixtures import (
    CORRELATION_ID_1,
    CORRELATION_ID_2,
    SESSION_ID_FEEDBACK_1,
    SESSION_ID_FEEDBACK_2,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# SQL for Test Setup and Verification
# =============================================================================

SQL_INSERT_TEST_PATTERN = """
INSERT INTO learned_patterns (
    id,
    pattern_signature,
    signature_hash,
    domain_id,
    domain_version,
    confidence,
    status,
    source_session_ids,
    recurrence_count,
    version,
    is_current,
    injection_count_rolling_20,
    success_count_rolling_20,
    failure_count_rolling_20,
    failure_streak,
    quality_score
) VALUES (
    $1,  -- id
    $2,  -- pattern_signature
    $3,  -- signature_hash
    $4,  -- domain_id
    $5,  -- domain_version
    $6,  -- confidence
    $7,  -- status
    $8,  -- source_session_ids (UUID array)
    $9,  -- recurrence_count
    $10, -- version
    $11, -- is_current
    $12, -- injection_count_rolling_20
    $13, -- success_count_rolling_20
    $14, -- failure_count_rolling_20
    $15, -- failure_streak
    $16  -- quality_score
)
RETURNING id
"""

SQL_INSERT_TEST_INJECTION = """
INSERT INTO pattern_injections (
    injection_id,
    session_id,
    correlation_id,
    pattern_ids,
    injection_context,
    cohort,
    assignment_seed,
    outcome_recorded
) VALUES (
    $1,  -- injection_id
    $2,  -- session_id
    $3,  -- correlation_id
    $4,  -- pattern_ids (UUID array)
    $5,  -- injection_context
    $6,  -- cohort
    $7,  -- assignment_seed
    $8   -- outcome_recorded
)
RETURNING injection_id
"""

SQL_GET_PATTERN_METRICS = """
SELECT
    id,
    injection_count_rolling_20,
    success_count_rolling_20,
    failure_count_rolling_20,
    failure_streak
FROM learned_patterns
WHERE id = $1
"""

SQL_CLEANUP_TEST_INJECTIONS = """
DELETE FROM pattern_injections
WHERE session_id = ANY($1)
"""

SQL_CLEANUP_TEST_PATTERNS = """
DELETE FROM learned_patterns
WHERE signature_hash LIKE $1
  AND id = ANY($2)
"""

SQL_VERIFY_PATTERNS_ARE_TEST_PATTERNS = """
SELECT id, signature_hash FROM learned_patterns
WHERE id = ANY($1)
  AND (signature_hash IS NULL OR signature_hash NOT LIKE $2)
"""

SQL_VERIFY_IDS_EXIST = """
SELECT id FROM learned_patterns
WHERE id = ANY($1)
"""


# =============================================================================
# Test Data Factory
# =============================================================================


async def create_test_pattern(
    conn: Any,
    *,
    pattern_id: UUID | None = None,
    signature: str | None = None,
    signature_hash: str | None = None,
    domain_id: str = E2E_DOMAIN,
    domain_version: str = "1.0",
    confidence: float = 0.75,
    status: str = "validated",
    source_session_ids: list[UUID] | None = None,
    recurrence_count: int = 5,
    version: int = 1,
    is_current: bool = True,
    injection_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    failure_streak: int = 0,
    quality_score: float = 0.7,
) -> UUID:
    """Create a test pattern in learned_patterns table.

    Args:
        conn: asyncpg connection.
        pattern_id: Pattern UUID (auto-generated if None).
        signature: Pattern signature text.
        signature_hash: SHA256 hash for lineage (auto-generated if None).
        domain_id: Domain identifier.
        domain_version: Domain version.
        confidence: Pattern confidence score.
        status: Lifecycle status (candidate, provisional, validated, deprecated).
        source_session_ids: Session UUIDs where pattern was observed.
        recurrence_count: Number of times pattern was observed.
        version: Pattern version number.
        is_current: Whether this is the current version.
        injection_count: Initial injection_count_rolling_20.
        success_count: Initial success_count_rolling_20.
        failure_count: Initial failure_count_rolling_20.
        failure_streak: Initial failure_streak.
        quality_score: Initial quality_score.

    Returns:
        The pattern UUID.

    Raises:
        pytest.skip: If signature_hash column doesn't exist (migration 009 not applied).
    """
    # Check if signature_hash column exists
    has_signature_hash = await _check_signature_hash_column_exists(conn)
    if not has_signature_hash:
        pytest.skip(
            "signature_hash column not found in learned_patterns table. "
            "Run migration 009_add_signature_hash.sql first."
        )

    if pattern_id is None:
        pattern_id = uuid4()
    if signature is None:
        signature = f"def e2e_test_pattern_{pattern_id.hex[:8]}(): pass"
    if signature_hash is None:
        signature_hash = create_e2e_signature_hash(str(pattern_id))
    if source_session_ids is None:
        source_session_ids = [uuid4()]

    result = await conn.fetchval(
        SQL_INSERT_TEST_PATTERN,
        pattern_id,
        signature,
        signature_hash,
        domain_id,
        domain_version,
        confidence,
        status,
        source_session_ids,
        recurrence_count,
        version,
        is_current,
        injection_count,
        success_count,
        failure_count,
        failure_streak,
        quality_score,
    )
    return result


async def create_test_injection(
    conn: Any,
    *,
    injection_id: UUID | None = None,
    session_id: UUID,
    correlation_id: UUID | None = None,
    pattern_ids: list[UUID],
    injection_context: str = "UserPromptSubmit",
    cohort: str = "treatment",
    assignment_seed: int = 12345,
    outcome_recorded: bool = False,
) -> UUID:
    """Create a test injection in pattern_injections table.

    Args:
        conn: asyncpg connection.
        injection_id: Injection UUID (auto-generated if None).
        session_id: Session UUID.
        correlation_id: Correlation UUID for tracing.
        pattern_ids: List of pattern UUIDs that were injected.
        injection_context: Hook context (SessionStart, UserPromptSubmit, etc.).
        cohort: A/B cohort (control, treatment).
        assignment_seed: Seed for cohort assignment.
        outcome_recorded: Whether outcome has been recorded.

    Returns:
        The injection UUID.
    """
    if injection_id is None:
        injection_id = uuid4()

    result = await conn.fetchval(
        SQL_INSERT_TEST_INJECTION,
        injection_id,
        session_id,
        correlation_id,
        pattern_ids,
        injection_context,
        cohort,
        assignment_seed,
        outcome_recorded,
    )
    return result


async def get_pattern_metrics(conn: Any, pattern_id: UUID) -> dict[str, Any] | None:
    """Get the rolling metrics for a pattern.

    Args:
        conn: asyncpg connection.
        pattern_id: Pattern UUID.

    Returns:
        Dictionary with metrics or None if not found.
    """
    row = await conn.fetchrow(SQL_GET_PATTERN_METRICS, pattern_id)
    if row is None:
        return None
    return dict(row)


async def cleanup_test_data(
    conn: Any,
    session_ids: list[UUID] | None = None,
    pattern_ids: list[UUID] | None = None,
) -> int:
    """Clean up test data from pattern_injections and learned_patterns.

    SAFETY ARCHITECTURE (Defense-in-Depth):
    ===========================================

    This function implements 6 safety layers to prevent accidental deletion
    of production patterns. A pattern is ONLY deleted if ALL conditions are met:

    Layer 1 - TYPE ENFORCEMENT:
        pattern_ids must be a list of UUID objects (validated at runtime).
        Prevents string injection or malformed IDs from bypassing checks.

    Layer 2 - WHITELIST APPROACH:
        Pattern ID must be explicitly provided in pattern_ids.
        No implicit deletion based on queries or patterns.

    Layer 3 - EXISTENCE VERIFICATION:
        All requested pattern IDs must exist in the database.
        Missing IDs indicate test bugs and abort cleanup.

    Layer 4 - SIGNATURE VALIDATION:
        All patterns must have non-NULL signature_hash.
        Production patterns typically have NULL signature_hash.
        Test patterns always have signature_hash set via create_e2e_signature_hash().

    Layer 5 - PREFIX VERIFICATION:
        All signature_hash values must start with E2E_SIGNATURE_PREFIX ('test_e2e_').
        This prefix is ONLY applied by E2E test infrastructure.

    Layer 6 - DUAL-CONDITION DELETE (TOCTOU Mitigation):
        The DELETE query requires BOTH:
          - ID in the explicit list (pattern_ids), AND
          - signature_hash starts with E2E prefix
        Even if a race condition modifies patterns between verification and deletion,
        the DELETE query itself re-validates both conditions.

    Layer 7 - POST-DELETE VERIFICATION:
        After deletion, verifies that exactly the expected number of patterns
        were deleted. A mismatch indicates a race condition or bug.

    TOCTOU (Time-of-Check to Time-of-Use) MITIGATION:
    ==================================================

    The verification queries (Layers 3-5) run BEFORE the DELETE, creating a
    potential TOCTOU window. This is mitigated by:

    1. The DELETE query itself includes the signature_hash check (Layer 6), so
       even if a pattern's signature_hash is modified between verification and
       deletion, it won't be deleted unless it STILL has the E2E prefix.

    2. UUIDs are used for pattern IDs, making collision essentially impossible.
       A production pattern cannot "take over" a test pattern's ID.

    3. Post-delete verification (Layer 7) detects any discrepancy and raises
       ValueError, ensuring no silent partial deletions.

    FAILURE MODES (all result in ValueError, no deletion occurs):
    ==============================================================
    - pattern_ids contains non-UUID types
    - Any pattern_id does not exist in the database
    - Any pattern_id has NULL signature_hash
    - Any pattern_id has signature_hash not starting with E2E_SIGNATURE_PREFIX
    - Deleted count does not match requested count (race condition detected)

    Args:
        conn: asyncpg connection.
        session_ids: Session IDs to clean up injections for.
        pattern_ids: Explicit list of pattern IDs created during this test.
            REQUIRED for pattern cleanup - if None or empty, no patterns are deleted.
            Must be a list of UUID objects (not strings).

    Returns:
        Number of patterns deleted.

    Raises:
        ValueError: If any safety check fails (see FAILURE MODES above).
        TypeError: If pattern_ids contains non-UUID elements.
    """
    # Clean up injections first (due to potential references)
    if session_ids:
        await conn.execute(SQL_CLEANUP_TEST_INJECTIONS, session_ids)

    # SAFETY LAYER 1 & 2: Only clean up patterns if explicit IDs are provided
    if not pattern_ids:
        return 0

    # SAFETY LAYER 1: Type enforcement - ensure all elements are UUIDs
    # Prevents string injection attacks or malformed IDs
    for i, pid in enumerate(pattern_ids):
        if not isinstance(pid, UUID):
            raise TypeError(
                f"SAFETY VIOLATION: pattern_ids[{i}] is not a UUID. "
                f"Got {type(pid).__name__}: {pid!r}. "
                f"All pattern IDs must be UUID objects, not strings. "
                f"Cleanup aborted."
            )

    # SAFETY LAYER 3: Verify all pattern IDs exist in the database
    # Non-existent IDs could indicate test bugs or race conditions
    existing_ids = await conn.fetch(SQL_VERIFY_IDS_EXIST, pattern_ids)
    existing_id_set = {row["id"] for row in existing_ids}
    requested_id_set = set(pattern_ids)
    missing_ids = requested_id_set - existing_id_set

    if missing_ids:
        raise ValueError(
            f"SAFETY VIOLATION: Attempted to delete non-existent patterns. "
            f"Pattern IDs not found in database: {[str(uid) for uid in missing_ids]}. "
            f"This may indicate a test setup bug or race condition. "
            f"Cleanup aborted."
        )

    # SAFETY LAYER 4 & 5: Verify ALL patterns have the E2E signature prefix
    # Query catches both NULL signature_hash AND non-matching prefixes
    # NULL signature_hash is explicitly flagged because it indicates a production
    # pattern. Test patterns always have signature_hash set via
    # create_e2e_signature_hash().
    non_test_patterns = await conn.fetch(
        SQL_VERIFY_PATTERNS_ARE_TEST_PATTERNS,
        pattern_ids,
        f"{E2E_SIGNATURE_PREFIX}%",
    )

    if non_test_patterns:
        violations = []
        for row in non_test_patterns:
            sig_hash = row["signature_hash"]
            if sig_hash is None:
                violations.append(f"{row['id']} (signature_hash=NULL)")
            else:
                violations.append(f"{row['id']} (signature_hash={sig_hash!r})")

        raise ValueError(
            f"SAFETY VIOLATION: Attempted to delete non-test patterns. "
            f"Pattern IDs with invalid signature_hash: {violations}. "
            f"Expected signature_hash to start with '{E2E_SIGNATURE_PREFIX}'. "
            f"Patterns with NULL signature_hash are also rejected. "
            f"Cleanup aborted to protect production data."
        )

    # SAFETY LAYER 6: Delete only patterns that match BOTH criteria:
    # 1. ID is in the explicit list (pattern_ids)
    # 2. signature_hash starts with E2E prefix (NOT NULL due to LIKE semantics)
    # This dual-condition DELETE mitigates TOCTOU by re-validating at delete time.
    result = await conn.execute(
        SQL_CLEANUP_TEST_PATTERNS,
        f"{E2E_SIGNATURE_PREFIX}%",
        pattern_ids,
    )

    # Parse "DELETE N" to get count
    deleted_count = 0
    if result and result.startswith("DELETE "):
        deleted_count = int(result.split()[1])

    # SAFETY LAYER 7: Post-delete verification
    # If fewer patterns were deleted than requested, a race condition may have
    # modified a pattern's signature_hash between verification and deletion.
    # This is a safety net - the pattern was NOT deleted (which is correct),
    # but we raise an error to alert the caller to the anomaly.
    expected_count = len(pattern_ids)
    if deleted_count != expected_count:
        raise ValueError(
            f"SAFETY ANOMALY: Deleted {deleted_count} patterns but expected "
            f"{expected_count}. This may indicate a race condition where a "
            f"pattern's signature_hash was modified between verification and "
            f"deletion. The patterns that were NOT deleted still exist in the "
            f"database. Investigate before proceeding."
        )

    return deleted_count


# =============================================================================
# TC4 Tests: Feedback Loop Updates
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_success_outcome_increments_success_count(e2e_db_conn: Any) -> None:
    """TC4.1: Success outcome increments success_count_rolling_20.

    Verifies that when a session succeeds:
    - injection_count_rolling_20 is incremented by 1
    - success_count_rolling_20 is incremented by 1
    - failure_count_rolling_20 remains unchanged
    - failure_streak is reset to 0
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create a test pattern with known initial metrics
    pattern_id = uuid4()
    initial_injection_count = 5
    initial_success_count = 3
    initial_failure_count = 2
    initial_failure_streak = 1  # Has a failure streak to verify reset

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
        injection_count=initial_injection_count,
        success_count=initial_success_count,
        failure_count=initial_failure_count,
        failure_streak=initial_failure_streak,
    )

    # Create an injection for the session
    session_id = SESSION_ID_FEEDBACK_1
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        correlation_id=CORRELATION_ID_1,
        pattern_ids=[pattern_id],
    )

    # Act: Record a SUCCESS outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
        correlation_id=CORRELATION_ID_1,
    )

    # Assert: Verify the result status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.patterns_updated == 1
    assert pattern_id in result.pattern_ids

    # Assert: Verify database state
    metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert metrics is not None

    # injection_count incremented
    assert metrics["injection_count_rolling_20"] == initial_injection_count + 1

    # success_count incremented
    assert metrics["success_count_rolling_20"] == initial_success_count + 1

    # failure_count unchanged
    assert metrics["failure_count_rolling_20"] == initial_failure_count

    # failure_streak reset to 0
    assert metrics["failure_streak"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_failure_outcome_increments_failure_count(e2e_db_conn: Any) -> None:
    """TC4.2: Failure outcome increments failure_count_rolling_20.

    Verifies that when a session fails:
    - injection_count_rolling_20 is incremented by 1
    - failure_count_rolling_20 is incremented by 1
    - success_count_rolling_20 remains unchanged
    - failure_streak is incremented by 1
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create a test pattern with known initial metrics
    pattern_id = uuid4()
    initial_injection_count = 5
    initial_success_count = 3
    initial_failure_count = 2
    initial_failure_streak = 0

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
        injection_count=initial_injection_count,
        success_count=initial_success_count,
        failure_count=initial_failure_count,
        failure_streak=initial_failure_streak,
    )

    # Create an injection for the session
    session_id = SESSION_ID_FEEDBACK_2
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        correlation_id=CORRELATION_ID_2,
        pattern_ids=[pattern_id],
    )

    # Act: Record a FAILURE outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=False,
        failure_reason="Test failure for TC4",
        repository=e2e_db_conn,
        correlation_id=CORRELATION_ID_2,
    )

    # Assert: Verify the result status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.patterns_updated == 1
    assert pattern_id in result.pattern_ids

    # Assert: Verify database state
    metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert metrics is not None

    # injection_count incremented
    assert metrics["injection_count_rolling_20"] == initial_injection_count + 1

    # failure_count incremented
    assert metrics["failure_count_rolling_20"] == initial_failure_count + 1

    # success_count unchanged
    assert metrics["success_count_rolling_20"] == initial_success_count

    # failure_streak incremented
    assert metrics["failure_streak"] == initial_failure_streak + 1


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_success_resets_failure_streak(e2e_db_conn: Any) -> None:
    """TC4.3: Success outcome resets failure_streak to 0.

    Verifies that a success outcome resets the failure_streak counter,
    even when the pattern has an existing streak of multiple failures.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create a test pattern with an existing failure streak
    pattern_id = uuid4()
    initial_failure_streak = 5  # Pattern has failed 5 times in a row

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
        injection_count=10,
        success_count=5,
        failure_count=5,
        failure_streak=initial_failure_streak,
    )

    # Verify the initial failure_streak
    initial_metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert initial_metrics is not None
    assert initial_metrics["failure_streak"] == initial_failure_streak

    # Create an injection for the session
    session_id = uuid4()  # Use a fresh session ID
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        pattern_ids=[pattern_id],
    )

    # Act: Record a SUCCESS outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert: Verify the result status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.patterns_updated == 1

    # Assert: failure_streak is reset to 0
    metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert metrics is not None
    assert metrics["failure_streak"] == 0, (
        f"Expected failure_streak=0 after success, got {metrics['failure_streak']}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_failure_increments_failure_streak(e2e_db_conn: Any) -> None:
    """TC4.4: Failure outcome increments failure_streak.

    Verifies that consecutive failures continue to increment the failure_streak
    counter, which is used for demotion decisions.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create a test pattern with an existing failure streak
    pattern_id = uuid4()
    initial_failure_streak = 2  # Pattern has failed 2 times already

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
        injection_count=5,
        success_count=3,
        failure_count=2,
        failure_streak=initial_failure_streak,
    )

    # Verify the initial failure_streak
    initial_metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert initial_metrics is not None
    assert initial_metrics["failure_streak"] == initial_failure_streak

    # Create an injection for the session
    session_id = uuid4()  # Use a fresh session ID
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        pattern_ids=[pattern_id],
    )

    # Act: Record a FAILURE outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=False,
        failure_reason="Another failure for streak testing",
        repository=e2e_db_conn,
    )

    # Assert: Verify the result status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.patterns_updated == 1

    # Assert: failure_streak is incremented
    metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert metrics is not None
    expected_streak = initial_failure_streak + 1
    assert metrics["failure_streak"] == expected_streak, (
        f"Expected failure_streak={expected_streak}, got {metrics['failure_streak']}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_multiple_patterns_updated_on_single_session(e2e_db_conn: Any) -> None:
    """TC4.5: Multiple patterns are updated when session has multiple injections.

    Verifies that when a session outcome is recorded, ALL patterns that were
    injected during that session have their metrics updated.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create two test patterns
    pattern_id_1 = uuid4()
    pattern_id_2 = uuid4()

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id_1,
        injection_count=3,
        success_count=2,
        failure_count=1,
        failure_streak=0,
    )

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id_2,
        injection_count=5,
        success_count=4,
        failure_count=1,
        failure_streak=1,
    )

    # Create an injection with both patterns
    session_id = uuid4()
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        pattern_ids=[pattern_id_1, pattern_id_2],
    )

    # Act: Record a SUCCESS outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert: Both patterns were updated
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    assert result.patterns_updated == 2
    assert pattern_id_1 in result.pattern_ids
    assert pattern_id_2 in result.pattern_ids

    # Verify pattern 1 metrics
    metrics_1 = await get_pattern_metrics(e2e_db_conn, pattern_id_1)
    assert metrics_1 is not None
    assert metrics_1["injection_count_rolling_20"] == 4  # 3 + 1
    assert metrics_1["success_count_rolling_20"] == 3  # 2 + 1
    assert metrics_1["failure_streak"] == 0  # Reset

    # Verify pattern 2 metrics
    metrics_2 = await get_pattern_metrics(e2e_db_conn, pattern_id_2)
    assert metrics_2 is not None
    assert metrics_2["injection_count_rolling_20"] == 6  # 5 + 1
    assert metrics_2["success_count_rolling_20"] == 5  # 4 + 1
    assert metrics_2["failure_streak"] == 0  # Reset from 1


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_rolling_window_cap_at_20(e2e_db_conn: Any) -> None:
    """TC4.6: Rolling window metrics are capped at 20.

    Verifies that metrics do not exceed the ROLLING_WINDOW_SIZE of 20,
    implementing the decay approximation for the sliding window.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        ROLLING_WINDOW_SIZE,
        record_session_outcome,
    )

    # Arrange: Create a pattern at the cap (20 injections, 19 successes)
    pattern_id = uuid4()
    initial_injection_count = ROLLING_WINDOW_SIZE  # 20
    initial_success_count = 19
    initial_failure_count = 1

    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
        injection_count=initial_injection_count,
        success_count=initial_success_count,
        failure_count=initial_failure_count,
        failure_streak=0,
    )

    # Create an injection for the session
    session_id = uuid4()
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        pattern_ids=[pattern_id],
    )

    # Act: Record a SUCCESS outcome
    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert: Verify the result status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.SUCCESS

    # Assert: Metrics are capped at ROLLING_WINDOW_SIZE
    metrics = await get_pattern_metrics(e2e_db_conn, pattern_id)
    assert metrics is not None

    # injection_count should be capped at 20
    assert metrics["injection_count_rolling_20"] <= ROLLING_WINDOW_SIZE

    # success_count should be capped at 20
    assert metrics["success_count_rolling_20"] <= ROLLING_WINDOW_SIZE

    # Due to the decay approximation, when at cap, adding a success
    # decrements failure_count (if > 0) to approximate forgetting old data
    # So failure_count may be decremented from 1 to 0
    assert metrics["failure_count_rolling_20"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_no_injections_returns_correct_status(e2e_db_conn: Any) -> None:
    """TC4.7: Session with no injections returns NO_INJECTIONS_FOUND status.

    Verifies that the feedback loop correctly handles sessions that have
    no pattern injections recorded.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Use a session ID that has no injections
    session_id = uuid4()  # Fresh session with no injections

    # Act: Try to record an outcome for a session with no injections
    result = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert: Should return NO_INJECTIONS_FOUND status
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
    assert result.patterns_updated == 0
    assert result.injections_updated == 0
    assert len(result.pattern_ids) == 0


@pytest.mark.asyncio
@pytest.mark.integration
@requires_postgres
@requires_e2e_postgres
async def test_already_recorded_returns_correct_status(e2e_db_conn: Any) -> None:
    """TC4.8: Recording outcome twice returns ALREADY_RECORDED status.

    Verifies idempotency: once an outcome is recorded for a session's
    injections, subsequent attempts return ALREADY_RECORDED.
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    # Arrange: Create a pattern and injection
    pattern_id = uuid4()
    await create_test_pattern(
        e2e_db_conn,
        pattern_id=pattern_id,
    )

    session_id = uuid4()
    await create_test_injection(
        e2e_db_conn,
        session_id=session_id,
        pattern_ids=[pattern_id],
    )

    # Act 1: Record outcome first time
    result_1 = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert 1: First recording should succeed
    from omniintelligence.nodes.node_pattern_feedback_effect.models import (
        EnumOutcomeRecordingStatus,
    )

    assert result_1.status == EnumOutcomeRecordingStatus.SUCCESS

    # Act 2: Try to record outcome again
    result_2 = await record_session_outcome(
        session_id=session_id,
        success=True,
        repository=e2e_db_conn,
    )

    # Assert 2: Second attempt should return ALREADY_RECORDED
    assert result_2.status == EnumOutcomeRecordingStatus.ALREADY_RECORDED
    assert result_2.patterns_updated == 0
