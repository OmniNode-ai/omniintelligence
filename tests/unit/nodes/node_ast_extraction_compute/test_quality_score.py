# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for Quality Scorer (OMN-5675)."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_quality_score import (
    QualityScorer,
)

QUALITY_CONFIG: dict = {
    "enabled": True,
    "weights": {
        "complexity": 0.20,
        "maintainability": 0.20,
        "documentation": 0.15,
        "temporal_relevance": 0.15,
        "pattern_compliance": 0.15,
        "architectural_compliance": 0.15,
    },
    "complexity_thresholds": {
        "cyclomatic_low": 5,
        "cyclomatic_medium": 10,
        "cyclomatic_high": 15,
        "cognitive_low": 7,
        "cognitive_medium": 15,
        "max_lines_function": 50,
        "max_lines_class": 300,
    },
    "code_smells": [
        {
            "pattern": r"def\s+\w+\([^)]{50,}\):",
            "name": "long_parameter_list",
            "penalty": -0.6,
        },
        {"pattern": r"global\s+\w+", "name": "global_variable", "penalty": -0.8},
        {"pattern": r"eval\(", "name": "eval_usage", "penalty": -0.9},
        {"pattern": r"import\s+\*", "name": "wildcard_import", "penalty": -0.4},
    ],
    "good_patterns": [
        {
            "pattern": r"def\s+\w+\(.*?\)\s*->\s*\w+:",
            "name": "type_annotations",
            "bonus": 0.8,
        },
        {
            "pattern": r"class\s+\w+\(.*Protocol.*\):",
            "name": "protocol_interface",
            "bonus": 0.9,
        },
        {"pattern": r'""".*?"""', "name": "docstring_present", "bonus": 0.7},
    ],
}


@pytest.mark.unit
class TestQualityScorer:
    """Tests for multi-dimensional quality scoring."""

    def test_high_quality_code(self) -> None:
        """Well-structured code with docstring and type hints scores high."""
        scorer = QualityScorer(QUALITY_CONFIG)
        source = '''
def calculate_total(items: list[float]) -> float:
    """Calculate the total sum of all items."""
    total = 0.0
    for item in items:
        total += item
    return total
'''
        result = scorer.score(source_code=source, entity_name="calculate_total")
        assert result.overall_score > 0.6
        assert "complexity" in result.dimensions
        assert "documentation" in result.dimensions

    def test_low_quality_complex_code(self) -> None:
        """Complex code with many branches scores low on complexity."""
        scorer = QualityScorer(QUALITY_CONFIG)
        # Generate code with high cyclomatic complexity (20+)
        branches = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(20))
        source = f"def complex_func(x):\n{branches}\n    return -1"

        result = scorer.score(source_code=source, entity_name="complex_func")
        assert result.overall_score < 0.7
        assert result.dimensions["complexity"] < 0.5

    def test_default_score_for_imports(self) -> None:
        """Entities without source code get default 0.5."""
        scorer = QualityScorer(QUALITY_CONFIG)
        result = scorer.score(source_code=None, entity_type="import", entity_name="os")
        assert result.overall_score == 0.5
        assert all(v == 0.5 for v in result.dimensions.values())

    def test_code_smell_detection(self) -> None:
        """Code with eval() and global gets penalized."""
        scorer = QualityScorer(QUALITY_CONFIG)
        source = """
global counter
def process(data):
    result = eval(data)
    return result
"""
        result = scorer.score(source_code=source, entity_name="process")
        # Pattern compliance should be low due to code smells
        assert result.dimensions["pattern_compliance"] < 0.5

    def test_good_pattern_bonus(self) -> None:
        """Code with Protocol and type annotations gets bonuses."""
        scorer = QualityScorer(QUALITY_CONFIG)
        source = '''
class MyHandler(Protocol):
    """Handler protocol for processing events."""
    def handle(self, event: str) -> bool:
        ...
'''
        result = scorer.score(source_code=source, entity_name="MyHandler")
        assert result.dimensions["pattern_compliance"] > 0.5
