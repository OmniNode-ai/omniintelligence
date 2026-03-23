# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Few-Shot Extractor for calibration examples.

Extracts the highest-value TP/FP/FN examples from calibration history
for few-shot prompt injection.

Reference: OMN-6174 (epic OMN-6164)
"""

from __future__ import annotations

import re
from collections import Counter

from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    FewShotExample,
)


class FewShotExtractor:
    """Extracts few-shot examples from historical calibration alignment data."""

    def extract(
        self,
        alignment_details: list[list[dict[str, object]]],
        config: CalibrationConfig,
    ) -> list[FewShotExample]:
        """Extract few-shot examples from historical alignment data.

        Args:
            alignment_details: List of alignment detail lists loaded from DB.
                Each inner list contains alignment dicts from one run.
            config: Calibration configuration with few-shot counts.

        Returns:
            List of FewShotExample instances, empty if insufficient data.
        """
        if len(alignment_details) < config.min_runs_for_fewshot:
            return []

        fn_examples = self._extract_false_negatives(alignment_details, config)
        fp_examples = self._extract_false_positives(alignment_details, config)
        tp_examples = self._extract_true_positives(alignment_details, config)

        return fn_examples + fp_examples + tp_examples

    def _extract_false_negatives(
        self,
        alignment_details: list[list[dict[str, object]]],
        config: CalibrationConfig,
    ) -> list[FewShotExample]:
        """Extract false negatives ranked by recurrence frequency."""
        fn_descriptions: list[str] = []
        fn_by_desc: dict[str, dict[str, object]] = {}

        for run in alignment_details:
            for a in run:
                if a.get("alignment_type") == "false_negative" and a.get(
                    "ground_truth"
                ):
                    gt = a["ground_truth"]
                    if isinstance(gt, dict):
                        desc = str(gt.get("description", ""))
                        fn_descriptions.append(desc)
                        if desc not in fn_by_desc:
                            fn_by_desc[desc] = gt

        freq = Counter(fn_descriptions)
        top = freq.most_common(config.fewshot_fn_count)

        return [
            FewShotExample(
                example_type="false_negative",
                category=str(fn_by_desc[desc].get("category", "unknown")),
                description=_generalize_description(desc),
                evidence=f"Missed by challenger in {count}/{len(alignment_details)} runs",
                ground_truth_present=True,
                explanation=(
                    f"Ground truth found this issue but challenger missed it "
                    f"in {count} of {len(alignment_details)} calibration runs."
                ),
            )
            for desc, count in top
            if desc in fn_by_desc
        ]

    def _extract_false_positives(
        self,
        alignment_details: list[list[dict[str, object]]],
        config: CalibrationConfig,
    ) -> list[FewShotExample]:
        """Extract false positives ranked by recurrence frequency."""
        fp_descriptions: list[str] = []
        fp_by_desc: dict[str, dict[str, object]] = {}

        for run in alignment_details:
            for a in run:
                if a.get("alignment_type") == "false_positive" and a.get("challenger"):
                    ch = a["challenger"]
                    if isinstance(ch, dict):
                        desc = str(ch.get("description", ""))
                        fp_descriptions.append(desc)
                        if desc not in fp_by_desc:
                            fp_by_desc[desc] = ch

        freq = Counter(fp_descriptions)
        top = freq.most_common(config.fewshot_fp_count)

        return [
            FewShotExample(
                example_type="false_positive",
                category=str(fp_by_desc[desc].get("category", "unknown")),
                description=_generalize_description(desc),
                evidence=f"Raised by challenger but not in ground truth in {count}/{len(alignment_details)} runs",
                ground_truth_present=False,
                explanation=(
                    f"Challenger flagged this as an issue but ground truth "
                    f"did not confirm it in {count} of {len(alignment_details)} runs. "
                    f"This is likely noise."
                ),
            )
            for desc, count in top
            if desc in fp_by_desc
        ]

    def _extract_true_positives(
        self,
        alignment_details: list[list[dict[str, object]]],
        config: CalibrationConfig,
    ) -> list[FewShotExample]:
        """Extract true positives with lowest similarity scores (boundary examples)."""
        boundary_tps: list[tuple[float, dict[str, object]]] = []

        for run in alignment_details:
            for a in run:
                if (
                    a.get("alignment_type") == "true_positive"
                    and a.get("aligned") is True
                    and a.get("ground_truth")
                ):
                    score = float(a.get("similarity_score", 1.0))
                    gt = a["ground_truth"]
                    if isinstance(gt, dict):
                        boundary_tps.append((score, gt))

        boundary_tps.sort(key=lambda x: x[0])
        top = boundary_tps[: config.fewshot_tp_count]

        return [
            FewShotExample(
                example_type="true_positive",
                category=str(gt.get("category", "unknown")),
                description=_generalize_description(str(gt.get("description", ""))),
                evidence=f"Matched with similarity score {score:.2f} (near threshold)",
                ground_truth_present=True,
                explanation=(
                    f"Both models found this issue but with only {score:.2f} "
                    f"similarity, indicating the challenger's description diverges "
                    f"from ground truth."
                ),
            )
            for score, gt in top
        ]


def _generalize_description(desc: str) -> str:
    """Generalize a description by replacing specific identifiers with placeholders.

    Prevents proprietary plan content from leaking into prompt files.
    """
    result = re.sub(r"`[a-zA-Z_][a-zA-Z0-9_]*`", "`<identifier>`", desc)
    result = re.sub(
        r'"[^"]{1,60}"',
        '"<string>"',
        result,
    )
    result = re.sub(
        r"[A-Za-z/]+\.[a-z]{2,4}(?::\d+)?",
        "<file-path>",
        result,
    )
    return result[:500]
