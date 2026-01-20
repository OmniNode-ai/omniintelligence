"""Unit tests for intelligence adapter transform handlers.

These tests verify the transformation logic for converting raw intelligence
service responses into canonical formats suitable for event publishing.

Coverage:
- Normal case with complete response data
- Fail-fast validation: missing required fields raise HandlerValidationError
- Score clamping for out-of-range values
- Security limits on collection sizes
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
from omniintelligence.nodes.intelligence_adapter.handlers.utils import (
    HandlerValidationError,
    MAX_ISSUES,
)


class TestTransformQualityResponse:
    """Tests for transform_quality_response handler with fail-fast validation.

    The quality handler now requires all fields to be present and valid.
    Missing required fields raise HandlerValidationError immediately.
    """

    def test_complete_response_object(self) -> None:
        """Test normal case with complete response as object."""

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
        assert result["success"] is True
        assert result["quality_score"] == 0.85
        assert result["onex_compliance"] == 0.9
        assert result["complexity_score"] == 0.7
        assert result["issues"] == ["violation1"]
        assert result["recommendations"] == ["rec1"]
        assert result["patterns"] == []
        assert result["result_data"]["architectural_era"] == "modern"
        assert result["result_data"]["temporal_relevance"] == 0.95

    def test_complete_response_dict(self) -> None:
        """Test normal case with complete response as dict."""
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
        assert result["success"] is True
        assert result["quality_score"] == 0.82
        assert result["onex_compliance"] == 0.88
        assert result["complexity_score"] == 0.65
        assert result["issues"] == ["missing docstring"]
        assert result["recommendations"] == ["add docstrings"]
        assert result["result_data"]["architectural_era"] == "modern"
        assert result["result_data"]["temporal_relevance"] == 0.9

    def test_empty_violations_and_recommendations(self) -> None:
        """Test with empty lists for violations and recommendations."""
        response = {
            "quality_score": 0.95,
            "onex_compliance": {
                "score": 1.0,
                "violations": [],
                "recommendations": [],
            },
            "maintainability": {"complexity_score": 0.8},
        }
        result = transform_quality_response(response)
        assert result["success"] is True
        assert result["issues"] == []
        assert result["recommendations"] == []

    def test_optional_fields_missing(self) -> None:
        """Test that optional fields (architectural_era, temporal_relevance) can be missing."""
        response = {
            "quality_score": 0.75,
            "onex_compliance": {
                "score": 0.8,
                "violations": [],
                "recommendations": [],
            },
            "maintainability": {"complexity_score": 0.6},
            # architectural_era and temporal_relevance are optional
        }
        result = transform_quality_response(response)
        assert result["success"] is True
        assert result["result_data"]["architectural_era"] is None
        assert result["result_data"]["temporal_relevance"] is None

    # =========================================================================
    # Fail-fast validation tests - missing required fields raise exceptions
    # =========================================================================

    def test_none_response_raises(self) -> None:
        """Test that None response raises HandlerValidationError."""
        with pytest.raises(HandlerValidationError, match="Response is None"):
            transform_quality_response(None)

    def test_missing_quality_score_raises(self) -> None:
        """Test that missing quality_score raises HandlerValidationError."""
        response = {
            "onex_compliance": {"score": 0.8, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="quality_score.*missing"):
            transform_quality_response(response)

    def test_none_quality_score_raises(self) -> None:
        """Test that None quality_score raises HandlerValidationError."""
        response = {
            "quality_score": None,
            "onex_compliance": {"score": 0.8, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="quality_score.*None"):
            transform_quality_response(response)

    def test_missing_onex_compliance_raises(self) -> None:
        """Test that missing onex_compliance raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="onex_compliance.*missing"):
            transform_quality_response(response)

    def test_none_onex_compliance_raises(self) -> None:
        """Test that None onex_compliance raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": None,
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="onex_compliance.*None"):
            transform_quality_response(response)

    def test_missing_onex_compliance_score_raises(self) -> None:
        """Test that missing onex_compliance.score raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="onex_compliance.score.*missing"):
            transform_quality_response(response)

    def test_missing_violations_raises(self) -> None:
        """Test that missing violations raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="violations.*missing"):
            transform_quality_response(response)

    def test_none_violations_raises(self) -> None:
        """Test that None violations raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "violations": None, "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="violations.*None"):
            transform_quality_response(response)

    def test_missing_recommendations_raises(self) -> None:
        """Test that missing recommendations raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "violations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="recommendations.*missing"):
            transform_quality_response(response)

    def test_missing_maintainability_raises(self) -> None:
        """Test that missing maintainability raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
        }
        with pytest.raises(HandlerValidationError, match="maintainability.*missing"):
            transform_quality_response(response)

    def test_missing_complexity_score_raises(self) -> None:
        """Test that missing complexity_score raises HandlerValidationError."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
            "maintainability": {},
        }
        with pytest.raises(HandlerValidationError, match="complexity_score.*missing"):
            transform_quality_response(response)

    def test_invalid_quality_score_type_raises(self) -> None:
        """Test that non-numeric quality_score raises HandlerValidationError."""
        response = {
            "quality_score": "not_a_number",
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        with pytest.raises(HandlerValidationError, match="quality_score.*must be numeric"):
            transform_quality_response(response)

    # =========================================================================
    # Score clamping tests - valid numeric values are clamped to [0.0, 1.0]
    # =========================================================================

    def test_quality_score_clamped_high(self) -> None:
        """Test that quality_score > 1.0 is clamped to 1.0."""
        response = {
            "quality_score": 1.5,
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert result["quality_score"] == 1.0

    def test_quality_score_clamped_low(self) -> None:
        """Test that quality_score < 0.0 is clamped to 0.0."""
        response = {
            "quality_score": -0.5,
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert result["quality_score"] == 0.0

    def test_compliance_score_clamped_high(self) -> None:
        """Test that compliance score > 1.0 is clamped to 1.0."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 99.0, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert result["onex_compliance"] == 1.0

    def test_complexity_score_clamped_low(self) -> None:
        """Test that complexity score < 0.0 is clamped to 0.0."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {"score": 0.9, "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": -10.0},
        }
        result = transform_quality_response(response)
        assert result["complexity_score"] == 0.0

    def test_string_score_coercion(self) -> None:
        """Test that numeric string scores are converted to floats."""
        response = {
            "quality_score": "0.75",
            "onex_compliance": {"score": "0.9", "violations": [], "recommendations": []},
            "maintainability": {"complexity_score": "0.6"},
        }
        result = transform_quality_response(response)
        assert result["quality_score"] == 0.75
        assert result["onex_compliance"] == 0.9
        assert result["complexity_score"] == 0.6

    # =========================================================================
    # Security and list handling tests
    # =========================================================================

    def test_single_violation_wrapped_in_list(self) -> None:
        """Test that a single violation string is wrapped in a list."""
        response = {
            "quality_score": 0.8,
            "onex_compliance": {
                "score": 0.9,
                "violations": "single violation",
                "recommendations": "single rec",
            },
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert result["issues"] == ["single violation"]
        assert result["recommendations"] == ["single rec"]

    def test_max_issues_limit(self) -> None:
        """Test that issues are limited to MAX_ISSUES for security."""
        huge_violations = [f"violation_{i}" for i in range(MAX_ISSUES + 500)]
        response = {
            "quality_score": 0.8,
            "onex_compliance": {
                "score": 0.9,
                "violations": huge_violations,
                "recommendations": [],
            },
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert len(result["issues"]) == MAX_ISSUES

    def test_max_recommendations_limit(self) -> None:
        """Test that recommendations are limited to MAX_ISSUES for security."""
        huge_recs = [f"rec_{i}" for i in range(MAX_ISSUES + 500)]
        response = {
            "quality_score": 0.8,
            "onex_compliance": {
                "score": 0.9,
                "violations": [],
                "recommendations": huge_recs,
            },
            "maintainability": {"complexity_score": 0.7},
        }
        result = transform_quality_response(response)
        assert len(result["recommendations"]) == MAX_ISSUES


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

        Strings are iterable, so without special handling list() would break them
        into characters. The handler detects single strings and wraps them in a list.
        """

        class MockResponse:
            detected_patterns = []
            anti_patterns = []
            recommendations = "single recommendation"  # String, not list
            architectural_compliance = None

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True, "success should be True"
        # Handler detects single string and wraps it in a list (not split into chars)
        assert result["recommendations"] == ["single recommendation"], (
            "single string recommendation should be wrapped in a list"
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
