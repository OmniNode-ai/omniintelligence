"""
Unit Tests for Pattern Quality Scorer

Tests all scoring components:
- Complexity scoring (cyclomatic complexity)
- Documentation scoring (docstrings, type hints)
- Test coverage scoring
- Reusability scoring (cross-file usage)
- Maintainability scoring (coupling, cohesion)
"""

import sys
from pathlib import Path

import pytest

# Add src directory to path for direct import
src_path = Path(__file__).parent.parent.parent.parent / "src"

# Import directly from file to avoid services package circular dependencies
import importlib.util

pattern_scorer_path = src_path / "archon_services" / "quality" / "pattern_scorer.py"
spec = importlib.util.spec_from_file_location("pattern_scorer", pattern_scorer_path)
pattern_scorer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern_scorer_module)
PatternScorer = pattern_scorer_module.PatternScorer


class TestPatternScorer:
    """Test suite for PatternScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a basic scorer instance."""
        return PatternScorer()

    @pytest.fixture
    def scorer_with_coverage(self):
        """Create a scorer with coverage data."""
        coverage_data = {
            "/path/to/file.py": {
                "covered_lines": [1, 2, 3, 4, 5],
                "total_lines": 10,
            },
            "/path/to/full_coverage.py": {
                "covered_lines": list(range(1, 21)),
                "total_lines": 20,
            },
        }
        return PatternScorer(coverage_data=coverage_data)

    # ======================================================================
    # Complexity Scoring Tests
    # ======================================================================

    def test_complexity_score_simple_function(self, scorer):
        """Test complexity score for simple function (CC < 10)."""
        code = """
def simple_function(x):
    return x + 1
"""
        score = scorer.calculate_complexity_score(code)
        assert score == 1.0, "Simple function should have perfect complexity score"

    def test_complexity_score_moderate_function(self, scorer):
        """Test complexity score for moderate complexity function (CC 10-20)."""
        code = """
def moderate_function(x):
    if x > 0:
        if x < 10:
            if x % 2 == 0:
                if x > 5:
                    if x < 8:
                        if x == 6:
                            if True:
                                if False:
                                    if x:
                                        return x
    return 0
"""
        score = scorer.calculate_complexity_score(code)
        assert score == 0.7, "Moderate complexity function should score 0.7"

    def test_complexity_score_complex_function(self, scorer):
        """Test complexity score for complex function (CC > 20)."""
        # Create a truly complex function with many branches
        code = """
def complex_function(x):
    result = 0
    if x > 0:
        result += 1
    if x > 1:
        result += 1
    if x > 2:
        result += 1
    if x > 3:
        result += 1
    if x > 4:
        result += 1
    if x > 5:
        result += 1
    if x > 6:
        result += 1
    if x > 7:
        result += 1
    if x > 8:
        result += 1
    if x > 9:
        result += 1
    if x > 10:
        result += 1
    if x > 11:
        result += 1
    if x > 12:
        result += 1
    if x > 13:
        result += 1
    if x > 14:
        result += 1
    if x > 15:
        result += 1
    if x > 16:
        result += 1
    if x > 17:
        result += 1
    if x > 18:
        result += 1
    if x > 19:
        result += 1
    if x > 20:
        result += 1
    return result
"""
        score = scorer.calculate_complexity_score(code)
        assert score == 0.4, f"Complex function (CC > 20) should score 0.4, got {score}"

    def test_complexity_score_empty_code(self, scorer):
        """Test complexity score for empty code."""
        code = ""
        score = scorer.calculate_complexity_score(code)
        assert score == 1.0, "Empty code should have perfect score"

    # ======================================================================
    # Documentation Scoring Tests
    # ======================================================================

    def test_documentation_score_full(self, scorer):
        """Test documentation score with both docstring and type hints."""
        code = """
def documented_function(x: int) -> int:
    \"\"\"This function is well documented.\"\"\"
    return x + 1
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_documentation_score(tree)
        assert score == 1.0, "Fully documented function should score 1.0"

    def test_documentation_score_docstring_only(self, scorer):
        """Test documentation score with only docstring."""
        code = """
def function_with_docstring(x):
    \"\"\"This function has a docstring.\"\"\"
    return x + 1
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_documentation_score(tree)
        assert score == 0.5, "Function with only docstring should score 0.5"

    def test_documentation_score_type_hints_only(self, scorer):
        """Test documentation score with only type hints."""
        code = """
def function_with_types(x: int) -> int:
    return x + 1
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_documentation_score(tree)
        assert score == 0.5, "Function with only type hints should score 0.5"

    def test_documentation_score_none(self, scorer):
        """Test documentation score with no documentation."""
        code = """
def undocumented_function(x):
    return x + 1
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_documentation_score(tree)
        assert score == 0.0, "Undocumented function should score 0.0"

    def test_documentation_score_class_docstring(self, scorer):
        """Test documentation score with class docstring."""
        code = """
class DocumentedClass:
    \"\"\"This class is documented.\"\"\"
    pass
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_documentation_score(tree)
        assert score >= 0.5, "Class with docstring should score at least 0.5"

    # ======================================================================
    # Test Coverage Scoring Tests
    # ======================================================================

    def test_coverage_score_with_data(self, scorer_with_coverage):
        """Test coverage score with actual coverage data."""
        score = scorer_with_coverage.calculate_test_coverage_score("/path/to/file.py")
        assert score == 0.5, "50% coverage should score 0.5"

    def test_coverage_score_full_coverage(self, scorer_with_coverage):
        """Test coverage score with 100% coverage."""
        score = scorer_with_coverage.calculate_test_coverage_score(
            "/path/to/full_coverage.py"
        )
        assert score == 1.0, "100% coverage should score 1.0"

    def test_coverage_score_no_data(self, scorer):
        """Test coverage score without coverage data."""
        score = scorer.calculate_test_coverage_score("/path/to/unknown.py")
        assert score == 0.5, "No coverage data should return neutral score 0.5"

    def test_coverage_score_no_file_path(self, scorer_with_coverage):
        """Test coverage score without file path."""
        score = scorer_with_coverage.calculate_test_coverage_score(None)
        assert score == 0.5, "No file path should return neutral score 0.5"

    # ======================================================================
    # Reusability Scoring Tests
    # ======================================================================

    def test_reusability_score_single_file(self, scorer):
        """Test reusability score for single file usage."""
        score = scorer.calculate_reusability_score(1)
        assert score == 0.3, "Single file usage should score 0.3"

    def test_reusability_score_medium_usage(self, scorer):
        """Test reusability score for medium usage (2-5 files)."""
        score = scorer.calculate_reusability_score(3)
        assert score == 0.6, "Medium usage (3 files) should score 0.6"

    def test_reusability_score_high_usage(self, scorer):
        """Test reusability score for high usage (5+ files)."""
        score = scorer.calculate_reusability_score(10)
        assert score == 1.0, "High usage (10 files) should score 1.0"

    def test_reusability_score_edge_case_two_files(self, scorer):
        """Test reusability score edge case for exactly 2 files."""
        score = scorer.calculate_reusability_score(2)
        assert score == 0.6, "Exactly 2 files should score 0.6"

    def test_reusability_score_edge_case_five_files(self, scorer):
        """Test reusability score edge case for exactly 5 files."""
        score = scorer.calculate_reusability_score(5)
        assert score == 1.0, "Exactly 5 files should score 1.0"

    # ======================================================================
    # Maintainability Scoring Tests
    # ======================================================================

    def test_maintainability_score_low_coupling(self, scorer):
        """Test maintainability score with low coupling."""
        code = """
def simple_function():
    return 42
"""
        import ast

        tree = ast.parse(code)
        score = scorer.calculate_maintainability_score(tree, code)
        assert score >= 0.5, "Low coupling should score at least 0.5"

    def test_maintainability_score_high_coupling(self, scorer):
        """Test maintainability score with high coupling."""
        code = """
import os
import sys
import json
import ast
import re
import pathlib
import typing
import collections
import itertools
import functools
import datetime

def coupled_function():
    return 42
"""
        import ast as ast_module

        tree = ast_module.parse(code)
        score = scorer.calculate_maintainability_score(tree, code)
        assert score < 1.0, "High coupling should score less than 1.0"

    # ======================================================================
    # Overall Quality Score Tests
    # ======================================================================

    def test_overall_quality_perfect_pattern(self, scorer_with_coverage):
        """Test overall quality score for a perfect pattern."""
        code = """
def well_crafted_function(x: int) -> int:
    \"\"\"A well-crafted function with low complexity.\"\"\"
    return x + 1
"""
        result = scorer_with_coverage.calculate_overall_quality(
            code=code,
            file_path="/path/to/full_coverage.py",
            usage_count=10,
        )

        assert "quality_score" in result
        assert "components" in result
        assert "weights" in result
        assert result["reproducible"] is True

        # Check score is reasonable
        assert (
            0.7 <= result["quality_score"] <= 1.0
        ), "Perfect pattern should score high"

        # Check all components are present
        assert "complexity" in result["components"]
        assert "documentation" in result["components"]
        assert "test_coverage" in result["components"]
        assert "reusability" in result["components"]
        assert "maintainability" in result["components"]

    def test_overall_quality_poor_pattern(self, scorer):
        """Test overall quality score for a poor pattern."""
        code = """
def bad_function(x):
    if x > 0:
        for i in range(x):
            if i > 0:
                for j in range(i):
                    if j > 0:
                        for k in range(j):
                            if k > 0:
                                for l in range(k):
                                    if l > 0:
                                        return l
    return 0
"""
        result = scorer.calculate_overall_quality(
            code=code,
            file_path=None,
            usage_count=1,
        )

        assert result["quality_score"] < 0.6, "Poor pattern should score low"

    def test_overall_quality_syntax_error(self, scorer):
        """Test overall quality score with syntax error."""
        code = "def broken_function(x"  # Syntax error - missing closing paren

        result = scorer.calculate_overall_quality(code=code)

        assert result["quality_score"] == 0.0, "Syntax error should score 0.0"
        assert "error" in result["details"]

    def test_overall_quality_weights_sum_to_one(self, scorer):
        """Test that scoring weights sum to 1.0."""
        weights = scorer.WEIGHTS
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.001, "Weights should sum to 1.0"

    def test_overall_quality_reproducibility(self, scorer):
        """Test that quality scores are reproducible."""
        code = """
def test_function(x: int) -> int:
    \"\"\"Test function.\"\"\"
    return x + 1
"""
        result1 = scorer.calculate_overall_quality(code=code, usage_count=3)
        result2 = scorer.calculate_overall_quality(code=code, usage_count=3)

        assert (
            result1["quality_score"] == result2["quality_score"]
        ), "Same input should produce same score"

    # ======================================================================
    # Batch Calculation Tests
    # ======================================================================

    def test_batch_calculate_quality(self, scorer):
        """Test batch quality calculation for multiple patterns."""
        patterns = [
            {
                "id": "pattern1",
                "name": "Simple Pattern",
                "code": "def simple(): return 42",
                "file_path": None,
                "usage_count": 1,
            },
            {
                "id": "pattern2",
                "name": "Complex Pattern",
                "code": '''
def complex(x: int) -> int:
    """Complex function."""
    return x + 1
''',
                "file_path": None,
                "usage_count": 5,
            },
        ]

        results = scorer.batch_calculate_quality(patterns)

        assert len(results) == 2, "Should return results for all patterns"
        assert results[0]["pattern_id"] == "pattern1"
        assert results[1]["pattern_id"] == "pattern2"
        assert "quality_score" in results[0]
        assert "quality_score" in results[1]

    def test_batch_calculate_quality_empty_list(self, scorer):
        """Test batch calculation with empty pattern list."""
        results = scorer.batch_calculate_quality([])
        assert results == [], "Empty input should return empty list"

    # ======================================================================
    # Edge Cases and Error Handling
    # ======================================================================

    def test_complexity_score_with_invalid_code(self, scorer):
        """Test complexity score gracefully handles invalid code."""
        code = "def broken("  # Syntax error
        # Should not raise exception - returns neutral score
        score = scorer.calculate_complexity_score(code)
        assert 0.0 <= score <= 1.0, "Invalid code should return score in valid range"

    def test_maintainability_score_empty_code(self, scorer):
        """Test maintainability score with empty code."""
        code = ""
        import ast

        try:
            tree = ast.parse(code)
            score = scorer.calculate_maintainability_score(tree, code)
            assert 0.0 <= score <= 1.0, "Empty code should return score in valid range"
        except SyntaxError:
            pass  # Expected for truly empty code

    def test_score_ranges(self, scorer):
        """Test that all scores are within valid range [0.0, 1.0]."""
        code = """
def test_function(x: int) -> int:
    \"\"\"Test function.\"\"\"
    if x > 0:
        return x
    return 0
"""
        import ast

        tree = ast.parse(code)

        # Test all scoring methods
        complexity = scorer.calculate_complexity_score(code)
        documentation = scorer.calculate_documentation_score(tree)
        coverage = scorer.calculate_test_coverage_score(None)
        reusability = scorer.calculate_reusability_score(3)
        maintainability = scorer.calculate_maintainability_score(tree, code)

        assert 0.0 <= complexity <= 1.0
        assert 0.0 <= documentation <= 1.0
        assert 0.0 <= coverage <= 1.0
        assert 0.0 <= reusability <= 1.0
        assert 0.0 <= maintainability <= 1.0


class TestPatternScorerIntegration:
    """Integration tests for PatternScorer with realistic patterns."""

    @pytest.fixture
    def scorer_with_full_coverage(self):
        """Create scorer with comprehensive coverage data."""
        coverage_data = {
            "/app/services/quality/pattern_scorer.py": {
                "covered_lines": list(range(1, 401)),  # Full coverage
                "total_lines": 400,
            },
        }
        return PatternScorer(coverage_data=coverage_data)

    def test_realistic_onex_pattern(self, scorer_with_full_coverage):
        """Test scoring a realistic ONEX pattern."""
        code = """
from typing import Dict, Any
from pydantic import BaseModel


class ModelPatternResult(BaseModel):
    \"\"\"Result model for pattern analysis.\"\"\"
    pattern_id: str
    quality_score: float
    metadata: Dict[str, Any]


class NodePatternAnalyzerEffect:
    \"\"\"ONEX Effect node for pattern quality analysis.\"\"\"

    def __init__(self, registry):
        \"\"\"Initialize with dependency injection.\"\"\"
        self.registry = registry

    async def execute_effect(self, contract) -> ModelPatternResult:
        \"\"\"Execute pattern quality analysis.\"\"\"
        pattern_id = contract.pattern_id
        quality_score = await self._calculate_quality(pattern_id)

        return ModelPatternResult(
            pattern_id=pattern_id,
            quality_score=quality_score,
            metadata={"status": "completed"}
        )

    async def _calculate_quality(self, pattern_id: str) -> float:
        \"\"\"Calculate quality score for pattern.\"\"\"
        # Simple calculation
        return 0.85
"""

        result = scorer_with_full_coverage.calculate_overall_quality(
            code=code,
            file_path="/app/services/quality/pattern_scorer.py",
            usage_count=8,
        )

        # ONEX pattern should score high
        assert (
            result["quality_score"] >= 0.75
        ), "Well-structured ONEX pattern should score highly"

        # Check individual components
        assert (
            result["components"]["documentation"] >= 0.5
        ), "ONEX pattern has good documentation"
        assert (
            result["components"]["complexity"] >= 0.7
        ), "ONEX pattern has low complexity"
        assert result["components"]["test_coverage"] == 1.0, "Full coverage provided"
        assert result["components"]["reusability"] >= 0.6, "Used in multiple files"
