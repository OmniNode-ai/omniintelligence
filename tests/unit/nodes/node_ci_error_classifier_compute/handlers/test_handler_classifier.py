# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for CI error classifier handler.

Ticket: OMN-3556
"""

import pytest

from omniintelligence.nodes.node_ci_error_classifier_compute.handlers.handler_classifier import (
    _parse_llm_response,
)


@pytest.mark.unit
def test_classification_normalized_to_lowercase() -> None:
    """LLM may return 'FLAKY_TEST' — must normalize before enum cast."""
    result = _parse_llm_response(
        {"classification": "FLAKY_TEST", "confidence": 0.9, "evidence": []}
    )
    assert result["classification"] == "flaky_test"


@pytest.mark.unit
def test_confidence_clamped_to_zero_one() -> None:
    """LLM may return confidence outside [0, 1] — must clamp."""
    assert (
        _parse_llm_response({"classification": "unknown", "confidence": 1.5})[
            "confidence"
        ]
        == 1.0
    )
    assert (
        _parse_llm_response({"classification": "unknown", "confidence": -0.1})[
            "confidence"
        ]
        == 0.0
    )


@pytest.mark.unit
def test_evidence_scalar_coerced_to_list() -> None:
    """LLM may return evidence as a string — must become list[str]."""
    result = _parse_llm_response(
        {
            "classification": "infra_failure",
            "confidence": 0.8,
            "evidence": "Connection timeout on port 5432",
        }
    )
    assert isinstance(result["evidence"], list)
    assert result["evidence"] == ["Connection timeout on port 5432"]


@pytest.mark.unit
def test_unknowns_scalar_coerced_to_list() -> None:
    """LLM may return unknowns as a string — must become list[str]."""
    result = _parse_llm_response(
        {
            "classification": "unknown",
            "confidence": 0.1,
            "unknowns": "Could not determine root cause",
        }
    )
    assert isinstance(result["unknowns"], list)


@pytest.mark.unit
def test_missing_evidence_defaults_to_empty_list() -> None:
    """Missing evidence and unknowns default to empty list."""
    result = _parse_llm_response({"classification": "test_failure", "confidence": 0.7})
    assert result["evidence"] == []
    assert result["unknowns"] == []


@pytest.mark.unit
def test_invalid_classification_falls_back_to_unknown() -> None:
    """If LLM returns an unknown taxonomy value, fall back gracefully."""
    result = _parse_llm_response(
        {"classification": "totally_made_up", "confidence": 0.5}
    )
    assert result["classification"] == "unknown"
