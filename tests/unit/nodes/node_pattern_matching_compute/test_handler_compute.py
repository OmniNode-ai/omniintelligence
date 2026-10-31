# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for pattern matching compute handler.

Tests the orchestration layer that bridges models and pure matching logic.
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_matching_compute.handlers import (
    handler_compute as canonical_handler,
)
from omniintelligence.nodes.node_pattern_matching_compute.models import (
    ModelPatternContext,
    ModelPatternMatchingInput,
    ModelPatternRecord,
)


@pytest.mark.unit
class TestHandlePatternMatchingCompute:
    """Tests for HandlerPatternMatchingCompute handler."""

    def test_successful_matching_with_patterns(self) -> None:
        """Should return successful result with matched patterns."""
        input_data = ModelPatternMatchingInput(
            code_snippet="""
            class Singleton:
                _instance = None

                @classmethod
                def get_instance(cls):
                    if cls._instance is None:
                        cls._instance = cls()
                    return cls._instance
            """,
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature="singleton pattern",
                    domain="design_patterns",
                    keywords=["singleton", "instance", "pattern"],
                    category="design_pattern",
                ),
            ],
            operation="match",
            context=ModelPatternContext(
                min_confidence=0.1,
                max_results=10,
            ),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.status == "completed"
        assert result.metadata.processing_time_ms is not None
        assert result.metadata.processing_time_ms >= 0
        assert result.metadata.algorithm_version is not None

    def test_empty_pattern_library(self) -> None:
        """Should handle empty pattern library gracefully."""
        input_data = ModelPatternMatchingInput(
            code_snippet="def foo(): pass",
            patterns=[],
            operation="match",
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        assert result.patterns_matched == []
        assert result.pattern_scores == {}
        assert result.matches == []

    def test_output_contains_rich_match_details(self) -> None:
        """Output should contain rich ModelPatternMatch objects."""
        input_data = ModelPatternMatchingInput(
            code_snippet="test pattern code example",
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature="test pattern",
                    domain="test",
                    keywords=["test", "pattern", "example"],
                    category="test_category",
                ),
            ],
            operation="match",
            context=ModelPatternContext(min_confidence=0.0),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        assert len(result.matches) > 0
        match = result.matches[0]
        assert match.pattern_id == "p1"
        assert match.category == "test_category"
        assert match.algorithm_used == "keyword_overlap"
        assert match.match_reason != ""

    def test_patterns_matched_backwards_compatible(self) -> None:
        """patterns_matched and pattern_scores should be populated for backwards compatibility."""
        input_data = ModelPatternMatchingInput(
            code_snippet="test pattern code",
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature="test pattern",
                    domain="test",
                    keywords=["test", "pattern"],
                    category="test",
                ),
            ],
            operation="match",
            context=ModelPatternContext(min_confidence=0.0),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        # Both simple and rich representations should be populated
        assert len(result.patterns_matched) == len(result.matches)
        assert len(result.pattern_scores) == len(result.matches)

    def test_metadata_contains_statistics(self) -> None:
        """Metadata should contain matching statistics."""
        input_data = ModelPatternMatchingInput(
            code_snippet="test code here",
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature="test",
                    domain="test",
                    keywords=["test"],
                    category="test",
                ),
                ModelPatternRecord(
                    pattern_id="p2",
                    signature="unrelated",
                    domain="test",
                    keywords=["unrelated"],
                    category="test",
                ),
            ],
            operation="match",
            context=ModelPatternContext(
                min_confidence=0.5,
                max_results=10,
            ),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.metadata is not None
        assert result.metadata.patterns_analyzed is not None
        assert result.metadata.patterns_analyzed == 2
        assert result.metadata.threshold_used == 0.5
        assert result.metadata.input_length is not None
        assert result.metadata.input_line_count is not None

    def test_validation_error_returns_structured_output(self) -> None:
        """Validation errors should return structured output, not raise.

        Tests that PatternMatchingValidationError from the handler is caught
        and converted to a structured error response with success=False.
        """
        # Whitespace-only code_snippet passes Pydantic min_length=1 but fails
        # handler's _validate_inputs check: "not code_snippet.strip()"
        input_data = ModelPatternMatchingInput(
            code_snippet="   ",  # Whitespace only - triggers validation error
            patterns=[],
            context=ModelPatternContext(
                min_confidence=0.5,
            ),
        )

        # Handler should return structured error, not raise
        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)
        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "validation_error"
        assert result.metadata.message is not None, (
            "Expected error message for validation_error"
        )
        assert "empty" in result.metadata.message.lower()

    def test_validate_operation_uses_regex_matching(self) -> None:
        """Validate operation should use regex matching algorithm."""
        input_data = ModelPatternMatchingInput(
            code_snippet="def calculate(x: int) -> int:\n    return x",
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature=r"def\s+\w+\s*\(",
                    domain="code_style",
                    category="function_definition",
                ),
            ],
            operation="validate",
            context=ModelPatternContext(min_confidence=0.5),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        if result.matches:
            assert result.matches[0].algorithm_used == "regex_match"

    def test_category_filtering_through_context(self) -> None:
        """Pattern categories should filter through context."""
        input_data = ModelPatternMatchingInput(
            code_snippet="test pattern code",
            patterns=[
                ModelPatternRecord(
                    pattern_id="p1",
                    signature="design pattern",
                    domain="patterns",
                    keywords=["pattern", "test"],
                    category="design_pattern",
                ),
                ModelPatternRecord(
                    pattern_id="p2",
                    signature="anti pattern",
                    domain="patterns",
                    keywords=["pattern", "test"],
                    category="anti_pattern",
                ),
            ],
            operation="match",
            context=ModelPatternContext(
                min_confidence=0.0,
                pattern_categories=["anti_pattern"],
            ),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.success is True
        # Only anti_pattern should be analyzed
        if result.matches:
            for match in result.matches:
                assert match.category == "anti_pattern"

    def test_correlation_id_preserved(self) -> None:
        """Correlation ID should be preserved in metadata."""
        from uuid import uuid4

        correlation_id = uuid4()
        input_data = ModelPatternMatchingInput(
            code_snippet="test code",
            patterns=[],
            context=ModelPatternContext(
                correlation_id=correlation_id,
            ),
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.metadata is not None
        assert result.metadata.correlation_id == str(correlation_id)

    def test_timestamp_populated(self) -> None:
        """Timestamp should be populated in metadata."""
        input_data = ModelPatternMatchingInput(
            code_snippet="test code",
            patterns=[],
        )

        result = canonical_handler.HandlerPatternMatchingCompute().handle(input_data)

        assert result.metadata is not None
        assert result.metadata.timestamp_utc is not None
        # Should be ISO 8601 format
        assert "T" in result.metadata.timestamp_utc


# Shared with the coverage receipt recorder; no random input defaults.
CANONICAL_PARITY_CASES = [
    {
        "case": "empty_library",
        "input": {"code_snippet": "worker pattern", "patterns": []},
    },
    {
        "case": "matched",
        "input": {
            "code_snippet": "worker pattern",
            "patterns": [
                {
                    "pattern_id": "p1",
                    "signature": "worker pattern",
                    "domain": "test",
                    "keywords": ["worker", "pattern"],
                    "category": "worker",
                }
            ],
            "context": {
                "min_confidence": 0.0,
                "correlation_id": "11111111-1111-1111-1111-111111111111",
            },
        },
    },
    {
        "case": "filtered",
        "input": {
            "code_snippet": "worker pattern",
            "patterns": [
                {
                    "pattern_id": "p1",
                    "signature": "worker pattern",
                    "domain": "test",
                    "keywords": ["worker", "pattern"],
                    "category": "worker",
                }
            ],
            "context": {"pattern_categories": ["other"], "min_confidence": 0.0},
        },
    },
    {
        "case": "no_match",
        "input": {
            "code_snippet": "unrelated",
            "patterns": [
                {
                    "pattern_id": "p1",
                    "signature": "worker pattern",
                    "domain": "test",
                    "keywords": ["worker", "pattern"],
                    "category": "worker",
                }
            ],
            "context": {"min_confidence": 1.0},
        },
    },
    {
        "case": "validation_error",
        "input": {
            "code_snippet": " \n ",
            "patterns": [
                {
                    "pattern_id": "p1",
                    "signature": "worker pattern",
                    "domain": "test",
                    "keywords": ["worker", "pattern"],
                    "category": "worker",
                }
            ],
            "context": {},
        },
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("payload", CANONICAL_PARITY_CASES, ids=lambda p: p["case"])
def test_canonical_dispatch_matches_preserved_core(payload, monkeypatch):
    """Compare canonical dispatch with the git-preserved core on branch cases.

    Resolve the class inside the test so the legacy tree collects successfully
    and fails this assertion, rather than failing import/collection.
    """
    handler_class = getattr(canonical_handler, "HandlerPatternMatchingCompute", None)
    assert handler_class is not None, "canonical handle(request) class is required"
    from omniintelligence.nodes.node_pattern_matching_compute.models import (
        ModelPatternMatchingInput,
    )

    request = ModelPatternMatchingInput.model_validate(payload["input"])
    # Only nondeterministic clocks/IDs are controlled; the algorithm runs normally.
    from uuid import UUID

    monkeypatch.setattr("time.perf_counter", lambda: 100.0)
    monkeypatch.setattr(
        "uuid.uuid4", lambda: UUID("22222222-2222-2222-2222-222222222222")
    )
    from datetime import UTC, datetime

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(canonical_handler, "datetime", FixedDatetime)
    expected = canonical_handler._execute_matching(request, 100.0)
    assert handler_class().handle(request) == expected
