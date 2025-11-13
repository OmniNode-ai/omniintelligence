"""
Pattern Extraction Module
==========================

AST-based pattern extraction engine for identifying reusable code patterns
from Python source files.

This module provides:
- AST parsing for Python source code analysis
- Pattern classification (function, class, design patterns)
- Complexity metrics calculation using radon
- Pattern extraction orchestration

Components:
- ast_parser: Low-level AST parsing and node extraction
- classifier: Pattern type classification and categorization
- metrics: Code complexity and quality metrics
- extractor: High-level pattern extraction orchestration

Usage:
    from pattern_extraction import PatternExtractor

    extractor = PatternExtractor()
    patterns = extractor.extract_from_file("path/to/file.py")

    for pattern in patterns:
        print(f"{pattern['pattern_name']}: {pattern['complexity']}")
"""

from pattern_extraction.ast_parser import ASTParser
from pattern_extraction.classifier import PatternClassifier
from pattern_extraction.extractor import PatternExtractor
from pattern_extraction.metrics import MetricsCalculator

__all__ = [
    "PatternExtractor",
    "ASTParser",
    "PatternClassifier",
    "MetricsCalculator",
]

__version__ = "1.0.0"
