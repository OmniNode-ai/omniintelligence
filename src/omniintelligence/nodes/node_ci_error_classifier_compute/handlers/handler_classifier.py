# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM error classifier handler — pure parse/normalize logic only.

No I/O in this module (compute node policy). The actual LLM call is
injected via protocol dependency at the effect layer.

Ticket: OMN-3556
"""

from __future__ import annotations

from typing import Any

from omniintelligence.enums.enum_error_taxonomy import EnumErrorTaxonomy


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


__all__ = [
    "_coerce_to_list",
    "_parse_llm_response",
]
