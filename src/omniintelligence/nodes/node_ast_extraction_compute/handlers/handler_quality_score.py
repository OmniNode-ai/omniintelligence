# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Multi-dimensional quality scorer for code entities.

Ported from Archive/omniarchon QualityScorer. Adapted to work on source code
strings and ModelCodeEntity metadata. All weights, thresholds, and patterns
read from contract config.

Scoring dimensions (configurable weights):
- complexity: cyclomatic + cognitive complexity via AST
- maintainability: readability, structure
- documentation: docstring coverage and quality
- temporal_relevance: how recently updated
- pattern_compliance: good patterns present
- architectural_compliance: ONEX patterns detected

Reference: OMN-5675
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from omniintelligence.nodes.node_ast_extraction_compute.models.model_quality_result import (
    ModelQualityResult,
)

logger = logging.getLogger(__name__)


class QualityScorer:
    """Scores code entities across 6 dimensions with configurable weights.

    All weights, thresholds, code smell patterns, and good patterns are
    read from contract config.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize from contract config's quality_scoring section."""
        self._weights = config.get(
            "weights",
            {
                "complexity": 0.20,
                "maintainability": 0.20,
                "documentation": 0.15,
                "temporal_relevance": 0.15,
                "pattern_compliance": 0.15,
                "architectural_compliance": 0.15,
            },
        )
        self._complexity = config.get(
            "complexity_thresholds",
            {
                "cyclomatic_low": 5,
                "cyclomatic_medium": 10,
                "cyclomatic_high": 15,
                "cognitive_low": 7,
                "cognitive_medium": 15,
                "max_lines_function": 50,
                "max_lines_class": 300,
            },
        )
        self._code_smells = config.get("code_smells", [])
        self._good_patterns = config.get("good_patterns", [])

    def score(
        self,
        *,
        source_code: str | None = None,
        entity_type: str = "function",
        entity_name: str = "",
    ) -> ModelQualityResult:
        """Score an entity across all dimensions.

        Args:
            source_code: Source code of the entity (None for imports etc).
            entity_type: Type of entity (class, function, import, etc).
            entity_name: Name of the entity.

        Returns:
            ModelQualityResult with overall score and per-dimension breakdown.
        """
        # Entities without source code get a default score
        if not source_code:
            return ModelQualityResult(
                overall_score=0.5,
                dimensions=dict.fromkeys(self._weights, 0.5),
            )

        dimensions: dict[str, float] = {}

        dimensions["complexity"] = self._score_complexity(source_code, entity_type)
        dimensions["maintainability"] = self._score_maintainability(
            source_code, entity_name
        )
        dimensions["documentation"] = self._score_documentation(source_code)
        dimensions["temporal_relevance"] = (
            0.7  # Default; actual freshness computed at query time (Invariant 5)
        )
        dimensions["pattern_compliance"] = self._score_pattern_compliance(source_code)
        dimensions["architectural_compliance"] = self._score_architectural_compliance(
            source_code
        )

        # Weighted sum
        overall = sum(
            dimensions.get(dim, 0.5) * weight for dim, weight in self._weights.items()
        )
        overall = max(0.0, min(1.0, overall))

        return ModelQualityResult(
            overall_score=round(overall, 4),
            dimensions={k: round(v, 4) for k, v in dimensions.items()},
        )

    def _score_complexity(self, source: str, entity_type: str) -> float:
        """Score based on cyclomatic complexity."""
        cyclomatic = self._calculate_cyclomatic_complexity(source)

        low = self._complexity.get("cyclomatic_low", 5)
        medium = self._complexity.get("cyclomatic_medium", 10)
        high = self._complexity.get("cyclomatic_high", 15)

        if cyclomatic <= low:
            return 0.9
        elif cyclomatic <= medium:
            return 0.7
        elif cyclomatic <= high:
            return 0.4
        else:
            return 0.2

    def _score_maintainability(self, source: str, entity_name: str) -> float:
        """Score readability and structure."""
        lines = source.split("\n")
        factors: list[float] = []

        # Naming quality
        if re.match(r"[a-z_][a-z0-9_]+", entity_name, re.I):
            factors.append(0.8)
        else:
            factors.append(0.4)

        # Line length
        long_lines = sum(1 for line in lines if len(line) > 100)
        if long_lines < len(lines) * 0.2:
            factors.append(0.7)
        else:
            factors.append(0.4)

        # Reasonable size
        if len(lines) <= 50:
            factors.append(0.9)
        elif len(lines) <= 150:
            factors.append(0.7)
        else:
            factors.append(0.4)

        return sum(factors) / len(factors) if factors else 0.5

    def _score_documentation(self, source: str) -> float:
        """Score documentation quality."""
        score = 0.0
        if re.search(r'""".*?"""', source, re.DOTALL):
            score += 0.5
        if re.search(r"->\s*\w+", source):
            score += 0.3
        comment_lines = len(re.findall(r"^\s*#[^!]", source, re.MULTILINE))
        code_lines = len(
            [
                line
                for line in source.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
        )
        ratio = comment_lines / max(code_lines, 1)
        if ratio > 0.1:
            score += 0.2
        elif ratio > 0.05:
            score += 0.1
        return min(score, 1.0)

    def _score_pattern_compliance(self, source: str) -> float:
        """Score based on code smell and good pattern detection."""
        score = 0.5

        # Good patterns (bonuses)
        for pattern_def in self._good_patterns:
            pattern = pattern_def.get("pattern", "")
            bonus = pattern_def.get("bonus", 0.0)
            if pattern and re.search(pattern, source, re.DOTALL):
                score += bonus * 0.1

        # Code smells (penalties)
        for smell_def in self._code_smells:
            pattern = smell_def.get("pattern", "")
            penalty = smell_def.get("penalty", 0.0)
            if pattern and re.search(pattern, source, re.DOTALL):
                score += penalty * 0.1  # penalty is negative

        return max(0.0, min(1.0, score))

    def _score_architectural_compliance(self, source: str) -> float:
        """Score ONEX architectural pattern compliance."""
        score = 0.7

        # Check for good patterns
        if re.search(r":\s*Protocol", source):
            score += 0.1
        if re.search(r"raise\s+\w+Error\(", source):
            score += 0.05
        if re.search(r"from\s+typing\s+import", source):
            score += 0.05

        # Check for issues
        if re.search(r"from\s+.*\s+import\s+\*", source):
            score -= 0.3
        if re.search(r"global\s+\w+", source):
            score -= 0.2

        return max(0.0, min(1.0, score))

    @staticmethod
    def _calculate_cyclomatic_complexity(source: str) -> int:
        """Calculate cyclomatic complexity by counting decision points via AST."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Fall back to regex counting
            decision_points = (
                len(re.findall(r"\bif\b", source))
                + len(re.findall(r"\belif\b", source))
                + len(re.findall(r"\bwhile\b", source))
                + len(re.findall(r"\bfor\b", source))
                + len(re.findall(r"\band\b", source))
                + len(re.findall(r"\bor\b", source))
                + len(re.findall(r"\bexcept\b", source))
            )
            return max(1, decision_points + 1)

        decision_types = (
            ast.If,
            ast.For,
            ast.While,
            ast.ExceptHandler,
            ast.BoolOp,  # and/or
        )
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, decision_types):
                if isinstance(node, ast.BoolOp):
                    # Each BoolOp has n-1 operators
                    count += len(node.values) - 1
                else:
                    count += 1
        return max(1, count + 1)
