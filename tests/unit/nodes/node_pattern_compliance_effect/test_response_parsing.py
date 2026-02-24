# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for LLM response parsing and violation extraction.

Tests the pure parsing functions that convert raw LLM text responses
into structured compliance results with typed violations.

Ticket: OMN-2256
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
    parse_llm_response,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models import (
    ModelApplicablePattern,
)


def _make_pattern(
    pattern_id: str = "P001",
    signature: str = "Use frozen Pydantic models",
    domain: str = "onex",
    confidence: float = 0.9,
) -> ModelApplicablePattern:
    """Helper to create test patterns."""
    return ModelApplicablePattern(
        pattern_id=pattern_id,
        pattern_signature=signature,
        domain_id=domain,
        confidence=confidence,
    )


class TestParseCompliantResponse:
    """Tests for parsing fully compliant LLM responses."""

    def test_fully_compliant_code(self) -> None:
        """Compliant response should have no violations and compliant=True."""
        response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.95,
                "violations": [],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["compliant"] is True
        assert result["violations"] == []
        assert result["confidence"] == 0.95

    def test_confidence_clamped_to_range(self) -> None:
        """Confidence values outside [0, 1] should be clamped."""
        response = json.dumps(
            {
                "compliant": True,
                "confidence": 1.5,
                "violations": [],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["confidence"] == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        """Negative confidence values should be clamped to 0.0."""
        response = json.dumps(
            {
                "compliant": True,
                "confidence": -0.5,
                "violations": [],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["confidence"] == 0.0


class TestParseViolations:
    """Tests for parsing responses with violations."""

    def test_single_violation(self) -> None:
        """Single violation should be parsed correctly."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.85,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Model is not frozen",
                        "severity": "major",
                        "line_reference": "line 5",
                    }
                ],
            }
        )
        patterns = [_make_pattern(pattern_id="P001", signature="Use frozen models")]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["compliant"] is False
        assert len(result["violations"]) == 1
        v = result["violations"][0]
        assert v["pattern_id"] == "P001"
        assert v["description"] == "Model is not frozen"
        assert v["severity"] == "major"
        assert v["line_reference"] == "line 5"
        assert v["pattern_signature"] == "Use frozen models"

    def test_multiple_violations(self) -> None:
        """Multiple violations should all be parsed."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.8,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Not frozen",
                        "severity": "critical",
                        "line_reference": None,
                    },
                    {
                        "pattern_id": "P002",
                        "description": "Missing TypedDict",
                        "severity": "minor",
                        "line_reference": "line 10",
                    },
                ],
            }
        )
        patterns = [
            _make_pattern(pattern_id="P001", signature="Frozen models"),
            _make_pattern(pattern_id="P002", signature="Use TypedDict"),
        ]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert len(result["violations"]) == 2
        assert result["violations"][0]["pattern_id"] == "P001"
        assert result["violations"][1]["pattern_id"] == "P002"

    def test_violation_with_null_line_reference(self) -> None:
        """Null line reference should be preserved."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.9,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Violation found",
                        "severity": "major",
                        "line_reference": None,
                    }
                ],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["violations"][0]["line_reference"] is None

    def test_violations_force_compliant_false(self) -> None:
        """If violations exist, compliant must be False regardless of LLM claim."""
        response = json.dumps(
            {
                "compliant": True,  # LLM says compliant but has violations
                "confidence": 0.9,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Found a violation",
                        "severity": "minor",
                        "line_reference": None,
                    }
                ],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["compliant"] is False

    def test_unknown_severity_defaults_to_major(self) -> None:
        """Unknown severity values should default to 'major'."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.8,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Found violation",
                        "severity": "catastrophic",
                        "line_reference": None,
                    }
                ],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["violations"][0]["severity"] == "major"

    def test_unknown_pattern_id_gets_fallback_signature(self) -> None:
        """Violations with unknown pattern IDs get a fallback signature."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.7,
                "violations": [
                    {
                        "pattern_id": "UNKNOWN-999",
                        "description": "Some violation",
                        "severity": "minor",
                        "line_reference": None,
                    }
                ],
            }
        )
        patterns = [_make_pattern(pattern_id="P001")]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert "Unknown pattern" in result["violations"][0]["pattern_signature"]


class TestParseMarkdownFences:
    """Tests for parsing JSON wrapped in markdown code fences."""

    def test_json_in_backtick_fence(self) -> None:
        """JSON wrapped in ```json ... ``` should be extracted."""
        raw = '```json\n{"compliant": true, "confidence": 0.9, "violations": []}\n```'
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=raw, patterns=patterns)

        assert result["compliant"] is True

    def test_json_in_plain_fence(self) -> None:
        """JSON wrapped in ``` ... ``` (no json tag) should be extracted."""
        raw = '```\n{"compliant": true, "confidence": 0.9, "violations": []}\n```'
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=raw, patterns=patterns)

        assert result["compliant"] is True

    def test_pure_json_no_fences(self) -> None:
        """Pure JSON without fences should work directly."""
        raw = '{"compliant": true, "confidence": 0.9, "violations": []}'
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=raw, patterns=patterns)

        assert result["compliant"] is True


class TestParseErrorHandling:
    """Tests for error handling during response parsing."""

    def test_invalid_json_returns_structured_error(self) -> None:
        """Non-JSON response should return structured error result."""
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text="not json at all", patterns=patterns)

        assert result["compliant"] is False
        assert result["confidence"] == 0.0
        assert result["violations"] == []
        assert "not valid JSON" in result["raw_response"]

    def test_non_dict_json_returns_structured_error(self) -> None:
        """JSON array instead of object should return structured error result."""
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text="[1, 2, 3]", patterns=patterns)

        assert result["compliant"] is False
        assert result["confidence"] == 0.0
        assert result["violations"] == []
        assert "Expected JSON object" in result["raw_response"]

    def test_missing_compliant_field_defaults_true(self) -> None:
        """Missing compliant field should default to True."""
        response = json.dumps({"confidence": 0.9, "violations": []})
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["compliant"] is True

    def test_missing_confidence_defaults_to_half(self) -> None:
        """Missing confidence field should default to 0.5."""
        response = json.dumps({"compliant": True, "violations": []})
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["confidence"] == 0.5

    def test_missing_violations_defaults_to_empty(self) -> None:
        """Missing violations field should default to empty list."""
        response = json.dumps({"compliant": True, "confidence": 0.9})
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["violations"] == []

    def test_non_list_violations_treated_as_empty(self) -> None:
        """Non-list violations field should be treated as empty."""
        response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": "not a list",
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["violations"] == []

    def test_non_dict_violation_entries_skipped(self) -> None:
        """Non-dict entries in violations list should be skipped."""
        response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.8,
                "violations": [
                    "string entry",
                    42,
                    {
                        "pattern_id": "P001",
                        "description": "Valid violation",
                        "severity": "major",
                        "line_reference": None,
                    },
                ],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert len(result["violations"]) == 1

    def test_non_numeric_confidence_defaults_to_zero(self) -> None:
        """Non-numeric confidence should default to 0.0."""
        response = json.dumps(
            {
                "compliant": True,
                "confidence": "high",
                "violations": [],
            }
        )
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=response, patterns=patterns)

        assert result["confidence"] == 0.0

    def test_raw_response_preserved(self) -> None:
        """Raw LLM response text should be preserved in result."""
        raw = '{"compliant": true, "confidence": 0.9, "violations": []}'
        patterns = [_make_pattern()]
        result = parse_llm_response(raw_text=raw, patterns=patterns)

        assert result["raw_response"] == raw
