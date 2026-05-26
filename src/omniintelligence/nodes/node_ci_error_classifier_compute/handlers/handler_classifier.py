# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM error classifier handler — pure parse/normalize logic only.

No I/O in this module (compute node policy). The actual LLM call is
injected via protocol dependency at the effect layer.

Ticket: OMN-3556
"""

from __future__ import annotations

import json
from typing import Any

from omniintelligence.enums.enum_error_taxonomy import EnumErrorTaxonomy
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_input import (
    ModelCiErrorClassifierInput,
)
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_output import (
    ModelCiErrorClassifierOutput,
)


def _coerce_to_list(value: object) -> list[str]:
    """Ensure value is list[str] regardless of model output shape."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _parse_llm_response(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate a raw LLM classification response.

    Guarantees:
    - classification is lowercase and maps to a valid EnumErrorTaxonomy
      (falls back to "unknown" if unrecognized)
    - confidence is clamped to [0.0, 1.0]
    - evidence is list[str] (scalar coerced to single-element list)
    - unknowns is list[str] (scalar coerced to single-element list)
    """
    # Normalize classification before enum cast — models return mixed case
    raw_classification = str(data.get("classification", "unknown")).lower().strip()
    try:
        classification = EnumErrorTaxonomy(raw_classification)
    except ValueError:
        classification = EnumErrorTaxonomy("unknown")

    # Clamp confidence — models occasionally return values outside [0, 1]
    raw_confidence = data.get("confidence", 0.0)
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "classification": classification.value,
        "confidence": confidence,
        "evidence": _coerce_to_list(data.get("evidence")),
        "unknowns": _coerce_to_list(data.get("unknowns")),
    }


def _parse_failure_output(failure_output: str) -> dict[str, Any]:
    """Attempt to parse raw LLM failure output as JSON.

    The LLM may return a JSON object with classification keys, or plain text.
    Falls back to an unknown classification when the output is not valid JSON
    or does not contain the expected keys.

    Args:
        failure_output: Raw string returned by the LLM (may be JSON or plain text).

    Returns:
        Dict suitable for passing to _parse_llm_response.
    """
    try:
        parsed = json.loads(failure_output)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Plain-text fallback: treat entire output as the classification hint
    return {"classification": failure_output.strip()}


def handle_classify_ci_error(
    input_data: ModelCiErrorClassifierInput,
) -> ModelCiErrorClassifierOutput:
    """Normalize and validate a CI error classification from raw LLM output.

    Parses ``input_data.failure_output`` (which may be a JSON object from the
    LLM or a plain-text classification hint) and normalises the result through
    ``_parse_llm_response``.

    Args:
        input_data: Input containing the raw LLM response and error fingerprint.

    Returns:
        Normalised classification output with clamped confidence and coerced lists.
    """
    raw_dict = _parse_failure_output(input_data.failure_output)
    parsed = _parse_llm_response(raw_dict)
    return ModelCiErrorClassifierOutput(**parsed)


__all__ = [
    "_coerce_to_list",
    "_parse_failure_output",
    "_parse_llm_response",
    "handle_classify_ci_error",
]
