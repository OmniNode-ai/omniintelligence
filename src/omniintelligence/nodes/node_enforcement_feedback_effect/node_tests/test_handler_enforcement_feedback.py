# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for enforcement feedback handler.

Tests the handler that processes enforcement events and applies conservative
confidence adjustments to pattern quality_scores.

Test organization:
1. No Violations - Events with zero violations
2. Unconfirmed Violations - Violations that don't meet criteria
3. Confirmed Violations - Happy path with adjustments
4. Mixed Violations - Events with both confirmed and unconfirmed
5. Conservative Adjustment - Verify -0.01 per confirmed violation
6. Quality Score Clamping - Floor at 0.0, ceiling at 1.0
7. Pattern Not Found - Missing pattern handling
8. Error Handling - Database error scenarios
9. Model Validation - Event model validation
10. Protocol Compliance - Mock conformance verification

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_enforcement_feedback_effect.handlers.handler_enforcement_feedback import (
    CONFIDENCE_ADJUSTMENT_PER_VIOLATION,
    process_enforcement_feedback,
)
from omniintelligence.nodes.node_enforcement_feedback_effect.models import (
    EnumEnforcementFeedbackStatus,
    ModelEnforcementEvent,
    ModelEnforcementFeedbackResult,
    ModelPatternViolation,
)
from omniintelligence.protocols import ProtocolPatternRepository

from .conftest import MockEnforcementRepository

# =============================================================================
# Test Class: No Violations
# =============================================================================


@pytest.mark.unit
class TestNoViolations:
    """Tests for enforcement events with zero violations."""

    @pytest.mark.asyncio
    async def test_no_violations_returns_no_violations_status(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_no_violations: ModelEnforcementEvent,
    ) -> None:
        """Event with zero violations returns NO_VIOLATIONS status."""
        result = await process_enforcement_feedback(
            event=sample_enforcement_event_no_violations,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.NO_VIOLATIONS
        assert result.confirmed_violations == 0
        assert result.adjustments == []
        assert result.processed_at is not None

    @pytest.mark.asyncio
    async def test_no_violations_does_not_query_database(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_no_violations: ModelEnforcementEvent,
    ) -> None:
        """Event with zero violations does not query the database."""
        await process_enforcement_feedback(
            event=sample_enforcement_event_no_violations,
            repository=mock_repository,
        )

        assert len(mock_repository.queries_executed) == 0

    @pytest.mark.asyncio
    async def test_no_violations_preserves_event_metadata(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_no_violations: ModelEnforcementEvent,
    ) -> None:
        """Event metadata (correlation_id, session_id, etc.) is preserved in result."""
        result = await process_enforcement_feedback(
            event=sample_enforcement_event_no_violations,
            repository=mock_repository,
        )

        assert (
            result.correlation_id
            == sample_enforcement_event_no_violations.correlation_id
        )
        assert result.session_id == sample_enforcement_event_no_violations.session_id
        assert (
            result.patterns_checked
            == sample_enforcement_event_no_violations.patterns_checked
        )
        assert result.violations_found == 0


# =============================================================================
# Test Class: Unconfirmed Violations
# =============================================================================


@pytest.mark.unit
class TestUnconfirmedViolations:
    """Tests for violations that don't meet the confirmation criteria."""

    @pytest.mark.asyncio
    async def test_advised_but_not_corrected_returns_no_adjustments(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_unconfirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Violation that was advised but NOT corrected does not adjust confidence."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_unconfirmed,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.NO_ADJUSTMENTS
        assert result.confirmed_violations == 0
        assert result.adjustments == []
        # Quality score should NOT have changed
        assert mock_repository.patterns[sample_pattern_id_a]["quality_score"] == 0.8

    @pytest.mark.asyncio
    async def test_not_advised_not_corrected_returns_no_adjustments(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Violation not advised and not corrected does not adjust confidence."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)

        event = ModelEnforcementEvent(
            correlation_id=sample_correlation_id,
            session_id=sample_session_id,
            patterns_checked=3,
            violations_found=1,
            violations=[
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_a,
                    pattern_name="test-pattern",
                    was_advised=False,
                    was_corrected=False,
                ),
            ],
        )

        result = await process_enforcement_feedback(
            event=event,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.NO_ADJUSTMENTS
        assert result.confirmed_violations == 0

    @pytest.mark.asyncio
    async def test_corrected_but_not_advised_returns_no_adjustments(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Violation corrected but NOT advised does not adjust confidence.

        This edge case should not happen in practice (you can't correct what
        you weren't advised about), but the handler must handle it correctly.
        """
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)

        event = ModelEnforcementEvent(
            correlation_id=sample_correlation_id,
            session_id=sample_session_id,
            patterns_checked=3,
            violations_found=1,
            violations=[
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_a,
                    pattern_name="test-pattern",
                    was_advised=False,
                    was_corrected=True,  # Corrected without advice - edge case
                ),
            ],
        )

        result = await process_enforcement_feedback(
            event=event,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.NO_ADJUSTMENTS
        assert result.confirmed_violations == 0


# =============================================================================
# Test Class: Confirmed Violations
# =============================================================================


@pytest.mark.unit
class TestConfirmedViolations:
    """Tests for confirmed violations (advised AND corrected)."""

    @pytest.mark.asyncio
    async def test_confirmed_violation_adjusts_confidence(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Confirmed violation applies -0.01 confidence adjustment."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.confirmed_violations == 1
        assert len(result.adjustments) == 1
        assert result.adjustments[0].pattern_id == sample_pattern_id_a
        assert result.adjustments[0].adjustment == CONFIDENCE_ADJUSTMENT_PER_VIOLATION
        # Quality score should have decreased
        assert mock_repository.patterns[sample_pattern_id_a][
            "quality_score"
        ] == pytest.approx(0.79)

    @pytest.mark.asyncio
    async def test_confirmed_violation_adjustment_value(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Verify the exact adjustment value is -0.01."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=1.0)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        assert result.adjustments[0].adjustment == -0.01
        assert mock_repository.patterns[sample_pattern_id_a][
            "quality_score"
        ] == pytest.approx(0.99)

    @pytest.mark.asyncio
    async def test_confirmed_violation_includes_reason(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Adjustment includes a descriptive reason."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        reason = result.adjustments[0].reason
        assert "advised" in reason.lower()
        assert "corrected" in reason.lower()


# =============================================================================
# Test Class: Mixed Violations
# =============================================================================


@pytest.mark.unit
class TestMixedViolations:
    """Tests for events with both confirmed and unconfirmed violations."""

    @pytest.mark.asyncio
    async def test_only_confirmed_violations_get_adjusted(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_mixed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
        sample_pattern_id_b: UUID,
    ) -> None:
        """Only confirmed violations (advised AND corrected) get confidence adjusted."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)
        mock_repository.add_pattern(sample_pattern_id_b, quality_score=0.9)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_mixed,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.confirmed_violations == 1  # Only pattern A is confirmed
        assert len(result.adjustments) == 1
        assert result.adjustments[0].pattern_id == sample_pattern_id_a
        # Pattern A should have decreased
        assert mock_repository.patterns[sample_pattern_id_a][
            "quality_score"
        ] == pytest.approx(0.79)
        # Pattern B should be UNCHANGED (its violations were not confirmed)
        assert mock_repository.patterns[sample_pattern_id_b]["quality_score"] == 0.9

    @pytest.mark.asyncio
    async def test_multiple_confirmed_violations_all_get_adjusted(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
        sample_pattern_id_a: UUID,
        sample_pattern_id_b: UUID,
    ) -> None:
        """Multiple confirmed violations each get their own adjustment."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)
        mock_repository.add_pattern(sample_pattern_id_b, quality_score=0.9)

        event = ModelEnforcementEvent(
            correlation_id=sample_correlation_id,
            session_id=sample_session_id,
            patterns_checked=10,
            violations_found=2,
            violations=[
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_a,
                    pattern_name="test-pattern-a",
                    was_advised=True,
                    was_corrected=True,
                ),
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_b,
                    pattern_name="test-pattern-b",
                    was_advised=True,
                    was_corrected=True,
                ),
            ],
        )

        result = await process_enforcement_feedback(
            event=event,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.confirmed_violations == 2
        assert len(result.adjustments) == 2
        adjusted_ids = {a.pattern_id for a in result.adjustments}
        assert sample_pattern_id_a in adjusted_ids
        assert sample_pattern_id_b in adjusted_ids


# =============================================================================
# Test Class: Conservative Adjustment
# =============================================================================


@pytest.mark.unit
class TestConservativeAdjustment:
    """Tests verifying the conservative adjustment policy."""

    def test_adjustment_constant_is_negative(self) -> None:
        """CONFIDENCE_ADJUSTMENT_PER_VIOLATION must be negative."""
        assert CONFIDENCE_ADJUSTMENT_PER_VIOLATION < 0

    def test_adjustment_constant_is_small(self) -> None:
        """CONFIDENCE_ADJUSTMENT_PER_VIOLATION must be small (conservative)."""
        assert abs(CONFIDENCE_ADJUSTMENT_PER_VIOLATION) <= 0.05

    def test_adjustment_constant_is_exactly_minus_001(self) -> None:
        """CONFIDENCE_ADJUSTMENT_PER_VIOLATION is exactly -0.01."""
        assert CONFIDENCE_ADJUSTMENT_PER_VIOLATION == -0.01

    @pytest.mark.asyncio
    async def test_50_violations_needed_to_drop_from_perfect(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
    ) -> None:
        """At -0.01 per violation, 50 confirmed violations drop score from 1.0 to 0.5."""
        pattern_id = uuid4()
        mock_repository.add_pattern(pattern_id, quality_score=1.0)

        for i in range(50):
            event = ModelEnforcementEvent(
                correlation_id=sample_correlation_id,
                session_id=sample_session_id,
                patterns_checked=1,
                violations_found=1,
                violations=[
                    ModelPatternViolation(
                        pattern_id=pattern_id,
                        pattern_name=f"pattern-{i}",
                        was_advised=True,
                        was_corrected=True,
                    ),
                ],
            )
            await process_enforcement_feedback(
                event=event,
                repository=mock_repository,
            )

        assert mock_repository.patterns[pattern_id]["quality_score"] == pytest.approx(
            0.5
        )


# =============================================================================
# Test Class: Quality Score Clamping
# =============================================================================


@pytest.mark.unit
class TestQualityScoreClamping:
    """Tests for quality_score floor clamping at 0.0."""

    @pytest.mark.asyncio
    async def test_score_does_not_go_below_zero(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Quality score is clamped at 0.0 (never goes negative)."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.005)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert mock_repository.patterns[sample_pattern_id_a]["quality_score"] >= 0.0

    @pytest.mark.asyncio
    async def test_score_at_zero_does_not_go_negative(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Quality score already at 0.0 stays at 0.0 after adjustment."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.0)

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert mock_repository.patterns[sample_pattern_id_a]["quality_score"] == 0.0


# =============================================================================
# Test Class: Pattern Not Found
# =============================================================================


@pytest.mark.unit
class TestPatternNotFound:
    """Tests for handling non-existent patterns in violations."""

    @pytest.mark.asyncio
    async def test_missing_pattern_is_skipped(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
    ) -> None:
        """Violation referencing a non-existent pattern is skipped silently."""
        # Don't add any pattern to the repository

        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        # Should still succeed but with no adjustments (pattern not found)
        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.confirmed_violations == 1
        assert len(result.adjustments) == 0  # Pattern not found, no adjustment

    @pytest.mark.asyncio
    async def test_some_patterns_exist_some_dont(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
        sample_pattern_id_a: UUID,
        sample_pattern_id_b: UUID,
    ) -> None:
        """When some patterns exist and some don't, only existing ones get adjusted."""
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)
        # Don't add pattern B

        event = ModelEnforcementEvent(
            correlation_id=sample_correlation_id,
            session_id=sample_session_id,
            patterns_checked=10,
            violations_found=2,
            violations=[
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_a,
                    pattern_name="test-pattern-a",
                    was_advised=True,
                    was_corrected=True,
                ),
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_b,
                    pattern_name="test-pattern-b",
                    was_advised=True,
                    was_corrected=True,
                ),
            ],
        )

        result = await process_enforcement_feedback(
            event=event,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.SUCCESS
        assert result.confirmed_violations == 2
        assert len(result.adjustments) == 1  # Only pattern A was found
        assert result.adjustments[0].pattern_id == sample_pattern_id_a


# =============================================================================
# Test Class: Error Handling
# =============================================================================


@pytest.mark.unit
class TestErrorHandling:
    """Tests for database error scenarios."""

    @pytest.mark.asyncio
    async def test_database_error_on_pattern_check_continues(
        self,
        mock_repository: MockEnforcementRepository,
        sample_enforcement_event_confirmed: ModelEnforcementEvent,
        sample_pattern_id_a: UUID,
    ) -> None:
        """Database error during pattern check is caught, processing continues.

        Per handler error policy: return structured errors, don't raise for
        expected failures. The handler catches exceptions per-violation and
        continues with remaining violations, reporting failures in
        processing_errors.
        """
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)
        mock_repository.simulate_db_error = Exception("Connection refused")

        # Should NOT raise - errors are handled per-violation
        result = await process_enforcement_feedback(
            event=sample_enforcement_event_confirmed,
            repository=mock_repository,
        )

        # Status is PARTIAL_SUCCESS because the error is reported structurally
        assert result.status == EnumEnforcementFeedbackStatus.PARTIAL_SUCCESS
        assert result.confirmed_violations == 1
        assert len(result.adjustments) == 0  # No adjustments due to error
        assert len(result.processing_errors) == 1
        assert result.processing_errors[0].pattern_id == sample_pattern_id_a
        assert result.processing_errors[0].error_type == "Exception"
        assert "Connection refused" in result.processing_errors[0].error

    @pytest.mark.asyncio
    async def test_partial_failure_reports_both_successes_and_errors(
        self,
        mock_repository: MockEnforcementRepository,
        sample_correlation_id: UUID,
        sample_session_id: UUID,
        sample_pattern_id_a: UUID,
        sample_pattern_id_b: UUID,
    ) -> None:
        """When one adjustment succeeds and another fails, both are reported.

        The result should have PARTIAL_SUCCESS status with the successful
        adjustment in ``adjustments`` and the failure in ``processing_errors``.
        """
        mock_repository.add_pattern(sample_pattern_id_a, quality_score=0.8)
        mock_repository.add_pattern(sample_pattern_id_b, quality_score=0.9)

        # Make only pattern_b fail by injecting a per-call error handler
        original_execute = mock_repository.execute

        async def _execute_with_selective_failure(query: str, *args: object) -> str:
            if args and args[0] == sample_pattern_id_b:
                raise ConnectionError("Transient DB failure")
            return await original_execute(query, *args)

        mock_repository.execute = _execute_with_selective_failure  # type: ignore[method-assign]

        event = ModelEnforcementEvent(
            correlation_id=sample_correlation_id,
            session_id=sample_session_id,
            patterns_checked=10,
            violations_found=2,
            violations=[
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_a,
                    pattern_name="pattern-a",
                    was_advised=True,
                    was_corrected=True,
                ),
                ModelPatternViolation(
                    pattern_id=sample_pattern_id_b,
                    pattern_name="pattern-b",
                    was_advised=True,
                    was_corrected=True,
                ),
            ],
        )

        result = await process_enforcement_feedback(
            event=event,
            repository=mock_repository,
        )

        assert result.status == EnumEnforcementFeedbackStatus.PARTIAL_SUCCESS
        assert result.confirmed_violations == 2
        assert len(result.adjustments) == 1
        assert result.adjustments[0].pattern_id == sample_pattern_id_a
        assert len(result.processing_errors) == 1
        assert result.processing_errors[0].pattern_id == sample_pattern_id_b
        assert result.processing_errors[0].error_type == "ConnectionError"


# =============================================================================
# Test Class: Model Validation
# =============================================================================


@pytest.mark.unit
class TestModelValidation:
    """Tests for event model validation."""

    def test_enforcement_event_is_frozen(self) -> None:
        """ModelEnforcementEvent is immutable (frozen)."""
        import pydantic

        event = ModelEnforcementEvent(
            correlation_id=uuid4(),
            session_id=uuid4(),
            patterns_checked=5,
            violations_found=0,
        )

        with pytest.raises(pydantic.ValidationError):
            event.patterns_checked = 10

    def test_pattern_violation_is_frozen(self) -> None:
        """ModelPatternViolation is immutable (frozen)."""
        import pydantic

        violation = ModelPatternViolation(
            pattern_id=uuid4(),
            pattern_name="test",
            was_advised=True,
            was_corrected=False,
        )

        with pytest.raises(pydantic.ValidationError):
            violation.was_corrected = True

    def test_enforcement_event_rejects_negative_patterns_checked(self) -> None:
        """patterns_checked must be >= 0."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelEnforcementEvent(
                correlation_id=uuid4(),
                session_id=uuid4(),
                patterns_checked=-1,
                violations_found=0,
            )

    def test_enforcement_event_rejects_negative_violations_found(self) -> None:
        """violations_found must be >= 0."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ModelEnforcementEvent(
                correlation_id=uuid4(),
                session_id=uuid4(),
                patterns_checked=5,
                violations_found=-1,
            )

    def test_result_model_is_frozen(self) -> None:
        """ModelEnforcementFeedbackResult is immutable (frozen)."""
        import pydantic

        result = ModelEnforcementFeedbackResult(
            status=EnumEnforcementFeedbackStatus.NO_VIOLATIONS,
            correlation_id=uuid4(),
            session_id=uuid4(),
        )

        with pytest.raises(pydantic.ValidationError):
            result.confirmed_violations = 99


# =============================================================================
# Test Class: Protocol Compliance
# =============================================================================


@pytest.mark.unit
class TestProtocolCompliance:
    """Tests verifying mock implementations satisfy protocols."""

    def test_mock_repository_is_protocol_compliant(
        self,
        mock_repository: MockEnforcementRepository,
    ) -> None:
        """MockEnforcementRepository satisfies ProtocolPatternRepository protocol."""
        assert isinstance(mock_repository, ProtocolPatternRepository)
