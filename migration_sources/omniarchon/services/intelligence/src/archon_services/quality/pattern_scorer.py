"""
Pattern Quality Scoring System

Purpose: Calculate comprehensive quality scores for code patterns based on:
- Complexity (cyclomatic complexity analysis)
- Documentation (docstrings, type hints)
- Test coverage (percentage of lines covered)
- Reusability (cross-file usage patterns)
- Maintainability (coupling, cohesion analysis)

Migration Date: 2025-10-28
ONEX Compliance: Yes
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from radon.complexity import cc_visit
from radon.metrics import h_visit, mi_visit


class PatternScorer:
    """
    Calculate quality scores for code patterns using multiple weighted metrics.

    Quality Score Formula:
        quality_score = (
            complexity_score * 0.30 +      # Cyclomatic complexity < 10
            documentation_score * 0.20 +   # Has docstring + type hints
            test_coverage_score * 0.20 +   # % covered by tests
            reusability_score * 0.15 +     # Used in multiple files
            maintainability_score * 0.15   # Low coupling, high cohesion
        )

    Score Range: 0.0 to 1.0 (higher is better)
    """

    # Weights for each scoring component
    WEIGHTS = {
        "complexity": 0.30,
        "documentation": 0.20,
        "test_coverage": 0.20,
        "reusability": 0.15,
        "maintainability": 0.15,
    }

    # Complexity thresholds (cyclomatic complexity)
    COMPLEXITY_THRESHOLDS = {
        "excellent": (0, 10, 1.0),  # CC < 10: score = 1.0
        "good": (10, 20, 0.7),  # CC 10-20: score = 0.7
        "poor": (20, float("inf"), 0.4),  # CC > 20: score = 0.4
    }

    # Reusability thresholds (number of files using pattern)
    REUSABILITY_THRESHOLDS = {
        "low": (1, 2, 0.3),  # 1 file: score = 0.3
        "medium": (2, 5, 0.6),  # 2-5 files: score = 0.6
        "high": (5, float("inf"), 1.0),  # 5+ files: score = 1.0
    }

    def __init__(self, coverage_data: Optional[Dict[str, Any]] = None):
        """
        Initialize the pattern scorer.

        Args:
            coverage_data: Optional coverage data from coverage.py
                          Format: {file_path: {'covered_lines': [...], 'total_lines': N}}
        """
        self.coverage_data = coverage_data or {}

    def calculate_overall_quality(
        self,
        code: str,
        file_path: Optional[str] = None,
        usage_count: int = 1,
    ) -> Dict[str, Any]:
        """
        Calculate overall quality score for a code pattern.

        Args:
            code: Source code to analyze
            file_path: Optional file path for coverage lookup
            usage_count: Number of files using this pattern

        Returns:
            Dictionary with:
                - quality_score: Overall score (0.0-1.0)
                - components: Individual component scores
                - details: Detailed metrics for each component
        """
        try:
            # Parse code to AST for analysis
            tree = ast.parse(code)
        except SyntaxError as e:
            # Return minimal score for unparseable code
            return {
                "quality_score": 0.0,
                "components": {},
                "details": {"error": f"Syntax error: {str(e)}"},
                "reproducible": True,
            }

        # Calculate individual component scores
        complexity_score = self.calculate_complexity_score(code)
        documentation_score = self.calculate_documentation_score(tree)
        test_coverage_score = self.calculate_test_coverage_score(file_path)
        reusability_score = self.calculate_reusability_score(usage_count)
        maintainability_score = self.calculate_maintainability_score(tree, code)

        # Calculate weighted overall score
        quality_score = (
            complexity_score * self.WEIGHTS["complexity"]
            + documentation_score * self.WEIGHTS["documentation"]
            + test_coverage_score * self.WEIGHTS["test_coverage"]
            + reusability_score * self.WEIGHTS["reusability"]
            + maintainability_score * self.WEIGHTS["maintainability"]
        )

        return {
            "quality_score": round(quality_score, 4),
            "components": {
                "complexity": round(complexity_score, 4),
                "documentation": round(documentation_score, 4),
                "test_coverage": round(test_coverage_score, 4),
                "reusability": round(reusability_score, 4),
                "maintainability": round(maintainability_score, 4),
            },
            "weights": self.WEIGHTS,
            "reproducible": True,
        }

    def calculate_complexity_score(self, code: str) -> float:
        """
        Calculate complexity score based on cyclomatic complexity.

        Uses radon to analyze cyclomatic complexity:
        - CC < 10: score = 1.0 (excellent)
        - CC 10-20: score = 0.7 (good)
        - CC > 20: score = 0.4 (poor)

        Args:
            code: Source code to analyze

        Returns:
            Score from 0.0 to 1.0
        """
        try:
            # Calculate cyclomatic complexity using radon
            complexity_results = cc_visit(code)

            if not complexity_results:
                # No complexity found (empty file or only simple statements)
                return 1.0

            # Get average complexity across all functions/classes
            avg_complexity = sum(
                result.complexity for result in complexity_results
            ) / len(complexity_results)

            # Map complexity to score using thresholds
            for threshold_name, (
                min_val,
                max_val,
                score,
            ) in self.COMPLEXITY_THRESHOLDS.items():
                if min_val <= avg_complexity < max_val:
                    return score

            # Default to poor score if thresholds don't match
            return 0.4

        except Exception:
            # Return neutral score on error
            return 0.5

    def calculate_documentation_score(self, tree: ast.AST) -> float:
        """
        Calculate documentation score based on docstrings and type hints.

        Scoring:
        - Has docstring: +0.5
        - Has type hints: +0.5

        Args:
            tree: AST of the code

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Check for docstrings
        has_docstring = self._has_docstring(tree)
        if has_docstring:
            score += 0.5

        # Check for type hints
        has_type_hints = self._has_type_hints(tree)
        if has_type_hints:
            score += 0.5

        return score

    def calculate_test_coverage_score(self, file_path: Optional[str] = None) -> float:
        """
        Calculate test coverage score as percentage of lines covered.

        Args:
            file_path: Path to the file to check coverage for

        Returns:
            Score from 0.0 to 1.0 (percentage of lines covered)
        """
        if not file_path or not self.coverage_data:
            # No coverage data available - return neutral score
            return 0.5

        # Normalize file path
        file_path = str(Path(file_path).resolve())

        if file_path not in self.coverage_data:
            # File not in coverage data - return neutral score
            return 0.5

        coverage_info = self.coverage_data[file_path]
        covered_lines = len(coverage_info.get("covered_lines", []))
        total_lines = coverage_info.get("total_lines", 0)

        if total_lines == 0:
            return 0.5

        # Return percentage as score
        return covered_lines / total_lines

    def calculate_reusability_score(self, usage_count: int) -> float:
        """
        Calculate reusability score based on cross-file usage.

        Scoring:
        - Used in 1 file: 0.3
        - Used in 2-5 files: 0.6
        - Used in 5+ files: 1.0

        Args:
            usage_count: Number of files using this pattern

        Returns:
            Score from 0.0 to 1.0
        """
        for threshold_name, (
            min_val,
            max_val,
            score,
        ) in self.REUSABILITY_THRESHOLDS.items():
            if min_val <= usage_count < max_val:
                return score

        # Default to high score for very high usage
        return 1.0

    def calculate_maintainability_score(self, tree: ast.AST, code: str) -> float:
        """
        Calculate maintainability score based on coupling and cohesion.

        Scoring:
        - Low coupling (few dependencies): +0.5
        - High cohesion (single responsibility): +0.5

        Args:
            tree: AST of the code
            code: Source code string

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Check coupling (number of imports)
        coupling_score = self._calculate_coupling_score(tree)
        score += coupling_score * 0.5

        # Check cohesion (single responsibility indicator)
        cohesion_score = self._calculate_cohesion_score(tree, code)
        score += cohesion_score * 0.5

        return score

    def _has_docstring(self, tree: ast.AST) -> bool:
        """Check if code has docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    return True
        return False

    def _has_type_hints(self, tree: ast.AST) -> bool:
        """Check if code has type hints."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function return type
                if node.returns is not None:
                    return True
                # Check parameter type hints
                for arg in node.args.args:
                    if arg.annotation is not None:
                        return True
        return False

    def _calculate_coupling_score(self, tree: ast.AST) -> float:
        """
        Calculate coupling score based on number of imports.

        Low coupling (0-5 imports): 1.0
        Medium coupling (6-10 imports): 0.6
        High coupling (10+ imports): 0.3
        """
        import_count = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_count += 1

        if import_count <= 5:
            return 1.0
        elif import_count <= 10:
            return 0.6
        else:
            return 0.3

    def _calculate_cohesion_score(self, tree: ast.AST, code: str) -> float:
        """
        Calculate cohesion score using maintainability index.

        Uses radon's maintainability index (0-100):
        - MI >= 20: High cohesion (1.0)
        - MI 10-20: Medium cohesion (0.6)
        - MI < 10: Low cohesion (0.3)
        """
        try:
            # Calculate maintainability index using radon
            mi_results = mi_visit(code, multi=True)

            if not mi_results:
                return 0.5  # Neutral score

            # Get average MI across all functions/classes
            avg_mi = sum(result.mi for result in mi_results) / len(mi_results)

            # Map MI to cohesion score
            if avg_mi >= 20:
                return 1.0
            elif avg_mi >= 10:
                return 0.6
            else:
                return 0.3

        except Exception:
            return 0.5  # Neutral score on error

    def batch_calculate_quality(
        self,
        patterns: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Calculate quality scores for multiple patterns.

        Args:
            patterns: List of pattern dictionaries with 'code', 'file_path', 'usage_count'

        Returns:
            List of quality score dictionaries
        """
        results = []

        for pattern in patterns:
            code = pattern.get("code", "")
            file_path = pattern.get("file_path")
            usage_count = pattern.get("usage_count", 1)

            quality_result = self.calculate_overall_quality(
                code=code,
                file_path=file_path,
                usage_count=usage_count,
            )

            # Add pattern identifier to result
            quality_result["pattern_id"] = pattern.get("id")
            quality_result["pattern_name"] = pattern.get("name")

            results.append(quality_result)

        return results
