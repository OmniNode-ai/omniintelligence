# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for anti-pattern detection false positive prevention.

This module tests that anti-patterns in comments, docstrings, and string literals
are NOT flagged as code anti-patterns. This addresses the issue where regex-based
detection would produce false positives.

The fix uses:
1. AST-based detection for mutable defaults (= [] and = {})
2. Comment/string stripping before regex for other anti-patterns
"""

from __future__ import annotations

import ast

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    score_code_quality,
)
from omniintelligence.nodes.node_quality_scoring_compute.handlers.handler_quality_scoring import (
    _count_mutable_default_arguments,
    _strip_comments_and_strings,
)


class TestAntiPatternFalsePositives:
    """Tests ensuring anti-patterns in comments/docstrings are not flagged."""

    def test_mutable_default_in_comment_not_flagged(self) -> None:
        """Anti-pattern = [] in comment should not be flagged."""
        code_with_comment = '''
def process(data: list[str]) -> list[str]:
    """Process data items."""
    # Don't use = [] as default, it's mutable
    # Also avoid = {} for same reason
    return data.copy()
'''
        code_with_actual_antipattern = '''
def process(data: list[str] = []) -> list[str]:
    """Process data items."""
    return data.copy()
'''
        result_comment = score_code_quality(code_with_comment, "python")
        result_actual = score_code_quality(code_with_actual_antipattern, "python")

        # Comment version should have higher patterns score (no anti-pattern)
        assert (
            result_comment["dimensions"]["patterns"]
            > result_actual["dimensions"]["patterns"]
        )

    def test_mutable_default_in_docstring_not_flagged(self) -> None:
        """Anti-pattern = {} in docstring should not be flagged."""
        code_with_docstring = '''
def process(data: dict[str, int]) -> dict[str, int]:
    """Process data dictionary.

    Note: Avoid using = {} as a default argument
    because it creates a mutable default.

    Example of what NOT to do:
        def bad(data = {}): pass  # Don't do this!

    Returns:
        Processed dictionary.
    """
    return dict(data)
'''
        code_with_actual_antipattern = '''
def process(data: dict[str, int] = {}) -> dict[str, int]:
    """Process data dictionary."""
    return dict(data)
'''
        result_docstring = score_code_quality(code_with_docstring, "python")
        result_actual = score_code_quality(code_with_actual_antipattern, "python")

        # Docstring version should have higher patterns score
        assert (
            result_docstring["dimensions"]["patterns"]
            > result_actual["dimensions"]["patterns"]
        )

    def test_kwargs_in_comment_not_flagged(self) -> None:
        """The **kwargs pattern in comment should not be flagged."""
        code_with_comment = '''
def process(name: str, value: int) -> str:
    """Process name and value."""
    # Note: we explicitly don't use **kwargs for type safety
    return f"{name}: {value}"
'''
        code_with_actual_antipattern = '''
def process(name: str, **kwargs) -> str:
    """Process name and extra arguments."""
    return f"{name}: {kwargs}"
'''
        result_comment = score_code_quality(code_with_comment, "python")
        result_actual = score_code_quality(code_with_actual_antipattern, "python")

        # Comment version should have higher patterns score
        assert (
            result_comment["dimensions"]["patterns"]
            > result_actual["dimensions"]["patterns"]
        )

    def test_any_type_in_docstring_not_flagged(self) -> None:
        """Type Any mentioned in docstring should not be flagged."""
        code_with_docstring = '''
def process(data: list[str]) -> list[str]:
    """Process data items.

    Note: We avoid using : Any in type hints because it
    defeats the purpose of type checking.

    Args:
        data: List of strings (not Any).

    Returns:
        Processed list.
    """
    return [item.upper() for item in data]
'''
        code_with_actual_antipattern = '''
from typing import Any

def process(data: Any) -> list:
    """Process data items."""
    return list(data)
'''
        result_docstring = score_code_quality(code_with_docstring, "python")
        result_actual = score_code_quality(code_with_actual_antipattern, "python")

        # Docstring version should have higher patterns score
        assert (
            result_docstring["dimensions"]["patterns"]
            > result_actual["dimensions"]["patterns"]
        )

    def test_dict_str_any_in_string_literal_not_flagged(self) -> None:
        """dict[str, Any] in string literal should not be flagged."""
        code_with_string = '''
def get_type_description() -> str:
    """Return description of avoided types."""
    return "Avoid using dict[str, Any] as it loses type information."
'''
        code_with_actual_antipattern = '''
from typing import Any

def process(data: dict[str, Any]) -> None:
    """Process arbitrary data."""
    pass
'''
        result_string = score_code_quality(code_with_string, "python")
        result_actual = score_code_quality(code_with_actual_antipattern, "python")

        # String version should have higher patterns score
        assert (
            result_string["dimensions"]["patterns"]
            > result_actual["dimensions"]["patterns"]
        )


class TestStripCommentsAndStrings:
    """Tests for the _strip_comments_and_strings helper function."""

    def test_strips_single_line_comment(self) -> None:
        """Single-line comments should be stripped."""
        content = "x = 1  # Comment with = [] and **kwargs"
        stripped = _strip_comments_and_strings(content)

        assert "= []" not in stripped
        assert "**kwargs" not in stripped
        assert "x = 1" in stripped

    def test_strips_triple_quoted_string(self) -> None:
        """Triple-quoted strings (docstrings) should be stripped."""
        content = '''
def foo():
    """Docstring mentioning = {} and : Any"""
    pass
'''
        stripped = _strip_comments_and_strings(content)

        assert "= {}" not in stripped
        assert ": Any" not in stripped
        assert "def foo():" in stripped

    def test_strips_single_quoted_string(self) -> None:
        """Single-quoted strings should be stripped."""
        content = """
error_msg = "Don't use = [] as default"
other_msg = 'Also avoid **kwargs'
"""
        stripped = _strip_comments_and_strings(content)

        assert "= []" not in stripped
        assert "**kwargs" not in stripped

    def test_preserves_code_structure(self) -> None:
        """Stripped content should preserve whitespace for line structure."""
        content = "x = 1  # Comment"
        stripped = _strip_comments_and_strings(content)

        # Length should be preserved (replaced with spaces)
        assert len(stripped) == len(content)

    def test_handles_hash_in_string(self) -> None:
        """Hash character inside string should not be treated as comment start."""
        content = """url = "http://example.com#anchor"  # This is a comment"""
        stripped = _strip_comments_and_strings(content)

        # The URL string should be stripped, but the structure preserved
        assert "# This is a comment" not in stripped


class TestCountMutableDefaultArguments:
    """Tests for the _count_mutable_default_arguments helper function."""

    def test_counts_empty_list_default(self) -> None:
        """Empty list [] as default should be counted."""
        code = "def foo(items=[]): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 1

    def test_counts_empty_dict_default(self) -> None:
        """Empty dict {} as default should be counted."""
        code = "def foo(data={}): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 1

    def test_counts_multiple_mutable_defaults(self) -> None:
        """Multiple mutable defaults should all be counted."""
        code = "def foo(items=[], data={}, other=[]): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 3

    def test_ignores_none_default(self) -> None:
        """None as default should not be counted."""
        code = "def foo(items=None): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0

    def test_ignores_string_default(self) -> None:
        """String default should not be counted."""
        code = "def foo(name='default'): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0

    def test_ignores_non_empty_list(self) -> None:
        """Non-empty list default should not be counted (different anti-pattern)."""
        code = "def foo(items=[1, 2, 3]): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0

    def test_ignores_non_empty_dict(self) -> None:
        """Non-empty dict default should not be counted."""
        code = "def foo(data={'key': 'value'}): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0

    def test_counts_kwonly_empty_list(self) -> None:
        """Empty list as keyword-only argument default should be counted."""
        code = "def foo(*, items=[]): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 1

    def test_counts_kwonly_empty_dict(self) -> None:
        """Empty dict as keyword-only argument default should be counted."""
        code = "def foo(*, data={}): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 1

    def test_handles_async_function(self) -> None:
        """Async function with mutable default should be counted."""
        code = "async def foo(items=[]): pass"
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 1

    def test_ignores_list_in_docstring(self) -> None:
        """= [] in docstring should be ignored (AST doesn't parse docstrings)."""
        code = '''
def foo(items: list | None = None):
    """Don't use items=[] as default."""
    pass
'''
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0

    def test_ignores_dict_in_comment(self) -> None:
        """= {} in comment should be ignored (comments not in AST)."""
        code = """
def foo(data: dict | None = None):
    # Note: don't use data={} as default
    pass
"""
        tree = ast.parse(code)
        count = _count_mutable_default_arguments(tree)
        assert count == 0


class TestActualCodeVsDocumentedAntiPatterns:
    """Tests comparing actual anti-patterns vs documented/discussed ones."""

    def test_documenting_antipattern_doesnt_lower_score(self) -> None:
        """Code that documents anti-patterns shouldn't be penalized."""
        well_documented_code = '''
from typing import Final

# Anti-patterns to avoid:
# - def foo(x = []): ...  # Mutable default
# - def bar(**kwargs): ...  # Type-unsafe
# - x: dict[str, Any]  # Too permissive

ANTI_PATTERNS: Final[list[str]] = [
    "Using = [] as default argument",
    "Using **kwargs without TypedDict",
    "Using dict[str, Any] instead of proper types",
]

def get_antipatterns() -> list[str]:
    """Return list of known anti-patterns.

    Known issues include:
    - def foo(data = {}): creates shared mutable
    - **kwargs loses type information
    - dict[str, Any] is essentially untyped
    """
    return ANTI_PATTERNS.copy()
'''
        # This code has many anti-patterns in comments/strings but no actual ones
        result = score_code_quality(well_documented_code, "python")

        # Should have a decent patterns score since no actual anti-patterns
        # The positive patterns (Final, list[str], docstring) should help
        assert result["dimensions"]["patterns"] >= 0.3

    def test_actual_antipatterns_are_still_detected(self) -> None:
        """Actual anti-patterns in code should still be detected."""
        code_with_actual_issues = '''
from typing import Any

def process(data: dict[str, Any], items=[], **kwargs) -> None:
    """Process data with various inputs."""
    cache = {}  # This is fine (not a default argument)
    pass
'''
        result = score_code_quality(code_with_actual_issues, "python")

        # Should have lower patterns score due to actual anti-patterns
        # dict[str, Any], = [], **kwargs are all anti-patterns
        assert result["dimensions"]["patterns"] < 0.4
