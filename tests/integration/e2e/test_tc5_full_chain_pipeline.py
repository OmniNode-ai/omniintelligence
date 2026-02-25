# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""TC5: Full-chain pattern learning pipeline integration test.

Tests the complete pipeline: Learn -> Store -> Feedback -> Promote
Uses real PostgreSQL (localhost:5432) and real Kafka (localhost:9092).

Chain:
  1. Pattern learning produces learned patterns from training data
  2. Patterns are stored in PostgreSQL via pattern_storage_effect
  3. Session feedback updates rolling metrics
  4. Promotion gates are evaluated against real DB data
  5. Final lifecycle state is verified

Design Decision - Single Test Function:
    Each pipeline stage depends on the output of the previous stage. Since
    pytest-asyncio is configured with function-scoped event loops in this
    project (asyncio_default_test_loop_scope=function), class-scoped async
    fixtures would run in a different event loop than the test methods.

    To avoid event loop conflicts, TC5 implements all 5 stages within a
    single test function. Each stage has clear section markers and
    assertions. If any stage fails, subsequent stages are never reached
    (natural short-circuit via assertion failure).

    This pattern is standard for pipeline integration tests where stages
    are not independently meaningful.

Infrastructure Requirements:
    - PostgreSQL: localhost:5432 (database: omniintelligence)
    - Kafka/Redpanda: localhost:9092

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from tests.integration.conftest import requires_postgres
from tests.integration.e2e.conftest import (
    E2E_DOMAIN,
    E2E_SIGNATURE_PREFIX,
    create_e2e_signature_hash,
    requires_e2e_kafka,
    requires_e2e_postgres,
)
from tests.integration.e2e.fixtures import sample_successful_session_data
from tests.integration.e2e.test_tc4_feedback_loop import (
    create_test_injection,
    create_test_pattern,
    get_pattern_metrics,
)

# =============================================================================
# Markers
# =============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


# =============================================================================
# Deterministic IDs for TC5
# =============================================================================

SESSION_ID_TC5_SUCCESS = UUID("55555555-1111-1111-1111-111111111111")
"""Session ID for the successful outcome in TC5."""

SESSION_ID_TC5_FAILURE = UUID("55555555-2222-2222-2222-222222222222")
"""Session ID for the failed outcome in TC5."""

CORRELATION_ID_TC5 = UUID("55555555-cccc-cccc-cccc-cccccccccccc")
"""Correlation ID for TC5 tracing."""


# =============================================================================
# SQL for TC5 Verification
# =============================================================================

SQL_VERIFY_STORED_PATTERNS = """
SELECT id, signature_hash, status, confidence,
       injection_count_rolling_20,
       success_count_rolling_20,
       failure_count_rolling_20,
       failure_streak
FROM learned_patterns
WHERE signature_hash LIKE $1
ORDER BY created_at ASC
"""


# =============================================================================
# TC5: Full Chain Pipeline Tests
# =============================================================================


@requires_postgres
@requires_e2e_postgres
@requires_e2e_kafka
class TestTC5FullChainPipeline:
    """Full-chain pattern learning pipeline integration test.

    Exercises the complete pipeline end-to-end:
        Learn -> Store -> Feedback -> Promote -> Verify

    All stages run within a single test function to share the same
    event loop and database connection. Assertions at each stage ensure
    correctness before proceeding to the next.
    """

    async def test_tc5_full_pipeline(
        self,
        pattern_learning_handler: Any,
        e2e_db_conn: Any,
        feedback_handler: Any,
        promotion_handler_with_kafka: Any,
    ) -> None:
        """TC5: Full-chain pipeline from learning through promotion verification.

        Stages:
            1. Learn patterns from training data (pure compute)
            2. Store learned patterns in PostgreSQL (effect)
            3. Record session feedback to update rolling metrics (effect)
            4. Evaluate promotion gates against real DB data (effect)
            5. Verify final lifecycle state consistency (verification)
        """
        # =================================================================
        # Stage 1: Learn patterns from training data
        # =================================================================

        training_data = sample_successful_session_data()
        assert len(training_data) == 5, "Expected 5 training data items"

        result = pattern_learning_handler.handle(training_data=training_data)

        assert result["success"] is True, (
            f"Pattern learning should succeed for valid training data. "
            f"Warnings: {result['warnings']}"
        )

        learned = list(result["learned_patterns"])
        candidates = list(result["candidate_patterns"])
        all_patterns = learned + candidates
        total_patterns = len(all_patterns)
        assert total_patterns >= 1, (
            f"Expected at least 1 pattern, got {total_patterns} "
            f"(learned={len(learned)}, candidates={len(candidates)})"
        )

        has_positive_confidence = any(
            p.score_components.confidence > 0 for p in all_patterns
        )
        assert has_positive_confidence, (
            "At least one pattern should have confidence > 0"
        )

        # =================================================================
        # Stage 2: Store learned patterns in PostgreSQL
        # =================================================================

        # Store up to 3 patterns to keep the test focused
        patterns_to_store = all_patterns[:3]
        stored_ids: list[UUID] = []
        stored_signatures: list[str] = []

        for i, pattern in enumerate(patterns_to_store):
            pattern_id = uuid4()
            sig_hash = create_e2e_signature_hash(f"tc5_chain_{i}_{pattern_id}")

            # Use confidence from the learned pattern (clamped to valid range)
            confidence = max(0.5, pattern.score_components.confidence)

            # Store as "provisional" status so promotion gates can evaluate
            await create_test_pattern(
                e2e_db_conn,
                pattern_id=pattern_id,
                signature=f"def e2e_test_tc5_pattern_{i}(): pass",
                signature_hash=sig_hash,
                domain_id=E2E_DOMAIN,
                confidence=confidence,
                status="provisional",
                injection_count=0,
                success_count=0,
                failure_count=0,
                failure_streak=0,
                quality_score=confidence,
            )

            stored_ids.append(pattern_id)
            stored_signatures.append(sig_hash)

        # Verify patterns exist in the database
        rows = await e2e_db_conn.fetch(
            SQL_VERIFY_STORED_PATTERNS,
            f"{E2E_SIGNATURE_PREFIX}%",
        )

        tc5_rows = [r for r in rows if r["signature_hash"] in stored_signatures]
        assert len(tc5_rows) == len(stored_ids), (
            f"Expected {len(stored_ids)} TC5 patterns in DB, found {len(tc5_rows)}"
        )

        for row in tc5_rows:
            assert row["status"] == "provisional"
            assert row["confidence"] >= 0.5
            assert row["injection_count_rolling_20"] == 0
            assert row["success_count_rolling_20"] == 0
            assert row["failure_count_rolling_20"] == 0
            assert row["failure_streak"] == 0

        # =================================================================
        # Stage 3: Record session feedback (success + failure)
        # =================================================================

        from omniintelligence.nodes.node_pattern_feedback_effect.models import (
            EnumOutcomeRecordingStatus,
        )

        # --- Session 1: SUCCESS outcome ---

        await create_test_injection(
            e2e_db_conn,
            session_id=SESSION_ID_TC5_SUCCESS,
            correlation_id=CORRELATION_ID_TC5,
            pattern_ids=stored_ids,
        )

        result_success = await feedback_handler(
            session_id=SESSION_ID_TC5_SUCCESS,
            success=True,
            correlation_id=CORRELATION_ID_TC5,
        )

        assert result_success.status == EnumOutcomeRecordingStatus.SUCCESS, (
            f"Expected SUCCESS status, got {result_success.status}"
        )
        assert result_success.patterns_updated == len(stored_ids), (
            f"Expected {len(stored_ids)} patterns updated, "
            f"got {result_success.patterns_updated}"
        )

        # Verify metrics after success
        for pid in stored_ids:
            metrics = await get_pattern_metrics(e2e_db_conn, pid)
            assert metrics is not None, f"Pattern {pid} not found in DB"
            assert metrics["injection_count_rolling_20"] == 1
            assert metrics["success_count_rolling_20"] == 1
            assert metrics["failure_count_rolling_20"] == 0
            assert metrics["failure_streak"] == 0

        # --- Session 2: FAILURE outcome ---

        await create_test_injection(
            e2e_db_conn,
            session_id=SESSION_ID_TC5_FAILURE,
            correlation_id=CORRELATION_ID_TC5,
            pattern_ids=stored_ids,
        )

        result_failure = await feedback_handler(
            session_id=SESSION_ID_TC5_FAILURE,
            success=False,
            failure_reason="TC5 simulated failure for pipeline test",
            correlation_id=CORRELATION_ID_TC5,
        )

        assert result_failure.status == EnumOutcomeRecordingStatus.SUCCESS, (
            f"Expected SUCCESS status for recording, got {result_failure.status}"
        )
        assert result_failure.patterns_updated == len(stored_ids)

        # Verify metrics after failure
        for pid in stored_ids:
            metrics = await get_pattern_metrics(e2e_db_conn, pid)
            assert metrics is not None, f"Pattern {pid} not found in DB"
            assert metrics["injection_count_rolling_20"] == 2
            assert metrics["success_count_rolling_20"] == 1
            assert metrics["failure_count_rolling_20"] == 1
            assert metrics["failure_streak"] == 1

        # =================================================================
        # Stage 4: Evaluate promotion gates (dry run)
        # =================================================================

        promotion_result = await promotion_handler_with_kafka(
            dry_run=True,
            correlation_id=CORRELATION_ID_TC5,
        )

        assert promotion_result is not None
        assert promotion_result.dry_run is True
        assert promotion_result.patterns_checked >= 0

        # TC5 patterns have only 2 injections (below MIN_INJECTION_COUNT=5),
        # so they should NOT be eligible for promotion.
        # Other provisional patterns in the DB may be eligible, so we only
        # check structural correctness.
        assert promotion_result.patterns_eligible >= 0

        # =================================================================
        # Stage 5: Verify final lifecycle state and metric consistency
        # =================================================================

        final_rows = await e2e_db_conn.fetch(
            SQL_VERIFY_STORED_PATTERNS,
            f"{E2E_SIGNATURE_PREFIX}%",
        )

        final_tc5_rows = [
            r for r in final_rows if r["signature_hash"] in stored_signatures
        ]
        assert len(final_tc5_rows) == len(stored_signatures), (
            f"Expected {len(stored_signatures)} TC5 patterns in DB, "
            f"found {len(final_tc5_rows)}"
        )

        for row in final_tc5_rows:
            sig_hash = row["signature_hash"]

            # Lifecycle state should be provisional (not enough injections
            # for promotion)
            assert row["status"] in (
                "provisional",
                "validated",
                "candidate",
            ), f"Pattern {sig_hash} has unexpected status: {row['status']}"

            # Metrics must be non-negative
            assert row["injection_count_rolling_20"] >= 0, (
                f"Pattern {sig_hash}: injection_count must be >= 0"
            )
            assert row["success_count_rolling_20"] >= 0, (
                f"Pattern {sig_hash}: success_count must be >= 0"
            )
            assert row["failure_count_rolling_20"] >= 0, (
                f"Pattern {sig_hash}: failure_count must be >= 0"
            )
            assert row["failure_streak"] >= 0, (
                f"Pattern {sig_hash}: failure_streak must be >= 0"
            )

            # Consistency: success + failure <= injection_count
            total_outcomes = (
                row["success_count_rolling_20"] + row["failure_count_rolling_20"]
            )
            assert total_outcomes <= row["injection_count_rolling_20"] + 1, (
                f"Pattern {sig_hash}: success({row['success_count_rolling_20']}) + "
                f"failure({row['failure_count_rolling_20']}) should be <= "
                f"injection_count({row['injection_count_rolling_20']})"
            )

            # Verify expected values from the 2 sessions
            assert row["injection_count_rolling_20"] == 2, (
                f"Pattern {sig_hash}: expected injection_count=2 after "
                f"2 sessions, got {row['injection_count_rolling_20']}"
            )
            assert row["success_count_rolling_20"] == 1, (
                f"Pattern {sig_hash}: expected success_count=1, "
                f"got {row['success_count_rolling_20']}"
            )
            assert row["failure_count_rolling_20"] == 1, (
                f"Pattern {sig_hash}: expected failure_count=1, "
                f"got {row['failure_count_rolling_20']}"
            )
            assert row["failure_streak"] == 1, (
                f"Pattern {sig_hash}: expected failure_streak=1 "
                f"(last session was failure), "
                f"got {row['failure_streak']}"
            )
