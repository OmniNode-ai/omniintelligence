"""
Relationship Detector Module
=============================

Detects relationships between code patterns using AST analysis.

Relationship Types:
- USES: Pattern A imports/uses pattern B (from imports)
- EXTENDS: Pattern A inherits from pattern B (from class inheritance)
- COMPOSED_OF: Pattern A calls functions from pattern B (from function calls)
- SIMILAR_TO: Patterns are semantically similar (from AST structure similarity)
"""

import ast
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class RelationshipType(str, Enum):
    """Types of relationships between patterns."""

    USES = "uses"
    EXTENDS = "extends"
    COMPOSED_OF = "composed_of"
    SIMILAR_TO = "similar_to"


@dataclass
class PatternRelationship:
    """
    Represents a relationship between two patterns.

    Attributes:
        source_pattern_id: UUID of source pattern
        target_pattern_name: Name of target pattern (resolved to ID later)
        relationship_type: Type of relationship
        confidence: Confidence score (0.0-1.0)
        context: Additional context about the relationship
    """

    source_pattern_id: Optional[str]  # UUID or None if not yet stored
    source_pattern_name: str  # Name for lookup
    target_pattern_name: str  # Name for lookup
    relationship_type: RelationshipType
    confidence: float
    context: Dict


class RelationshipDetector:
    """
    Detects relationships between code patterns using AST analysis.

    Uses Python AST to detect:
    1. Import relationships (USES)
    2. Inheritance relationships (EXTENDS)
    3. Call relationships (COMPOSED_OF)
    4. Structural similarity (SIMILAR_TO)
    """

    def __init__(self):
        """Initialize relationship detector."""
        pass

    def detect_all_relationships(
        self,
        source_code: str,
        source_pattern_name: str,
        source_pattern_id: Optional[str] = None,
    ) -> List[PatternRelationship]:
        """
        Detect all relationships from source code.

        Args:
            source_code: Python source code to analyze
            source_pattern_name: Name of the source pattern
            source_pattern_id: UUID of source pattern (if already stored)

        Returns:
            List of detected relationships

        Raises:
            SyntaxError: If source code has invalid syntax
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise SyntaxError(f"Failed to parse source code: {e}")

        relationships = []

        # Detect USES relationships (imports)
        relationships.extend(
            self._detect_import_relationships(
                tree, source_pattern_name, source_pattern_id
            )
        )

        # Detect EXTENDS relationships (inheritance)
        relationships.extend(
            self._detect_inheritance_relationships(
                tree, source_pattern_name, source_pattern_id
            )
        )

        # Detect COMPOSED_OF relationships (function calls)
        relationships.extend(
            self._detect_call_relationships(
                tree, source_pattern_name, source_pattern_id, source_code
            )
        )

        return relationships

    def _detect_import_relationships(
        self,
        tree: ast.AST,
        source_pattern_name: str,
        source_pattern_id: Optional[str],
    ) -> List[PatternRelationship]:
        """
        Detect USES relationships from import statements.

        Analyzes:
        - import module
        - from module import name
        - from module import name as alias

        Args:
            tree: AST tree
            source_pattern_name: Name of source pattern
            source_pattern_id: UUID of source pattern

        Returns:
            List of USES relationships
        """
        relationships = []
        imported_modules = set()

        for node in ast.walk(tree):
            # Handle "import module"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    imported_modules.add(module_name)

            # Handle "from module import name"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)

        # Create relationship for each unique import
        for module_name in imported_modules:
            relationships.append(
                PatternRelationship(
                    source_pattern_id=source_pattern_id,
                    source_pattern_name=source_pattern_name,
                    target_pattern_name=module_name,
                    relationship_type=RelationshipType.USES,
                    confidence=1.0,  # Explicit import = 100% confidence
                    context={
                        "detection_method": "import_analysis",
                        "import_type": "explicit",
                    },
                )
            )

        return relationships

    def _detect_inheritance_relationships(
        self,
        tree: ast.AST,
        source_pattern_name: str,
        source_pattern_id: Optional[str],
    ) -> List[PatternRelationship]:
        """
        Detect EXTENDS relationships from class inheritance.

        Analyzes:
        - class MyClass(BaseClass)
        - class MyClass(module.BaseClass)
        - Multiple inheritance

        Args:
            tree: AST tree
            source_pattern_name: Name of source pattern
            source_pattern_id: UUID of source pattern

        Returns:
            List of EXTENDS relationships
        """
        relationships = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name

                # Extract base classes
                for base in node.bases:
                    base_name = self._extract_name_from_node(base)
                    if base_name:
                        relationships.append(
                            PatternRelationship(
                                source_pattern_id=source_pattern_id,
                                source_pattern_name=f"{source_pattern_name}.{class_name}",
                                target_pattern_name=base_name,
                                relationship_type=RelationshipType.EXTENDS,
                                confidence=1.0,  # Explicit inheritance = 100% confidence
                                context={
                                    "detection_method": "inheritance_analysis",
                                    "class_name": class_name,
                                    "base_class": base_name,
                                },
                            )
                        )

        return relationships

    def _detect_call_relationships(
        self,
        tree: ast.AST,
        source_pattern_name: str,
        source_pattern_id: Optional[str],
        source_code: str,
    ) -> List[PatternRelationship]:
        """
        Detect COMPOSED_OF relationships from function calls.

        Analyzes:
        - function_name()
        - module.function_name()
        - object.method_name()

        Args:
            tree: AST tree
            source_pattern_name: Name of source pattern
            source_pattern_id: UUID of source pattern
            source_code: Original source code for context

        Returns:
            List of COMPOSED_OF relationships
        """
        relationships = []
        call_counts: Dict[str, int] = {}  # Track call frequency

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called_name = self._extract_name_from_node(node.func)
                if called_name:
                    call_counts[called_name] = call_counts.get(called_name, 0) + 1

        # Create relationships based on call frequency
        for called_name, count in call_counts.items():
            # Calculate confidence based on frequency (more calls = higher confidence)
            # Scale: 1 call = 0.8, 2 calls = 0.85, 3 calls = 0.9, 4+ calls = 1.0
            confidence = min(0.8 + (count - 1) * 0.05, 1.0)

            relationships.append(
                PatternRelationship(
                    source_pattern_id=source_pattern_id,
                    source_pattern_name=source_pattern_name,
                    target_pattern_name=called_name,
                    relationship_type=RelationshipType.COMPOSED_OF,
                    confidence=confidence,
                    context={
                        "detection_method": "call_analysis",
                        "call_count": count,
                        "confidence_calculation": f"min(0.8 + ({count} - 1) * 0.05, 1.0)",
                    },
                )
            )

        return relationships

    def calculate_structural_similarity(
        self, source_code_a: str, source_code_b: str
    ) -> float:
        """
        Calculate structural similarity between two code patterns.

        Uses AST structure comparison to determine similarity.

        Similarity factors:
        - Number of functions (weight: 0.3)
        - Number of classes (weight: 0.3)
        - Similar function signatures (weight: 0.2)
        - Similar imports (weight: 0.2)

        Args:
            source_code_a: First pattern source code
            source_code_b: Second pattern source code

        Returns:
            Similarity score (0.0-1.0)

        Raises:
            SyntaxError: If either source has invalid syntax
        """
        try:
            tree_a = ast.parse(source_code_a)
            tree_b = ast.parse(source_code_b)
        except SyntaxError as e:
            raise SyntaxError(f"Failed to parse source code: {e}")

        # Extract features
        features_a = self._extract_structural_features(tree_a)
        features_b = self._extract_structural_features(tree_b)

        # Calculate similarity scores for each feature
        scores = []

        # 1. Function count similarity (weight: 0.3)
        func_count_a = features_a["function_count"]
        func_count_b = features_b["function_count"]
        if func_count_a == 0 and func_count_b == 0:
            func_similarity = 1.0
        else:
            func_similarity = 1.0 - abs(func_count_a - func_count_b) / max(
                func_count_a, func_count_b, 1
            )
        scores.append((func_similarity, 0.3))

        # 2. Class count similarity (weight: 0.3)
        class_count_a = features_a["class_count"]
        class_count_b = features_b["class_count"]
        if class_count_a == 0 and class_count_b == 0:
            class_similarity = 1.0
        else:
            class_similarity = 1.0 - abs(class_count_a - class_count_b) / max(
                class_count_a, class_count_b, 1
            )
        scores.append((class_similarity, 0.3))

        # 3. Function signature similarity (weight: 0.2)
        sig_overlap = len(
            features_a["function_signatures"] & features_b["function_signatures"]
        )
        sig_total = len(
            features_a["function_signatures"] | features_b["function_signatures"]
        )
        sig_similarity = sig_overlap / sig_total if sig_total > 0 else 0.0
        scores.append((sig_similarity, 0.2))

        # 4. Import similarity (weight: 0.2)
        import_overlap = len(features_a["imports"] & features_b["imports"])
        import_total = len(features_a["imports"] | features_b["imports"])
        import_similarity = import_overlap / import_total if import_total > 0 else 0.0
        scores.append((import_similarity, 0.2))

        # Calculate weighted average
        total_score = sum(score * weight for score, weight in scores)

        return round(total_score, 4)

    def _extract_structural_features(self, tree: ast.AST) -> Dict:
        """
        Extract structural features from AST for similarity comparison.

        Args:
            tree: AST tree

        Returns:
            Dictionary with features:
                - function_count: Number of functions
                - class_count: Number of classes
                - function_signatures: Set of function signatures
                - imports: Set of imported modules
        """
        features = {
            "function_count": 0,
            "class_count": 0,
            "function_signatures": set(),
            "imports": set(),
        }

        for node in ast.walk(tree):
            # Count functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                features["function_count"] += 1
                # Extract function signature
                signature = self._get_function_signature(node)
                features["function_signatures"].add(signature)

            # Count classes
            elif isinstance(node, ast.ClassDef):
                features["class_count"] += 1

            # Extract imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    features["imports"].add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    features["imports"].add(node.module)

        return features

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """
        Get function signature as string.

        Args:
            node: FunctionDef or AsyncFunctionDef node

        Returns:
            Function signature string (e.g., "func_name(arg1, arg2)")
        """
        args = []
        for arg in node.args.args:
            args.append(arg.arg)

        return f"{node.name}({', '.join(args)})"

    def _extract_name_from_node(self, node: ast.AST) -> Optional[str]:
        """
        Extract name from AST node (handles Name, Attribute, etc.).

        Args:
            node: AST node

        Returns:
            Name string or None if cannot extract
        """
        if isinstance(node, ast.Name):
            return node.id

        elif isinstance(node, ast.Attribute):
            # Handle module.name or object.method
            value_name = self._extract_name_from_node(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
            return node.attr

        elif isinstance(node, ast.Call):
            # Handle function calls
            return self._extract_name_from_node(node.func)

        return None


# Example usage
if __name__ == "__main__":
    detector = RelationshipDetector()

    # Example source code
    source_code = """
import os
from pathlib import Path
from typing import List

class MyClass(BaseClass):
    def __init__(self):
        self.path = Path()

    def process(self):
        os.path.exists("/tmp")
        self.helper()

    def helper(self):
        pass
"""

    # Detect relationships
    relationships = detector.detect_all_relationships(
        source_code, "MyClass", source_pattern_id=None
    )

    print(f"Detected {len(relationships)} relationships:\n")
    for rel in relationships:
        print(
            f"- {rel.relationship_type.value}: {rel.source_pattern_name} -> {rel.target_pattern_name}"
        )
        print(f"  Confidence: {rel.confidence}")
        print(f"  Context: {rel.context}")
        print()

    # Test similarity
    code_a = "def foo(x, y): return x + y"
    code_b = "def bar(a, b): return a + b"

    similarity = detector.calculate_structural_similarity(code_a, code_b)
    print(f"Structural similarity: {similarity}")
