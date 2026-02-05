# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for match_criteria() and handle_success_criteria_compute().

This module tests the core matching logic and handler orchestration including:
    - Single and multiple criterion matching
    - Required criteria gating
    - Weighted scoring
    - Edge cases (empty criteria, MISSING fields, null fields)
    - Handler error handling and metadata
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    CriteriaMatchingValidationError,
    match_criteria,
    handle_success_criteria_compute,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.models import (
    ModelSuccessCriteriaInput,
)


class TestMatchCriteriaBasicMatching:
    """Tests for basic criterion matching behavior."""

    def test_single_criterion_matches(self) -> None:
        """Test that a single matching criterion returns success."""
        outcome = {"status": "success", "exit_code": 0}
        criteria = [
            {
                "criterion_id": "check_status",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            }
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert "check_status" in result["matched_criteria"]
        assert result["unmatched_criteria"] == []
        assert result["match_score"] == 1.0

    def test_single_criterion_fails(self) -> None:
        """Test that a single non-matching criterion returns failure."""
        outcome = {"status": "failure", "exit_code": 1}
        criteria = [
            {
                "criterion_id": "check_status",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            }
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert result["matched_criteria"] == []
        assert "check_status" in result["unmatched_criteria"]
        assert result["match_score"] == 0.0

    def test_multiple_criteria_all_match(self) -> None:
        """Test that all matching criteria return success."""
        outcome = {"status": "success", "exit_code": 0, "retries": 0}
        criteria = [
            {
                "criterion_id": "status_ok",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "exit_ok",
                "field": "exit_code",
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "no_retries",
                "field": "retries",
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": False,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert set(result["matched_criteria"]) == {"status_ok", "exit_ok", "no_retries"}
        assert result["unmatched_criteria"] == []
        assert result["match_score"] == 1.0

    def test_multiple_criteria_some_fail(self) -> None:
        """Test that partial matches are reflected in score."""
        outcome = {"status": "success", "exit_code": 1}
        criteria = [
            {
                "criterion_id": "status_ok",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": False,
            },
            {
                "criterion_id": "exit_ok",
                "field": "exit_code",
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": False,
            },
        ]

        result = match_criteria(outcome, criteria)

        # All criteria are optional, so success is True
        assert result["success"] is True
        assert "status_ok" in result["matched_criteria"]
        assert "exit_ok" in result["unmatched_criteria"]
        # Score = 1/2 = 0.5
        assert result["match_score"] == 0.5


class TestMatchCriteriaRequiredCriteria:
    """Tests for required criteria gating behavior."""

    def test_required_true_criterion_fails_causes_overall_failure(self) -> None:
        """Test that a failing required criterion causes overall failure."""
        outcome = {"status": "success", "exit_code": 1}
        criteria = [
            {
                "criterion_id": "status_ok",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": False,
            },
            {
                "criterion_id": "exit_ok",
                "field": "exit_code",
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": True,  # This one fails
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert "status_ok" in result["matched_criteria"]
        assert "exit_ok" in result["unmatched_criteria"]
        # Score = 1/2 = 0.5
        assert result["match_score"] == 0.5

    def test_required_false_criterion_fails_allows_success(self) -> None:
        """Test that failing optional criteria don't prevent overall success."""
        outcome = {"status": "success", "exit_code": 1}
        criteria = [
            {
                "criterion_id": "status_ok",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "exit_ok",
                "field": "exit_code",
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": False,  # This one fails but is optional
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert "status_ok" in result["matched_criteria"]
        assert "exit_ok" in result["unmatched_criteria"]
        # Score = 1/2 = 0.5
        assert result["match_score"] == 0.5

    def test_all_required_pass_with_optional_failures(self) -> None:
        """Test success when all required pass but optionals fail."""
        outcome = {"a": 1, "b": 2, "c": 3}
        criteria = [
            {
                "criterion_id": "req_a",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "req_b",
                "field": "b",
                "operator": "equals",
                "expected_value": 2,
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "opt_c",
                "field": "c",
                "operator": "equals",
                "expected_value": 99,  # Fails
                "weight": 1.0,
                "required": False,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True  # All required passed
        assert set(result["matched_criteria"]) == {"req_a", "req_b"}
        assert result["unmatched_criteria"] == ["opt_c"]


class TestMatchCriteriaScoring:
    """Tests for weighted score calculation."""

    def test_score_calculation_with_weights(self) -> None:
        """Test that scores are weighted correctly."""
        outcome = {"a": 1, "b": 2}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
                "weight": 3.0,  # Matches, weight 3
                "required": False,
            },
            {
                "criterion_id": "c2",
                "field": "b",
                "operator": "equals",
                "expected_value": 99,  # Does not match, weight 1
                "weight": 1.0,
                "required": False,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        # Score = 3 / (3 + 1) = 0.75
        assert result["match_score"] == 0.75

    def test_total_weight_zero_all_required_pass(self) -> None:
        """Test score=1.0 when total_weight==0 and all required pass."""
        outcome = {"status": "success"}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 0.0,  # Zero weight
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert result["match_score"] == 1.0

    def test_total_weight_zero_required_fails(self) -> None:
        """Test score=0.0 when total_weight==0 and required fails."""
        outcome = {"status": "failure"}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 0.0,  # Zero weight
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert result["match_score"] == 0.0

    def test_empty_criteria_returns_success(self) -> None:
        """Test that empty criteria list returns success with score 1.0."""
        result = match_criteria({"status": "any"}, [])

        assert result["success"] is True
        assert result["match_score"] == 1.0
        assert result["matched_criteria"] == []
        assert result["unmatched_criteria"] == []

    def test_mixed_weights_calculation(self) -> None:
        """Test accurate score with varied weights."""
        outcome = {"a": 1, "b": 2, "c": 3}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
                "weight": 2.0,  # Matches
                "required": False,
            },
            {
                "criterion_id": "c2",
                "field": "b",
                "operator": "equals",
                "expected_value": 2,
                "weight": 3.0,  # Matches
                "required": False,
            },
            {
                "criterion_id": "c3",
                "field": "c",
                "operator": "equals",
                "expected_value": 99,  # Does not match
                "weight": 5.0,
                "required": False,
            },
        ]

        result = match_criteria(outcome, criteria)

        # Score = (2 + 3) / (2 + 3 + 5) = 5/10 = 0.5
        assert result["match_score"] == 0.5


class TestMatchCriteriaEdgeCases:
    """Tests for edge cases like MISSING and null fields."""

    def test_missing_field_handling(self) -> None:
        """Test that MISSING field causes criterion to fail."""
        outcome = {"status": "success"}  # No 'exit_code' field
        criteria = [
            {
                "criterion_id": "exit_ok",
                "field": "exit_code",  # This field is MISSING
                "operator": "equals",
                "expected_value": 0,
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert "exit_ok" in result["unmatched_criteria"]
        # Check match_details for the reason
        assert len(result["match_details"]) == 1
        assert result["match_details"][0]["actual_type"] == "missing"
        assert "missing" in result["match_details"][0]["reason"].lower()

    def test_null_field_handling_distinct_from_missing(self) -> None:
        """Test that null field is distinct from MISSING."""
        outcome = {"status": None}  # Field exists but is None
        criteria = [
            {
                "criterion_id": "status_null",
                "field": "status",
                "operator": "is_null",
                "expected_value": None,
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert "status_null" in result["matched_criteria"]
        assert result["match_details"][0]["actual_type"] == "null"

    def test_missing_field_fails_is_null_operator(self) -> None:
        """Test that MISSING field fails is_null operator."""
        outcome = {"other": "value"}  # No 'status' field
        criteria = [
            {
                "criterion_id": "status_null",
                "field": "status",  # MISSING
                "operator": "is_null",
                "expected_value": None,
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert "status_null" in result["unmatched_criteria"]
        # MISSING is not null, it's missing
        assert result["match_details"][0]["actual_type"] == "missing"

    def test_missing_field_fails_is_not_null_operator(self) -> None:
        """Test that MISSING field fails is_not_null operator."""
        outcome = {"other": "value"}  # No 'status' field
        criteria = [
            {
                "criterion_id": "status_exists",
                "field": "status",  # MISSING
                "operator": "is_not_null",
                "expected_value": None,
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is False
        assert "status_exists" in result["unmatched_criteria"]

    def test_null_vs_missing_detailed(self) -> None:
        """Test detailed distinction between null and MISSING values."""
        # Outcome with explicit null value
        outcome_with_null = {"value": None}
        # Outcome without the field at all
        outcome_without_field = {"other": 123}

        # Test equals with None expectation
        criteria_equals_none = [
            {
                "criterion_id": "c1",
                "field": "value",
                "operator": "equals",
                "expected_value": None,
                "weight": 1.0,
                "required": True,
            },
        ]

        # null == None should pass
        result_null = match_criteria(outcome_with_null, criteria_equals_none)
        assert result_null["success"] is True

        # MISSING != None (MISSING fails all non-null-check operators)
        result_missing = match_criteria(outcome_without_field, criteria_equals_none)
        assert result_missing["success"] is False

    def test_nested_field_path(self) -> None:
        """Test matching with nested field paths."""
        outcome = {
            "result": {
                "status": "success",
                "metrics": {"count": 42},
            }
        }
        criteria = [
            {
                "criterion_id": "nested_status",
                "field": "result.status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "nested_count",
                "field": "result.metrics.count",
                "operator": "equals",
                "expected_value": 42,
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert set(result["matched_criteria"]) == {"nested_status", "nested_count"}

    def test_list_index_field_path(self) -> None:
        """Test matching with list index in field path."""
        outcome = {"items": [{"name": "first"}, {"name": "second"}]}
        criteria = [
            {
                "criterion_id": "first_item",
                "field": "items.0.name",
                "operator": "equals",
                "expected_value": "first",
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "second_item",
                "field": "items.1.name",
                "operator": "equals",
                "expected_value": "second",
                "weight": 1.0,
                "required": True,
            },
        ]

        result = match_criteria(outcome, criteria)

        assert result["success"] is True
        assert set(result["matched_criteria"]) == {"first_item", "second_item"}


class TestMatchCriteriaValidation:
    """Tests for criteria validation errors."""

    def test_duplicate_criterion_ids_raises_error(self) -> None:
        """Test that duplicate criterion_ids raise validation error."""
        outcome = {"status": "success"}
        criteria = [
            {
                "criterion_id": "dup",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            },
            {
                "criterion_id": "dup",  # Duplicate
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1.0,
                "required": False,
            },
        ]

        with pytest.raises(CriteriaMatchingValidationError, match="Duplicate"):
            match_criteria(outcome, criteria)

    def test_invalid_operator_raises_error(self) -> None:
        """Test that invalid operator raises validation error."""
        outcome = {"status": "success"}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "invalid_op",  # Invalid
                "expected_value": "success",
                "weight": 1.0,
                "required": True,
            },
        ]

        with pytest.raises(CriteriaMatchingValidationError, match="Invalid operator"):
            match_criteria(outcome, criteria)

    def test_negative_weight_raises_error(self) -> None:
        """Test that negative weight raises validation error."""
        outcome = {"status": "success"}
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": -1.0,  # Negative
                "required": True,
            },
        ]

        with pytest.raises(CriteriaMatchingValidationError, match="Negative weight"):
            match_criteria(outcome, criteria)


class TestHandleSuccessCriteriaComputeSuccess:
    """Tests for successful handler execution."""

    def test_handler_returns_success_when_criteria_match(self) -> None:
        """Test handler returns success=True when criteria match."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success", "exit_code": 0},
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": 1.0,
                    "required": True,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.success is True
        assert "c1" in output.matched_criteria
        assert output.match_score == 1.0

    def test_metadata_includes_processing_time(self) -> None:
        """Test that metadata includes processing time."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success"},
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": 1.0,
                    "required": True,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.metadata is not None
        assert "processing_time_ms" in output.metadata
        assert output.metadata["processing_time_ms"] >= 0

    def test_metadata_includes_counts(self) -> None:
        """Test that metadata includes match counts."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success", "exit_code": 1},
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": 1.0,
                    "required": True,
                },
                {
                    "criterion_id": "c2",
                    "field": "exit_code",
                    "operator": "equals",
                    "expected_value": 0,  # Does not match (exit_code is 1)
                    "weight": 1.0,
                    "required": False,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.metadata is not None
        assert output.metadata["total_criteria"] == 2
        assert output.metadata["matched_count"] == 1
        assert output.metadata["unmatched_count"] == 1


class TestHandleSuccessCriteriaComputeErrors:
    """Tests for handler error handling."""

    def test_validation_error_returns_structured_output(self) -> None:
        """Test that validation errors return structured output, not raise."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success"},
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "invalid_operator",  # Invalid
                    "expected_value": "success",
                    "weight": 1.0,
                    "required": True,
                },
            ],
        )

        # Should not raise - returns structured error
        output = handle_success_criteria_compute(input_data)

        assert output.success is False
        assert output.match_score == 0.0
        assert output.metadata is not None
        # Error should be in match_details
        assert len(output.metadata["match_details"]) > 0
        assert "validation_error" in output.metadata["match_details"][0].lower()

    def test_handler_returns_failure_with_error_message(self) -> None:
        """Test handler returns failure with error message on validation error."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success"},
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": -5.0,  # Negative weight triggers validation error
                    "required": True,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.success is False
        assert output.metadata is not None
        # Should contain validation_error in match_details
        details = output.metadata.get("match_details", [])
        assert any("validation_error" in str(d).lower() for d in details)


class TestHandleSuccessCriteriaComputeEdgeCases:
    """Tests for handler edge cases."""

    def test_empty_criteria_set_returns_success(self) -> None:
        """Test that empty criteria set returns success."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "any"},
            criteria_set=[],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.success is True
        assert output.match_score == 1.0
        assert output.matched_criteria == []
        assert output.unmatched_criteria == []

    def test_handler_with_correlation_id(self) -> None:
        """Test handler works with correlation_id."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={"status": "success"},
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
            criteria_set=[
                {
                    "criterion_id": "c1",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": 1.0,
                    "required": True,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.success is True

    def test_handler_multiple_criteria_mixed_results(self) -> None:
        """Test handler with multiple criteria having mixed results."""
        input_data = ModelSuccessCriteriaInput(
            execution_outcome={
                "status": "success",
                "exit_code": 0,
                "retry_count": 5,  # Higher than expected
            },
            criteria_set=[
                {
                    "criterion_id": "status_ok",
                    "field": "status",
                    "operator": "equals",
                    "expected_value": "success",
                    "weight": 2.0,
                    "required": True,
                },
                {
                    "criterion_id": "exit_ok",
                    "field": "exit_code",
                    "operator": "equals",
                    "expected_value": 0,
                    "weight": 2.0,
                    "required": True,
                },
                {
                    "criterion_id": "low_retries",
                    "field": "retry_count",
                    "operator": "less_than",
                    "expected_value": 3,  # Fails: 5 is not < 3
                    "weight": 1.0,
                    "required": False,
                },
            ],
        )

        output = handle_success_criteria_compute(input_data)

        assert output.success is True  # All required passed
        assert set(output.matched_criteria) == {"status_ok", "exit_ok"}
        assert output.unmatched_criteria == ["low_retries"]
        # Score = (2 + 2) / (2 + 2 + 1) = 4/5 = 0.8
        assert output.match_score == 0.8
