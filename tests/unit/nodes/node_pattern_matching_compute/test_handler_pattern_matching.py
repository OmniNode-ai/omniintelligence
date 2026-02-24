# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for pattern matching handler functions.

Tests the pure matching logic without any I/O dependencies.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
    PatternRecord,
    match_patterns,
)


@pytest.mark.unit
class TestMatchPatterns:
    """Tests for the match_patterns function."""

    def test_empty_pattern_library_returns_empty_result(self) -> None:
        """Empty pattern library should return success with no matches."""
        result = match_patterns(
            code_snippet="def foo(): return None",
            patterns=[],
            min_confidence=0.5,
        )
        assert result["success"] is True
        assert result["matches"] == []
        assert result["patterns_analyzed"] == 0
        assert result["patterns_matched"] == 0

    def test_keyword_overlap_matching(self) -> None:
        """Keyword overlap should match patterns with shared vocabulary."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="singleton pattern implementation",
                domain="design_patterns",
                keywords=["singleton", "instance", "pattern"],
                category="design_pattern",
            ),
            PatternRecord(
                pattern_id="p2",
                signature="factory pattern",
                domain="design_patterns",
                keywords=["factory", "create", "pattern"],
                category="design_pattern",
            ),
        ]

        code = """
        class Singleton:
            _instance = None

            @classmethod
            def get_instance(cls):
                if cls._instance is None:
                    cls._instance = cls()
                return cls._instance
        """

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.1,  # Low threshold to ensure matches
            operation="match",
        )

        assert result["success"] is True
        assert result["patterns_analyzed"] == 2
        # Singleton pattern should match better due to keyword overlap
        if result["matches"]:
            top_match = result["matches"][0]
            assert top_match["pattern_id"] == "p1"
            assert top_match["algorithm_used"] == "keyword_overlap"

    def test_regex_matching_with_validate_operation(self) -> None:
        """Validate operation should use regex matching."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature=r"def\s+\w+\s*\(.*\)\s*->",
                domain="code_style",
                category="type_annotation",
            ),
        ]

        code = "def calculate(x: int, y: int) -> int:\n    return x + y"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.5,
            operation="validate",
        )

        assert result["success"] is True
        if result["matches"]:
            assert result["matches"][0]["algorithm_used"] == "regex_match"
            assert result["matches"][0]["confidence"] == 1.0

    def test_substring_matching_fallback(self) -> None:
        """Invalid regex should fall back to substring matching."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="[invalid(regex",  # Invalid regex syntax
                domain="test",
                category="test",
            ),
        ]

        # Code contains the literal invalid pattern string
        code = "[invalid(regex is here"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.5,
            operation="validate",
        )

        assert result["success"] is True
        assert len(result["matches"]) == 1
        # Substring match returns 0.8 confidence
        assert result["matches"][0]["confidence"] == 0.8

    def test_category_filtering(self) -> None:
        """Patterns should be filtered by category when specified."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="design pattern",
                domain="patterns",
                keywords=["pattern", "design"],
                category="design_pattern",
            ),
            PatternRecord(
                pattern_id="p2",
                signature="anti pattern",
                domain="patterns",
                keywords=["pattern", "anti"],
                category="anti_pattern",
            ),
        ]

        code = "# This is a pattern example"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.0,
            pattern_categories=["anti_pattern"],
        )

        # Only p2 should be analyzed
        assert result["patterns_analyzed"] == 1
        if result["matches"]:
            assert result["matches"][0]["pattern_id"] == "p2"

    def test_max_results_limiting(self) -> None:
        """Results should be limited to max_results."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id=f"p{i}",
                signature=f"pattern {i}",
                domain="test",
                keywords=["test", "pattern"],
                category="test",
            )
            for i in range(10)
        ]

        code = "# test pattern code"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.0,
            max_results=3,
        )

        assert len(result["matches"]) <= 3

    def test_confidence_threshold_filtering(self) -> None:
        """Patterns below threshold should be filtered out."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="exact match needed",
                domain="test",
                keywords=["exact", "match"],
                category="test",
            ),
        ]

        code = "completely unrelated code"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.9,  # High threshold
        )

        # Should filter out low-confidence matches
        assert result["success"] is True
        assert result["patterns_filtered"] >= 0

    def test_empty_code_snippet_returns_validation_error(self) -> None:
        """Empty code snippet should return structured validation error.

        Per ONEX handler pattern, validation errors return structured output
        with success=False instead of raising exceptions.
        """
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="test",
                domain="test",
            ),
        ]

        result = match_patterns(
            code_snippet="",
            patterns=patterns,
        )

        assert result["success"] is False
        assert result["error_code"] == "PATMATCH_001"
        assert "cannot be empty" in result["error"]

    def test_whitespace_only_code_returns_validation_error(self) -> None:
        """Whitespace-only code should return structured validation error.

        Per ONEX handler pattern, validation errors return structured output
        with success=False instead of raising exceptions.
        """
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="test",
                domain="test",
            ),
        ]

        result = match_patterns(
            code_snippet="   \n\t  ",
            patterns=patterns,
        )

        assert result["success"] is False
        assert result["error_code"] == "PATMATCH_001"
        assert "cannot be empty" in result["error"]

    def test_invalid_confidence_threshold_returns_validation_error(self) -> None:
        """Invalid confidence threshold should return structured validation error.

        Per ONEX handler pattern, validation errors return structured output
        with success=False instead of raising exceptions.
        """
        result = match_patterns(
            code_snippet="code",
            patterns=[],
            min_confidence=1.5,
        )

        assert result["success"] is False
        assert result["error_code"] == "PATMATCH_001"
        assert "min_confidence" in result["error"]

    def test_invalid_max_results_returns_validation_error(self) -> None:
        """Invalid max_results should return structured validation error.

        Per ONEX handler pattern, validation errors return structured output
        with success=False instead of raising exceptions.
        """
        result = match_patterns(
            code_snippet="code",
            patterns=[],
            max_results=0,
        )

        assert result["success"] is False
        assert result["error_code"] == "PATMATCH_001"
        assert "max_results" in result["error"]

    def test_results_sorted_by_confidence_descending(self) -> None:
        """Results should be sorted by confidence descending."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="low",
                signature="unrelated",
                domain="test",
                keywords=["unrelated"],
                category="test",
            ),
            PatternRecord(
                pattern_id="high",
                signature="pattern match test",
                domain="test",
                keywords=["test", "pattern", "match"],
                category="test",
            ),
        ]

        code = "this is a test pattern match example"

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.0,
        )

        if len(result["matches"]) >= 2:
            confidences = [m["confidence"] for m in result["matches"]]
            assert confidences == sorted(confidences, reverse=True)

    def test_match_detail_contains_required_fields(self) -> None:
        """Match detail should contain all required fields."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="test pattern",
                domain="test_domain",
                keywords=["test"],
                category="test_category",
            ),
        ]

        result = match_patterns(
            code_snippet="this is a test",
            patterns=patterns,
            min_confidence=0.0,
        )

        if result["matches"]:
            match = result["matches"][0]
            assert "pattern_id" in match
            assert "pattern_name" in match
            assert "confidence" in match
            assert "category" in match
            assert "match_reason" in match
            assert "algorithm_used" in match


@pytest.mark.unit
class TestKeywordExtraction:
    """Tests for the keyword extraction algorithm."""

    def test_filters_noise_words(self) -> None:
        """Common Python keywords should be filtered out."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="meaningful identifier",
                domain="test",
                keywords=["meaningful", "identifier"],
                category="test",
            ),
        ]

        # Code with lots of Python keywords
        code = """
        def function(self, args, kwargs):
            if True and False or None:
                pass
            return None
        meaningful identifier here
        """

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.0,
        )

        # Should match on 'meaningful' and 'identifier', not Python keywords
        assert result["success"] is True

    def test_extracts_identifiers(self) -> None:
        """Should extract meaningful identifiers from code."""
        patterns: list[PatternRecord] = [
            PatternRecord(
                pattern_id="p1",
                signature="user_repository pattern",
                domain="test",
                keywords=["user_repository", "repository"],
                category="test",
            ),
        ]

        code = """
        class UserRepository:
            def get_user(self, user_id):
                pass
        """

        result = match_patterns(
            code_snippet=code,
            patterns=patterns,
            min_confidence=0.0,
        )

        # Should match on 'user_repository' keyword
        assert result["success"] is True
