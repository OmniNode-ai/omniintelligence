# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Few-shot example extractor for the Review Calibration Loop.

Selects high-value TP and FP examples from calibration history to inject
into adversarial reviewer prompts.

Reference: OMN-6174
"""

from __future__ import annotations

from collections import Counter

from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationRunResult,
    FewShotExample,
    FindingAlignment,
)


class FewShotExtractor:
    """Extracts few-shot examples from calibration run history.

    Algorithm:
    1. Filter to valid (non-error) runs, check min_runs threshold.
    2. Collect all alignments across valid runs.
    3. TPs: deduplicate by description, rank by best similarity_score DESC.
    4. FPs: rank by recurrence frequency (how many runs contain that description).
    5. Format as FewShotExample with explanation text.
    """

    def extract(
        self,
        runs: list[CalibrationRunResult],
        config: CalibrationConfig,
    ) -> list[FewShotExample]:
        valid_runs = [r for r in runs if r.error is None and r.metrics is not None]

        if len(valid_runs) < config.min_runs_for_fewshot:
            return []

        all_alignments: list[FindingAlignment] = []
        for run in valid_runs:
            all_alignments.extend(run.alignments)

        tp_examples = self._extract_tps(all_alignments, config.fewshot_tp_count)
        fp_examples = self._extract_fps(valid_runs, config.fewshot_fp_count)

        return tp_examples + fp_examples

    def _extract_tps(
        self,
        alignments: list[FindingAlignment],
        count: int,
    ) -> list[FewShotExample]:
        if count <= 0:
            return []

        tps = [a for a in alignments if a.alignment_type == "true_positive"]

        # Deduplicate by description, keeping the highest similarity score
        best_by_desc: dict[str, FindingAlignment] = {}
        for tp in tps:
            desc = tp.challenger.description if tp.challenger else ""
            existing = best_by_desc.get(desc)
            if existing is None or tp.similarity_score > existing.similarity_score:
                best_by_desc[desc] = tp

        ranked = sorted(
            best_by_desc.values(),
            key=lambda a: a.similarity_score,
            reverse=True,
        )

        return [self._tp_to_example(a) for a in ranked[:count]]

    def _extract_fps(
        self,
        runs: list[CalibrationRunResult],
        count: int,
    ) -> list[FewShotExample]:
        if count <= 0:
            return []

        # Count how many runs each FP description appears in
        freq: Counter[str] = Counter()
        fp_by_desc: dict[str, FindingAlignment] = {}

        for run in runs:
            seen_in_run: set[str] = set()
            for a in run.alignments:
                if a.alignment_type != "false_positive":
                    continue
                desc = a.challenger.description if a.challenger else ""
                if desc not in seen_in_run:
                    freq[desc] += 1
                    seen_in_run.add(desc)
                if desc not in fp_by_desc:
                    fp_by_desc[desc] = a

        ranked_descs = [desc for desc, _ in freq.most_common()]

        return [
            self._fp_to_example(fp_by_desc[desc], freq[desc])
            for desc in ranked_descs[:count]
        ]

    @staticmethod
    def _tp_to_example(alignment: FindingAlignment) -> FewShotExample:
        challenger = alignment.challenger
        category = challenger.category if challenger else "unknown"
        description = challenger.description if challenger else ""
        return FewShotExample(
            example_type="true_positive",
            category=category,
            description=description,
            evidence=f"similarity_score={alignment.similarity_score:.3f}",
            ground_truth_present=True,
            explanation=(
                f"Both ground truth and challenger identified this {category} issue "
                f"with {alignment.similarity_score:.0%} confidence."
            ),
        )

    @staticmethod
    def _fp_to_example(
        alignment: FindingAlignment,
        frequency: int,
    ) -> FewShotExample:
        challenger = alignment.challenger
        category = challenger.category if challenger else "unknown"
        description = challenger.description if challenger else ""
        return FewShotExample(
            example_type="false_positive",
            category=category,
            description=description,
            evidence=f"recurrence_frequency={frequency}",
            ground_truth_present=False,
            explanation=(
                f"Challenger flagged this {category} issue but ground truth did not. "
                f"Recurred in {frequency} run(s) — likely a systematic noise pattern."
            ),
        )
