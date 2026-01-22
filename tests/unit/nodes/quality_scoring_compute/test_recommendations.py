# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for recommendation generation.

This module tests the recommendation generation system:
    - Low score recommendations
    - Recommendation format and structure
    - Language-specific recommendations
    - Quality correlation
"""

from __future__ import annotations

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    score_code_quality,
)


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_generates_recommendations_for_low_scores(self) -> None:
        """Low dimension scores should generate relevant recommendations."""
        # Code lacking documentation
        no_docs = "def f(x): return x * 2"

        result = score_code_quality(no_docs, "python")

        assert len(result["recommendations"]) > 0

    def test_recommendations_are_strings(self) -> None:
        """All recommendations should be strings."""
        code = "x = 1"
        result = score_code_quality(code, "python")

        assert all(isinstance(r, str) for r in result["recommendations"])

    def test_recommendations_include_dimension_tags(self) -> None:
        """Recommendations should include dimension tags in brackets."""
        code = "def f(x): return x"  # Missing types, docs, patterns
        result = score_code_quality(code, "python")

        # Should have recommendations with dimension tags
        for rec in result["recommendations"]:
            # Each recommendation should start with [dimension_name]
            assert rec.startswith("[") and "]" in rec

    def test_syntax_error_produces_low_scores(self) -> None:
        """Syntax errors should produce low baseline scores due to AST parse failures."""
        bad_code = "def broken(:"
        result = score_code_quality(bad_code, "python")

        # Syntax error code gets baseline low scores for dimensions using AST
        # Each dimension that fails to parse returns 0.3
        assert result["success"] is True
        assert result["quality_score"] <= 0.5
        # Should have recommendations due to low scores
        assert len(result["recommendations"]) > 0

    def test_unsupported_language_recommendation(self) -> None:
        """Unsupported languages should produce unsupported_language recommendation."""
        result = score_code_quality("let x = 5;", "javascript")

        assert any("[unsupported_language]" in r for r in result["recommendations"])

    def test_high_quality_code_fewer_recommendations(self) -> None:
        """High quality code should have fewer recommendations."""
        high_quality = '''
"""Module for data processing."""
from typing import TypedDict, Final
from pydantic import BaseModel, Field

CONSTANT: Final[int] = 100

class DataInput(TypedDict):
    """Input data structure."""
    value: int
    name: str

class DataProcessor(BaseModel):
    """Processes data following ONEX patterns."""
    multiplier: int = Field(default=1, ge=1)

    model_config = {"frozen": True, "extra": "forbid"}

    def process(self, data: DataInput) -> int:
        """Process the input data.

        Args:
            data: Input data to process.

        Returns:
            Processed integer result.
        """
        return data["value"] * self.multiplier
'''
        low_quality = "def f(x, **kwargs): return x"

        result_high = score_code_quality(high_quality, "python")
        result_low = score_code_quality(low_quality, "python")

        assert len(result_high["recommendations"]) <= len(result_low["recommendations"])
