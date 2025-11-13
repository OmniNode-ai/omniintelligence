"""
Unit Tests for RelationshipDetector

Tests relationship detection for:
- USES (imports)
- EXTENDS (inheritance)
- COMPOSED_OF (function calls)
- SIMILAR_TO (structural similarity)
"""

import pytest
from relationship_detector import RelationshipDetector, RelationshipType


class TestRelationshipDetector:
    """Test suite for RelationshipDetector."""

    def setup_method(self):
        """Setup test fixtures."""
        self.detector = RelationshipDetector()

    def test_detect_import_relationships_basic(self):
        """Test detection of basic import statements."""
        source_code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        # Filter USES relationships
        uses_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.USES
        ]

        assert len(uses_rels) == 3  # os, sys, pathlib, typing

        # Check specific imports
        imported_modules = {r.target_pattern_name for r in uses_rels}
        assert "os" in imported_modules
        assert "sys" in imported_modules
        assert "pathlib" in imported_modules

    def test_detect_inheritance_relationships(self):
        """Test detection of class inheritance."""
        source_code = """
class MyClass(BaseClass):
    pass

class AnotherClass(BaseClass, MixinClass):
    pass
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        # Filter EXTENDS relationships
        extends_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.EXTENDS
        ]

        assert len(extends_rels) == 3  # BaseClass (2x), MixinClass

        # Check specific base classes
        base_classes = [r.target_pattern_name for r in extends_rels]
        assert base_classes.count("BaseClass") == 2
        assert "MixinClass" in base_classes

    def test_detect_call_relationships(self):
        """Test detection of function calls."""
        source_code = """
def my_function():
    helper_function()
    helper_function()
    another_function()
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        # Filter COMPOSED_OF relationships
        composed_rels = [
            r
            for r in relationships
            if r.relationship_type == RelationshipType.COMPOSED_OF
        ]

        assert len(composed_rels) == 2  # helper_function, another_function

        # Check confidence scores
        helper_rel = next(
            r for r in composed_rels if r.target_pattern_name == "helper_function"
        )
        another_rel = next(
            r for r in composed_rels if r.target_pattern_name == "another_function"
        )

        # helper_function called 2 times -> higher confidence
        assert helper_rel.confidence > another_rel.confidence
        assert helper_rel.confidence == min(0.8 + (2 - 1) * 0.05, 1.0)  # 0.85
        assert another_rel.confidence == 0.8  # 1 call

    def test_detect_module_attribute_calls(self):
        """Test detection of module.function() calls."""
        source_code = """
import os

def my_function():
    os.path.exists("/tmp")
    os.listdir("/home")
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        # Filter COMPOSED_OF relationships
        composed_rels = [
            r
            for r in relationships
            if r.relationship_type == RelationshipType.COMPOSED_OF
        ]

        # Should detect os.path.exists and os.listdir
        called_names = {r.target_pattern_name for r in composed_rels}
        assert "os.path.exists" in called_names
        assert "os.listdir" in called_names

    def test_structural_similarity_identical_code(self):
        """Test structural similarity with identical code."""
        code_a = "def foo(x, y): return x + y"
        code_b = "def foo(x, y): return x + y"

        similarity = self.detector.calculate_structural_similarity(code_a, code_b)

        assert similarity == 1.0  # Identical code should have 1.0 similarity

    def test_structural_similarity_different_names(self):
        """Test structural similarity with different names but same structure."""
        code_a = "def foo(x, y): return x + y"
        code_b = "def bar(a, b): return a + b"

        similarity = self.detector.calculate_structural_similarity(code_a, code_b)

        # Should have high similarity due to same structure
        # Function count: same (1.0)
        # Class count: same (1.0)
        # Function signatures: different names (0.0)
        # Imports: same (1.0)
        # Weighted: 0.3 + 0.3 + 0.0 + 0.2 = 0.8
        assert similarity >= 0.6  # High similarity

    def test_structural_similarity_different_structures(self):
        """Test structural similarity with different structures."""
        code_a = """
class MyClass:
    def method_a(self):
        pass
    def method_b(self):
        pass
"""
        code_b = """
def function_a():
    pass
def function_b():
    pass
def function_c():
    pass
"""

        similarity = self.detector.calculate_structural_similarity(code_a, code_b)

        # Different structures (class vs functions)
        # Should have lower similarity
        assert similarity < 0.5

    def test_complex_pattern_detection(self):
        """Test detection on a complex real-world pattern."""
        source_code = """
import asyncio
from typing import Dict, List
from pathlib import Path

class NodePatternStorageEffect(BaseEffect):
    def __init__(self, db_connection):
        super().__init__(db_connection)
        self.validator = PatternValidator()

    async def execute_effect(self, contract):
        result = await self.validator.validate(contract)
        return await self.store_pattern(result)

    async def store_pattern(self, pattern_data):
        return await self.db_connection.execute(query)
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "NodePatternStorageEffect", None
        )

        # Should detect:
        # USES: asyncio, typing, pathlib
        uses_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.USES
        ]
        assert len(uses_rels) >= 3

        # EXTENDS: BaseEffect
        extends_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.EXTENDS
        ]
        assert len(extends_rels) == 1
        assert extends_rels[0].target_pattern_name == "BaseEffect"

        # COMPOSED_OF: Multiple method calls
        composed_rels = [
            r
            for r in relationships
            if r.relationship_type == RelationshipType.COMPOSED_OF
        ]
        assert len(composed_rels) > 0

    def test_no_relationships_empty_code(self):
        """Test detection with empty source code."""
        source_code = ""

        with pytest.raises(SyntaxError):
            self.detector.detect_all_relationships(source_code, "test_pattern", None)

    def test_no_relationships_comments_only(self):
        """Test detection with comments only."""
        source_code = """
# This is a comment
# Another comment
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        assert len(relationships) == 0

    def test_extract_name_from_complex_attribute(self):
        """Test extraction of complex attribute names."""
        import ast

        # Test module.class.method
        node = ast.parse("module.class.method()").body[0].value

        name = self.detector._extract_name_from_node(node.func)
        assert name == "module.class.method"

    def test_confidence_scores(self):
        """Test that confidence scores are in valid range [0.0, 1.0]."""
        source_code = """
import os

class MyClass(BaseClass):
    def method(self):
        helper()
        helper()
        helper()
"""
        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        for rel in relationships:
            assert (
                0.0 <= rel.confidence <= 1.0
            ), f"Confidence {rel.confidence} out of range for {rel.relationship_type}"

    def test_context_metadata(self):
        """Test that context metadata is properly set."""
        source_code = "import os"

        relationships = self.detector.detect_all_relationships(
            source_code, "test_pattern", None
        )

        uses_rel = relationships[0]
        assert uses_rel.context is not None
        assert "detection_method" in uses_rel.context
        assert uses_rel.context["detection_method"] == "import_analysis"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
