"""Pure handler for pattern compliance evaluation.

Contains the prompt construction, LLM response parsing, and violation
extraction logic. This handler is pure in the sense that all I/O
dependencies are injected via the ProtocolLlmClient protocol.

The handler:
    - Builds a structured prompt from code + patterns
    - Delegates the LLM call to the injected client
    - Parses the JSON response into typed violations
    - Returns a ComplianceLlmResponseDict (including structured errors)

Ticket: OMN-2256
"""

from __future__ import annotations

import json
import logging
import re
from typing import Final, cast, get_args

from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ComplianceLlmResponseDict,
    ComplianceViolationDict,
    SeverityLiteral,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_request import (
    ModelApplicablePattern,
)

logger = logging.getLogger(__name__)

# Prompt template version -- tracked in output metadata.
# Increment when the prompt template changes materially.
COMPLIANCE_PROMPT_VERSION: Final[str] = "1.0.0"

# Valid severity levels for violations -- derived from the canonical
# SeverityLiteral type so the two cannot drift apart.
VALID_SEVERITIES: Final[frozenset[str]] = frozenset(get_args(SeverityLiteral))


def build_compliance_prompt(
    *,
    content: str,
    language: str,
    patterns: list[ModelApplicablePattern],
) -> str:
    """Build the user prompt for compliance evaluation.

    Constructs a structured prompt that presents the code and patterns
    to the LLM, requesting a JSON response with violations.

    Args:
        content: Source code content to evaluate.
        language: Programming language of the content.
        patterns: List of patterns to check against.

    Returns:
        The formatted user prompt string.
    """
    pattern_descriptions = "\n".join(
        f"  - Pattern [{p.pattern_id}]: {p.pattern_signature} "
        f"(domain: {p.domain_id}, confidence: {p.confidence:.2f})"
        for p in patterns
    )

    return (
        f"Evaluate the following {language} code against these patterns.\n"
        f"\n"
        f"PATTERNS TO CHECK:\n"
        f"{pattern_descriptions}\n"
        f"\n"
        f"CODE TO EVALUATE:\n"
        f"```{language}\n"
        f"{content}\n"
        f"```\n"
        f"\n"
        f"For each pattern, determine if the code follows it. If not, report a violation.\n"
        f"\n"
        f"Respond with a JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "compliant": true/false,\n'
        f'  "confidence": 0.0-1.0,\n'
        f'  "violations": [\n'
        f"    {{\n"
        f'      "pattern_id": "the pattern ID",\n'
        f'      "description": "how the code violates the pattern",\n'
        f'      "severity": "critical|major|minor|info",\n'
        f'      "line_reference": "line N" or null\n'
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )


def parse_llm_response(
    *,
    raw_text: str,
    patterns: list[ModelApplicablePattern],
) -> ComplianceLlmResponseDict:
    """Parse the LLM response text into a structured compliance result.

    Extracts JSON from the LLM response, validates the structure, and
    enriches violations with pattern signature from the input patterns.

    Returns a structured error result (compliant=False, confidence=0.0) when
    parsing fails, rather than raising exceptions. This follows the ONEX
    handler convention: domain errors are data, not exceptions.

    Args:
        raw_text: Raw text response from the LLM.
        patterns: The patterns that were checked (for signature lookup).

    Returns:
        Parsed compliance result with violations. On parse failure, returns
        a result with compliant=False, confidence=0.0, empty violations,
        and the error detail in raw_response.
    """
    # Build a lookup for pattern signatures by ID.
    pattern_lookup: dict[str, str] = {
        p.pattern_id: p.pattern_signature for p in patterns
    }

    # Extract JSON from the response (handle markdown fences if present).
    json_text = _extract_json(raw_text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning(
            "LLM response is not valid JSON: %s. Raw (first 500 chars): %s",
            e,
            raw_text[:500],
        )
        return _parse_error_result(
            f"LLM response is not valid JSON: {e}. "
            f"Raw response (first 500 chars): {raw_text[:500]}"
        )

    if not isinstance(data, dict):
        logger.warning(
            "Expected JSON object, got %s. Raw (first 500 chars): %s",
            type(data).__name__,
            raw_text[:500],
        )
        return _parse_error_result(
            f"Expected JSON object, got {type(data).__name__}. "
            f"Raw response (first 500 chars): {raw_text[:500]}"
        )

    # Extract top-level fields with safe defaults.
    compliant = bool(data.get("compliant", True))
    confidence = _clamp_float(data.get("confidence", 0.5), 0.0, 1.0)

    raw_violations = data.get("violations", [])
    if not isinstance(raw_violations, list):
        raw_violations = []

    violations: list[ComplianceViolationDict] = []
    for raw_v in raw_violations:
        if not isinstance(raw_v, dict):
            continue

        pattern_id = str(raw_v.get("pattern_id", "unknown"))
        description = str(raw_v.get("description", "No description provided"))
        severity = str(raw_v.get("severity", "major")).lower()
        line_ref = raw_v.get("line_reference")

        # Normalize severity to valid values.
        if severity not in VALID_SEVERITIES:
            severity = "major"
        typed_severity = cast(SeverityLiteral, severity)

        # Look up the pattern signature from input patterns.
        pattern_signature = pattern_lookup.get(
            pattern_id, f"Unknown pattern: {pattern_id}"
        )

        violations.append(
            ComplianceViolationDict(
                pattern_id=pattern_id,
                pattern_signature=pattern_signature,
                description=description,
                severity=typed_severity,
                line_reference=str(line_ref) if line_ref is not None else None,
            )
        )

    # If violations exist, compliant must be False.
    if violations:
        compliant = False

    return ComplianceLlmResponseDict(
        compliant=compliant,
        violations=violations,
        confidence=confidence,
        raw_response=raw_text,
    )


def _parse_error_result(error_message: str) -> ComplianceLlmResponseDict:
    """Create a structured error result for parse failures.

    Args:
        error_message: Description of the parse failure.

    Returns:
        ComplianceLlmResponseDict indicating parse failure.
    """
    return ComplianceLlmResponseDict(
        compliant=False,
        violations=[],
        confidence=0.0,
        raw_response=error_message,
    )


def _extract_json(text: str) -> str:
    """Extract JSON from text that may contain markdown fences.

    Handles common LLM output formats:
        1. Pure JSON (no fences)
        2. ```json ... ``` fenced
        3. ``` ... ``` fenced

    Args:
        text: Raw text potentially containing JSON.

    Returns:
        The extracted JSON string.
    """
    stripped = text.strip()

    # Try to find JSON within markdown code fences.
    fence_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```",
        stripped,
        re.DOTALL,
    )
    if fence_match:
        return fence_match.group(1).strip()

    return stripped


def _clamp_float(value: object, min_val: float, max_val: float) -> float:
    """Clamp a value to a float within [min_val, max_val].

    Args:
        value: Value to clamp (will be converted to float).
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped float value.
    """
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return min_val
    return max(min_val, min(max_val, f))


__all__ = [
    "COMPLIANCE_PROMPT_VERSION",
    "build_compliance_prompt",
    "parse_llm_response",
]
