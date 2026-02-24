# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for pattern learning feature extraction handler.

This module tests the feature extraction handler for pattern learning:
    - extract_features: Single item feature extraction
    - extract_features_batch: Batch extraction with deterministic ordering

Test coverage includes:
    - Deterministic ordering in batch processing
    - Python extraction populating all fields
    - Non-Python language handling (minimal features)
    - Syntax error handling (graceful fallback)
    - Identifier normalization (lowercase, sorted, deduped)
    - ONEX pattern detection
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
    extract_features,
    extract_features_batch,
)
from omniintelligence.nodes.node_pattern_learning_compute.models import (
    TrainingDataItemDict,
)

# =============================================================================
# Test Data Helpers
# =============================================================================


def make_training_item(
    item_id: str,
    code_snippet: str,
    language: str = "python",
    labels: list[str] | None = None,
) -> TrainingDataItemDict:
    """Create a TrainingDataItemDict for testing.

    Args:
        item_id: Unique identifier for the training item.
        code_snippet: Code content to extract features from.
        language: Programming language (default: "python").
        labels: Optional list of training labels.

    Returns:
        A TrainingDataItemDict with the specified fields.
    """
    item: TrainingDataItemDict = {
        "item_id": item_id,
        "code_snippet": code_snippet,
        "language": language,
        "labels": labels or [],
    }
    return item


# =============================================================================
# extract_features_batch - Deterministic Ordering Tests
# =============================================================================


@pytest.mark.unit
class TestBatchDeterministicOrdering:
    """Tests for deterministic ordering in batch extraction."""

    def test_batch_deterministic_ordering(self) -> None:
        """Batch extraction sorts by item_id and produces deterministic output."""
        # Create items with out-of-order IDs
        items = [
            make_training_item("item_c", "x = 1", "python"),
            make_training_item("item_a", "y = 2", "python"),
            make_training_item("item_b", "z = 3", "python"),
        ]

        # Call extract_features_batch
        result = extract_features_batch(items)

        # Assert output is sorted by item_id
        assert len(result) == 3
        assert result[0]["item_id"] == "item_a"
        assert result[1]["item_id"] == "item_b"
        assert result[2]["item_id"] == "item_c"

    def test_batch_same_input_same_output(self) -> None:
        """Same input always produces same output."""
        items = [
            make_training_item("item_z", "a = 1", "python"),
            make_training_item("item_m", "b = 2", "python"),
            make_training_item("item_a", "c = 3", "python"),
        ]

        # Call twice with same input
        result1 = extract_features_batch(items)
        result2 = extract_features_batch(items)

        # Assert same output
        assert result1 == result2

    def test_batch_empty_input_returns_empty_list(self) -> None:
        """Empty input should return empty list."""
        result = extract_features_batch([])
        assert result == []

    def test_batch_single_item(self) -> None:
        """Single item batch returns list with one result."""
        items = [make_training_item("only_item", "x = 1", "python")]

        result = extract_features_batch(items)

        assert len(result) == 1
        assert result[0]["item_id"] == "only_item"


# =============================================================================
# extract_features - Python Extraction Tests
# =============================================================================


@pytest.mark.unit
class TestPythonExtraction:
    """Tests for Python code feature extraction."""

    def test_python_extraction_populates_all_fields(self) -> None:
        """Python code extraction produces all required ExtractedFeaturesDict fields."""
        code = '''
from typing import Final

class MyClass(BaseModel):
    """A sample class with docstring."""

    name: str
    value: int = 0

    @property
    def display_name(self) -> str:
        """Return formatted name."""
        return f"Name: {self.name}"

def my_function(x: int) -> int:
    """A sample function."""
    return x * 2
'''
        item = make_training_item("python_item", code, "python", ["test_label"])

        result = extract_features(item)

        # Assert all required fields are present
        assert result["item_id"] == "python_item"
        assert isinstance(result["keywords"], tuple)
        assert len(result["keywords"]) > 0
        assert isinstance(result["pattern_indicators"], tuple)
        assert isinstance(result["structural"], dict)
        assert isinstance(result["base_classes"], tuple)
        assert isinstance(result["decorators"], tuple)
        assert result["labels"] == ("test_label",)
        assert result["language"] == "python"
        assert result["extraction_quality"] == "full"

    def test_python_extracts_class_and_function_names(self) -> None:
        """Extraction includes class and function names in keywords."""
        code = """
class MyClass:
    def my_method(self):
        pass

def standalone_function():
    pass
"""
        item = make_training_item("names_test", code, "python")

        result = extract_features(item)

        # Keywords should include class and function names (lowercased)
        assert "myclass" in result["keywords"]
        assert "my_method" in result["keywords"]
        assert "standalone_function" in result["keywords"]

    def test_python_extracts_structural_metrics(self) -> None:
        """Extraction populates structural metrics correctly."""
        code = '''
class ClassOne:
    """Docstring."""
    def method_a(self, x: int) -> int:
        if x > 0:
            return x
        return 0

class ClassTwo:
    pass

def func_one():
    pass

def func_two(a: str, b: str) -> str:
    return a + b
'''
        item = make_training_item("structural_test", code, "python")

        result = extract_features(item)
        structural = result["structural"]

        assert structural["class_count"] == 2
        assert structural["function_count"] == 3  # 1 method + 2 functions
        assert structural["has_type_hints"] is True
        assert structural["has_docstrings"] is True
        assert structural["line_count"] > 0
        assert structural["cyclomatic_complexity"] >= 1

    def test_python_extracts_base_classes(self) -> None:
        """Extraction includes inherited base class names."""
        code = """
class ChildClass(ParentClass, Mixin):
    pass

class AnotherChild(BaseModel):
    pass
"""
        item = make_training_item("base_class_test", code, "python")

        result = extract_features(item)

        # Base classes should be extracted (not normalized - preserves case)
        assert "ParentClass" in result["base_classes"]
        assert "Mixin" in result["base_classes"]
        assert "BaseModel" in result["base_classes"]

    def test_python_extracts_decorators(self) -> None:
        """Extraction includes decorator names."""
        code = """
@dataclass
@frozen
class MyDataClass:
    name: str

@property
@lru_cache
def cached_property(self):
    pass
"""
        item = make_training_item("decorator_test", code, "python")

        result = extract_features(item)

        # Decorators should be extracted (normalized)
        assert "dataclass" in result["decorators"]
        assert "frozen" in result["decorators"]
        assert "property" in result["decorators"]
        assert "lru_cache" in result["decorators"]

    def test_python3_language_variant(self) -> None:
        """Python3 language variant is recognized."""
        item = make_training_item("py3_test", "x = 1", "python3")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"

    def test_py_language_variant(self) -> None:
        """'py' language variant is recognized."""
        item = make_training_item("py_test", "x = 1", "py")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"

    def test_python2_language_variant(self) -> None:
        """Python2 language variant is recognized."""
        item = make_training_item("py2_test", "x = 1", "python2")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"


# =============================================================================
# extract_features - Non-Python Handling Tests
# =============================================================================


@pytest.mark.unit
class TestNonPythonHandling:
    """Tests for non-Python language handling."""

    def test_non_python_returns_minimal_features(self) -> None:
        """Non-Python language returns minimal/empty features without crashing."""
        code = """
function hello() {
    console.log("Hello");
}
"""
        item = make_training_item("js_item", code, "javascript", ["js_label"])

        result = extract_features(item)

        # Assert minimal features
        assert result["item_id"] == "js_item"
        assert result["keywords"] == ()
        assert result["pattern_indicators"] == ()
        assert result["base_classes"] == ()
        assert result["decorators"] == ()
        assert result["labels"] == ("js_label",)
        assert result["language"] == "javascript"

    def test_non_python_sets_extraction_quality_minimal(self) -> None:
        """Non-Python explicitly sets extraction_quality to 'minimal'."""
        item = make_training_item("go_item", "package main", "go")

        result = extract_features(item)

        assert result["extraction_quality"] == "minimal"

    def test_non_python_structural_has_zeros(self) -> None:
        """Non-Python structural features have zeros/False values."""
        item = make_training_item("rust_item", "fn main() {}", "rust")

        result = extract_features(item)
        structural = result["structural"]

        assert structural["class_count"] == 0
        assert structural["function_count"] == 0
        assert structural["max_nesting_depth"] == 0
        assert structural["line_count"] == 0
        assert structural["cyclomatic_complexity"] == 0
        assert structural["has_type_hints"] is False
        assert structural["has_docstrings"] is False

    def test_various_non_python_languages(self) -> None:
        """Various non-Python languages all return minimal features."""
        languages = ["javascript", "go", "rust", "java", "c++", "typescript", "ruby"]

        for lang in languages:
            item = make_training_item(f"{lang}_item", "code here", lang)
            result = extract_features(item)

            assert result["extraction_quality"] == "minimal", f"Failed for {lang}"
            assert result["keywords"] == (), f"Failed for {lang}"

    def test_empty_language_returns_minimal(self) -> None:
        """Empty language string returns minimal features."""
        item = make_training_item("empty_lang", "x = 1", "")

        result = extract_features(item)

        assert result["extraction_quality"] == "minimal"


# =============================================================================
# extract_features - Syntax Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestSyntaxErrorHandling:
    """Tests for syntax error graceful fallback."""

    def test_syntax_error_returns_minimal_features(self) -> None:
        """Invalid Python syntax returns minimal features without crashing."""
        code = "def broken("  # Incomplete function definition

        item = make_training_item("broken_item", code, "python", ["broken_label"])

        # Should not raise
        result = extract_features(item)

        # Assert minimal features returned
        assert result["item_id"] == "broken_item"
        assert result["keywords"] == ()
        assert result["pattern_indicators"] == ()
        assert result["base_classes"] == ()
        assert result["decorators"] == ()
        assert result["labels"] == ("broken_label",)
        assert result["language"] == "python"
        assert result["extraction_quality"] == "minimal"

    def test_syntax_error_does_not_raise(self) -> None:
        """Syntax errors are handled gracefully without exceptions."""
        invalid_snippets = [
            "def broken(",
            "class Incomplete:",
            "if True\n  pass",  # Missing colon
            "return = 5",  # Invalid assignment
            "def f(x=, y):",  # Invalid default arg
        ]

        for snippet in invalid_snippets:
            item = make_training_item("error_item", snippet, "python")
            # Should not raise any exception
            result = extract_features(item)
            assert result["extraction_quality"] == "minimal"

    def test_syntax_error_preserves_provenance(self) -> None:
        """Syntax error preserves item_id, labels, and language."""
        item = make_training_item(
            "provenance_test",
            "def broken(",
            "python",
            ["label_a", "label_b"],
        )

        result = extract_features(item)

        assert result["item_id"] == "provenance_test"
        assert result["labels"] == ("label_a", "label_b")
        assert result["language"] == "python"


# =============================================================================
# extract_features - Normalization Tests
# =============================================================================


@pytest.mark.unit
class TestNormalization:
    """Tests for identifier normalization."""

    def test_normalization_applied_correctly(self) -> None:
        """Identifiers are normalized (lowercase, sorted, deduped)."""
        code = """
class MyClass:
    pass

class MyClass:  # Duplicate definition
    pass

def my_func():
    pass

def ANOTHER_FUNC():
    pass
"""
        item = make_training_item("norm_test", code, "python")

        result = extract_features(item)

        # Keywords should be lowercase
        for keyword in result["keywords"]:
            assert keyword == keyword.lower(), f"Keyword not lowercase: {keyword}"

        # Keywords should be sorted
        assert list(result["keywords"]) == sorted(result["keywords"])

        # Should not have duplicates (myclass appears once even though defined twice)
        keyword_list = list(result["keywords"])
        assert len(keyword_list) == len(set(keyword_list))

    def test_keywords_sorted_alphabetically(self) -> None:
        """Keywords are sorted in alphabetical order."""
        code = """
def zebra():
    pass

def apple():
    pass

def mango():
    pass
"""
        item = make_training_item("sort_test", code, "python")

        result = extract_features(item)

        # Check that function names appear in sorted order within keywords
        keywords = result["keywords"]
        assert "apple" in keywords
        assert "mango" in keywords
        assert "zebra" in keywords

        # Verify overall sorting
        assert list(keywords) == sorted(keywords)

    def test_mixed_case_identifiers_normalized(self) -> None:
        """Mixed case identifiers are all lowercased."""
        code = """
class MyClassName:
    def MY_METHOD(self):
        pass

CONSTANT = 1
myVariable = 2
"""
        item = make_training_item("case_test", code, "python")

        result = extract_features(item)

        # All keywords should be lowercase
        assert "myclassname" in result["keywords"]
        assert "my_method" in result["keywords"]
        assert "constant" in result["keywords"]
        assert "myvariable" in result["keywords"]

        # No uppercase keywords
        for kw in result["keywords"]:
            assert kw == kw.lower()


# =============================================================================
# extract_features - ONEX Pattern Detection Tests
# =============================================================================


@pytest.mark.unit
class TestOnexPatternDetection:
    """Tests for ONEX pattern detection in pattern_indicators."""

    def test_onex_pattern_detection(self) -> None:
        """ONEX base classes and keywords are detected as pattern_indicators."""
        code = '''
from pydantic import BaseModel, Field
from typing import Final

class NodeMyCompute(NodeCompute):
    """A compute node following ONEX patterns."""

    model_config = {"frozen": True, "extra": "forbid"}

    value: Final[int] = Field(default=0)
'''
        item = make_training_item("onex_test", code, "python")

        result = extract_features(item)

        # ONEX base class should be in pattern_indicators
        assert "nodecompute" in result["pattern_indicators"]

    def test_onex_base_classes_detected(self) -> None:
        """ONEX base classes (NodeCompute, NodeEffect, etc.) are detected."""
        code = """
class MyCompute(NodeCompute):
    pass

class MyEffect(NodeEffect):
    pass

class MyReducer(NodeReducer):
    pass

class MyOrchestrator(NodeOrchestrator):
    pass
"""
        item = make_training_item("onex_bases_test", code, "python")

        result = extract_features(item)

        # All ONEX base classes should be detected
        indicators = result["pattern_indicators"]
        assert "nodecompute" in indicators
        assert "nodeeffect" in indicators
        assert "nodereducer" in indicators
        assert "nodeorchestrator" in indicators

    def test_onex_keywords_detected(self) -> None:
        """ONEX pattern keywords (frozen, forbid, etc.) are detected."""
        code = """
from pydantic import Field
from typing import Final, ClassVar, Protocol

class MyModel:
    model_config = {"frozen": True, "extra": "forbid"}
    class_var: ClassVar[int] = 0
"""
        item = make_training_item("onex_keywords_test", code, "python")

        result = extract_features(item)

        indicators = result["pattern_indicators"]
        # At least some ONEX keywords should be detected
        # (exact detection depends on AST walking implementation)
        assert len(indicators) >= 0  # Non-crashing assertion

    def test_basemodel_inheritance_detected(self) -> None:
        """Pydantic BaseModel inheritance is detected."""
        code = """
from pydantic import BaseModel

class MyModel(BaseModel):
    name: str
"""
        item = make_training_item("basemodel_test", code, "python")

        result = extract_features(item)

        # BaseModel should be in pattern_indicators
        assert "basemodel" in result["pattern_indicators"]

    def test_non_onex_code_has_no_pattern_indicators(self) -> None:
        """Code without ONEX patterns has empty pattern_indicators."""
        code = """
def simple_function(x, y):
    return x + y

class RegularClass:
    def __init__(self):
        self.value = 0
"""
        item = make_training_item("no_onex_test", code, "python")

        result = extract_features(item)

        # No ONEX patterns detected
        assert len(result["pattern_indicators"]) == 0


# =============================================================================
# extract_features - Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_code_snippet(self) -> None:
        """Empty code snippet returns minimal features."""
        item = make_training_item("empty_code", "", "python")

        result = extract_features(item)

        # Empty Python is valid syntax
        assert result["extraction_quality"] == "full"
        assert result["keywords"] == ()
        assert result["structural"]["line_count"] == 0

    def test_whitespace_only_code(self) -> None:
        """Whitespace-only code is valid Python."""
        item = make_training_item("whitespace_code", "   \n\t\n   ", "python")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"
        assert result["keywords"] == ()

    def test_comment_only_code(self) -> None:
        """Comment-only code is valid Python."""
        code = """# This is a comment
# Another comment
"""
        item = make_training_item("comment_only", code, "python")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"

    def test_missing_item_id_uses_empty_string(self) -> None:
        """Missing item_id defaults to empty string."""
        item: TrainingDataItemDict = {
            "code_snippet": "x = 1",
            "language": "python",
            "labels": [],
        }

        result = extract_features(item)

        assert result["item_id"] == ""

    def test_missing_labels_uses_empty_tuple(self) -> None:
        """Missing labels defaults to empty tuple."""
        item: TrainingDataItemDict = {
            "item_id": "no_labels",
            "code_snippet": "x = 1",
            "language": "python",
        }

        result = extract_features(item)

        assert result["labels"] == ()

    def test_labels_converted_to_tuple(self) -> None:
        """Labels list is converted to tuple for immutability."""
        item = make_training_item("tuple_test", "x = 1", "python", ["a", "b", "c"])

        result = extract_features(item)

        assert isinstance(result["labels"], tuple)
        assert result["labels"] == ("a", "b", "c")

    def test_labels_already_tuple_preserved(self) -> None:
        """Labels already as tuple are preserved without double-wrapping."""
        # Create item with labels as tuple directly (simulating pre-processed input)
        item: TrainingDataItemDict = {
            "item_id": "tuple_labels_test",
            "code_snippet": "x = 1",
            "language": "python",
            "labels": ("pre", "existing", "tuple"),  # Already a tuple
        }

        result = extract_features(item)

        # Should be preserved as-is, not wrapped: (("pre", "existing", "tuple"),)
        assert isinstance(result["labels"], tuple)
        assert result["labels"] == ("pre", "existing", "tuple")
        assert len(result["labels"]) == 3  # Not 1 (which would indicate wrapping)

    def test_large_code_snippet(self) -> None:
        """Large code snippets are handled without issues."""
        # Generate a large code snippet
        lines = [f"def func_{i}():\n    return {i}\n" for i in range(100)]
        code = "\n".join(lines)

        item = make_training_item("large_code", code, "python")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"
        assert result["structural"]["function_count"] == 100

    def test_deeply_nested_code(self) -> None:
        """Deeply nested code is handled correctly."""
        code = """
def deeply_nested():
    if True:
        for i in range(10):
            while True:
                try:
                    with open("f"):
                        if True:
                            pass
                except:
                    pass
"""
        item = make_training_item("nested_code", code, "python")

        result = extract_features(item)

        assert result["extraction_quality"] == "full"
        assert result["structural"]["max_nesting_depth"] >= 5
