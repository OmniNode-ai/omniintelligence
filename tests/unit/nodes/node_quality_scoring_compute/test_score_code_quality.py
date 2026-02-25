# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the main score_code_quality function.

This module tests the core scoring interface including:
    - Valid code scoring
    - ONEX compliance
    - Custom weights
    - Error handling
    - Result structure validation
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    ANALYSIS_VERSION,
    score_code_quality,
)


class TestScoreCodeQuality:
    """Tests for the main score_code_quality function."""

    def test_scores_valid_python_code(self) -> None:
        """Test scoring well-formed Python code returns complete result."""
        code = '''
class ModelExample(BaseModel):
    """A well-documented model."""
    name: str = Field(..., description="Name field")
    value: int = Field(default=0)

    model_config = {"frozen": True, "extra": "forbid"}
'''
        result = score_code_quality(code, "python")

        assert result["success"] is True
        assert 0.0 <= result["quality_score"] <= 1.0
        assert "complexity" in result["dimensions"]
        assert "maintainability" in result["dimensions"]
        assert "documentation" in result["dimensions"]
        assert "temporal_relevance" in result["dimensions"]
        assert "patterns" in result["dimensions"]
        assert "architectural" in result["dimensions"]
        assert result["source_language"] == "python"
        assert result["analysis_version"] == str(ANALYSIS_VERSION)

    def test_high_score_for_onex_compliant_code(self) -> None:
        """ONEX-compliant code should score well on patterns dimension."""
        onex_code = '''
from typing import TypedDict, ClassVar, Final
from pydantic import BaseModel, Field, field_validator

class ResponseProtocol(TypedDict):
    """Protocol for response structure."""
    success: bool
    data: dict[str, str]

class ModelConfig(BaseModel):
    """Frozen ONEX-compliant model."""
    value: str = Field(..., min_length=1)

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Validate and normalize value."""
        return v.strip()
'''
        result = score_code_quality(onex_code, "python")

        assert result["dimensions"]["patterns"] >= 0.7
        # High quality code should be ONEX compliant with default threshold
        assert result["quality_score"] >= 0.6

    def test_low_score_for_antipatterns(self) -> None:
        """Code with ONEX antipatterns should score lower on patterns."""
        bad_code = """
def process(data, **kwargs):
    result = {}
    for k, v in data.items():
        result[k] = v
    return result
"""
        result = score_code_quality(bad_code, "python")

        # Untyped functions with mutable defaults and **kwargs
        assert result["dimensions"]["patterns"] < 0.7
        # Anti-patterns should lower patterns score (replaces old type_coverage check)
        assert result["dimensions"]["documentation"] < 0.7

    def test_custom_weights_affect_score(self) -> None:
        """Test that custom weights affect the final score."""
        code = "def hello(): pass"

        # Weight heavily on documentation (which this lacks)
        doc_weights = {
            "complexity": 0.05,
            "maintainability": 0.05,
            "documentation": 0.70,
            "temporal_relevance": 0.05,
            "patterns": 0.05,
            "architectural": 0.10,
        }
        result_doc = score_code_quality(code, "python", weights=doc_weights)

        # Weight heavily on complexity (simple code should score well)
        complexity_weights = {
            "complexity": 0.70,
            "maintainability": 0.05,
            "documentation": 0.05,
            "temporal_relevance": 0.05,
            "patterns": 0.05,
            "architectural": 0.10,
        }
        result_complexity = score_code_quality(
            code, "python", weights=complexity_weights
        )

        # Complexity-weighted should be higher than doc-weighted for this simple code
        assert result_complexity["quality_score"] > result_doc["quality_score"]

    def test_onex_threshold_affects_compliance(self) -> None:
        """Test ONEX compliance threshold determination."""
        medium_code = '''
class Example:
    """Example class with basic structure."""
    def __init__(self, value: str) -> None:
        self.value = value
'''
        # Low threshold - should pass
        result_low = score_code_quality(medium_code, "python", onex_threshold=0.3)

        # High threshold - should fail
        result_high = score_code_quality(medium_code, "python", onex_threshold=0.95)

        # Same dimension scores for both
        assert (
            result_low["dimensions"]["patterns"]
            == result_high["dimensions"]["patterns"]
        )

        # Compliance is determined by: score >= threshold
        # With threshold 0.3, compliance should match score >= 0.3
        assert result_low["onex_compliant"] == (result_low["quality_score"] >= 0.3)
        # With threshold 0.95, compliance should match score >= 0.95
        assert result_high["onex_compliant"] == (result_high["quality_score"] >= 0.95)

    def test_handles_syntax_error_gracefully(self) -> None:
        """Malformed Python should not crash, returns low baseline scores."""
        bad_syntax = "def broken( class while:"

        result = score_code_quality(bad_syntax, "python")

        assert result["success"] is True  # Does not crash
        assert result["quality_score"] >= 0.0
        assert result["onex_compliant"] is False
        # Syntax error code gets baseline low scores (0.3) for all dimensions
        # that depend on AST parsing
        assert result["quality_score"] <= 0.5

    def test_unsupported_language_baseline_scores(self) -> None:
        """Unsupported languages should return baseline scores."""
        code = 'fn main() { println!("Hello"); }'

        result = score_code_quality(code, "rust")

        assert result["success"] is True
        assert result["source_language"] == "rust"
        assert result["quality_score"] == 0.5  # Baseline
        # All dimensions should be baseline
        for dim_score in result["dimensions"].values():
            assert dim_score == 0.5
        # Should have unsupported language recommendation
        assert any("unsupported" in r.lower() for r in result["recommendations"])

    def test_empty_content_returns_validation_error(self) -> None:
        """Empty or whitespace content should return structured error.

        Per CLAUDE.md handler pattern, validation errors are domain errors
        returned as structured output with success=False, not raised.
        """
        result = score_code_quality("", "python")
        assert result["success"] is False
        assert result["quality_score"] == 0.0
        assert any("empty" in r.lower() for r in result["recommendations"])
        assert any("validation_error" in r.lower() for r in result["recommendations"])

        result_whitespace = score_code_quality("   \n\t  ", "python")
        assert result_whitespace["success"] is False
        assert any("empty" in r.lower() for r in result_whitespace["recommendations"])

    def test_returns_typed_dict_structure(self) -> None:
        """Result should match QualityScoringResult TypedDict structure."""
        result = score_code_quality("x = 1", "python")

        # Verify all required keys present
        required_keys = {
            "success",
            "quality_score",
            "dimensions",
            "onex_compliant",
            "recommendations",
            "source_language",
            "analysis_version",
        }
        assert required_keys.issubset(set(result.keys())), (
            f"Missing required keys: {required_keys - set(result.keys())}"
        )
        # radon_complexity_enabled is an optional key added in OMN-1452
        allowed_optional_keys = {"radon_complexity_enabled"}
        unexpected_keys = set(result.keys()) - required_keys - allowed_optional_keys
        assert not unexpected_keys, f"Unexpected keys in result: {unexpected_keys}"

    def test_scores_are_bounded(self) -> None:
        """All scores should be in valid range [0.0, 1.0]."""
        test_cases = [
            "x = 1",
            "def foo(): pass",
            """
class Large:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
""",
        ]

        for code in test_cases:
            result = score_code_quality(code, "python")

            assert 0.0 <= result["quality_score"] <= 1.0
            for dim, score in result["dimensions"].items():
                assert 0.0 <= score <= 1.0, f"Dimension {dim} out of bounds: {score}"
