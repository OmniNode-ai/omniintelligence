# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Integration tests for enforcement feedback effect node.

These tests require a running PostgreSQL database with the learned_patterns
table. They verify that the handler correctly reads and writes quality_score
values in a real database.

Marked with @pytest.mark.integration - skipped when infrastructure is unavailable.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import requires_kafka, requires_postgres


@pytest.mark.integration
class TestEnforcementFeedbackIntegration:
    """Integration tests requiring PostgreSQL."""

    @pytest.mark.asyncio
    @requires_postgres
    async def test_confirmed_violation_updates_quality_score_in_db(
        self,
        db_conn: object,  # asyncpg connection provided by conftest
    ) -> None:
        """Confirmed violation decreases quality_score in the database.

        This test is skipped when the database is not available.
        When running, it:
        1. Inserts a test pattern with quality_score = 0.8
        2. Processes a confirmed enforcement event
        3. Verifies quality_score was decreased by 0.01
        4. Cleans up the test pattern

        Implementation notes:
        - Use db_conn (asyncpg connection) to INSERT a row into learned_patterns
          with a known quality_score (e.g. 0.8) and status='provisional'.
        - Build a ModelEnforcementEvent with one ModelPatternViolation where
          was_advised=True and was_corrected=True (confirmed violation).
        - Wrap db_conn in a ProtocolPatternRepository adapter and call
          process_enforcement_feedback(event, repository=repo).
        - Assert result.status == EnumEnforcementFeedbackStatus.SUCCESS.
        - Assert len(result.adjustments) == 1 and
          result.adjustments[0].adjustment == CONFIDENCE_ADJUSTMENT_PER_VIOLATION (-0.01).
        - SELECT quality_score FROM learned_patterns WHERE id=<pattern_id> and
          assert it equals 0.8 + (-0.01) = 0.79 (handler uses SQL_ADJUST_QUALITY_SCORE
          with LEAST(GREATEST(quality_score + $2, 0.0), 1.0)).
        - DELETE the test pattern in a finally block to avoid polluting the DB.
        """
        # TODO: implement - see handler SQL for test requirements
        pytest.skip(
            "TODO: implement - verify SQL_ADJUST_QUALITY_SCORE decrements quality_score "
            "by CONFIDENCE_ADJUSTMENT_PER_VIOLATION (-0.01) for a confirmed violation "
            "(was_advised=True AND was_corrected=True) in the learned_patterns table"
        )

    @pytest.mark.asyncio
    @requires_postgres
    async def test_quality_score_floor_clamping_in_db(
        self,
        db_conn: object,
    ) -> None:
        """Quality score does not go below 0.0 in the database.

        This test verifies the GREATEST(..., 0.0) SQL clamping works
        correctly with a real database.

        Implementation notes:
        - Insert a test pattern into learned_patterns with quality_score = 0.0
          (already at the floor).
        - Build a ModelEnforcementEvent with one confirmed violation
          (was_advised=True, was_corrected=True) referencing that pattern_id.
        - Call process_enforcement_feedback(event, repository=repo).
        - Assert result.status == EnumEnforcementFeedbackStatus.SUCCESS.
        - SELECT quality_score FROM learned_patterns WHERE id=<pattern_id> and
          assert it equals 0.0 (not -0.01), confirming GREATEST(..., 0.0) in
          SQL_ADJUST_QUALITY_SCORE clamps the score at the floor.
        - DELETE the test pattern in a finally block.

        The SQL being tested:
            UPDATE learned_patterns
            SET quality_score = LEAST(GREATEST(quality_score + $2, 0.0), 1.0)
            WHERE id = $1
        """
        # TODO: implement - see handler SQL for test requirements
        pytest.skip(
            "TODO: implement - verify GREATEST(..., 0.0) clamping in SQL_ADJUST_QUALITY_SCORE "
            "prevents quality_score from going below 0.0 when a pattern already has score=0.0 "
            "and a confirmed violation applies CONFIDENCE_ADJUSTMENT_PER_VIOLATION (-0.01)"
        )

    @pytest.mark.asyncio
    @requires_postgres
    @requires_kafka
    async def test_kafka_event_consumption_end_to_end(
        self,
        db_conn: object,
    ) -> None:
        """End-to-end test: Kafka event -> handler -> DB update.

        This test verifies the full flow from Kafka event consumption
        through handler processing to database update. Requires both
        Kafka and PostgreSQL infrastructure.

        Implementation notes:
        - Insert a test pattern into learned_patterns with a known quality_score.
        - Publish a ModelEnforcementEvent JSON payload to the Kafka topic
          'onex.evt.omniclaude.pattern-enforcement.v1' (subscribe topic from
          contract.yaml for node_enforcement_feedback_effect).
        - Start NodeClaudeHookEventEffect (or NodeEnforcementFeedbackEffect)
          with the real Kafka consumer and PostgreSQL repository wired together.
        - Wait (with timeout) for the consumer to process the message.
        - SELECT quality_score FROM learned_patterns WHERE id=<pattern_id> and
          assert it was decremented by CONFIDENCE_ADJUSTMENT_PER_VIOLATION (-0.01).
        - Assert result.status in {SUCCESS, PARTIAL_SUCCESS} from the handler.
        - Clean up: DELETE test pattern and reset Kafka consumer offset or use
          a unique group_id per test run to avoid replaying stale messages.

        Dependencies: Kafka running at KAFKA_BOOTSTRAP_SERVERS (see .env),
        PostgreSQL running at POSTGRES_HOST:POSTGRES_PORT (see .env).

        Kafka topic to publish to (from contract.yaml subscribe_topics):
            onex.evt.omniclaude.pattern-enforcement.v1
        """
        # TODO: implement - see handler SQL for test requirements
        pytest.skip(
            "TODO: implement - end-to-end test publishing ModelEnforcementEvent to Kafka "
            "topic 'onex.evt.omniclaude.pattern-enforcement.v1' (the subscribe topic "
            "declared in contract.yaml for node_enforcement_feedback_effect) and verifying "
            "the handler consumes it and applies SQL_ADJUST_QUALITY_SCORE "
            "(-0.01) to the pattern's quality_score in the learned_patterns table; "
            "requires both Kafka (KAFKA_BOOTSTRAP_SERVERS) and PostgreSQL infrastructure"
        )
