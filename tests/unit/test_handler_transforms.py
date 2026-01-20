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
        assert result["success"] is True
        assert result["quality_score"] == 0.85
        assert result["onex_compliance"] == 0.9
        assert result["complexity_score"] == 0.7
        assert result["issues"] == ["violation1"]
        assert result["recommendations"] == ["rec1"]
        assert result["patterns"] == []
        assert result["result_data"]["architectural_era"] == "modern"
        assert result["result_data"]["temporal_relevance"] == 0.95

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing."""

        class MockResponse:
            quality_score = 0.75
            # Missing: onex_compliance, maintainability, architectural_era, temporal_relevance

        result = transform_quality_response(MockResponse())
        assert result["success"] is True
        assert result["quality_score"] == 0.75
        assert result["onex_compliance"] == 0.0
        assert result["complexity_score"] == 0.0
        assert result["issues"] == []
        assert result["recommendations"] == []
        assert result["result_data"]["architectural_era"] is None
        assert result["result_data"]["temporal_relevance"] is None

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
        assert result["success"] is True
        assert result["quality_score"] == 0.75
        assert result["onex_compliance"] == 0.0
        assert result["complexity_score"] == 0.0
        assert result["issues"] == []
        assert result["recommendations"] == []

    def test_missing_quality_score(self) -> None:
        """Test handling when quality_score is missing."""

        class MockResponse:
            pass  # No attributes

        result = transform_quality_response(MockResponse())
        assert result["success"] is True
        assert result["quality_score"] == 0.0  # Should default to 0.0
        assert result["onex_compliance"] == 0.0
        assert result["complexity_score"] == 0.0
        assert result["issues"] == []
        assert result["recommendations"] == []

    def test_partial_onex_compliance(self) -> None:
        """Test when onex_compliance has partial data."""

        class MockCompliance:
            score = 0.8
            # Missing: violations, recommendations

        class MockResponse:
            quality_score = 0.9
            onex_compliance = MockCompliance()

        result = transform_quality_response(MockResponse())
        assert result["success"] is True
        assert result["onex_compliance"] == 0.8
        assert result["issues"] == []  # No violations attribute
        assert result["recommendations"] == []  # No recommendations attribute


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
        assert result["success"] is True
        assert len(result["patterns"]) == 1
        assert result["patterns"][0] == {"name": "singleton", "confidence": 0.9}
        assert result["onex_compliance"] == 0.88
        assert "god_class: Class does too much" in result["issues"]
        assert result["recommendations"] == ["Use DI"]
        assert result["result_data"]["analysis_summary"] == "Good patterns"
        assert result["result_data"]["confidence_scores"] == {"overall": 0.85}

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing.

        The pattern handler uses hasattr checks, so missing attributes
        are handled gracefully with empty defaults.
        """

        class MockResponse:
            pass  # No attributes

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True
        assert result["patterns"] == []
        assert result["issues"] == []
        assert result["recommendations"] == []
        assert result["onex_compliance"] == 0.0
        assert result["result_data"]["analysis_summary"] == ""
        assert result["result_data"]["confidence_scores"] == {}

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
        assert result["success"] is True
        assert result["patterns"] == []
        assert result["issues"] == []
        assert result["recommendations"] == []
        assert result["onex_compliance"] == 0.0

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
        assert result["success"] is True
        assert len(result["patterns"]) == 2
        assert len(result["issues"]) == 2
        assert "spaghetti_code: Complex control flow" in result["issues"]
        assert "magic_numbers: Unexplained constants" in result["issues"]
        assert len(result["recommendations"]) == 2

    def test_anti_pattern_missing_attributes(self) -> None:
        """Test anti-pattern handling when attributes are missing."""

        class MockAntiPatternIncomplete:
            pattern_type = "some_type"
            # Missing: description

        class MockResponse:
            detected_patterns = []
            anti_patterns = [MockAntiPatternIncomplete()]

        result = transform_pattern_response(MockResponse())
        assert result["success"] is True
        # Incomplete anti-pattern should not be added to issues
        assert result["issues"] == []


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
        assert result["success"] is True
        assert result["complexity_score"] == 0.7
        assert "Cache results: Add caching" in result["recommendations"]
        assert result["result_data"]["baseline_metrics"] == {
            "complexity_estimate": 0.7,
            "lines_of_code": 500,
        }
        assert result["result_data"]["total_opportunities"] == 1
        assert result["result_data"]["estimated_improvement"] == 0.25

    def test_missing_optional_attributes(self) -> None:
        """Test graceful handling when optional attributes are missing.

        The performance handler uses hasattr checks, so missing attributes
        are handled gracefully with defaults.
        """

        class MockResponse:
            pass  # No attributes

        result = transform_performance_response(MockResponse())
        assert result["success"] is True
        assert result["complexity_score"] == 0.0
        assert result["recommendations"] == []
        assert result["result_data"]["baseline_metrics"] == {}
        assert result["result_data"]["optimization_opportunities"] == []
        assert result["result_data"]["total_opportunities"] == 0
        assert result["result_data"]["estimated_improvement"] == 0.0

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
        assert result["success"] is True
        assert result["complexity_score"] == 0.5
        assert result["recommendations"] == []
        assert result["result_data"]["optimization_opportunities"] == []

    def test_baseline_metrics_none(self) -> None:
        """Test when baseline_metrics is None but attribute exists."""

        class MockResponse:
            baseline_metrics = None
            optimization_opportunities = []
            total_opportunities = 0
            estimated_total_improvement = 0.0

        result = transform_performance_response(MockResponse())
        assert result["success"] is True
        assert result["complexity_score"] == 0.0  # Default when None
        assert result["result_data"]["baseline_metrics"] == {}

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
        assert result["success"] is True
        assert len(result["recommendations"]) == 2
        assert "Enable caching: Add Redis caching layer" in result["recommendations"]
        assert (
            "Database indexing: Add index on user_id column" in result["recommendations"]
        )
        assert len(result["result_data"]["optimization_opportunities"]) == 2
        assert result["result_data"]["total_opportunities"] == 2
        assert result["result_data"]["estimated_improvement"] == 0.45

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
        assert result["success"] is True
        # Incomplete opportunity should not be added to recommendations
        assert result["recommendations"] == []
        # But it should still be in result_data
        assert len(result["result_data"]["optimization_opportunities"]) == 1
