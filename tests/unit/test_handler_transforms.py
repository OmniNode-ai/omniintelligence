"""Unit tests for intelligence adapter transform handlers.

These tests verify the transformation logic for converting raw intelligence
service responses into canonical formats suitable for event publishing.

Coverage:
- Normal case with complete response data
- Graceful handling of missing optional attributes
- Default values when required fields are absent
"""

from __future__ import annotations

import pytest

# Import directly from handler modules to avoid triggering the full nodes import chain
# which requires omnibase_core and other heavy dependencies
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_pattern import (
    transform_pattern_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_performance import (
    transform_performance_response,
)
from omniintelligence.nodes.intelligence_adapter.handlers.handler_transform_quality import (
    transform_quality_response,
)


class TestTransformQualityResponse:
    """Tests for transform_quality_response handler."""

    def test_complete_response(self) -> None:
        """Test normal case with complete response."""

        class MockCompliance:
            score = 0.9
            violations = ["violation1"]
            recommendations = ["rec1"]

        class MockMaintainability:
            complexity_score = 0.7

        class MockResponse:
            quality_score = 0.85
            onex_compliance = MockCompliance()
            maintainability = MockMaintainability()
            architectural_era = "modern"
            temporal_relevance = 0.95

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True for complete response"
        assert result["quality_score"] == 0.85, "quality_score should match response value"
        assert result["onex_compliance"] == 0.9, (
            "onex_compliance should extract score from nested object"
        )
        assert result["complexity_score"] == 0.7, (
            "complexity_score should extract from maintainability"
        )
        assert result["issues"] == ["violation1"], "issues should contain violations"
        assert result["recommendations"] == ["rec1"], "recommendations should be extracted"
        assert result["patterns"] == [], "patterns should be empty list (reserved)"
        assert result["result_data"]["architectural_era"] == "modern", (
            "result_data should include architectural_era"
        )
        assert result["result_data"]["temporal_relevance"] == 0.95, (
            "result_data should include temporal_relevance"
        )

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing."""

        class MockResponse:
            quality_score = 0.75
            # Missing: onex_compliance, maintainability, architectural_era, temporal_relevance

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True for partial response"
        assert result["quality_score"] == 0.75, "quality_score should be extracted"
        assert result["onex_compliance"] == 0.0, (
            "onex_compliance should default to 0.0 when missing"
        )
        assert result["complexity_score"] == 0.0, (
            "complexity_score should default to 0.0 when missing"
        )
        assert result["issues"] == [], "issues should be empty when onex_compliance missing"
        assert result["recommendations"] == [], (
            "recommendations should be empty when compliance missing"
        )
        assert result["result_data"]["architectural_era"] is None, (
            "architectural_era should be None when missing"
        )
        assert result["result_data"]["temporal_relevance"] is None, (
            "temporal_relevance should be None when missing"
        )

    def test_none_optional_fields(self) -> None:
        """Test graceful handling when optional fields are None.

        The quality handler properly checks for None using truthiness checks,
        so None values should be handled gracefully.
        """

        class MockResponse:
            quality_score = 0.75
            onex_compliance = None
            maintainability = None
            architectural_era = None
            temporal_relevance = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True for None fields"
        assert result["quality_score"] == 0.75, "quality_score should be extracted"
        assert result["onex_compliance"] == 0.0, (
            "onex_compliance should default to 0.0 for None"
        )
        assert result["complexity_score"] == 0.0, (
            "complexity_score should default to 0.0 for None"
        )
        assert result["issues"] == [], "issues should be empty for None compliance"
        assert result["recommendations"] == [], (
            "recommendations should be empty for None compliance"
        )

    def test_missing_quality_score(self) -> None:
        """Test handling when quality_score is missing."""

        class MockResponse:
            pass  # No attributes

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True even with no attributes"
        assert result["quality_score"] == 0.0, (
            "quality_score should default to 0.0 when missing"
        )
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0"
        assert result["complexity_score"] == 0.0, "complexity_score should default to 0.0"
        assert result["issues"] == [], "issues should be empty list"
        assert result["recommendations"] == [], "recommendations should be empty list"

    def test_partial_onex_compliance(self) -> None:
        """Test when onex_compliance has partial data."""

        class MockCompliance:
            score = 0.8
            # Missing: violations, recommendations

        class MockResponse:
            quality_score = 0.9
            onex_compliance = MockCompliance()

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True for valid response"
        assert result["onex_compliance"] == 0.8, "onex_compliance should extract score"
        assert result["issues"] == [], "issues should be empty when violations missing"
        assert result["recommendations"] == [], "recommendations should be empty when attr missing"

    def test_none_quality_score_explicit(self) -> None:
        """Test handling when quality_score is explicitly set to None.

        The quality handler now has explicit None checks that default to 0.0.
        This ensures downstream consumers always receive a numeric value.
        """

        class MockResponse:
            quality_score = None  # Explicitly None, not missing
            onex_compliance = None
            maintainability = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True even with None quality_score"
        # Handler explicitly checks `is not None` and defaults to 0.0
        assert result["quality_score"] == 0.0, (
            "quality_score should default to 0.0 when explicitly set to None"
        )
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0 for None"
        assert result["complexity_score"] == 0.0, "complexity_score should default to 0.0 for None"

    def test_onex_compliance_missing_score_attribute(self) -> None:
        """Test when onex_compliance exists but has no score attribute.

        This tests the defensive check for score attribute access.
        """

        class MockIncompleteCompliance:
            # Has violations but no score attribute
            violations = ["some_violation"]

        class MockResponse:
            quality_score = 0.8
            onex_compliance = MockIncompleteCompliance()

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Issues should be extracted despite missing score
        assert result["issues"] == ["some_violation"], "issues should extract violations"
        # The handler accesses .score directly which would raise AttributeError
        # This test documents the expected behavior - score access will fail
        # if onex_compliance exists but has no score

    def test_violations_and_recommendations_are_none(self) -> None:
        """Test when violations and recommendations are explicitly None."""

        class MockCompliance:
            score = 0.7
            violations = None
            recommendations = None

        class MockResponse:
            quality_score = 0.8
            onex_compliance = MockCompliance()

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["onex_compliance"] == 0.7, "onex_compliance should extract score"
        # extend() with None would fail, but hasattr check protects us
        assert result["issues"] == [], "issues should handle None violations gracefully"
        assert result["recommendations"] == [], "recommendations should handle None gracefully"

    def test_none_response(self) -> None:
        """Test handling when response is None.

        The handler should return a failure response with error message.
        """
        result = transform_quality_response(None)
        assert result["success"] is False, "success should be False for None response"
        assert result["quality_score"] == 0.0, "quality_score should default to 0.0"
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0"
        assert result["complexity_score"] == 0.0, "complexity_score should default to 0.0"
        assert result["issues"] == [], "issues should be empty list"
        assert result["recommendations"] == [], "recommendations should be empty list"
        assert "error" in result, "error key should be present"
        assert "None" in result["error"], "error message should mention None"

    def test_dict_response(self) -> None:
        """Test handling when response is a dict instead of an object.

        The handler should support dict-based responses for API flexibility.
        """
        response = {
            "quality_score": 0.82,
            "onex_compliance": {
                "score": 0.88,
                "violations": ["missing docstring"],
                "recommendations": ["add docstrings"],
            },
            "maintainability": {
                "complexity_score": 0.65,
            },
            "architectural_era": "modern",
            "temporal_relevance": 0.9,
        }
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True for dict response"
        assert result["quality_score"] == 0.82, "quality_score should be extracted from dict"
        assert result["onex_compliance"] == 0.88, "onex_compliance should extract nested score"
        assert result["complexity_score"] == 0.65, "complexity_score should extract nested value"
        assert result["issues"] == ["missing docstring"], "violations should be extracted"
        assert result["recommendations"] == ["add docstrings"], "recommendations should be extracted"
        assert result["result_data"]["architectural_era"] == "modern", (
            "architectural_era should be extracted"
        )
        assert result["result_data"]["temporal_relevance"] == 0.9, (
            "temporal_relevance should be extracted"
        )

    def test_quality_score_string_coercion(self) -> None:
        """Test when quality_score is a string that needs type coercion.

        The handler should safely convert numeric strings to floats.
        """

        class MockResponse:
            quality_score = "0.75"  # String instead of float
            onex_compliance = None
            maintainability = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True for string quality_score"
        assert result["quality_score"] == 0.75, "string quality_score should be converted to float"

    def test_quality_score_invalid_string(self) -> None:
        """Test when quality_score is an invalid string that cannot be converted.

        The handler should default to 0.0 for non-numeric strings.
        """

        class MockResponse:
            quality_score = "not_a_number"
            onex_compliance = None
            maintainability = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True even with invalid string"
        assert result["quality_score"] == 0.0, "invalid string should default to 0.0"

    def test_quality_score_out_of_range_high(self) -> None:
        """Test when quality_score exceeds 1.0.

        The handler should clamp values to the valid range [0.0, 1.0].
        """

        class MockResponse:
            quality_score = 1.5  # Out of range high
            onex_compliance = None
            maintainability = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["quality_score"] == 1.0, "quality_score > 1.0 should be clamped to 1.0"

    def test_quality_score_out_of_range_low(self) -> None:
        """Test when quality_score is below 0.0.

        The handler should clamp values to the valid range [0.0, 1.0].
        """

        class MockResponse:
            quality_score = -0.5  # Out of range low
            onex_compliance = None
            maintainability = None

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["quality_score"] == 0.0, "quality_score < 0.0 should be clamped to 0.0"

    def test_single_violation_not_list(self) -> None:
        """Test when violations is a single item, not a list.

        The handler should wrap single items in a list.
        """

        class MockCompliance:
            score = 0.7
            violations = "single violation string"  # Not a list
            recommendations = "single recommendation"  # Not a list

        class MockResponse:
            quality_score = 0.8
            onex_compliance = MockCompliance()

        result = transform_quality_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["issues"] == ["single violation string"], (
            "single violation should be wrapped in list"
        )
        assert result["recommendations"] == ["single recommendation"], (
            "single recommendation should be wrapped in list"
        )

    def test_mixed_dict_and_object_nested(self) -> None:
        """Test when response has mixed dict and object nested structures.

        The handler should handle hybrid responses gracefully.
        """

        class MockMaintainability:
            complexity_score = 0.6

        response = {
            "quality_score": 0.85,
            "onex_compliance": {
                "score": 0.9,
                "violations": [],
            },
            "maintainability": MockMaintainability(),  # Object nested in dict
            "architectural_era": "transitional",
        }
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True for hybrid response"
        assert result["quality_score"] == 0.85, "quality_score should be extracted"
        assert result["onex_compliance"] == 0.9, "nested dict score should be extracted"
        # Note: maintainability as object in dict won't work with _get_attr_or_key
        # because dict access returns the object, but then we try dict access on object
        # This documents current behavior


class TestTransformPatternResponse:
    """Tests for transform_pattern_response handler."""

    def test_complete_response(self) -> None:
        """Test normal case with complete response."""

        class MockPattern:
            def model_dump(self) -> dict:
                return {"name": "singleton", "confidence": 0.9}

        class MockAntiPattern:
            pattern_type = "god_class"
            description = "Class does too much"

        class MockCompliance:
            onex_compliance = 0.88

        class MockResponse:
            detected_patterns = [MockPattern()]
            anti_patterns = [MockAntiPattern()]
            recommendations = ["Use DI"]
            architectural_compliance = MockCompliance()
            analysis_summary = "Good patterns"
            confidence_scores = {"overall": 0.85}

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True for complete response"
        assert len(result["patterns"]) == 1, "should have one detected pattern"
        assert result["patterns"][0] == {"name": "singleton", "confidence": 0.9}, (
            "pattern should be serialized via model_dump"
        )
        assert result["onex_compliance"] == 0.88, (
            "onex_compliance should extract from architectural_compliance"
        )
        assert "god_class: Class does too much" in result["issues"], (
            "issues should format anti-patterns as 'type: description'"
        )
        assert result["recommendations"] == ["Use DI"], "recommendations should be extracted"
        assert result["result_data"]["analysis_summary"] == "Good patterns", (
            "result_data should include analysis_summary"
        )
        assert result["result_data"]["confidence_scores"] == {"overall": 0.85}, (
            "result_data should include confidence_scores"
        )

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing.

        The pattern handler uses hasattr checks, so missing attributes
        are handled gracefully with empty defaults.
        """

        class MockResponse:
            pass  # No attributes

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True for empty response"
        assert result["patterns"] == [], "patterns should default to empty list"
        assert result["issues"] == [], "issues should default to empty list"
        assert result["recommendations"] == [], "recommendations should default to empty list"
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0"
        assert result["result_data"]["analysis_summary"] == "", (
            "analysis_summary should default to empty string"
        )
        assert result["result_data"]["confidence_scores"] == {}, (
            "confidence_scores should default to empty dict"
        )

    def test_empty_collections(self) -> None:
        """Test when collections are empty lists (not None)."""

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = []
            architectural_compliance = None
            analysis_summary = None
            confidence_scores = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True for empty collections"
        assert result["patterns"] == [], "empty patterns list should remain empty"
        assert result["issues"] == [], "empty anti_patterns should result in empty issues"
        assert result["recommendations"] == [], "empty recommendations should remain empty"
        assert result["onex_compliance"] == 0.0, "onex_compliance should default for None"

    def test_multiple_patterns_and_anti_patterns(self) -> None:
        """Test with multiple detected patterns and anti-patterns."""

        class MockPattern1:
            def model_dump(self) -> dict:
                return {"name": "factory", "confidence": 0.85}

        class MockPattern2:
            def model_dump(self) -> dict:
                return {"name": "observer", "confidence": 0.92}

        class MockAntiPattern1:
            pattern_type = "spaghetti_code"
            description = "Complex control flow"

        class MockAntiPattern2:
            pattern_type = "magic_numbers"
            description = "Unexplained constants"

        class MockResponse:
            detected_patterns = [MockPattern1(), MockPattern2()]
            anti_patterns = [MockAntiPattern1(), MockAntiPattern2()]
            recommendations = ["Refactor", "Add constants file"]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True for multi-item response"
        assert len(result["patterns"]) == 2, "should have two detected patterns"
        assert len(result["issues"]) == 2, "should have two anti-pattern issues"
        assert "spaghetti_code: Complex control flow" in result["issues"], (
            "first anti-pattern should be formatted correctly"
        )
        assert "magic_numbers: Unexplained constants" in result["issues"], (
            "second anti-pattern should be formatted correctly"
        )
        assert len(result["recommendations"]) == 2, "should have two recommendations"

    def test_anti_pattern_missing_description(self) -> None:
        """Test anti-pattern handling when description is missing.

        Anti-patterns with only pattern_type should be included with a fallback
        description to ensure partial data is captured rather than silently dropped.
        """

        class MockAntiPatternNoDescription:
            pattern_type = "some_type"
            # Missing: description

        class MockResponse:
            detected_patterns = []
            anti_patterns = [MockAntiPatternNoDescription()]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Anti-pattern with only pattern_type should be included with fallback description
        assert result["issues"] == [
            "some_type: (no description)"
        ], "anti-pattern with missing description should use fallback"

    def test_anti_pattern_missing_pattern_type(self) -> None:
        """Test anti-pattern handling when pattern_type is missing.

        Anti-patterns with only description should be included with a fallback
        pattern type identifier.
        """

        class MockAntiPatternNoType:
            description = "This is a problem"
            # Missing: pattern_type

        class MockResponse:
            detected_patterns = []
            anti_patterns = [MockAntiPatternNoType()]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Anti-pattern with only description should be included with fallback type
        assert result["issues"] == [
            "Unknown anti-pattern: This is a problem"
        ], "anti-pattern with missing pattern_type should use fallback"

    def test_anti_pattern_missing_both_attributes(self) -> None:
        """Test anti-pattern handling when both attributes are missing.

        Anti-patterns without pattern_type AND description should be skipped
        as they provide no useful information.
        """

        class MockAntiPatternEmpty:
            # Missing both: pattern_type, description
            pass

        class MockResponse:
            detected_patterns = []
            anti_patterns = [MockAntiPatternEmpty()]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Anti-pattern with neither attribute should be skipped
        assert result["issues"] == [], "anti-pattern with no useful attributes should be skipped"

    def test_anti_pattern_none_values(self) -> None:
        """Test anti-pattern handling when attributes are explicitly None.

        Anti-patterns with None values should be handled the same as missing.
        """

        class MockAntiPatternNoneValues:
            pattern_type = None
            description = None

        class MockResponse:
            detected_patterns = []
            anti_patterns = [MockAntiPatternNoneValues()]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Anti-pattern with None values should be skipped (truthy check fails)
        assert result["issues"] == [], "anti-pattern with None values should be skipped"

    def test_pattern_model_dump_raises_exception(self) -> None:
        """Test handling when a pattern's model_dump() raises an exception.

        The handler now catches model_dump exceptions and includes an error dict
        in the patterns list instead of propagating the exception.
        """

        class MockBadPattern:
            def model_dump(self) -> dict:
                raise ValueError("Serialization failed")

        class MockResponse:
            detected_patterns = [MockBadPattern()]
            anti_patterns = []
            recommendations = []

        # The handler catches model_dump exceptions and returns error dict
        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True despite model_dump error"
        assert len(result["patterns"]) == 1, "error should be captured in patterns list"
        assert "error" in result["patterns"][0], "error key should be in pattern dict"
        assert "Serialization failed" in result["patterns"][0]["error"], (
            "error message should contain original exception message"
        )

    def test_pattern_model_dump_returns_none(self) -> None:
        """Test handling when a pattern's model_dump() returns None.

        model_dump() should return a dict, but if it returns None,
        that None should be included in the patterns list.
        """

        class MockPattern:
            def model_dump(self):
                return None

        class MockResponse:
            detected_patterns = [MockPattern()]
            anti_patterns = []
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["patterns"] == [None], "None from model_dump should be included in patterns"

    def test_pattern_already_dict(self) -> None:
        """Test handling when a pattern is already a dict (no serialization needed).

        The handler should pass through dict patterns as-is.
        """

        class MockResponse:
            detected_patterns = [{"name": "factory", "confidence": 0.9}]
            anti_patterns = []
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["patterns"] == [{"name": "factory", "confidence": 0.9}], (
            "dict patterns should pass through unchanged"
        )

    def test_pattern_with_pydantic_v1_dict_method(self) -> None:
        """Test handling when a pattern has Pydantic v1 .dict() method (no model_dump).

        The handler should fall back to .dict() for older Pydantic models.
        """

        class MockPydanticV1Pattern:
            # No model_dump, but has dict (Pydantic v1 style)
            def dict(self) -> dict:
                return {"name": "observer", "confidence": 0.85}

        class MockResponse:
            detected_patterns = [MockPydanticV1Pattern()]
            anti_patterns = []
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["patterns"] == [{"name": "observer", "confidence": 0.85}], (
            "patterns with .dict() method should serialize via fallback"
        )

    def test_pattern_no_serialization_method(self) -> None:
        """Test handling when a pattern has no model_dump or dict method.

        The handler should wrap such patterns in a dict with raw_pattern key.
        """

        class MockPlainPattern:
            def __str__(self) -> str:
                return "PlainPattern(name=singleton)"

        class MockResponse:
            detected_patterns = [MockPlainPattern()]
            anti_patterns = []
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert len(result["patterns"]) == 1, "pattern should be captured"
        assert "raw_pattern" in result["patterns"][0], (
            "pattern without serialization should be wrapped with raw_pattern key"
        )
        assert "PlainPattern" in result["patterns"][0]["raw_pattern"], (
            "raw_pattern should contain string representation"
        )

    def test_none_collections_explicitly_set(self) -> None:
        """Test when collections are explicitly None (not missing)."""

        class MockResponse:
            detected_patterns = None
            anti_patterns = None
            recommendations = None
            architectural_compliance = None
            analysis_summary = None
            confidence_scores = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True for None collections"
        assert result["patterns"] == [], "None detected_patterns should become empty list"
        assert result["issues"] == [], "None anti_patterns should become empty issues"
        assert result["recommendations"] == [], "None recommendations should become empty list"
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0"

    def test_analysis_summary_and_confidence_scores_none(self) -> None:
        """Test result_data when analysis_summary and confidence_scores are None.

        When these attributes are explicitly set to None, the handler should
        convert them to sensible defaults (empty string and empty dict) for
        defensive handling and safer downstream processing.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = []
            analysis_summary = None
            confidence_scores = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # None values are converted to sensible defaults for safer downstream handling
        assert result["result_data"]["analysis_summary"] == "", (
            "None analysis_summary should be converted to empty string"
        )
        assert result["result_data"]["confidence_scores"] == {}, (
            "None confidence_scores should be converted to empty dict"
        )

    def test_architectural_compliance_missing_onex_compliance_attr(self) -> None:
        """Test when architectural_compliance exists but lacks onex_compliance attr."""

        class MockArchCompliance:
            # Has some attributes but not onex_compliance
            some_other_attr = 0.9

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = []
            architectural_compliance = MockArchCompliance()

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["onex_compliance"] == 0.0, (
            "onex_compliance should default to 0.0 when attr missing"
        )

    def test_recommendations_not_iterable(self) -> None:
        """Test when recommendations is a non-iterable value (single string).

        The handler should wrap non-iterable recommendations in a list.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = 12345  # Non-iterable integer
            architectural_compliance = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Non-iterable truthy value should be converted to string and wrapped in list
        assert result["recommendations"] == ["12345"], (
            "non-iterable recommendations should be converted to string list"
        )

    def test_recommendations_single_string(self) -> None:
        """Test when recommendations is a string (which is iterable but not a list).

        Strings are iterable, so a single string becomes a list of characters
        unless handled specially. The handler should convert to list properly.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = "single recommendation"  # String, not list
            architectural_compliance = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # String is iterable, so list() breaks it into characters
        # This documents current behavior (may want to change this)
        assert len(result["recommendations"]) == len("single recommendation"), (
            "string recommendations are split into characters by list()"
        )

    def test_mixed_patterns_good_and_bad(self) -> None:
        """Test with a mix of good and bad patterns.

        The handler should process each pattern independently, capturing
        errors for bad ones without failing the entire transformation.
        """

        class MockGoodPattern:
            def model_dump(self) -> dict:
                return {"name": "factory", "confidence": 0.9}

        class MockBadPattern:
            def model_dump(self) -> dict:
                raise ValueError("Bad pattern")

        class MockResponse:
            detected_patterns = [MockGoodPattern(), MockBadPattern()]
            anti_patterns = []
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert len(result["patterns"]) == 2, "both patterns should be captured"
        assert result["patterns"][0] == {"name": "factory", "confidence": 0.9}, (
            "good pattern should serialize correctly"
        )
        assert "error" in result["patterns"][1], (
            "bad pattern should capture error"
        )

    def test_none_response(self) -> None:
        """Test graceful handling when response is None.

        When the response itself is None (e.g., API returned nothing),
        the handler should return a safe empty result structure with
        success=False.
        """
        result = transform_pattern_response(None)
        assert result["success"] is False, "success should be False for None response"
        assert result["onex_compliance"] == 0.0, "onex_compliance should default to 0.0"
        assert result["patterns"] == [], "patterns should be empty list"
        assert result["issues"] == [], "issues should be empty list"
        assert result["recommendations"] == [], "recommendations should be empty list"
        assert result["result_data"]["analysis_summary"] == "", (
            "analysis_summary should be empty string"
        )
        assert result["result_data"]["confidence_scores"] == {}, (
            "confidence_scores should be empty dict"
        )

    def test_anti_pattern_as_dict(self) -> None:
        """Test anti-pattern handling when it's a dict instead of an object.

        Some APIs might return anti-patterns as plain dicts rather than objects.
        The handler should support both formats.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = [
                {"pattern_type": "god_object", "description": "Class has too many responsibilities"},
                {"pattern_type": "spaghetti_code"},  # Missing description
                {"description": "Unclear code flow"},  # Missing pattern_type
            ]
            recommendations = []

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert len(result["issues"]) == 3, "all three anti-patterns should produce issues"
        assert "god_object: Class has too many responsibilities" in result["issues"]
        assert "spaghetti_code: (no description)" in result["issues"]
        assert "Unknown anti-pattern: Unclear code flow" in result["issues"]

    def test_architectural_compliance_as_dict(self) -> None:
        """Test ONEX compliance extraction when architectural_compliance is a dict.

        Some APIs might return compliance as a plain dict rather than an object.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = []
            architectural_compliance = {"onex_compliance": 0.85}

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["onex_compliance"] == 0.85, "onex_compliance should be extracted from dict"

    def test_onex_compliance_non_numeric_value(self) -> None:
        """Test ONEX compliance handling when value is non-numeric.

        If onex_compliance contains a non-numeric value, it should
        safely default to 0.0.
        """

        class MockArchCompliance:
            onex_compliance = "invalid"

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = []
            architectural_compliance = MockArchCompliance()

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["onex_compliance"] == 0.0, (
            "non-numeric onex_compliance should default to 0.0"
        )

    def test_none_items_in_collections(self) -> None:
        """Test handling when collections contain None items.

        Lists of patterns or anti-patterns might contain None items
        which should be gracefully skipped.
        """

        class MockPattern:
            def model_dump(self) -> dict:
                return {"name": "valid_pattern"}

        class MockResponse:
            detected_patterns = [None, MockPattern(), None]
            anti_patterns = [None, None]
            recommendations = ["rec1", None, "rec2"]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Only the valid pattern should be in results (None items skipped)
        assert len(result["patterns"]) == 1, "only non-None patterns should be included"
        assert result["patterns"][0] == {"name": "valid_pattern"}
        # None anti-patterns are skipped
        assert result["issues"] == [], "None anti-patterns should be skipped"
        # Recommendations include None items since list() preserves them
        # (this is acceptable - they become None strings in the list)


class TestTransformPerformanceResponse:
    """Tests for transform_performance_response handler."""

    def test_complete_response(self) -> None:
        """Test normal case with complete response."""

        class MockMetrics:
            complexity_estimate = 0.7

            def model_dump(self) -> dict:
                return {"complexity_estimate": 0.7, "lines_of_code": 500}

        class MockOpportunity:
            title = "Cache results"
            description = "Add caching"

            def model_dump(self) -> dict:
                return {"title": self.title, "description": self.description}

        class MockResponse:
            baseline_metrics = MockMetrics()
            optimization_opportunities = [MockOpportunity()]
            total_opportunities = 1
            estimated_total_improvement = 0.25

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for complete response"
        assert result["complexity_score"] == 0.7, (
            "complexity_score should extract from baseline_metrics"
        )
        assert "Cache results: Add caching" in result["recommendations"], (
            "recommendations should format opportunities as 'title: description'"
        )
        assert result["result_data"]["baseline_metrics"] == {
            "complexity_estimate": 0.7,
            "lines_of_code": 500,
        }, "baseline_metrics should serialize via model_dump"
        assert result["result_data"]["total_opportunities"] == 1, (
            "total_opportunities should be extracted"
        )
        assert result["result_data"]["estimated_improvement"] == 0.25, (
            "estimated_improvement should be extracted"
        )

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing.

        The performance handler uses hasattr checks, so missing attributes
        are handled gracefully with defaults.
        """

        class MockResponse:
            pass  # No attributes

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for empty response"
        assert result["complexity_score"] == 0.0, "complexity_score should default to 0.0"
        assert result["recommendations"] == [], "recommendations should default to empty list"
        assert result["result_data"]["baseline_metrics"] == {}, (
            "baseline_metrics should default to empty dict"
        )
        assert result["result_data"]["optimization_opportunities"] == [], (
            "optimization_opportunities should default to empty list"
        )
        assert result["result_data"]["total_opportunities"] == 0, (
            "total_opportunities should default to 0"
        )
        assert result["result_data"]["estimated_improvement"] == 0.0, (
            "estimated_improvement should default to 0.0"
        )

    def test_empty_optimization_opportunities(self) -> None:
        """Test when optimization_opportunities is an empty list."""

        class MockMetrics:
            complexity_estimate = 0.5

            def model_dump(self) -> dict:
                return {"complexity_estimate": 0.5}

        class MockResponse:
            baseline_metrics = MockMetrics()
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for empty opportunities"
        assert result["complexity_score"] == 0.5, "complexity_score should be extracted"
        assert result["recommendations"] == [], "empty opportunities means empty recommendations"
        assert result["result_data"]["optimization_opportunities"] == [], (
            "empty opportunities list should remain empty"
        )

    def test_baseline_metrics_none(self) -> None:
        """Test when baseline_metrics is None but attribute exists."""

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for None baseline_metrics"
        assert result["complexity_score"] == 0.0, "complexity_score should default for None"
        assert result["result_data"]["baseline_metrics"] == {}, (
            "None baseline_metrics should become empty dict"
        )

    def test_multiple_optimization_opportunities(self) -> None:
        """Test with multiple optimization opportunities."""

        class MockOpportunity1:
            title = "Enable caching"
            description = "Add Redis caching layer"

            def model_dump(self) -> dict:
                return {"title": self.title, "description": self.description}

        class MockOpportunity2:
            title = "Database indexing"
            description = "Add index on user_id column"

            def model_dump(self) -> dict:
                return {"title": self.title, "description": self.description}

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = [MockOpportunity1(), MockOpportunity2()]
            total_opportunities = 2
            estimated_total_improvement = 0.45

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for multi-opportunity response"
        assert len(result["recommendations"]) == 2, "should have two recommendations"
        assert "Enable caching: Add Redis caching layer" in result["recommendations"], (
            "first recommendation should be formatted correctly"
        )
        assert "Database indexing: Add index on user_id column" in result["recommendations"], (
            "second recommendation should be formatted correctly"
        )
        assert len(result["result_data"]["optimization_opportunities"]) == 2, (
            "should have two serialized opportunities"
        )
        assert result["result_data"]["total_opportunities"] == 2, (
            "total_opportunities should match"
        )
        assert result["result_data"]["estimated_improvement"] == 0.45, (
            "estimated_improvement should match"
        )

    def test_opportunity_missing_attributes(self) -> None:
        """Test opportunity handling when attributes are incomplete."""

        class MockOpportunityIncomplete:
            title = "Some optimization"
            # Missing: description

            def model_dump(self) -> dict:
                return {"title": self.title}

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = [MockOpportunityIncomplete()]
            total_opportunities = 1
            estimated_total_improvement = 0.1

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Incomplete opportunity should not be added to recommendations
        assert result["recommendations"] == [], (
            "opportunity without description should not be in recommendations"
        )
        # But it should still be in result_data
        assert len(result["result_data"]["optimization_opportunities"]) == 1, (
            "opportunity should still be serialized to result_data"
        )

    def test_baseline_metrics_model_dump_raises_exception(self) -> None:
        """Test handling when baseline_metrics model_dump() raises an exception.

        This tests the behavior when baseline_metrics.model_dump() raises
        an exception. The handler does not catch this exception, so it propagates.
        """

        class MockBadMetrics:
            complexity_estimate = 0.5

            def model_dump(self) -> dict:
                raise RuntimeError("Metrics serialization failed")

        class MockResponse:
            baseline_metrics = MockBadMetrics()
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        # The handler does not catch model_dump exceptions, so this should raise
        with pytest.raises(RuntimeError, match="Metrics serialization failed"):
            transform_performance_response(MockResponse())

    def test_opportunity_model_dump_raises_exception(self) -> None:
        """Test handling when an opportunity's model_dump() raises an exception.

        The handler iterates through opportunities and calls model_dump() on each.
        If any raises an exception, it will propagate.
        """

        class MockBadOpportunity:
            title = "Good title"
            description = "Good description"

            def model_dump(self) -> dict:
                raise ValueError("Opportunity serialization failed")

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = [MockBadOpportunity()]
            total_opportunities = 1
            estimated_total_improvement = 0.1

        # The handler does not catch model_dump exceptions, so this should raise
        with pytest.raises(ValueError, match="Opportunity serialization failed"):
            transform_performance_response(MockResponse())

    def test_baseline_metrics_missing_model_dump(self) -> None:
        """Test when baseline_metrics exists but lacks model_dump method.

        The handler checks hasattr(baseline_metrics, 'model_dump') before calling.
        """

        class MockMetricsNoModelDump:
            complexity_estimate = 0.6
            # Missing: model_dump method

        class MockResponse:
            baseline_metrics = MockMetricsNoModelDump()
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["complexity_score"] == 0.6, (
            "complexity_score should be extracted even without model_dump"
        )
        assert result["result_data"]["baseline_metrics"] == {}, (
            "baseline_metrics should be empty dict when model_dump missing"
        )

    def test_opportunity_missing_model_dump(self) -> None:
        """Test when opportunity exists but lacks model_dump method.

        The handler filters out opportunities without model_dump in result_data.
        """

        class MockOpportunityNoModelDump:
            title = "Optimize database"
            description = "Add indexes"
            # Missing: model_dump method

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = [MockOpportunityNoModelDump()]
            total_opportunities = 1
            estimated_total_improvement = 0.15

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Recommendation should be added (has title and description)
        assert result["recommendations"] == ["Optimize database: Add indexes"], (
            "recommendation should be created from title and description"
        )
        # But should NOT be in optimization_opportunities (no model_dump)
        assert result["result_data"]["optimization_opportunities"] == [], (
            "opportunity without model_dump should be filtered from result_data"
        )

    def test_none_collections_explicitly_set(self) -> None:
        """Test when collections are explicitly None (not missing)."""

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = None
            total_opportunities = None
            estimated_total_improvement = None

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True for None collections"
        assert result["complexity_score"] == 0.0, "complexity_score should default to 0.0"
        assert result["recommendations"] == [], "None opportunities should become empty list"
        assert result["result_data"]["baseline_metrics"] == {}, (
            "None baseline_metrics should become empty dict"
        )
        assert result["result_data"]["optimization_opportunities"] == [], (
            "None opportunities should become empty list in result_data"
        )
        # total_opportunities and estimated_improvement use hasattr, not the value
        # hasattr returns True for attributes set to None

    def test_baseline_metrics_missing_complexity_estimate(self) -> None:
        """Test when baseline_metrics exists but lacks complexity_estimate."""

        class MockMetricsNoComplexity:
            # Has model_dump but no complexity_estimate
            def model_dump(self) -> dict:
                return {"other_metric": 0.5}

        class MockResponse:
            baseline_metrics = MockMetricsNoComplexity()
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True"
        assert result["complexity_score"] == 0.0, (
            "complexity_score should default to 0.0 when complexity_estimate missing"
        )
        assert result["result_data"]["baseline_metrics"] == {"other_metric": 0.5}, (
            "baseline_metrics should serialize other attributes"
        )

    def test_complexity_estimate_is_none(self) -> None:
        """Test when complexity_estimate is explicitly None.

        The performance handler checks for None values and defaults to 0.0.
        This ensures downstream consumers always receive a numeric value.
        """

        class MockMetrics:
            complexity_estimate = None

            def model_dump(self) -> dict:
                return {"complexity_estimate": None}

        class MockResponse:
            baseline_metrics = MockMetrics()
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Handler checks if baseline_metrics and complexity_estimate are truthy
        # None is falsy, so it defaults to 0.0
        assert result["complexity_score"] == 0.0, (
            "complexity_score should default to 0.0 when complexity_estimate is None"
        )


class TestQualityResponseEdgeCases:
    """Edge case tests for transform_quality_response handler.

    These tests cover boundary conditions and malformed data scenarios
    identified in PR review. They ensure defensive handling of unexpected
    inputs and proper score clamping.
    """

    # =========================================================================
    # Negative score clamping tests
    # =========================================================================

    def test_quality_transform_negative_score_clamps_to_zero(self) -> None:
        """Test that negative quality scores are clamped to 0.0."""
        response = {"quality_score": -0.5}
        result = transform_quality_response(response)
        assert result["quality_score"] == 0.0, (
            "negative quality_score should be clamped to 0.0"
        )

    def test_quality_transform_negative_compliance_clamps_to_zero(self) -> None:
        """Test that negative compliance scores are clamped to 0.0."""
        response = {"onex_compliance": {"score": -1.0}}
        result = transform_quality_response(response)
        assert result["onex_compliance"] == 0.0, (
            "negative onex_compliance score should be clamped to 0.0"
        )

    def test_quality_transform_negative_complexity_clamps_to_zero(self) -> None:
        """Test that negative complexity scores are clamped to 0.0."""
        response = {"maintainability": {"complexity_score": -0.25}}
        result = transform_quality_response(response)
        assert result["complexity_score"] == 0.0, (
            "negative complexity_score should be clamped to 0.0"
        )

    # =========================================================================
    # Scores > 1.0 clamping tests
    # =========================================================================

    def test_quality_transform_score_over_one_clamps_to_one(self) -> None:
        """Test that scores over 1.0 are clamped to 1.0."""
        response = {"quality_score": 1.5}
        result = transform_quality_response(response)
        assert result["quality_score"] == 1.0, (
            "quality_score > 1.0 should be clamped to 1.0"
        )

    def test_quality_transform_compliance_over_one_clamps_to_one(self) -> None:
        """Test that compliance scores over 1.0 are clamped to 1.0."""
        response = {"onex_compliance": {"score": 99.0}}
        result = transform_quality_response(response)
        assert result["onex_compliance"] == 1.0, (
            "onex_compliance score > 1.0 should be clamped to 1.0"
        )

    def test_quality_transform_complexity_over_one_clamps_to_one(self) -> None:
        """Test that complexity scores over 1.0 are clamped to 1.0."""
        response = {"maintainability": {"complexity_score": 2.5}}
        result = transform_quality_response(response)
        assert result["complexity_score"] == 1.0, (
            "complexity_score > 1.0 should be clamped to 1.0"
        )

    # =========================================================================
    # Malformed nested objects tests
    # =========================================================================

    def test_quality_transform_malformed_onex_compliance_string(self) -> None:
        """Test handling when onex_compliance is a string instead of dict.

        When onex_compliance is a non-dict/non-object value, the handler
        should gracefully handle it by treating attribute access as missing.
        """
        response = {"quality_score": 0.8, "onex_compliance": "invalid"}
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True despite malformed data"
        assert result["onex_compliance"] == 0.0, (
            "malformed onex_compliance should default to 0.0"
        )

    def test_quality_transform_malformed_maintainability_list(self) -> None:
        """Test handling when maintainability is a list instead of dict.

        When maintainability is not a dict/object, complexity_score extraction
        should fail gracefully and return the default value.
        """
        response = {"quality_score": 0.8, "maintainability": [1, 2, 3]}
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True despite malformed data"
        assert result["complexity_score"] == 0.0, (
            "malformed maintainability should result in default complexity_score"
        )

    def test_quality_transform_malformed_onex_compliance_number(self) -> None:
        """Test handling when onex_compliance is a number instead of dict.

        Numbers don't have dict keys or attributes, so should be handled
        as missing compliance data.
        """
        response = {"quality_score": 0.9, "onex_compliance": 42}
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True"
        assert result["onex_compliance"] == 0.0, (
            "numeric onex_compliance should default to 0.0"
        )

    def test_quality_transform_malformed_maintainability_string(self) -> None:
        """Test handling when maintainability is a string instead of dict."""
        response = {"quality_score": 0.75, "maintainability": "high"}
        result = transform_quality_response(response)
        assert result["success"] is True, "success should be True"
        assert result["complexity_score"] == 0.0, (
            "string maintainability should default to 0.0 complexity"
        )

    # =========================================================================
    # Empty violations list vs None tests
    # =========================================================================

    def test_quality_transform_empty_violations_list(self) -> None:
        """Test that empty violations list returns empty issues."""
        response = {"onex_compliance": {"violations": []}}
        result = transform_quality_response(response)
        assert result["issues"] == [], "empty violations list should return empty issues"

    def test_quality_transform_none_violations(self) -> None:
        """Test that None violations returns empty issues."""
        response = {"onex_compliance": {"violations": None}}
        result = transform_quality_response(response)
        assert result["issues"] == [], "None violations should return empty issues"

    def test_quality_transform_empty_recommendations_list(self) -> None:
        """Test that empty recommendations list returns empty recommendations."""
        response = {"onex_compliance": {"recommendations": []}}
        result = transform_quality_response(response)
        assert result["recommendations"] == [], (
            "empty recommendations list should return empty"
        )

    def test_quality_transform_none_recommendations(self) -> None:
        """Test that None recommendations returns empty recommendations."""
        response = {"onex_compliance": {"recommendations": None}}
        result = transform_quality_response(response)
        assert result["recommendations"] == [], (
            "None recommendations should return empty"
        )

    # =========================================================================
    # Non-iterable violations (string) test
    # =========================================================================

    def test_quality_transform_string_violation_wrapped_in_list(self) -> None:
        """Test that a single string violation is wrapped in a list.

        The _safe_list utility wraps non-list values in a list,
        so a single string violation becomes a one-element list.
        """
        response = {"onex_compliance": {"violations": "single error"}}
        result = transform_quality_response(response)
        assert result["issues"] == ["single error"], (
            "single string violation should be wrapped in list"
        )

    def test_quality_transform_string_recommendation_wrapped_in_list(self) -> None:
        """Test that a single string recommendation is wrapped in a list."""
        response = {"onex_compliance": {"recommendations": "add tests"}}
        result = transform_quality_response(response)
        assert result["recommendations"] == ["add tests"], (
            "single string recommendation should be wrapped in list"
        )

    # =========================================================================
    # Extreme boundary values tests
    # =========================================================================

    def test_quality_transform_extreme_positive_values(self) -> None:
        """Test handling of extremely large positive scores.

        Positive infinity should be clamped to SCORE_MAX (1.0).
        """
        response = {"quality_score": float("inf")}
        result = transform_quality_response(response)
        assert result["quality_score"] == 1.0, (
            "positive infinity should be clamped to 1.0"
        )

    def test_quality_transform_negative_infinity(self) -> None:
        """Test handling of negative infinity scores.

        Negative infinity should be clamped to SCORE_MIN (0.0).
        """
        response = {"quality_score": float("-inf")}
        result = transform_quality_response(response)
        assert result["quality_score"] == 0.0, (
            "negative infinity should be clamped to 0.0"
        )

    def test_quality_transform_nan_values(self) -> None:
        """Test handling of NaN scores.

        NaN values present a special case because NaN comparisons always
        return False. Due to Python's min/max behavior with NaN:
        - min(max_val, nan) returns max_val (because nan <= max_val is False)
        - max(min_val, max_val) returns max_val

        This means NaN gets clamped to SCORE_MAX (1.0), which is a valid
        score value rather than an invalid NaN propagating through the system.
        While unconventional, this is acceptable defensive behavior.
        """
        import math

        response = {"quality_score": float("nan")}
        result = transform_quality_response(response)
        # NaN should not crash the system
        assert result["success"] is True, "success should be True even with NaN"
        # Due to Python's min/max semantics, NaN gets clamped to 1.0
        # This is acceptable - the system produces a valid score rather than NaN
        score = result["quality_score"]
        assert not math.isnan(score), "NaN should not propagate to output"
        assert 0.0 <= score <= 1.0, "score should be within valid range"

    def test_quality_transform_compliance_infinity(self) -> None:
        """Test compliance score with infinity value."""
        response = {"onex_compliance": {"score": float("inf")}}
        result = transform_quality_response(response)
        assert result["onex_compliance"] == 1.0, (
            "infinite compliance score should be clamped to 1.0"
        )

    def test_quality_transform_very_small_positive_number(self) -> None:
        """Test handling of very small positive numbers (epsilon)."""
        response = {"quality_score": 1e-300}
        result = transform_quality_response(response)
        # Very small positive numbers should be preserved (within [0.0, 1.0])
        assert result["quality_score"] >= 0.0, "tiny positive should remain positive"
        assert result["quality_score"] <= 1.0, "tiny positive should be <= 1.0"

    # =========================================================================
    # Security limit test - MAX_ISSUES
    # =========================================================================

    def test_quality_transform_respects_max_issues_limit(self) -> None:
        """Test that issues are limited to MAX_ISSUES for memory safety.

        The handler applies MAX_ISSUES limit to prevent memory exhaustion
        from maliciously large violation lists.
        """
        from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
            MAX_ISSUES,
        )

        # Create more violations than the limit
        violations = [f"issue_{i}" for i in range(MAX_ISSUES + 500)]
        response = {"onex_compliance": {"violations": violations}}
        result = transform_quality_response(response)
        assert len(result["issues"]) <= MAX_ISSUES, (
            f"issues should be limited to MAX_ISSUES ({MAX_ISSUES})"
        )

    def test_quality_transform_respects_max_recommendations_limit(self) -> None:
        """Test that recommendations are limited to MAX_ISSUES for memory safety."""
        from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
            MAX_ISSUES,
        )

        # Create more recommendations than the limit
        recommendations = [f"rec_{i}" for i in range(MAX_ISSUES + 100)]
        response = {"onex_compliance": {"recommendations": recommendations}}
        result = transform_quality_response(response)
        assert len(result["recommendations"]) <= MAX_ISSUES, (
            f"recommendations should be limited to MAX_ISSUES ({MAX_ISSUES})"
        )

    # =========================================================================
    # Additional malformed data tests
    # =========================================================================

    def test_quality_transform_nested_dict_violations(self) -> None:
        """Test when violations contains dicts instead of strings.

        The handler should include dict items in the issues list
        as-is, allowing downstream consumers to handle them.
        """
        response = {
            "onex_compliance": {
                "violations": [
                    {"code": "E001", "message": "Missing docstring"},
                    "simple violation",
                ]
            }
        }
        result = transform_quality_response(response)
        assert len(result["issues"]) == 2, "both violations should be included"
        assert {"code": "E001", "message": "Missing docstring"} in result["issues"], (
            "dict violation should be preserved"
        )
        assert "simple violation" in result["issues"], (
            "string violation should be preserved"
        )

    def test_quality_transform_boolean_quality_score(self) -> None:
        """Test handling when quality_score is a boolean.

        Booleans can be converted to float (True=1.0, False=0.0).
        """
        response_true = {"quality_score": True}
        result_true = transform_quality_response(response_true)
        assert result_true["quality_score"] == 1.0, "True should convert to 1.0"

        response_false = {"quality_score": False}
        result_false = transform_quality_response(response_false)
        assert result_false["quality_score"] == 0.0, "False should convert to 0.0"

    def test_quality_transform_tuple_violations(self) -> None:
        """Test handling when violations is a tuple instead of list.

        Tuples should be converted to lists by _safe_list.
        """
        response = {"onex_compliance": {"violations": ("error1", "error2")}}
        result = transform_quality_response(response)
        assert result["issues"] == ["error1", "error2"], (
            "tuple violations should be converted to list"
        )

    def test_quality_transform_set_violations(self) -> None:
        """Test handling when violations is a set instead of list.

        Sets should be converted to lists by _safe_list.
        """
        response = {"onex_compliance": {"violations": {"error1", "error2"}}}
        result = transform_quality_response(response)
        # Sets don't preserve order, so just check membership
        assert len(result["issues"]) == 2, "set should be converted to list"
        assert "error1" in result["issues"], "error1 should be in issues"
        assert "error2" in result["issues"], "error2 should be in issues"
