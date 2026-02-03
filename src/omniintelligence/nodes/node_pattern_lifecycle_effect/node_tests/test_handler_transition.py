# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern lifecycle effect node handler.

Tests the handler that applies pattern status transitions as projections.
Covers idempotency, status guard, PROVISIONAL guard, and atomic transactions.

Test organization:
1. Successful Transitions - Happy path scenarios
2. Idempotency - Duplicate request detection
3. Status Guard - Optimistic locking verification
4. PROVISIONAL Guard - Legacy state protection
5. Pattern Not Found - Missing pattern handling
6. Audit Records - Audit trail insertion
7. Kafka Events - Event emission verification
8. Error Handling - Database error scenarios
9. Protocol Compliance - Mock conformance verification

Reference:
    - OMN-1805: Pattern lifecycle effect node with atomic projections
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    ProtocolIdempotencyStore,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    _parse_update_count,
    apply_transition,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
    ModelTransitionResult,
)

from .conftest import (
    MockIdempotencyStore,
    MockKafkaPublisher,
    MockPatternRepository,
)


# =============================================================================
# Test Class: Successful Transitions
# =============================================================================


@pytest.mark.unit
class TestSuccessfulTransitions:
    """Tests for successful pattern status transitions.

    These tests verify the happy path where:
    - Pattern exists with expected status
    - Request is not a duplicate
    - Transition is applied successfully
    """

    @pytest.mark.asyncio
    async def test_successful_transition_provisional_to_validated(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test successful status transition from provisional to validated."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.duplicate is False
        assert result.pattern_id == sample_pattern_id
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.transitioned_at == sample_transition_at
        assert result.transition_id is not None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_successful_transition_validated_to_deprecated(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test successful status transition from validated to deprecated."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="validated")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="validated",
            to_status="deprecated",
            trigger="demote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.duplicate is False
        assert result.to_status == "deprecated"
        # Verify pattern was updated in repository
        assert mock_repository.patterns[sample_pattern_id]["status"] == "deprecated"

    @pytest.mark.asyncio
    async def test_successful_transition_candidate_to_validated(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test successful status transition from candidate to validated."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="validated",
            trigger="validation_passed",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.from_status == "candidate"
        assert result.to_status == "validated"

    @pytest.mark.asyncio
    async def test_transition_with_optional_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test transition with all optional fields populated."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")
        gate_snapshot = {
            "injection_count_rolling_20": 15,
            "success_rate_rolling_20": 0.85,
            "failure_streak": 0,
        }

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="auto_promote",
            actor="promotion_scheduler",
            reason="Passed all promotion gates",
            gate_snapshot=gate_snapshot,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert "Passed all promotion gates" in (result.reason or "")


# =============================================================================
# Test Class: Idempotency
# =============================================================================


@pytest.mark.unit
class TestIdempotency:
    """Tests for idempotency (duplicate request detection).

    These tests verify that:
    - Duplicate requests return success=True with duplicate=True
    - No database mutations occur for duplicates
    - No Kafka events are emitted for duplicates
    """

    @pytest.mark.asyncio
    async def test_duplicate_request_returns_success_with_duplicate_flag(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test idempotency - same request_id returns duplicate=True."""
        # Arrange: Pre-populate idempotency store with the request_id
        idempotency_store = MockIdempotencyStore(
            processed_ids={sample_request_id},
        )
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        assert result.duplicate is True
        assert result.pattern_id == sample_pattern_id
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.transition_id is None  # No new transition created
        assert result.transitioned_at is None  # No timestamp for duplicate

    @pytest.mark.asyncio
    async def test_duplicate_request_does_not_execute_database_queries(
        self,
        mock_repository: MockPatternRepository,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Duplicate request does not execute any database mutation queries."""
        # Arrange
        idempotency_store = MockIdempotencyStore(
            processed_ids={sample_request_id},
        )
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: No UPDATE or INSERT queries executed
        update_queries = [
            q for q, _ in mock_repository.queries_executed if "UPDATE" in q
        ]
        insert_queries = [
            q for q, _ in mock_repository.queries_executed if "INSERT" in q
        ]
        assert len(update_queries) == 0
        assert len(insert_queries) == 0

    @pytest.mark.asyncio
    async def test_duplicate_request_does_not_emit_kafka_event(
        self,
        mock_repository: MockPatternRepository,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Duplicate request does not emit Kafka event."""
        # Arrange
        idempotency_store = MockIdempotencyStore(
            processed_ids={sample_request_id},
        )
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=idempotency_store,
            producer=mock_producer,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: No events published
        assert len(mock_producer.published_events) == 0

    @pytest.mark.asyncio
    async def test_new_request_id_is_recorded_in_idempotency_store(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """New request_id is recorded in idempotency store after success."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: Request ID was recorded
        assert sample_request_id in mock_idempotency_store.processed_ids
        assert sample_request_id in mock_idempotency_store.recorded_ids

    @pytest.mark.asyncio
    async def test_different_request_ids_both_succeed(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Two different request_ids for same pattern both succeed (different transitions)."""
        # Arrange: Two different request IDs
        request_id_1 = uuid4()
        request_id_2 = uuid4()
        pattern_id_2 = uuid4()

        mock_repository.add_pattern(sample_pattern_id, status="provisional")
        mock_repository.add_pattern(pattern_id_2, status="provisional")

        # Act: First transition
        result_1 = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=request_id_1,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Act: Second transition (different pattern)
        result_2 = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=request_id_2,
            correlation_id=sample_correlation_id,
            pattern_id=pattern_id_2,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: Both succeeded, neither is duplicate
        assert result_1.success is True
        assert result_1.duplicate is False
        assert result_2.success is True
        assert result_2.duplicate is False


# =============================================================================
# Test Class: Status Guard (Optimistic Locking)
# =============================================================================


@pytest.mark.unit
class TestStatusGuard:
    """Tests for status guard (optimistic locking) verification.

    These tests verify that:
    - Transitions only succeed if pattern's current status matches from_status
    - Status mismatches return success=False with descriptive error
    - No audit record is inserted on status mismatch
    """

    @pytest.mark.asyncio
    async def test_status_mismatch_returns_failure(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test status guard - fails if from_status doesn't match current."""
        # Arrange: Pattern has status "candidate", but we expect "provisional"
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",  # Expected provisional, but pattern is candidate
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.duplicate is False
        assert result.pattern_id == sample_pattern_id
        assert result.transition_id is None
        assert result.transitioned_at is None
        # Error message should indicate status mismatch/guard failure
        error_lower = (result.error_message or "").lower()
        assert "expected" in error_lower or "status" in error_lower

    @pytest.mark.asyncio
    async def test_status_mismatch_error_includes_expected_and_actual(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Status mismatch error message includes both expected and actual status."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="validated")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="deprecated",
            trigger="demote",
            transition_at=sample_transition_at,
        )

        # Assert: Error message contains both statuses
        error_msg = result.error_message or ""
        assert "provisional" in error_msg.lower()
        assert "validated" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_status_mismatch_does_not_insert_audit(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Status mismatch does not insert audit record."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: No audit records inserted
        assert len(mock_repository.inserted_audits) == 0

    @pytest.mark.asyncio
    async def test_concurrent_transition_scenario(
        self,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Simulate concurrent transition where status changes between fetch and update.

        This test simulates a race condition:
        1. Handler A fetches pattern (status=provisional)
        2. Handler B fetches pattern (status=provisional)
        3. Handler B updates pattern (status=validated)
        4. Handler A tries to update (should fail status guard)
        """
        # Arrange: Repository that changes status mid-transaction
        mock_repository = MockPatternRepository()
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # First transition succeeds
        result_1 = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=uuid4(),
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Second transition with same from_status should fail
        result_2 = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=uuid4(),  # Different request ID
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",  # Pattern is now "validated"
            to_status="deprecated",
            trigger="demote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result_1.success is True
        assert result_2.success is False
        # Error message should indicate status mismatch/guard failure
        error_lower = (result_2.error_message or "").lower()
        assert "expected" in error_lower or "status" in error_lower


# =============================================================================
# Test Class: PROVISIONAL Guard
# =============================================================================


@pytest.mark.unit
class TestProvisionalGuard:
    """Tests for PROVISIONAL guard (legacy state protection).

    These tests verify that:
    - Transitions TO "provisional" status are rejected
    - Rejection happens before any database operations
    - Transitions FROM "provisional" are still allowed
    """

    @pytest.mark.asyncio
    async def test_provisional_target_rejected(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Test PROVISIONAL guard - to_status='provisional' is rejected."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="provisional",  # FORBIDDEN - legacy state
            trigger="validation_passed",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.duplicate is False
        assert "provisional" in (result.error_message or "").lower()
        assert "not allowed" in (result.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_provisional_target_rejected_with_enum(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """PROVISIONAL guard rejects transitions to provisional status.

        Note: Case sensitivity is now enforced by the enum type system.
        This test verifies the guard works with the typed enum value.
        """
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act - Use proper enum value
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=uuid4(),
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.PROVISIONAL,
            trigger="validation_passed",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False, "Should reject to_status=PROVISIONAL"

    @pytest.mark.asyncio
    async def test_provisional_guard_before_idempotency_check(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """PROVISIONAL guard is checked before idempotency store is consulted.

        This ensures we don't record a request_id for an invalid transition.
        """
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="candidate")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="candidate",
            to_status="provisional",  # FORBIDDEN
            trigger="validation_passed",
            transition_at=sample_transition_at,
        )

        # Assert: Request ID should NOT be recorded (guard failed first)
        assert sample_request_id not in mock_idempotency_store.processed_ids

    @pytest.mark.asyncio
    async def test_transition_from_provisional_allowed(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Transitions FROM provisional are still allowed (only TO is blocked)."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",  # FROM provisional is OK
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True


# =============================================================================
# Test Class: Pattern Not Found
# =============================================================================


@pytest.mark.unit
class TestPatternNotFound:
    """Tests for handling non-existent patterns."""

    @pytest.mark.asyncio
    async def test_pattern_not_found_returns_failure(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Transition on non-existent pattern returns failure."""
        # Arrange: Do NOT add pattern to repository

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.duplicate is False
        # Error message should indicate pattern doesn't exist
        error_lower = (result.error_message or "").lower()
        assert "does not exist" in error_lower or "not found" in error_lower
        assert result.transition_id is None

    @pytest.mark.asyncio
    async def test_pattern_not_found_does_not_insert_audit(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Pattern not found does not insert audit record."""
        # Arrange: No pattern

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: No audit records
        assert len(mock_repository.inserted_audits) == 0


# =============================================================================
# Test Class: Audit Records
# =============================================================================


@pytest.mark.unit
class TestAuditRecords:
    """Tests for audit record insertion."""

    @pytest.mark.asyncio
    async def test_audit_record_inserted_on_success(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Successful transition inserts audit record."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: Audit record was inserted
        assert len(mock_repository.inserted_audits) == 1
        insert_query = mock_repository.inserted_audits[0]["query"]
        assert "INSERT INTO pattern_lifecycle_transitions" in insert_query

    @pytest.mark.asyncio
    async def test_audit_record_contains_required_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Audit record contains all required fields."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            actor="test_actor",
            reason="Test reason",
            transition_at=sample_transition_at,
        )

        # Assert: Check the args passed to INSERT
        args = mock_repository.inserted_audits[0]["args"]
        # Args order: id, pattern_id, from_status, to_status, trigger, actor, reason,
        #             gate_snapshot, transitioned_at, request_id, correlation_id
        assert args[1] == sample_pattern_id  # pattern_id
        assert args[2] == "provisional"  # from_status
        assert args[3] == "validated"  # to_status
        assert args[4] == "promote"  # trigger
        assert args[5] == "test_actor"  # actor
        assert args[6] == "Test reason"  # reason
        assert args[9] == sample_request_id  # request_id
        assert args[10] == sample_correlation_id  # correlation_id


# =============================================================================
# Test Class: Kafka Events
# =============================================================================


@pytest.mark.unit
class TestKafkaEvents:
    """Tests for Kafka event emission."""

    @pytest.mark.asyncio
    async def test_kafka_event_emitted_on_success(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Successful transition emits Kafka event when producer available."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=mock_producer,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert len(mock_producer.published_events) == 1
        topic, key, value = mock_producer.published_events[0]
        assert "pattern-lifecycle-transitioned" in topic
        assert key == str(sample_pattern_id)
        assert value["event_type"] == "PatternLifecycleTransitioned"
        assert value["from_status"] == "provisional"
        assert value["to_status"] == "validated"

    @pytest.mark.asyncio
    async def test_kafka_event_contains_correlation_id(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Kafka event includes correlation_id for tracing."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=mock_producer,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        _, _, value = mock_producer.published_events[0]
        assert value["correlation_id"] == str(sample_correlation_id)
        assert value["request_id"] == str(sample_request_id)

    @pytest.mark.asyncio
    async def test_no_event_when_producer_is_none(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """No exception when producer is None (graceful degradation)."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act - Should not raise
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,  # No Kafka producer
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert: Transition still succeeded
        assert result.success is True

    @pytest.mark.asyncio
    async def test_event_topic_uses_env_prefix(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        mock_producer: MockKafkaPublisher,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Event topic uses correct environment prefix."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=mock_producer,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
            topic_env_prefix="prod",
        )

        # Assert
        topic, _, _ = mock_producer.published_events[0]
        assert topic.startswith("prod.")


# =============================================================================
# Test Class: Error Handling
# =============================================================================


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_database_error_returns_failure(
        self,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Database error during transition returns failure result."""
        # Arrange
        mock_repository = MockPatternRepository()
        mock_repository.add_pattern(sample_pattern_id, status="provisional")
        mock_repository.simulate_db_error = Exception("Connection refused")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is False
        assert result.duplicate is False
        assert "error" in (result.reason or "").lower()
        assert result.transition_id is None


# =============================================================================
# Test Class: Helper Function - _parse_update_count
# =============================================================================


@pytest.mark.unit
class TestParseUpdateCount:
    """Tests for the _parse_update_count helper function."""

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

    def test_mock_idempotency_store_is_protocol_compliant(
        self,
        mock_idempotency_store: MockIdempotencyStore,
    ) -> None:
        """MockIdempotencyStore satisfies ProtocolIdempotencyStore protocol."""
        assert isinstance(mock_idempotency_store, ProtocolIdempotencyStore)

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
    async def test_result_model_is_frozen(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """ModelTransitionResult is immutable (frozen)."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert isinstance(result, ModelTransitionResult)
        # Frozen models raise ValidationError on mutation
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            result.success = False  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_result_includes_all_status_fields(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Result includes from_status and to_status regardless of outcome."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act - Success case
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.from_status == "provisional"
        assert result.to_status == "validated"
        assert result.pattern_id == sample_pattern_id


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_trigger_rejected(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Empty string trigger is rejected with validation error.

        Trigger is a required field that documents why the transition occurred.
        Empty triggers make audit logs useless for debugging.
        """
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="",  # Empty trigger - should be rejected
            transition_at=sample_transition_at,
        )

        # Assert: Empty trigger should be rejected
        assert result.success is False
        assert result.duplicate is False
        error_msg = (result.error_message or "").lower()
        assert "trigger" in error_msg or "empty" in error_msg or "required" in error_msg

    @pytest.mark.asyncio
    async def test_whitespace_only_trigger_rejected(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Whitespace-only trigger is rejected with validation error.

        Triggers containing only whitespace are functionally empty and should
        be rejected for the same reasons as empty strings.
        """
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="   ",  # Whitespace-only trigger - should be rejected
            transition_at=sample_transition_at,
        )

        # Assert: Whitespace-only trigger should be rejected
        assert result.success is False
        assert result.duplicate is False
        error_msg = (result.error_message or "").lower()
        assert "trigger" in error_msg or "empty" in error_msg or "required" in error_msg

    @pytest.mark.asyncio
    async def test_very_long_reason_handled(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Very long reason string is handled without error."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")
        long_reason = "A" * 10000  # 10,000 character reason

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            reason=long_reason,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True

    @pytest.mark.asyncio
    async def test_same_from_and_to_status(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Transition where from_status == to_status (no-op) is allowed.

        This is a valid scenario for retries or re-application of state.
        """
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="validated")

        # Act - Transition from validated to validated
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="validated",
            to_status="validated",  # Same as from
            trigger="reconfirm",
            transition_at=sample_transition_at,
        )

        # Assert: Should succeed (no-op is valid)
        assert result.success is True
        assert result.from_status == "validated"
        assert result.to_status == "validated"

    @pytest.mark.asyncio
    async def test_null_gate_snapshot_handled(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """None gate_snapshot is handled correctly (stored as NULL)."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            gate_snapshot=None,  # Explicitly None
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        # Check that NULL was passed for gate_snapshot in the INSERT
        args = mock_repository.inserted_audits[0]["args"]
        assert args[7] is None  # gate_snapshot_json position

    @pytest.mark.asyncio
    async def test_complex_gate_snapshot_serialized(
        self,
        mock_repository: MockPatternRepository,
        mock_idempotency_store: MockIdempotencyStore,
        sample_pattern_id: UUID,
        sample_request_id: UUID,
        sample_correlation_id: UUID,
        sample_transition_at: datetime,
    ) -> None:
        """Complex gate_snapshot dict is serialized to JSON."""
        # Arrange
        mock_repository.add_pattern(sample_pattern_id, status="provisional")
        gate_snapshot = {
            "injection_count_rolling_20": 15,
            "success_rate_rolling_20": 0.85,
            "failure_streak": 0,
            "nested": {
                "key": "value",
                "list": [1, 2, 3],
            },
        }

        # Act
        result = await apply_transition(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            producer=None,
            request_id=sample_request_id,
            correlation_id=sample_correlation_id,
            pattern_id=sample_pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            gate_snapshot=gate_snapshot,
            transition_at=sample_transition_at,
        )

        # Assert
        assert result.success is True
        # Check that JSON was passed for gate_snapshot
        args = mock_repository.inserted_audits[0]["args"]
        import json

        gate_snapshot_json = args[7]
        assert gate_snapshot_json is not None
        parsed = json.loads(gate_snapshot_json)
        assert parsed["injection_count_rolling_20"] == 15
        assert parsed["nested"]["key"] == "value"
