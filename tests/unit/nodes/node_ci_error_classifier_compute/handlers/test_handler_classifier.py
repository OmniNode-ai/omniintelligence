# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for CI error classifier handler.

Tickets: OMN-3556, OMN-11577
"""

import json

import pytest

from omniintelligence.nodes.node_ci_error_classifier_compute.handlers.handler_classifier import (
    _parse_failure_output,
    _parse_llm_response,
    handle_classify_ci_error,
)
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_input import (
    ModelCiErrorClassifierInput,
)
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_output import (
    ModelCiErrorClassifierOutput,
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


# ---------------------------------------------------------------------------
# _parse_failure_output
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_failure_output_valid_json_dict() -> None:
    """Valid JSON object is parsed and returned as dict."""
    payload = json.dumps(
        {"classification": "type_error", "confidence": 0.85, "evidence": ["line 42"]}
    )
    result = _parse_failure_output(payload)
    assert result["classification"] == "type_error"
    assert result["confidence"] == 0.85


@pytest.mark.unit
def test_parse_failure_output_plain_text_fallback() -> None:
    """Non-JSON input is returned as a dict with classification hint."""
    result = _parse_failure_output("test_failure")
    assert result == {"classification": "test_failure"}


@pytest.mark.unit
def test_parse_failure_output_json_non_dict_fallback() -> None:
    """JSON that isn't a dict (e.g. array) falls back to plain-text path."""
    result = _parse_failure_output('["test_failure"]')
    assert result == {"classification": '["test_failure"]'}


@pytest.mark.unit
def test_parse_failure_output_strips_whitespace() -> None:
    """Leading/trailing whitespace around plain-text output is stripped."""
    result = _parse_failure_output("  linting_failure  ")
    assert result == {"classification": "linting_failure"}


# ---------------------------------------------------------------------------
# handle_classify_ci_error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_handle_classify_ci_error_json_input() -> None:
    """JSON failure_output is parsed and normalised to a typed output model."""
    payload = json.dumps(
        {
            "classification": "TYPE_ERROR",
            "confidence": 0.92,
            "evidence": ["mypy: error at line 7"],
            "unknowns": [],
        }
    )
    inp = ModelCiErrorClassifierInput(
        error_fingerprint="abc" * 10 + "ab",  # 32 hex chars
        failure_output=payload,
    )
    out = handle_classify_ci_error(inp)
    assert isinstance(out, ModelCiErrorClassifierOutput)
    assert out.classification == "type_error"
    assert out.confidence == 0.92
    assert out.evidence == ["mypy: error at line 7"]
    assert out.unknowns == []


@pytest.mark.unit
def test_handle_classify_ci_error_plain_text_falls_back_to_unknown() -> None:
    """Plain-text failure_output that isn't a taxonomy value → 'unknown'."""
    inp = ModelCiErrorClassifierInput(
        error_fingerprint="deadbeef" * 8,
        failure_output="Something went very wrong during the build",
    )
    out = handle_classify_ci_error(inp)
    assert out.classification == "unknown"
    assert out.confidence == 0.0


@pytest.mark.unit
def test_handle_classify_ci_error_plain_text_known_taxonomy() -> None:
    """Plain-text failure_output matching a taxonomy value is accepted."""
    inp = ModelCiErrorClassifierInput(
        error_fingerprint="cafebabe" * 8,
        failure_output="linting_failure",
    )
    out = handle_classify_ci_error(inp)
    assert out.classification == "linting_failure"


@pytest.mark.unit
def test_handle_classify_ci_error_confidence_clamped() -> None:
    """Confidence values outside [0, 1] in JSON are clamped."""
    payload = json.dumps({"classification": "build_failure", "confidence": 2.5})
    inp = ModelCiErrorClassifierInput(
        error_fingerprint="feedface" * 8,
        failure_output=payload,
    )
    out = handle_classify_ci_error(inp)
    assert out.confidence == 1.0
