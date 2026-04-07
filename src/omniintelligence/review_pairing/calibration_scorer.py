# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Scorer for computing precision/recall/noise metrics.

Computes ModelCalibrationMetrics from a list of ModelFindingAlignment results.

Reference: OMN-6168
"""

from __future__ import annotations

from omniintelligence.review_pairing.models_calibration import (
    ModelCalibrationMetrics,
    ModelFindingAlignment,
)


class CalibrationScorer:
    """Computes calibration metrics from alignment results."""

    def score(
        self,
        alignments: list[ModelFindingAlignment],
        model: str,
    ) -> ModelCalibrationMetrics:
        """Compute precision, recall, F1, and noise ratio from alignments.

        Args:
            alignments: List of ModelFindingAlignment records from the alignment engine.
            model: Model key for these metrics.

        Returns:
            ModelCalibrationMetrics with computed values.
        """
        tp = sum(1 for a in alignments if a.alignment_type == "true_positive")
        fp = sum(1 for a in alignments if a.alignment_type == "false_positive")
        fn = sum(1 for a in alignments if a.alignment_type == "false_negative")

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        noise_ratio = fp / (tp + fp) if (tp + fp) > 0 else 0.0

        return ModelCalibrationMetrics(
            model=model,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            noise_ratio=noise_ratio,
        )
