# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A clean compute node with no I/O violations.

This fixture represents a properly designed ONEX compute node that:
- Has no direct infrastructure client imports
- Does not access environment variables
- Performs no file I/O operations
- Receives all configuration via function parameters
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ComputeResult:
    """Result of a compute operation."""

    value: float
    metadata: dict[str, Any]


def compute_quality_score(
    code: str,
    weights: dict[str, float],
    threshold: float = 0.8,
) -> ComputeResult:
    """Compute a quality score for the given code.

    This is a pure function - no I/O, no side effects.

    Args:
        code: The source code to analyze.
        weights: Scoring weights for different metrics.
        threshold: Minimum acceptable score.

    Returns:
        ComputeResult with the computed score.
    """
    # Pure computation - no I/O
    lines = code.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]

    # Simple heuristic scoring
    score = min(1.0, len(non_empty_lines) / 100 * weights.get("lines", 1.0))

    return ComputeResult(
        value=score,
        metadata={
            "line_count": len(lines),
            "non_empty_lines": len(non_empty_lines),
            "meets_threshold": score >= threshold,
        },
    )


def transform_data(input_data: dict[str, Any]) -> dict[str, Any]:
    """Transform input data - pure function, no I/O."""
    return {
        key.upper(): value for key, value in input_data.items() if value is not None
    }
