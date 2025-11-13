"""
Pattern Extractor Module
=========================

Main orchestration module for AST-based pattern extraction.

This module ties together:
- AST parsing (ast_parser)
- Pattern classification (classifier)
- Complexity metrics (metrics)

Provides high-level API for extracting code patterns from Python files.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from pattern_extraction.ast_parser import ASTParser, ClassNode, FunctionNode
from pattern_extraction.classifier import PatternClassifier
from pattern_extraction.metrics import MetricsCalculator


class PatternExtractor:
    """
    Main pattern extraction orchestrator.

    Extracts code patterns from Python files by:
    1. Parsing source code into AST
    2. Extracting functions and classes
    3. Classifying pattern types
    4. Calculating complexity metrics
    5. Generating structured pattern data

    Example:
        extractor = PatternExtractor()
        patterns = extractor.extract_from_file("my_module.py")

        for pattern in patterns:
            print(f"{pattern['pattern_name']}: {pattern['complexity']}")
    """

    def __init__(self):
        """Initialize pattern extractor."""
        self.parser = ASTParser()
        self.classifier = PatternClassifier()
        self.metrics_calculator = MetricsCalculator()

    def extract_from_file(self, file_path: str) -> List[Dict]:
        """
        Extract patterns from a Python file.

        Args:
            file_path: Path to Python source file

        Returns:
            List of pattern dictionaries with:
                - pattern_name: Name of the pattern
                - pattern_type: Type of pattern (function/class/design)
                - category: Specific category
                - file_path: Source file path
                - line_range: [start, end] line numbers
                - implementation: Source code
                - complexity: Cyclomatic complexity
                - maintainability_index: MI score
                - tags: List of descriptive tags
                - docstring: Documentation (if any)

        Raises:
            FileNotFoundError: If file does not exist
            SyntaxError: If file contains invalid Python syntax
        """
        # Parse file
        self.parser.parse_file(file_path)

        patterns = []

        # Extract function patterns
        functions = self.parser.extract_functions()
        for func in functions:
            pattern = self._create_function_pattern(func, file_path)
            if pattern:
                patterns.append(pattern)

        # Extract class patterns
        classes = self.parser.extract_classes()
        for cls in classes:
            pattern = self._create_class_pattern(cls, file_path)
            if pattern:
                patterns.append(pattern)

        return patterns

    def extract_from_source(
        self, source_code: str, source_name: str = "<source>"
    ) -> List[Dict]:
        """
        Extract patterns from Python source code string.

        Args:
            source_code: Python source code
            source_name: Name to identify the source (default: "<source>")

        Returns:
            List of pattern dictionaries (same format as extract_from_file)

        Raises:
            SyntaxError: If source contains invalid Python syntax
        """
        # Parse source
        self.parser.parse_source(source_code)

        patterns = []

        # Extract function patterns
        functions = self.parser.extract_functions()
        for func in functions:
            pattern = self._create_function_pattern(func, source_name)
            if pattern:
                patterns.append(pattern)

        # Extract class patterns
        classes = self.parser.extract_classes()
        for cls in classes:
            pattern = self._create_class_pattern(cls, source_name)
            if pattern:
                patterns.append(pattern)

        return patterns

    def extract_from_directory(
        self, directory_path: str, recursive: bool = True, pattern: str = "*.py"
    ) -> Dict[str, List[Dict]]:
        """
        Extract patterns from all Python files in a directory.

        Args:
            directory_path: Path to directory
            recursive: Whether to search recursively (default: True)
            pattern: File pattern to match (default: "*.py")

        Returns:
            Dictionary mapping file paths to lists of patterns

        Raises:
            NotADirectoryError: If directory_path is not a directory
        """
        directory = Path(directory_path)

        if not directory.is_dir():
            raise NotADirectoryError(f"{directory_path} is not a directory")

        results = {}

        # Find all Python files
        if recursive:
            python_files = directory.rglob(pattern)
        else:
            python_files = directory.glob(pattern)

        # Extract patterns from each file
        for file_path in python_files:
            try:
                patterns = self.extract_from_file(str(file_path))
                if patterns:  # Only include files with patterns
                    results[str(file_path)] = patterns
            except (SyntaxError, Exception) as e:
                # Skip files with errors
                print(f"Warning: Skipping {file_path}: {e}")
                continue

        return results

    def _create_function_pattern(
        self, func: FunctionNode, file_path: str
    ) -> Optional[Dict]:
        """
        Create pattern dictionary from FunctionNode.

        Args:
            func: FunctionNode to process
            file_path: Source file path

        Returns:
            Pattern dictionary or None if pattern should be skipped
        """
        # Classify the function
        classification = self.classifier.classify_function(func)

        # Get source code segment
        implementation = self.parser.get_source_segment(func.line_start, func.line_end)

        # Calculate metrics
        try:
            # Use the full source for context
            full_source = "\n".join(self.parser.source_lines)
            metrics = self.metrics_calculator.calculate_function_metrics(
                full_source, func.name
            )

            complexity = metrics.cyclomatic_complexity
            maintainability = metrics.maintainability_index
            complexity_grade = metrics.complexity_grade
        except (ValueError, Exception):
            # Fallback if metrics calculation fails
            complexity = 0
            maintainability = 0.0
            complexity_grade = "N/A"

        # Build pattern dictionary
        pattern = {
            "pattern_name": func.name,
            "pattern_type": classification["pattern_type"].value,
            "category": classification["category"].value,
            "file_path": file_path,
            "line_range": [func.line_start, func.line_end],
            "implementation": implementation,
            "complexity": complexity,
            "maintainability_index": maintainability,
            "complexity_grade": complexity_grade,
            "tags": classification["tags"],
            "docstring": func.docstring,
            "is_async": func.is_async,
            "decorators": func.decorators,
            "confidence": classification["confidence"],
        }

        return pattern

    def _create_class_pattern(self, cls: ClassNode, file_path: str) -> Optional[Dict]:
        """
        Create pattern dictionary from ClassNode.

        Args:
            cls: ClassNode to process
            file_path: Source file path

        Returns:
            Pattern dictionary or None if pattern should be skipped
        """
        # Classify the class
        classification = self.classifier.classify_class(cls)

        # Get source code segment
        implementation = self.parser.get_source_segment(cls.line_start, cls.line_end)

        # Calculate metrics
        try:
            # Use the full source for context
            full_source = "\n".join(self.parser.source_lines)
            metrics = self.metrics_calculator.calculate_class_metrics(
                full_source, cls.name
            )

            complexity = metrics.cyclomatic_complexity
            maintainability = metrics.maintainability_index
            complexity_grade = metrics.complexity_grade
        except (ValueError, Exception):
            # Fallback if metrics calculation fails
            complexity = 0
            maintainability = 0.0
            complexity_grade = "N/A"

        # Build pattern dictionary
        pattern = {
            "pattern_name": cls.name,
            "pattern_type": classification["pattern_type"].value,
            "category": classification["category"].value,
            "file_path": file_path,
            "line_range": [cls.line_start, cls.line_end],
            "implementation": implementation,
            "complexity": complexity,
            "maintainability_index": maintainability,
            "complexity_grade": complexity_grade,
            "tags": classification["tags"],
            "docstring": cls.docstring,
            "base_classes": cls.bases,
            "methods": cls.methods,
            "decorators": cls.decorators,
            "confidence": classification["confidence"],
        }

        return pattern

    def export_patterns_json(self, patterns: List[Dict], output_file: str):
        """
        Export patterns to JSON file.

        Args:
            patterns: List of pattern dictionaries
            output_file: Path to output JSON file
        """
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2)

    def get_pattern_summary(self, patterns: List[Dict]) -> Dict:
        """
        Get summary statistics for extracted patterns.

        Args:
            patterns: List of pattern dictionaries

        Returns:
            Dictionary with summary statistics:
                - total_patterns: Total number of patterns
                - by_type: Count by pattern type
                - by_category: Count by category
                - avg_complexity: Average complexity
                - avg_maintainability: Average maintainability index
                - high_complexity: Patterns with complexity > 10
        """
        if not patterns:
            return {
                "total_patterns": 0,
                "by_type": {},
                "by_category": {},
                "avg_complexity": 0.0,
                "avg_maintainability": 0.0,
                "high_complexity": [],
            }

        # Count by type
        by_type = {}
        for pattern in patterns:
            ptype = pattern["pattern_type"]
            by_type[ptype] = by_type.get(ptype, 0) + 1

        # Count by category
        by_category = {}
        for pattern in patterns:
            category = pattern["category"]
            by_category[category] = by_category.get(category, 0) + 1

        # Calculate averages
        complexities = [p["complexity"] for p in patterns if p["complexity"] > 0]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0.0

        maintainabilities = [
            p["maintainability_index"]
            for p in patterns
            if p["maintainability_index"] > 0
        ]
        avg_maintainability = (
            sum(maintainabilities) / len(maintainabilities)
            if maintainabilities
            else 0.0
        )

        # Find high complexity patterns
        high_complexity = [
            {
                "name": p["pattern_name"],
                "complexity": p["complexity"],
                "file": p["file_path"],
            }
            for p in patterns
            if p["complexity"] > 10
        ]

        return {
            "total_patterns": len(patterns),
            "by_type": by_type,
            "by_category": by_category,
            "avg_complexity": round(avg_complexity, 2),
            "avg_maintainability": round(avg_maintainability, 2),
            "high_complexity": high_complexity,
        }


# Example usage
if __name__ == "__main__":
    # Example: Extract patterns from this file
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = __file__  # Analyze this file

    extractor = PatternExtractor()

    print(f"Extracting patterns from: {file_path}\n")

    try:
        patterns = extractor.extract_from_file(file_path)

        print(f"Found {len(patterns)} patterns:\n")

        for i, pattern in enumerate(patterns, 1):
            print(f"{i}. {pattern['pattern_name']}")
            print(f"   Type: {pattern['pattern_type']}")
            print(f"   Category: {pattern['category']}")
            print(
                f"   Complexity: {pattern['complexity']} ({pattern['complexity_grade']})"
            )
            print(f"   Maintainability: {pattern['maintainability_index']:.2f}")
            print(f"   Tags: {', '.join(pattern['tags'])}")
            print()

        # Print summary
        summary = extractor.get_pattern_summary(patterns)
        print("\n=== SUMMARY ===")
        print(f"Total patterns: {summary['total_patterns']}")
        print(f"Average complexity: {summary['avg_complexity']}")
        print(f"Average maintainability: {summary['avg_maintainability']}")

        if summary["high_complexity"]:
            print(f"\nHigh complexity patterns ({len(summary['high_complexity'])}):")
            for item in summary["high_complexity"]:
                print(f"  - {item['name']}: {item['complexity']}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
