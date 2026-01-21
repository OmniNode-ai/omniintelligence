# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for weight configuration validation.

This module tests weight configuration validation:
    - Default weights sum to 1.0
    - Invalid weight keys
    - Extra weight keys
    - Weight sum validation
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.quality_scoring_compute.handlers import (
    DEFAULT_WEIGHTS,
    score_code_quality,
)
from omniintelligence.nodes.quality_scoring_compute.handlers.exceptions import (
    QualityScoringValidationError,
)


class TestWeightValidation:
    """Tests for weight configuration validation."""

    def test_default_weights_sum_to_one(self) -> None:
        """DEFAULT_WEIGHTS should sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_invalid_weight_keys_raise_error(self) -> None:
        """Weights with invalid keys should raise QualityScoringValidationError."""
        invalid_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            # Missing: documentation, temporal_relevance, patterns, architectural
        }
        with pytest.raises(QualityScoringValidationError, match="[Mm]issing"):
            score_code_quality("x = 1", "python", weights=invalid_weights)

    def test_extra_weight_keys_raise_error(self) -> None:
        """Weights with extra keys should raise QualityScoringValidationError."""
        extra_weights = {
            "complexity": 0.15,
            "maintainability": 0.15,
            "documentation": 0.15,
            "temporal_relevance": 0.15,
            "patterns": 0.15,
            "architectural": 0.15,
            "extra_dimension": 0.10,  # Not a valid dimension
        }
        with pytest.raises(QualityScoringValidationError, match="[Ee]xtra"):
            score_code_quality("x = 1", "python", weights=extra_weights)

    def test_weights_not_summing_to_one_raise_error(self) -> None:
        """Weights not summing to 1.0 should raise QualityScoringValidationError."""
        bad_weights = {
            "complexity": 0.5,
            "maintainability": 0.5,
            "documentation": 0.5,
            "temporal_relevance": 0.5,
            "patterns": 0.5,
            "architectural": 0.5,  # Sum = 3.0
        }
        with pytest.raises(QualityScoringValidationError, match="sum"):
            score_code_quality("x = 1", "python", weights=bad_weights)
