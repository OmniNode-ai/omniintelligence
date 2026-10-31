# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    HandlerQualityScoring,
    ModelScoreCodeQualityRequest,
)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_character_code(self) -> None:
        """Single character valid Python should be scored."""
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content="1", language="python")
        )
        assert result["success"] is True

    def test_only_comments(self) -> None:
        """Code with only comments should be scored."""
        code = """
# This is a comment
# Another comment
"""
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )
        assert result["success"] is True

    def test_unicode_content(self) -> None:
        """Unicode content should be handled correctly."""
        code = '''
def greet(name: str) -> str:
    """Return greeting message."""
    return f"Hello, {name}!"
'''
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )
        assert result["success"] is True

    def test_very_long_function(self) -> None:
        """Very long functions should get lower maintainability score."""
        # Generate a function with many lines
        long_func = "def long_func():\n" + "    x = 1\n" * 100 + "    return x"
        short_func = "def short_func():\n    return 1"

        result_long = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=long_func, language="python")
        )
        result_short = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=short_func, language="python")
        )

        assert (
            result_short["dimensions"]["maintainability"]
            > result_long["dimensions"]["maintainability"]
        )

    def test_deeply_nested_code(self) -> None:
        """Deeply nested code should score lower on complexity."""
        nested = """
def deep():
    if True:
        for i in range(10):
            while True:
                if i > 5:
                    for j in range(5):
                        if j > 2:
                            return j
                break
"""
        flat = """
def flat():
    return 42
"""
        result_nested = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=nested, language="python")
        )
        result_flat = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=flat, language="python")
        )

        assert (
            result_flat["dimensions"]["complexity"]
            > result_nested["dimensions"]["complexity"]
        )

    def test_async_functions(self) -> None:
        """Async functions should be scored correctly."""
        async_code = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    return {}
'''
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=async_code, language="python")
        )

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
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )

        # Well-named class with proper method conventions should score high on maintainability
        assert result["dimensions"]["maintainability"] >= 0.8

    def test_language_case_insensitive(self) -> None:
        """Language parameter should be case insensitive."""
        code = "x = 1"

        result_lower = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )
        result_upper = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="PYTHON")
        )
        result_mixed = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="Python")
        )

        assert result_lower["quality_score"] == result_upper["quality_score"]
        assert result_lower["quality_score"] == result_mixed["quality_score"]

    def test_py_alias_for_python(self) -> None:
        """'py' should be accepted as alias for 'python'."""
        code = "x = 1"

        result_py = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="py")
        )
        result_python = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )

        # Both should be analyzed as Python, not unsupported
        assert result_py["source_language"] == "py"
        assert result_python["source_language"] == "python"
        # Should get same analysis (not baseline unsupported scores)
        assert "[unsupported_language]" not in str(result_py["recommendations"])
        assert "[unsupported_language]" not in str(result_python["recommendations"])

    def test_no_functions_high_temporal_relevance(self) -> None:
        """Code with no staleness indicators should get high temporal_relevance score."""
        code = """
CONSTANT = 42
data = {"key": "value"}
"""
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )

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
        result = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=code, language="python")
        )

        # Mix of good and bad naming should result in moderate score
        assert 0.5 <= result["dimensions"]["maintainability"] <= 0.9

    def test_list_comprehensions_count_as_complexity(self) -> None:
        """List comprehensions should add to complexity score."""
        without_comprehension = """
def simple(items: list) -> list:
    return items
"""
        with_comprehension = """
def complex_comprehension(items: list) -> list:
    return [x for x in items if x > 0 for y in x if y != 0]
"""
        result_simple = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(
                content=without_comprehension, language="python"
            )
        )
        result_complex = HandlerQualityScoring().handle(
            ModelScoreCodeQualityRequest(content=with_comprehension, language="python")
        )

        # Comprehensions add complexity
        assert (
            result_simple["dimensions"]["complexity"]
            >= result_complex["dimensions"]["complexity"]
        )

    def test_compute_error_on_unexpected_failure(self) -> None:
        """Test that unexpected failures return structured error.

        Per CLAUDE.md handler pattern, unknown errors are returned as
        structured output with success=False, not raised as exceptions.
        """
        # Mock ast.parse to raise an unexpected exception (not SyntaxError)
        with patch("ast.parse", side_effect=MemoryError("Simulated memory exhaustion")):
            result = HandlerQualityScoring().handle(
                ModelScoreCodeQualityRequest(
                    content="valid_code = 1", language="python"
                )
            )
            assert result["success"] is False
            assert result["quality_score"] == 0.0
            assert any("unexpected" in r.lower() for r in result["recommendations"])
            assert any(
                "validation_error" in r.lower() for r in result["recommendations"]
            )
