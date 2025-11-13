"""
Metrics Calculator Module
==========================

Calculates code complexity and quality metrics using radon.

This module provides:
- Cyclomatic complexity calculation
- Maintainability index calculation
- Halstead metrics
- Lines of code metrics
- Complexity scoring and categorization
"""

from dataclasses import dataclass
from typing import Dict, Optional

try:
    from radon.complexity import cc_visit
    from radon.metrics import h_visit, mi_visit
    from radon.raw import analyze

    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False


@dataclass
class ComplexityMetrics:
    """
    Code complexity metrics.

    Attributes:
        cyclomatic_complexity: Cyclomatic complexity score
        maintainability_index: Maintainability index (0-100)
        lines_of_code: Total lines of code
        logical_lines: Logical lines of code
        comment_lines: Number of comment lines
        blank_lines: Number of blank lines
        halstead_difficulty: Halstead difficulty metric
        halstead_effort: Halstead effort metric
        complexity_grade: Complexity grade (A-F)
    """

    cyclomatic_complexity: int
    maintainability_index: float
    lines_of_code: int
    logical_lines: int
    comment_lines: int
    blank_lines: int
    halstead_difficulty: Optional[float]
    halstead_effort: Optional[float]
    complexity_grade: str


class MetricsCalculator:
    """
    Calculates code complexity and quality metrics.

    Uses radon library for industry-standard metrics:
    - Cyclomatic Complexity (McCabe)
    - Maintainability Index
    - Halstead metrics
    - Raw metrics (LOC, LLOC, etc.)
    """

    # Complexity grade thresholds
    GRADE_THRESHOLDS = {
        "A": 5,  # Simple
        "B": 10,  # Well structured
        "C": 20,  # Complex
        "D": 30,  # Very complex
        "E": 40,  # Extremely complex
        "F": float("inf"),  # Unmaintainable
    }

    def __init__(self):
        """
        Initialize metrics calculator.

        Raises:
            ImportError: If radon library is not installed
        """
        if not RADON_AVAILABLE:
            raise ImportError(
                "radon library is required for metrics calculation. "
                "Install with: pip install radon"
            )

    def calculate_function_metrics(
        self, source_code: str, function_name: str
    ) -> ComplexityMetrics:
        """
        Calculate metrics for a specific function.

        Args:
            source_code: Python source code containing the function
            function_name: Name of the function to analyze

        Returns:
            ComplexityMetrics for the function

        Raises:
            ValueError: If function not found in source code
        """
        # Calculate cyclomatic complexity
        cc_results = cc_visit(source_code)

        # Find the target function
        target_cc = None
        for result in cc_results:
            if result.name == function_name:
                target_cc = result
                break

        if target_cc is None:
            raise ValueError(f"Function '{function_name}' not found in source code")

        # Calculate raw metrics for the entire source
        raw_metrics = analyze(source_code)

        # Calculate Halstead metrics
        halstead_metrics = h_visit(source_code)
        halstead_difficulty = None
        halstead_effort = None

        if halstead_metrics:
            halstead_difficulty = halstead_metrics[0].difficulty
            halstead_effort = halstead_metrics[0].effort

        # Calculate maintainability index
        mi_score = mi_visit(source_code, multi=False)

        # Determine complexity grade
        complexity_grade = self._calculate_grade(target_cc.complexity)

        return ComplexityMetrics(
            cyclomatic_complexity=target_cc.complexity,
            maintainability_index=mi_score,
            lines_of_code=raw_metrics.loc,
            logical_lines=raw_metrics.lloc,
            comment_lines=raw_metrics.comments,
            blank_lines=raw_metrics.blank,
            halstead_difficulty=halstead_difficulty,
            halstead_effort=halstead_effort,
            complexity_grade=complexity_grade,
        )

    def calculate_class_metrics(
        self, source_code: str, class_name: str
    ) -> ComplexityMetrics:
        """
        Calculate metrics for a specific class.

        Args:
            source_code: Python source code containing the class
            class_name: Name of the class to analyze

        Returns:
            ComplexityMetrics for the class (aggregated from all methods)

        Raises:
            ValueError: If class not found in source code
        """
        # Calculate cyclomatic complexity for all functions
        cc_results = cc_visit(source_code)

        # Find the target class and its methods
        class_found = False
        total_complexity = 0

        for result in cc_results:
            # Check if this is the class itself
            if type(result).__name__ == "Class" and result.name == class_name:
                class_found = True
                total_complexity = result.complexity
                break
            # Check if this is a method of our class (for Function results)
            elif hasattr(result, "classname") and result.classname == class_name:
                class_found = True
                total_complexity += result.complexity

        if not class_found:
            raise ValueError(f"Class '{class_name}' not found in source code")

        # Calculate raw metrics
        raw_metrics = analyze(source_code)

        # Calculate Halstead metrics
        halstead_metrics = h_visit(source_code)
        halstead_difficulty = None
        halstead_effort = None

        if halstead_metrics:
            halstead_difficulty = halstead_metrics[0].difficulty
            halstead_effort = halstead_metrics[0].effort

        # Calculate maintainability index
        mi_score = mi_visit(source_code, multi=False)

        # Determine complexity grade based on total complexity
        complexity_grade = self._calculate_grade(total_complexity)

        return ComplexityMetrics(
            cyclomatic_complexity=total_complexity,
            maintainability_index=mi_score,
            lines_of_code=raw_metrics.loc,
            logical_lines=raw_metrics.lloc,
            comment_lines=raw_metrics.comments,
            blank_lines=raw_metrics.blank,
            halstead_difficulty=halstead_difficulty,
            halstead_effort=halstead_effort,
            complexity_grade=complexity_grade,
        )

    def calculate_metrics(self, source_code: str) -> Dict[str, any]:
        """
        Calculate overall metrics for source code.

        Args:
            source_code: Python source code to analyze

        Returns:
            Dictionary with overall metrics
        """
        # Calculate raw metrics
        raw_metrics = analyze(source_code)

        # Calculate cyclomatic complexity
        cc_results = cc_visit(source_code)
        total_complexity = sum(result.complexity for result in cc_results)
        avg_complexity = total_complexity / len(cc_results) if cc_results else 0

        # Calculate Halstead metrics
        halstead_metrics = h_visit(source_code)
        halstead_difficulty = None
        halstead_effort = None
        halstead_volume = None

        if halstead_metrics:
            halstead_difficulty = halstead_metrics[0].difficulty
            halstead_effort = halstead_metrics[0].effort
            halstead_volume = halstead_metrics[0].volume

        # Calculate maintainability index
        mi_score = mi_visit(source_code, multi=False)

        return {
            "lines_of_code": raw_metrics.loc,
            "logical_lines": raw_metrics.lloc,
            "comment_lines": raw_metrics.comments,
            "blank_lines": raw_metrics.blank,
            "total_complexity": total_complexity,
            "average_complexity": avg_complexity,
            "maintainability_index": mi_score,
            "halstead_difficulty": halstead_difficulty,
            "halstead_effort": halstead_effort,
            "halstead_volume": halstead_volume,
            "function_count": len(cc_results),
        }

    def _calculate_grade(self, complexity: int) -> str:
        """
        Calculate complexity grade based on cyclomatic complexity.

        Args:
            complexity: Cyclomatic complexity score

        Returns:
            Grade letter (A-F)
        """
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if complexity <= threshold:
                return grade
        return "F"

    def get_complexity_interpretation(self, complexity: int) -> str:
        """
        Get human-readable interpretation of complexity score.

        Args:
            complexity: Cyclomatic complexity score

        Returns:
            Human-readable interpretation
        """
        if complexity <= 5:
            return "Simple, easy to understand and maintain"
        elif complexity <= 10:
            return "Well-structured, moderately complex"
        elif complexity <= 20:
            return "Complex, consider refactoring"
        elif complexity <= 30:
            return "Very complex, refactoring recommended"
        elif complexity <= 40:
            return "Extremely complex, high risk"
        else:
            return "Unmaintainable, immediate refactoring required"

    def get_maintainability_interpretation(self, mi_score: float) -> str:
        """
        Get human-readable interpretation of maintainability index.

        Args:
            mi_score: Maintainability index (0-100)

        Returns:
            Human-readable interpretation
        """
        if mi_score >= 80:
            return "Highly maintainable"
        elif mi_score >= 60:
            return "Moderately maintainable"
        elif mi_score >= 40:
            return "Low maintainability, needs improvement"
        else:
            return "Very low maintainability, critical issues"
