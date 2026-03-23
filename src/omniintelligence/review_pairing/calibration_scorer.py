# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Calibration Scorer: computes precision/recall/noise from alignment results.

Reference: OMN-6168 (epic OMN-6164)
"""

from __future__ import annotations

from omniintelligence.review_pairing.models_calibration import (
    CalibrationMetrics,
    FindingAlignment,
)


class CalibrationScorer:
    """Computes calibration metrics from alignment results."""

    def score(
        self,
        alignments: list[FindingAlignment],
        ground_truth_count: int,
        challenger_count: int,
        model: str,
    ) -> CalibrationMetrics:
        """Compute precision, recall, F1, and noise ratio from alignments.

        Args:
            alignments: List of FindingAlignment records from the alignment engine.
            ground_truth_count: Total number of ground-truth findings.
            challenger_count: Total number of challenger findings.
            model: Challenger model key.

        Returns:
            CalibrationMetrics with computed scores.
        """
        tp = sum(
            1 for a in alignments if a.aligned and a.alignment_type == "true_positive"
        )
        fp = challenger_count - tp
        fn = ground_truth_count - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if (precision + recall) > 0.0
            else 0.0
        )
        noise = fp / challenger_count if challenger_count > 0 else 0.0

        return CalibrationMetrics(
            model=model,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 6),
            recall=round(recall, 6),
            f1_score=round(f1, 6),
            noise_ratio=round(noise, 6),
        )
