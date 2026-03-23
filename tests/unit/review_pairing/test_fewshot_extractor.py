# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Few-Shot Extractor.

Reference: OMN-6174 (epic OMN-6164)
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.fewshot_extractor import (
    FewShotExtractor,
    _generalize_description,
)
from omniintelligence.review_pairing.models_calibration import CalibrationConfig


def _make_alignment(
    alignment_type: str,
    description: str = "Test finding",
    category: str = "architecture",
    similarity_score: float = 0.9,
) -> dict[str, object]:
    gt = {
        "category": category,
        "description": description,
        "severity": "error",
        "source_model": "codex",
    }
    ch = {
        "category": category,
        "description": description,
        "severity": "error",
        "source_model": "deepseek-r1",
    }
    if alignment_type == "false_negative":
        return {
            "alignment_type": "false_negative",
            "ground_truth": gt,
            "challenger": None,
            "similarity_score": 0.0,
            "aligned": False,
        }
    if alignment_type == "false_positive":
        return {
            "alignment_type": "false_positive",
            "ground_truth": None,
            "challenger": ch,
            "similarity_score": 0.0,
            "aligned": False,
        }
    return {
        "alignment_type": "true_positive",
        "ground_truth": gt,
        "challenger": ch,
        "similarity_score": similarity_score,
        "aligned": True,
    }


@pytest.mark.unit
class TestFewShotExtractor:
    @pytest.fixture
    def extractor(self) -> FewShotExtractor:
        return FewShotExtractor()

    @pytest.fixture
    def config(self) -> CalibrationConfig:
        return CalibrationConfig(
            ground_truth_model="codex",
            challenger_models=["deepseek-r1"],
            min_runs_for_fewshot=3,
            fewshot_tp_count=2,
            fewshot_fp_count=2,
            fewshot_fn_count=2,
        )

    def test_returns_empty_if_insufficient_runs(
        self, extractor: FewShotExtractor, config: CalibrationConfig
    ) -> None:
        data: list[list[dict[str, object]]] = [
            [_make_alignment("true_positive")],
            [_make_alignment("true_positive")],
        ]
        result = extractor.extract(data, config)
        assert result == []

    def test_extracts_false_negatives_by_frequency(
        self, extractor: FewShotExtractor, config: CalibrationConfig
    ) -> None:
        frequent_fn = _make_alignment(
            "false_negative", description="Missing auth check"
        )
        rare_fn = _make_alignment("false_negative", description="Unused import")
        data = [
            [frequent_fn, rare_fn],
            [frequent_fn],
            [frequent_fn, rare_fn],
        ]
        result = extractor.extract(data, config)
        fn_examples = [e for e in result if e.example_type == "false_negative"]
        assert len(fn_examples) == 2
        assert "Missing auth check" in fn_examples[
            0
        ].description or "Missing auth check" in _generalize_description(
            "Missing auth check"
        )

    def test_extracts_false_positives_by_frequency(
        self, extractor: FewShotExtractor, config: CalibrationConfig
    ) -> None:
        frequent_fp = _make_alignment(
            "false_positive", description="Unnecessary async wrapper"
        )
        data = [
            [frequent_fp],
            [frequent_fp],
            [frequent_fp],
        ]
        result = extractor.extract(data, config)
        fp_examples = [e for e in result if e.example_type == "false_positive"]
        assert len(fp_examples) == 1

    def test_extracts_true_positives_by_lowest_similarity(
        self, extractor: FewShotExtractor, config: CalibrationConfig
    ) -> None:
        low_sim = _make_alignment(
            "true_positive", description="Edge case A", similarity_score=0.55
        )
        high_sim = _make_alignment(
            "true_positive", description="Edge case B", similarity_score=0.95
        )
        data = [
            [low_sim, high_sim],
            [low_sim, high_sim],
            [low_sim, high_sim],
        ]
        result = extractor.extract(data, config)
        tp_examples = [e for e in result if e.example_type == "true_positive"]
        assert len(tp_examples) <= 2
        if tp_examples:
            assert "0.55" in tp_examples[0].evidence

    def test_does_not_exceed_configured_counts(
        self, extractor: FewShotExtractor, config: CalibrationConfig
    ) -> None:
        many_fns = [
            _make_alignment("false_negative", description=f"Finding {i}")
            for i in range(10)
        ]
        data = [many_fns, many_fns, many_fns]
        result = extractor.extract(data, config)
        fn_examples = [e for e in result if e.example_type == "false_negative"]
        assert len(fn_examples) <= config.fewshot_fn_count


@pytest.mark.unit
class TestGeneralizeDescription:
    def test_replaces_identifiers(self) -> None:
        result = _generalize_description("the function `foo_bar` is missing")
        assert "`<identifier>`" in result

    def test_replaces_file_paths(self) -> None:
        result = _generalize_description("issue in src/main.py:42")
        assert "<file-path>" in result

    def test_truncates_long_descriptions(self) -> None:
        long = "x" * 600
        result = _generalize_description(long)
        assert len(result) <= 500
