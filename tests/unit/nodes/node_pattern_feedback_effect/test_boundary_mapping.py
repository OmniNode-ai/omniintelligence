"""Unit tests for boundary mapping functions (OMN-1763).

Tests the conversion from ClaudeSessionOutcome events to handler arguments.
These are pure mapping functions that convert between external event format
and internal handler parameters.

Functions under test:
    - `_outcome_to_success()`: Maps ClaudeCodeSessionOutcome enum to bool
    - `_extract_failure_reason()`: Extracts error message from event
    - `event_to_handler_args()`: Full event to handler kwargs mapping

Reference:
    - OMN-1763: Event-driven pattern feedback with ClaudeSessionOutcome
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    _extract_failure_reason,
    _outcome_to_success,
    event_to_handler_args,
)

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Helper: Mock error for testing _extract_failure_reason edge cases
# =============================================================================


@dataclass
class MockErrorDetails:
    """Mock error details for testing edge cases in error extraction."""

    message: str | None = None
    code: str | None = None


# =============================================================================
# Test Class: _outcome_to_success Mapping
# =============================================================================


@pytest.mark.unit
class TestOutcomeToSuccess:
    """Test _outcome_to_success mapping function.

    This function maps ClaudeCodeSessionOutcome enum values to boolean:
    - SUCCESS -> True (only success case)
    - All others -> False (conservative failure handling)
    """

    def test_success_maps_to_true(self) -> None:
        """SUCCESS outcome maps to True."""
        assert _outcome_to_success(ClaudeCodeSessionOutcome.SUCCESS) is True

    def test_failed_maps_to_false(self) -> None:
        """FAILED outcome maps to False."""
        assert _outcome_to_success(ClaudeCodeSessionOutcome.FAILED) is False

    def test_abandoned_maps_to_false(self) -> None:
        """ABANDONED outcome maps to False."""
        assert _outcome_to_success(ClaudeCodeSessionOutcome.ABANDONED) is False

    def test_unknown_maps_to_false(self) -> None:
        """UNKNOWN outcome maps to False."""
        assert _outcome_to_success(ClaudeCodeSessionOutcome.UNKNOWN) is False

    def test_all_enum_values_handled(self) -> None:
        """Verify all enum values are tested."""
        all_outcomes = list(ClaudeCodeSessionOutcome)
        assert len(all_outcomes) == 4, "Expected 4 outcome values"
        for outcome in all_outcomes:
            result = _outcome_to_success(outcome)
            assert isinstance(result, bool), f"{outcome} did not return bool"


# =============================================================================
# Test Class: _extract_failure_reason Mapping
# =============================================================================


@pytest.mark.unit
class TestExtractFailureReason:
    """Test _extract_failure_reason mapping function.

    Priority: error.message > error.code > "Unknown error" > None (no error)
    """

    def test_none_error_returns_none(self) -> None:
        """No error returns None."""
        event = ClaudeSessionOutcome(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
        )
        assert _extract_failure_reason(event) is None

    def test_error_with_message_returns_message(self) -> None:
        """Error with message returns the message."""
        # Use model_construct to bypass validation and set mock error
        # The function uses hasattr, so mock with message/code attributes works
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(message="Connection timeout"),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "Connection timeout"

    def test_error_with_code_only_returns_code(self) -> None:
        """Error with code but no message returns code."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(code="ERR_TIMEOUT"),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "ERR_TIMEOUT"

    def test_error_with_both_message_and_code_prefers_message(self) -> None:
        """Error with both message and code prefers message."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(message="Connection timeout", code="ERR_TIMEOUT"),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "Connection timeout"

    def test_error_with_empty_message_returns_code(self) -> None:
        """Error with empty message string falls back to code."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(message="", code="ERR_EMPTY"),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "ERR_EMPTY"

    def test_error_with_neither_message_nor_code_returns_unknown(self) -> None:
        """Error object without message or code returns 'Unknown error'."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "Unknown error"

    def test_error_with_none_message_and_none_code_returns_unknown(self) -> None:
        """Explicit None values return 'Unknown error'."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(message=None, code=None),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "Unknown error"

    def test_error_without_message_attribute_uses_code(self) -> None:
        """Error object missing message attribute uses code."""

        class ErrorWithCodeOnly:
            code = "MISSING_MESSAGE"

        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=ErrorWithCodeOnly(),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "MISSING_MESSAGE"

    def test_error_without_code_attribute_uses_message(self) -> None:
        """Error object missing code attribute uses message."""

        class ErrorWithMessageOnly:
            message = "Only message"

        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=ErrorWithMessageOnly(),
            correlation_id=None,
        )
        assert _extract_failure_reason(event) == "Only message"


# =============================================================================
# Test Class: event_to_handler_args Full Mapping
# =============================================================================


@pytest.mark.unit
class TestEventToHandlerArgs:
    """Test event_to_handler_args full mapping function."""

    def test_success_event_mapping(self) -> None:
        """Successful event maps correctly to handler args."""
        session_id = uuid4()
        correlation_id = uuid4()
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=correlation_id,
        )

        args = event_to_handler_args(event)

        assert args["session_id"] == session_id
        assert args["success"] is True
        assert args["failure_reason"] is None
        assert args["correlation_id"] == correlation_id

    def test_failed_event_mapping(self) -> None:
        """Failed event maps correctly to handler args."""
        session_id = uuid4()
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=None,
            correlation_id=None,
        )

        args = event_to_handler_args(event)

        assert args["session_id"] == session_id
        assert args["success"] is False
        assert args["failure_reason"] is None
        assert args["correlation_id"] is None

    def test_failed_event_with_error_mapping(self) -> None:
        """Failed event with error details extracts failure reason."""
        session_id = uuid4()
        event = ClaudeSessionOutcome.model_construct(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=MockErrorDetails(message="Database connection failed"),
            correlation_id=None,
        )

        args = event_to_handler_args(event)

        assert args["session_id"] == session_id
        assert args["success"] is False
        assert args["failure_reason"] == "Database connection failed"

    def test_abandoned_event_mapping(self) -> None:
        """Abandoned event maps correctly (treated as failure)."""
        event = ClaudeSessionOutcome(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.ABANDONED,
            error=None,
        )

        args = event_to_handler_args(event)

        assert args["success"] is False

    def test_unknown_event_mapping(self) -> None:
        """Unknown event maps correctly (conservative: treated as failure)."""
        event = ClaudeSessionOutcome(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.UNKNOWN,
            error=None,
        )

        args = event_to_handler_args(event)

        assert args["success"] is False

    def test_all_expected_keys_present(self) -> None:
        """Verify all expected keys are present in returned dict."""
        event = ClaudeSessionOutcome(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=None,
        )

        args = event_to_handler_args(event)

        expected_keys = {"session_id", "success", "failure_reason", "correlation_id"}
        assert set(args.keys()) == expected_keys

    def test_no_extra_keys_present(self) -> None:
        """Verify no unexpected keys are added to the dict."""
        event = ClaudeSessionOutcome(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=uuid4(),
        )

        args = event_to_handler_args(event)

        assert len(args) == 4  # Exactly 4 keys


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestBoundaryMappingEdgeCases:
    """Edge case tests for boundary mapping functions."""

    def test_event_with_all_none_optional_fields(self) -> None:
        """Event with all optional fields as None handles correctly."""
        session_id = uuid4()
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=None,
        )

        args = event_to_handler_args(event)

        assert args["session_id"] == session_id
        assert args["success"] is True
        assert args["failure_reason"] is None
        assert args["correlation_id"] is None

    def test_uuid_types_preserved(self) -> None:
        """Verify UUID types are preserved through mapping."""
        session_id = uuid4()
        correlation_id = uuid4()
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=None,
            correlation_id=correlation_id,
        )

        args = event_to_handler_args(event)

        assert isinstance(args["session_id"], UUID)
        assert isinstance(args["correlation_id"], UUID)

    def test_specific_uuid_values_preserved(self) -> None:
        """Verify specific UUID values pass through unchanged."""
        session_id = UUID("12345678-1234-5678-1234-567812345678")
        correlation_id = UUID("87654321-4321-8765-4321-876543218765")
        event = ClaudeSessionOutcome(
            session_id=session_id,
            outcome=ClaudeCodeSessionOutcome.FAILED,
            error=None,
            correlation_id=correlation_id,
        )

        args = event_to_handler_args(event)

        assert args["session_id"] == session_id
        assert args["correlation_id"] == correlation_id

    def test_success_event_with_error_still_extracts_reason(self) -> None:
        """Success event with error field still extracts failure_reason."""
        event = ClaudeSessionOutcome.model_construct(
            session_id=uuid4(),
            outcome=ClaudeCodeSessionOutcome.SUCCESS,
            error=MockErrorDetails(message="Unexpected error attached"),
            correlation_id=None,
        )

        args = event_to_handler_args(event)

        assert args["success"] is True
        assert args["failure_reason"] == "Unexpected error attached"


__all__ = [
    "TestOutcomeToSuccess",
    "TestExtractFailureReason",
    "TestEventToHandlerArgs",
    "TestBoundaryMappingEdgeCases",
]
