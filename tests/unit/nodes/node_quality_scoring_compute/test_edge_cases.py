# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for edge cases and boundary conditions.

This module tests edge cases and boundary conditions:
    - Single character code
    - Comments only
    - Unicode content
    - Very long functions
    - Deeply nested code
    - Async functions
    - Language handling
    - Unexpected failures
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    score_code_quality,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.exceptions import (
    QualityScoringComputeError,
)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_character_code(self) -> None:
        """Single character valid Python should be scored."""
        result = score_code_quality("1", "python")
        assert result["success"] is True

    def test_only_comments(self) -> None:
        """Code with only comments should be scored."""
        code = """
# This is a comment
# Another comment
"""
        result = score_code_quality(code, "python")
        assert result["success"] is True

    def test_unicode_content(self) -> None:
        """Unicode content should be handled correctly."""
        code = '''
def greet(name: str) -> str:
    """Return greeting message."""
    return f"Hello, {name}!"
'''
        result = score_code_quality(code, "python")
        assert result["success"] is True

    def test_very_long_function(self) -> None:
        """Very long functions should get lower maintainability score."""
        # Generate a function with many lines
        long_func = "def long_func():\n" + "    x = 1\n" * 100 + "    return x"
        short_func = "def short_func():\n    return 1"

        result_long = score_code_quality(long_func, "python")
        result_short = score_code_quality(short_func, "python")

        assert (
            result_short["dimensions"]["maintainability"]
            > result_long["dimensions"]["maintainability"]
        )

    def test_deeply_nested_code(self) -> None:
        """Deeply nested code should score lower on complexity."""
        nested = '''
def deep():
    if True:
        for i in range(10):
            while True:
                if i > 5:
                    for j in range(5):
                        if j > 2:
                            return j
                break
'''
        flat = '''
def flat():
    return 42
'''
        result_nested = score_code_quality(nested, "python")
        result_flat = score_code_quality(flat, "python")

        assert result_flat["dimensions"]["complexity"] > result_nested["dimensions"]["complexity"]

    def test_async_functions(self) -> None:
        """Async functions should be scored correctly."""
        async_code = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    return {}
'''
        result = score_code_quality(async_code, "python")

        assert result["success"] is True
        # Async function should have reasonable complexity (simple code scores well)
        assert result["dimensions"]["complexity"] >= 0.8

    def test_class_methods(self) -> None:
        """Class methods should score well on maintainability."""
        code = '''
class Example:
    """Example class."""

    def instance_method(self, value: int) -> int:
        """Instance method."""
        return value * 2

    @classmethod
    def class_method(cls, value: int) -> int:
        """Class method."""
        return value * 3
'''
        result = score_code_quality(code, "python")

        # Well-named class with proper method conventions should score high on maintainability
        assert result["dimensions"]["maintainability"] >= 0.8

    def test_language_case_insensitive(self) -> None:
        """Language parameter should be case insensitive."""
        code = "x = 1"

        result_lower = score_code_quality(code, "python")
        result_upper = score_code_quality(code, "PYTHON")
        result_mixed = score_code_quality(code, "Python")

        assert result_lower["quality_score"] == result_upper["quality_score"]
        assert result_lower["quality_score"] == result_mixed["quality_score"]

    def test_py_alias_for_python(self) -> None:
        """'py' should be accepted as alias for 'python'."""
        code = "x = 1"

        result_py = score_code_quality(code, "py")
        result_python = score_code_quality(code, "python")

        # Both should be analyzed as Python, not unsupported
        assert result_py["source_language"] == "py"
        assert result_python["source_language"] == "python"
        # Should get same analysis (not baseline unsupported scores)
        assert "[unsupported_language]" not in str(result_py["recommendations"])
        assert "[unsupported_language]" not in str(result_python["recommendations"])

    def test_no_functions_high_temporal_relevance(self) -> None:
        """Code with no staleness indicators should get high temporal_relevance score."""
        code = '''
CONSTANT = 42
data = {"key": "value"}
'''
        result = score_code_quality(code, "python")

        # No TODO/FIXME/deprecated markers means high temporal relevance (1.0)
        assert result["dimensions"]["temporal_relevance"] == 1.0

    def test_multiple_classes(self) -> None:
        """Multiple classes should all be evaluated."""
        code = '''
class GoodClass:
    """Good naming."""
    pass

class another_class:
    pass

class AnotherGoodClass:
    """Another good class."""
    pass
'''
        result = score_code_quality(code, "python")

        # Mix of good and bad naming should result in moderate score
        assert 0.5 <= result["dimensions"]["maintainability"] <= 0.9

    def test_list_comprehensions_count_as_complexity(self) -> None:
        """List comprehensions should add to complexity score."""
        without_comprehension = '''
def simple(items: list) -> list:
    return items
'''
        with_comprehension = '''
def complex_comprehension(items: list) -> list:
    return [x for x in items if x > 0 for y in x if y != 0]
'''
        result_simple = score_code_quality(without_comprehension, "python")
        result_complex = score_code_quality(with_comprehension, "python")

        # Comprehensions add complexity
        assert result_simple["dimensions"]["complexity"] >= result_complex["dimensions"]["complexity"]

    def test_compute_error_on_unexpected_failure(self) -> None:
        """Test that QualityScoringComputeError is raised for unexpected failures."""
        # Mock ast.parse to raise an unexpected exception (not SyntaxError)
        with patch("ast.parse", side_effect=MemoryError("Simulated memory exhaustion")):
            with pytest.raises(QualityScoringComputeError, match=r"[Uu]nexpected"):
                score_code_quality("valid_code = 1", "python")
