# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for weight configuration validation.

This module tests weight configuration validation:
    - Default weights sum to 1.0
    - Invalid weight keys return structured error
    - Extra weight keys return structured error
    - Weight sum validation returns structured error

Per CLAUDE.md handler pattern, validation errors are domain errors
returned as structured output with success=False, not raised.
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_quality_scoring_compute.handlers import (
    DEFAULT_WEIGHTS,
    score_code_quality,
)


class TestWeightValidation:
    """Tests for weight configuration validation."""

    def test_default_weights_sum_to_one(self) -> None:
        """DEFAULT_WEIGHTS should sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_invalid_weight_keys_return_error(self) -> None:
        """Weights with invalid keys should return structured error.

        Per CLAUDE.md handler pattern, validation errors are domain errors
        returned as structured output with success=False, not raised.
        """
        invalid_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            # Missing: documentation, temporal_relevance, patterns, architectural
        }
        result = score_code_quality("x = 1", "python", weights=invalid_weights)
        assert result["success"] is False
        assert result["quality_score"] == 0.0
        assert any("missing" in r.lower() for r in result["recommendations"])
        assert any("validation_error" in r.lower() for r in result["recommendations"])

    def test_extra_weight_keys_return_error(self) -> None:
        """Weights with extra keys should return structured error.

        Per CLAUDE.md handler pattern, validation errors are domain errors
        returned as structured output with success=False, not raised.
        """
        extra_weights = {
            "complexity": 0.15,
            "maintainability": 0.15,
            "documentation": 0.15,
            "temporal_relevance": 0.15,
            "patterns": 0.15,
            "architectural": 0.15,
            "extra_dimension": 0.10,  # Not a valid dimension
        }
        result = score_code_quality("x = 1", "python", weights=extra_weights)
        assert result["success"] is False
        assert result["quality_score"] == 0.0
        assert any("extra" in r.lower() for r in result["recommendations"])
        assert any("validation_error" in r.lower() for r in result["recommendations"])

    def test_weights_not_summing_to_one_return_error(self) -> None:
        """Weights not summing to 1.0 should return structured error.

        Per CLAUDE.md handler pattern, validation errors are domain errors
        returned as structured output with success=False, not raised.
        """
        bad_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            "documentation": 0.5,
            "temporal_relevance": 0.5,
            "patterns": 0.5,
            "architectural": 0.5,  # Sum = 3.0
        }
        result = score_code_quality("x = 1", "python", weights=bad_weights)
        assert result["success"] is False
        assert result["quality_score"] == 0.0
        assert any("sum" in r.lower() for r in result["recommendations"])
        assert any("validation_error" in r.lower() for r in result["recommendations"])
