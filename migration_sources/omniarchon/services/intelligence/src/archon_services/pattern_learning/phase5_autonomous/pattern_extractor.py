"""
Pattern Extractor Service

Autonomous pattern extraction from successful code validations using AST analysis.
Extracts architectural, quality, security, and ONEX compliance patterns.

Created: 2025-10-15 (MVP Phase 5A)
Purpose: Self-improving pattern learning through autonomous discovery
"""

import ast
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from src.archon_services.pattern_learning.phase5_autonomous.models.model_extracted_pattern import (
    ExtractedPattern,
    PatternCategory,
)

logger = logging.getLogger(__name__)


class PatternExtractor:
    """
    Extract patterns from successful code validations using Python AST analysis.

    Analyzes code that passes validation to identify:
    - Architectural patterns (inheritance, composition, mixins)
    - Quality patterns (error handling, type hints, documentation)
    - Security patterns (input validation, sanitization)
    - ONEX patterns (container usage, structured logging, node base classes)

    Usage:
        extractor = PatternExtractor()
        patterns = await extractor.extract_patterns(
            code="class NodeExample(NodeBase): pass",
            validation_result={"is_valid": True, "quality_score": 0.9},
            node_type="effect"
        )
    """

    # Known ONEX base classes
    ONEX_BASE_CLASSES = {
        "NodeBase",
        "NodeEffect",
        "NodeCompute",
        "NodeReducer",
        "NodeOrchestrator",
        "EffectNode",
        "ComputeNode",
        "ReducerNode",
        "OrchestratorNode",
    }

    # Known ONEX mixins
    ONEX_MIXINS = {
        "EventBusMixin",
        "CachingMixin",
        "HealthCheckMixin",
        "MetricsMixin",
        "RetryMixin",
        "CircuitBreakerMixin",
        "ValidationMixin",
        "PerformanceTrackerMixin",
        "AggregationMixin",
        "StateManagementMixin",
        "PersistenceMixin",
        "WorkflowMixin",
        "DependencyManagementMixin",
        "ErrorHandlingMixin",
    }

    # ONEX container patterns
    ONEX_CONTAINER_PATTERNS = [
        r"Container\[",
        r"from omnibase\.container import",
        r"@inject_dependencies",
        r"self\.container",
    ]

    # Structured logging patterns
    ONEX_LOGGING_PATTERNS = [
        r"StructuredLogger",
        r"correlation_id",
        r"logger\.info\(.*correlation_id",
        r"extra=\{.*correlation_id",
    ]

    def __init__(self):
        """Initialize pattern extractor."""
        self.known_patterns: Dict[str, ExtractedPattern] = {}
        self.pattern_frequency: Dict[str, int] = {}

    async def extract_patterns(
        self,
        code: str,
        validation_result: Dict[str, Any],
        node_type: str,
        file_path: Optional[str] = None,
    ) -> List[ExtractedPattern]:
        """
        Extract patterns from code that passed validation.

        Analyzes successful code to identify reusable patterns across 4 categories:
        - Architectural: Base classes, mixins, composition
        - Quality: Error handling, type hints, documentation
        - Security: Input validation, sanitization
        - ONEX: Container usage, logging, compliance

        Args:
            code: Python source code that passed validation
            validation_result: Validation result dictionary with quality scores
            node_type: Type of node (effect, compute, reducer, orchestrator)
            file_path: Optional file path for context

        Returns:
            List of extracted patterns with confidence scores
        """
        patterns: List[ExtractedPattern] = []

        # Only extract patterns from successful validations
        if not validation_result.get("is_valid", False):
            logger.debug("Skipping pattern extraction for failed validation")
            return patterns

        # Parse code into AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Failed to parse code for pattern extraction: {e}")
            return patterns

        logger.info(
            f"Extracting patterns from {node_type} node "
            f"(quality_score={validation_result.get('quality_score', 0.0):.2f})"
        )

        # Extract patterns from each category
        patterns.extend(
            self._extract_architectural_patterns(tree, node_type, file_path)
        )
        patterns.extend(self._extract_quality_patterns(tree, file_path))
        patterns.extend(self._extract_security_patterns(tree, file_path))
        patterns.extend(self._extract_onex_patterns(tree, code, node_type, file_path))

        # Update pattern frequency and confidence
        for pattern in patterns:
            self._update_pattern_tracking(pattern, validation_result)

        logger.info(
            f"Extracted {len(patterns)} patterns: "
            f"architectural={sum(1 for p in patterns if p.pattern_category == PatternCategory.ARCHITECTURAL)}, "
            f"quality={sum(1 for p in patterns if p.pattern_category == PatternCategory.QUALITY)}, "
            f"security={sum(1 for p in patterns if p.pattern_category == PatternCategory.SECURITY)}, "
            f"onex={sum(1 for p in patterns if p.pattern_category == PatternCategory.ONEX)}"
        )

        return patterns

    def _extract_architectural_patterns(
        self,
        tree: ast.AST,
        node_type: str,
        file_path: Optional[str] = None,
    ) -> List[ExtractedPattern]:
        """
        Extract architectural patterns (inheritance, composition, mixins).

        Looks for:
        - Base class inheritance patterns (NodeBase, NodeEffect, etc.)
        - Mixin composition patterns
        - Design pattern implementations

        Args:
            tree: Parsed AST tree
            node_type: Node type (effect, compute, reducer, orchestrator)
            file_path: Optional file path for context

        Returns:
            List of architectural patterns found
        """
        patterns: List[ExtractedPattern] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract base class patterns
                if node.bases:
                    base_names = [self._get_name(base) for base in node.bases]

                    # Check for ONEX base class inheritance
                    onex_bases = [b for b in base_names if b in self.ONEX_BASE_CLASSES]
                    if onex_bases:
                        pattern_id = (
                            f"arch_base_{node_type}_{self._hash_list(onex_bases)}"
                        )

                        pattern = ExtractedPattern(
                            pattern_id=pattern_id,
                            pattern_category=PatternCategory.ARCHITECTURAL,
                            pattern_type="base_class_inheritance",
                            code_snippet=f"class {node.name}({', '.join(base_names)})",
                            context={
                                "node_type": node_type,
                                "bases": base_names,
                                "onex_bases": onex_bases,
                                "class_name": node.name,
                                "file_path": file_path,
                            },
                            confidence=0.9,  # High confidence for explicit base classes
                            metadata={
                                "category": "inheritance",
                                "ast_node_type": "ClassDef",
                                "line_number": (
                                    node.lineno if hasattr(node, "lineno") else None
                                ),
                            },
                        )
                        patterns.append(pattern)

                    # Extract mixin composition patterns
                    mixin_bases = [
                        b for b in base_names if "Mixin" in b or b in self.ONEX_MIXINS
                    ]
                    if mixin_bases:
                        pattern_id = f"arch_mixin_{self._hash_list(mixin_bases)}"

                        pattern = ExtractedPattern(
                            pattern_id=pattern_id,
                            pattern_category=PatternCategory.ARCHITECTURAL,
                            pattern_type="mixin_composition",
                            code_snippet=f"Mixins: {', '.join(mixin_bases)}",
                            context={
                                "mixins": mixin_bases,
                                "node_type": node_type,
                                "class_name": node.name,
                                "file_path": file_path,
                            },
                            confidence=0.85,  # Slightly lower confidence for mixins
                            metadata={
                                "category": "composition",
                                "ast_node_type": "ClassDef",
                                "mixin_count": len(mixin_bases),
                                "line_number": (
                                    node.lineno if hasattr(node, "lineno") else None
                                ),
                            },
                        )
                        patterns.append(pattern)

                # Check for method patterns (execute_effect, execute_compute, etc.)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = item.name
                        if method_name.startswith("execute_") or method_name in [
                            "run_effect",
                            "compute",
                            "reduce",
                        ]:
                            pattern_id = f"arch_method_{node_type}_{method_name}"

                            pattern = ExtractedPattern(
                                pattern_id=pattern_id,
                                pattern_category=PatternCategory.ARCHITECTURAL,
                                pattern_type="onex_method_implementation",
                                code_snippet=f"async def {method_name}(self, ...)",
                                context={
                                    "method_name": method_name,
                                    "node_type": node_type,
                                    "class_name": node.name,
                                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                                    "file_path": file_path,
                                },
                                confidence=0.95,  # Very high confidence for ONEX methods
                                metadata={
                                    "category": "method_implementation",
                                    "ast_node_type": "FunctionDef",
                                    "line_number": (
                                        item.lineno if hasattr(item, "lineno") else None
                                    ),
                                },
                            )
                            patterns.append(pattern)

        return patterns

    def _extract_quality_patterns(
        self,
        tree: ast.AST,
        file_path: Optional[str] = None,
    ) -> List[ExtractedPattern]:
        """
        Extract quality patterns (error handling, type hints, documentation).

        Looks for:
        - Try/except/finally error handling
        - Type annotations on functions and methods
        - Docstrings and documentation
        - Logging statements

        Args:
            tree: Parsed AST tree
            file_path: Optional file path for context

        Returns:
            List of quality patterns found
        """
        patterns: List[ExtractedPattern] = []

        for node in ast.walk(tree):
            # Error handling patterns
            if isinstance(node, ast.Try):
                has_finally = bool(node.finalbody)
                has_else = bool(node.orelse)
                exception_types = []

                for handler in node.handlers:
                    if handler.type:
                        exception_types.append(self._get_name(handler.type))

                pattern_id = (
                    f"quality_error_handling_{self._hash_list(exception_types)}"
                )

                pattern = ExtractedPattern(
                    pattern_id=pattern_id,
                    pattern_category=PatternCategory.QUALITY,
                    pattern_type="error_handling",
                    code_snippet="try/except with proper exception handling",
                    context={
                        "has_finally": has_finally,
                        "has_else": has_else,
                        "exception_types": exception_types,
                        "handler_count": len(node.handlers),
                        "file_path": file_path,
                    },
                    confidence=0.8,
                    metadata={
                        "category": "error_handling",
                        "ast_node_type": "Try",
                        "line_number": node.lineno if hasattr(node, "lineno") else None,
                    },
                )
                patterns.append(pattern)

            # Type hint patterns
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_return_type = node.returns is not None
                has_arg_types = any(arg.annotation for arg in node.args.args)

                if has_return_type or has_arg_types:
                    pattern_id = f"quality_type_hints_{node.name}"

                    # Count typed arguments
                    typed_arg_count = sum(1 for arg in node.args.args if arg.annotation)
                    total_arg_count = len(node.args.args)

                    pattern = ExtractedPattern(
                        pattern_id=pattern_id,
                        pattern_category=PatternCategory.QUALITY,
                        pattern_type="type_annotations",
                        code_snippet=f"def {node.name}(...) -> ...",
                        context={
                            "function": node.name,
                            "has_return_type": has_return_type,
                            "typed_arg_count": typed_arg_count,
                            "total_arg_count": total_arg_count,
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                            "file_path": file_path,
                        },
                        confidence=0.9,  # High confidence for type safety
                        metadata={
                            "category": "type_safety",
                            "ast_node_type": "FunctionDef",
                            "line_number": (
                                node.lineno if hasattr(node, "lineno") else None
                            ),
                        },
                    )
                    patterns.append(pattern)

                # Docstring patterns
                if ast.get_docstring(node):
                    docstring = ast.get_docstring(node)
                    pattern_id = f"quality_docstring_{node.name}"

                    # Analyze docstring quality
                    has_args_section = (
                        "Args:" in docstring or "Parameters:" in docstring
                    )
                    has_returns_section = "Returns:" in docstring
                    has_raises_section = "Raises:" in docstring

                    pattern = ExtractedPattern(
                        pattern_id=pattern_id,
                        pattern_category=PatternCategory.QUALITY,
                        pattern_type="documentation",
                        code_snippet=f'"""{docstring[:50]}..."""',
                        context={
                            "function": node.name,
                            "docstring_length": len(docstring),
                            "has_args_section": has_args_section,
                            "has_returns_section": has_returns_section,
                            "has_raises_section": has_raises_section,
                            "file_path": file_path,
                        },
                        confidence=0.75,
                        metadata={
                            "category": "documentation",
                            "ast_node_type": "FunctionDef",
                            "line_number": (
                                node.lineno if hasattr(node, "lineno") else None
                            ),
                        },
                    )
                    patterns.append(pattern)

        return patterns

    def _extract_security_patterns(
        self,
        tree: ast.AST,
        file_path: Optional[str] = None,
    ) -> List[ExtractedPattern]:
        """
        Extract security patterns (validation, sanitization).

        Looks for:
        - Input validation at function entry
        - Parameter checking and assertion
        - Sanitization calls

        Args:
            tree: Parsed AST tree
            file_path: Optional file path for context

        Returns:
            List of security patterns found
        """
        patterns: List[ExtractedPattern] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for input validation in first few statements
                validation_found = False
                validation_types = []

                for stmt in node.body[:3]:  # Check first 3 statements
                    if isinstance(stmt, ast.If):
                        validation_found = True
                        validation_types.append("conditional_check")
                    elif isinstance(stmt, ast.Assert):
                        validation_found = True
                        validation_types.append("assertion")
                    elif isinstance(stmt, ast.Raise):
                        validation_found = True
                        validation_types.append("early_raise")

                if validation_found:
                    pattern_id = f"security_input_validation_{node.name}"

                    pattern = ExtractedPattern(
                        pattern_id=pattern_id,
                        pattern_category=PatternCategory.SECURITY,
                        pattern_type="input_validation",
                        code_snippet="Input validation at function start",
                        context={
                            "function": node.name,
                            "validation_types": validation_types,
                            "arg_count": len(node.args.args),
                            "file_path": file_path,
                        },
                        confidence=0.85,
                        metadata={
                            "category": "validation",
                            "ast_node_type": "FunctionDef",
                            "line_number": (
                                node.lineno if hasattr(node, "lineno") else None
                            ),
                        },
                    )
                    patterns.append(pattern)

        return patterns

    def _extract_onex_patterns(
        self,
        tree: ast.AST,
        code: str,
        node_type: str,
        file_path: Optional[str] = None,
    ) -> List[ExtractedPattern]:
        """
        Extract ONEX compliance patterns.

        Looks for:
        - Container usage and dependency injection
        - Structured logging with correlation IDs
        - Transaction management
        - ONEX naming conventions

        Args:
            tree: Parsed AST tree
            code: Raw source code for regex matching
            node_type: Node type (effect, compute, reducer, orchestrator)
            file_path: Optional file path for context

        Returns:
            List of ONEX patterns found
        """
        patterns: List[ExtractedPattern] = []

        # Container pattern detection (regex-based)
        container_usage = any(
            re.search(pattern, code) for pattern in self.ONEX_CONTAINER_PATTERNS
        )
        if container_usage:
            pattern_id = "onex_container_usage"

            pattern = ExtractedPattern(
                pattern_id=pattern_id,
                pattern_category=PatternCategory.ONEX,
                pattern_type="container_dependency_injection",
                code_snippet="Container usage for dependency injection",
                context={
                    "has_container": True,
                    "node_type": node_type,
                    "file_path": file_path,
                },
                confidence=0.95,  # Very high confidence for explicit container usage
                metadata={
                    "category": "dependency_injection",
                    "pattern_source": "regex",
                },
            )
            patterns.append(pattern)

        # Structured logging pattern detection
        structured_logging = any(
            re.search(pattern, code) for pattern in self.ONEX_LOGGING_PATTERNS
        )
        if structured_logging:
            pattern_id = "onex_structured_logging"

            pattern = ExtractedPattern(
                pattern_id=pattern_id,
                pattern_category=PatternCategory.ONEX,
                pattern_type="structured_logging",
                code_snippet="Structured logging with correlation IDs",
                context={
                    "has_structured_logging": True,
                    "has_correlation_id": "correlation_id" in code,
                    "node_type": node_type,
                    "file_path": file_path,
                },
                confidence=0.9,
                metadata={
                    "category": "observability",
                    "pattern_source": "regex",
                },
            )
            patterns.append(pattern)

        # Transaction management patterns (AST-based)
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                # Check for transaction context managers
                for item in node.items:
                    context_expr = item.context_expr
                    if isinstance(context_expr, ast.Attribute):
                        attr_name = self._get_full_attribute_name(context_expr)
                        if (
                            "transaction" in attr_name.lower()
                            or "begin" in attr_name.lower()
                        ):
                            pattern_id = "onex_transaction_management"

                            pattern = ExtractedPattern(
                                pattern_id=pattern_id,
                                pattern_category=PatternCategory.ONEX,
                                pattern_type="transaction_management",
                                code_snippet=f"async with {attr_name}:",
                                context={
                                    "context_manager": attr_name,
                                    "node_type": node_type,
                                    "file_path": file_path,
                                },
                                confidence=0.85,
                                metadata={
                                    "category": "data_consistency",
                                    "ast_node_type": "With",
                                    "line_number": (
                                        node.lineno if hasattr(node, "lineno") else None
                                    ),
                                },
                            )
                            patterns.append(pattern)

        # ONEX naming convention patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                # Check for ONEX naming patterns: Node<Name><Type>
                if class_name.startswith("Node") and any(
                    class_name.endswith(suffix)
                    for suffix in ["Effect", "Compute", "Reducer", "Orchestrator"]
                ):
                    pattern_id = f"onex_naming_convention_{class_name}"

                    pattern = ExtractedPattern(
                        pattern_id=pattern_id,
                        pattern_category=PatternCategory.ONEX,
                        pattern_type="naming_convention",
                        code_snippet=f"class {class_name}",
                        context={
                            "class_name": class_name,
                            "node_type": node_type,
                            "follows_convention": True,
                            "file_path": file_path,
                        },
                        confidence=1.0,  # Perfect confidence for naming conventions
                        metadata={
                            "category": "naming",
                            "ast_node_type": "ClassDef",
                            "line_number": (
                                node.lineno if hasattr(node, "lineno") else None
                            ),
                        },
                    )
                    patterns.append(pattern)

        return patterns

    def _update_pattern_tracking(
        self,
        pattern: ExtractedPattern,
        validation_result: Dict[str, Any],
    ) -> None:
        """
        Update pattern tracking based on validation result.

        Args:
            pattern: Extracted pattern to track
            validation_result: Validation result with quality scores
        """
        pattern_key = f"{pattern.pattern_category.value}:{pattern.pattern_id}"

        # Update frequency
        if pattern_key in self.pattern_frequency:
            self.pattern_frequency[pattern_key] += 1
            # Update existing pattern
            if pattern.pattern_id in self.known_patterns:
                existing = self.known_patterns[pattern.pattern_id]
                existing.increment_frequency()
                # Update confidence based on validation success
                existing.update_confidence(validation_result.get("is_valid", False))
        else:
            self.pattern_frequency[pattern_key] = 1
            self.known_patterns[pattern.pattern_id] = pattern
            # Initialize confidence based on quality score
            quality_score = validation_result.get("quality_score", 0.5)
            pattern.confidence = min(
                1.0, quality_score * 1.1
            )  # Boost slightly for first occurrence

    async def get_emerging_patterns(
        self, min_frequency: int = 5
    ) -> List[ExtractedPattern]:
        """
        Get patterns that are emerging (high frequency, recent observations).

        Args:
            min_frequency: Minimum frequency threshold for emerging patterns

        Returns:
            List of emerging patterns sorted by frequency
        """
        emerging = [
            pattern
            for pattern in self.known_patterns.values()
            if pattern.frequency >= min_frequency
        ]

        # Sort by frequency (highest first)
        emerging.sort(key=lambda p: p.frequency, reverse=True)

        logger.info(
            f"Found {len(emerging)} emerging patterns with frequency >= {min_frequency}"
        )

        return emerging

    def _get_name(self, node: ast.AST) -> str:
        """
        Extract name from AST node.

        Args:
            node: AST node

        Returns:
            Name string or "Unknown"
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return "Unknown"

    def _get_full_attribute_name(self, node: ast.Attribute) -> str:
        """
        Get full attribute name (e.g., 'self.transaction_manager.begin').

        Args:
            node: AST Attribute node

        Returns:
            Full attribute path
        """
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _hash_list(self, items: List[str]) -> str:
        """
        Create short hash from list of items.

        Args:
            items: List of strings

        Returns:
            Short hash (8 characters)
        """
        combined = "_".join(sorted(items))
        return hashlib.md5(combined.encode()).hexdigest()[:8]
