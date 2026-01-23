# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the semantic analysis handler.

This module tests the core semantic analysis interface including:
    - Entity extraction (functions, classes, imports, constants)
    - Relationship detection (imports, inherits, calls, defines)
    - Error handling and edge cases
    - Semantic feature computation
    - Result structure validation
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.semantic_analysis_compute.handlers import (
    ANALYSIS_VERSION_STR,
    analyze_semantics,
)


# =============================================================================
# Test Fixtures - Sample Python Code Snippets
# =============================================================================


SAMPLE_FUNCTION = '''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}"
'''

SAMPLE_ASYNC_FUNCTION = '''
import asyncio

@retry(max_attempts=3)
@log_execution
async def fetch_data(url: str, timeout: float = 30.0) -> dict:
    """Fetch data from a URL asynchronously.

    Args:
        url: The URL to fetch from.
        timeout: Request timeout in seconds.

    Returns:
        The fetched data as a dictionary.
    """
    await asyncio.sleep(0.1)
    return {"data": "value"}
'''

SAMPLE_CLASS = '''
class Animal:
    """Base animal class."""
    def speak(self) -> str:
        pass

class Dog(Animal):
    """A dog that can speak."""
    def speak(self) -> str:
        return "woof"

    def fetch(self, item: str) -> str:
        return f"fetched {item}"
'''

SAMPLE_WITH_IMPORTS = '''
import os
from typing import List, Optional
from pathlib import Path
'''

SAMPLE_CONSTANTS = '''
MAX_RETRIES: int = 3
DEFAULT_TIMEOUT = 30.0
API_VERSION = "1.0.0"
_PRIVATE_CONST = "internal"
'''

SAMPLE_REALISTIC_FILE = '''
"""A realistic Python module for testing semantic analysis."""

import os
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT: int = 30
MAX_RETRIES = 3

@dataclass
class Config:
    """Configuration container."""
    host: str
    port: int = 8080

class ServiceBase:
    """Base service class."""
    def initialize(self) -> None:
        """Initialize the service."""
        pass

class MyService(ServiceBase):
    """Concrete service implementation."""

    def __init__(self, config: Config) -> None:
        """Initialize with config."""
        self.config = config
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the service."""
        self._setup()
        self._initialized = True

    def _setup(self) -> None:
        """Internal setup routine."""
        pass

    def process(self, data: List[str]) -> Optional[str]:
        """Process data items.

        Args:
            data: List of data items to process.

        Returns:
            Processed result or None if empty.
        """
        if not data:
            return None
        return self._transform(data[0])

    def _transform(self, item: str) -> str:
        """Transform a single item."""
        return item.upper()

def create_service(host: str, port: int = 8080) -> MyService:
    """Factory function to create a service instance."""
    config = Config(host=host, port=port)
    return MyService(config)
'''


# =============================================================================
# Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Tests for entity extraction from source code."""

    def test_extract_function_entity(self) -> None:
        """Test basic function entity extraction."""
        result = analyze_semantics(SAMPLE_FUNCTION, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        # Find the greet function
        functions = [e for e in result["entities"] if e["entity_type"] == "function"]
        assert len(functions) == 1

        greet_func = functions[0]
        assert greet_func["name"] == "greet"
        assert greet_func["docstring"] == "Greet someone."
        assert greet_func["line_start"] >= 1
        assert greet_func["line_end"] >= greet_func["line_start"]
        assert greet_func["decorators"] == []
        assert greet_func["metadata"]["is_async"] is False
        assert "name" in greet_func["metadata"]["arguments"]

    def test_extract_async_function(self) -> None:
        """Test async function extraction with decorators."""
        result = analyze_semantics(SAMPLE_ASYNC_FUNCTION, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        functions = [e for e in result["entities"] if e["entity_type"] == "function"]
        assert len(functions) == 1

        async_func = functions[0]
        assert async_func["name"] == "fetch_data"
        assert async_func["metadata"]["is_async"] is True
        assert "Fetch data from a URL" in (async_func["docstring"] or "")
        # Decorators should be captured
        assert "retry" in async_func["decorators"]
        assert "log_execution" in async_func["decorators"]
        # Arguments should include url, timeout
        args = async_func["metadata"]["arguments"]
        assert "url" in args
        assert "timeout" in args
        # Return type should be captured
        assert async_func["metadata"].get("return_type") == "dict"

    def test_extract_class_entity(self) -> None:
        """Test class entity extraction with bases and methods."""
        result = analyze_semantics(SAMPLE_CLASS, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        classes = [e for e in result["entities"] if e["entity_type"] == "class"]
        assert len(classes) == 2

        # Find Animal class
        animal = next(c for c in classes if c["name"] == "Animal")
        assert animal["docstring"] == "Base animal class."
        assert animal["metadata"]["bases"] == []  # No explicit base
        assert "speak" in animal["metadata"]["methods"]

        # Find Dog class
        dog = next(c for c in classes if c["name"] == "Dog")
        assert dog["docstring"] == "A dog that can speak."
        assert "Animal" in dog["metadata"]["bases"]
        assert "speak" in dog["metadata"]["methods"]
        assert "fetch" in dog["metadata"]["methods"]

    def test_extract_imports(self) -> None:
        """Test import entity extraction for both import and from imports."""
        result = analyze_semantics(SAMPLE_WITH_IMPORTS, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        imports = [e for e in result["entities"] if e["entity_type"] == "import"]
        assert len(imports) == 4  # os, List, Optional, Path

        # Check direct import (`import os`)
        os_import = next((i for i in imports if i["name"] == "os"), None)
        assert os_import is not None
        assert os_import["metadata"]["source_module"] == "os"

        # Check from import (`from typing import List`)
        list_import = next((i for i in imports if i["name"] == "List"), None)
        assert list_import is not None
        assert list_import["metadata"]["source_module"] == "typing"
        assert list_import["metadata"]["imported_name"] == "List"

        path_import = next((i for i in imports if i["name"] == "Path"), None)
        assert path_import is not None
        assert path_import["metadata"]["source_module"] == "pathlib"

    def test_extract_constants(self) -> None:
        """Test module-level constant extraction."""
        result = analyze_semantics(SAMPLE_CONSTANTS, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        constants = [e for e in result["entities"] if e["entity_type"] == "constant"]
        # Should extract MAX_RETRIES, DEFAULT_TIMEOUT, API_VERSION
        # _PRIVATE_CONST is lowercase prefix, but PRIVATE_CONST part is uppercase
        constant_names = {c["name"] for c in constants}

        assert "MAX_RETRIES" in constant_names
        assert "DEFAULT_TIMEOUT" in constant_names
        assert "API_VERSION" in constant_names

        # Check annotated constant has type annotation metadata
        max_retries = next(c for c in constants if c["name"] == "MAX_RETRIES")
        assert max_retries["metadata"].get("type_annotation") == "int"


# =============================================================================
# Relationship Detection Tests
# =============================================================================


class TestRelationshipDetection:
    """Tests for relationship extraction from source code."""

    def test_detect_import_relationships(self) -> None:
        """Test IMPORTS relation extraction."""
        result = analyze_semantics(SAMPLE_WITH_IMPORTS, "python")

        assert result["success"] is True

        import_relations = [r for r in result["relations"] if r["relation_type"] == "imports"]
        assert len(import_relations) >= 3

        # All should have module as source
        for rel in import_relations:
            assert rel["source"] == "module"
            assert rel["confidence"] == 1.0

        # Check specific imports
        targets = {r["target"] for r in import_relations}
        assert "os" in targets
        assert "typing.List" in targets
        assert "typing.Optional" in targets
        assert "pathlib.Path" in targets

    def test_detect_inheritance_relationships(self) -> None:
        """Test INHERITS relation extraction."""
        result = analyze_semantics(SAMPLE_CLASS, "python")

        assert result["success"] is True

        inherits_relations = [r for r in result["relations"] if r["relation_type"] == "inherits"]
        assert len(inherits_relations) == 1

        dog_inherits = inherits_relations[0]
        assert dog_inherits["source"] == "Dog"
        assert dog_inherits["target"] == "Animal"
        assert dog_inherits["confidence"] == 1.0

    def test_detect_call_relationships(self) -> None:
        """Test CALLS relation extraction (best-effort)."""
        code = '''
def helper() -> int:
    return 42

def process() -> int:
    result = helper()
    return result + helper()
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True

        call_relations = [r for r in result["relations"] if r["relation_type"] == "calls"]

        # Should detect process -> helper call
        process_to_helper = next(
            (r for r in call_relations if r["source"] == "process" and r["target"] == "helper"),
            None,
        )
        assert process_to_helper is not None
        # Confidence should be 0.8-1.0 range (base 0.8 with frequency boost)
        assert 0.8 <= process_to_helper["confidence"] <= 1.0
        # Multiple calls should boost confidence
        assert process_to_helper["confidence"] > 0.8  # frequency factor kicks in

    def test_detect_defines_relationships(self) -> None:
        """Test DEFINES relation extraction."""
        result = analyze_semantics(SAMPLE_FUNCTION, "python")

        assert result["success"] is True

        defines_relations = [r for r in result["relations"] if r["relation_type"] == "defines"]

        # Module should define the greet function
        greet_defined = next(
            (r for r in defines_relations if r["target"] == "greet"),
            None,
        )
        assert greet_defined is not None
        assert greet_defined["source"] == "module"
        assert greet_defined["confidence"] == 1.0

    def test_imports_excluded_from_defines_relations(self) -> None:
        """Test that import entities do not get DEFINES relations.

        Import entities already have IMPORTS relations, so DEFINES would be
        redundant. Only functions, classes, and constants should have DEFINES.
        """
        result = analyze_semantics(SAMPLE_WITH_IMPORTS, "python")

        assert result["success"] is True

        # Get import entity names
        import_entity_names = {
            e["name"] for e in result["entities"] if e["entity_type"] == "import"
        }
        # Should have imports: os, List, Optional, Path
        assert len(import_entity_names) >= 3

        # Get DEFINES relation targets
        defines_targets = {
            r["target"]
            for r in result["relations"]
            if r["relation_type"] == "defines"
        }

        # Imports should NOT appear in DEFINES targets
        overlap = import_entity_names & defines_targets
        assert overlap == set(), (
            f"Imports should not have DEFINES relations, but found: {overlap}"
        )

        # Verify imports DO have IMPORTS relations
        imports_relations = [
            r for r in result["relations"] if r["relation_type"] == "imports"
        ]
        assert len(imports_relations) >= 3, "Imports should still have IMPORTS relations"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_parse_error_returns_parse_ok_false(self) -> None:
        """Test that syntax errors result in parse_ok=False."""
        bad_syntax = "def broken( class while:"

        result = analyze_semantics(bad_syntax, "python")

        assert result["success"] is True  # Operation completed
        assert result["parse_ok"] is False
        assert len(result["entities"]) == 0
        assert len(result["relations"]) == 0
        assert len(result["warnings"]) > 0
        assert any("syntax" in w.lower() or "error" in w.lower() for w in result["warnings"])

    def test_empty_content_returns_warning(self) -> None:
        """Test that empty input returns validation error."""
        result = analyze_semantics("", "python")

        assert result["success"] is False
        assert result["parse_ok"] is False
        assert len(result["warnings"]) > 0
        assert any("empty" in w.lower() for w in result["warnings"])

        # Whitespace-only should also fail
        result_whitespace = analyze_semantics("   \n\t  ", "python")
        assert result_whitespace["success"] is False
        assert result_whitespace["parse_ok"] is False

    def test_non_python_returns_warning(self) -> None:
        """Test that unsupported languages return appropriate result."""
        rust_code = 'fn main() { println!("Hello"); }'

        result = analyze_semantics(rust_code, "rust")

        assert result["success"] is True  # Operation completed successfully
        assert result["parse_ok"] is False  # But couldn't parse as Python
        assert len(result["entities"]) == 0
        assert len(result["warnings"]) > 0
        assert any("unsupported" in w.lower() for w in result["warnings"])

    def test_language_case_insensitive(self) -> None:
        """Test that language parameter is case insensitive."""
        code = "x = 1"

        result_lower = analyze_semantics(code, "python")
        result_upper = analyze_semantics(code, "PYTHON")
        result_mixed = analyze_semantics(code, "Python")

        assert result_lower["parse_ok"] is True
        assert result_upper["parse_ok"] is True
        assert result_mixed["parse_ok"] is True

    def test_py_alias_for_python(self) -> None:
        """Test that 'py' is accepted as alias for 'python'."""
        code = "def test(): pass"

        result = analyze_semantics(code, "py")

        assert result["success"] is True
        assert result["parse_ok"] is True
        assert len(result["entities"]) > 0


# =============================================================================
# Integration Tests - Full File Analysis
# =============================================================================


class TestFullFileAnalysis:
    """Tests for analyzing realistic Python files."""

    def test_analyze_semantics_full_file(self) -> None:
        """Test analysis of a realistic Python file."""
        result = analyze_semantics(SAMPLE_REALISTIC_FILE, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        # Verify entity counts
        functions = [e for e in result["entities"] if e["entity_type"] == "function"]
        classes = [e for e in result["entities"] if e["entity_type"] == "class"]
        imports = [e for e in result["entities"] if e["entity_type"] == "import"]
        constants = [e for e in result["entities"] if e["entity_type"] == "constant"]

        # Should have: create_service + Config, ServiceBase, MyService methods
        assert len(functions) >= 5
        # Should have: Config, ServiceBase, MyService
        assert len(classes) >= 3
        # Should have: os, Optional, List, dataclass, Path
        assert len(imports) >= 4
        # Should have: DEFAULT_TIMEOUT, MAX_RETRIES
        assert len(constants) >= 2

        # Verify key entities exist
        entity_names = {e["name"] for e in result["entities"]}
        assert "create_service" in entity_names
        assert "MyService" in entity_names
        assert "ServiceBase" in entity_names
        assert "Config" in entity_names

        # Verify relationships
        assert len(result["relations"]) > 0

        # Check inheritance
        inherits = [r for r in result["relations"] if r["relation_type"] == "inherits"]
        myservice_inherits = next(
            (r for r in inherits if r["source"] == "MyService"),
            None,
        )
        assert myservice_inherits is not None
        assert myservice_inherits["target"] == "ServiceBase"

    def test_semantic_features_computed(self) -> None:
        """Test that semantic features are properly computed."""
        result = analyze_semantics(SAMPLE_REALISTIC_FILE, "python")

        assert result["success"] is True
        features = result["semantic_features"]

        # Verify counts
        assert features["function_count"] >= 5
        assert features["class_count"] >= 3
        assert features["import_count"] >= 4
        assert features["line_count"] > 0

        # Verify complexity score is in valid range
        assert 0.0 <= features["complexity_score"] <= 1.0

        # Verify language
        assert features["primary_language"] == "python"

        # Verify detected frameworks (dataclass should be detected)
        # Note: dataclass might not be in framework patterns

        # Verify entity names captured
        assert "create_service" in features["entity_names"]
        assert "MyService" in features["entity_names"]

        # Verify relationship count matches
        assert features["relationship_count"] == len(result["relations"])

        # Verify documentation ratio is reasonable (code has docstrings)
        assert 0.0 <= features["documentation_ratio"] <= 1.0
        assert features["documentation_ratio"] > 0.0  # Has docstrings

        # Verify test indicator is reasonable
        assert 0.0 <= features["test_coverage_indicator"] <= 1.0


# =============================================================================
# Metadata Tests
# =============================================================================


class TestMetadata:
    """Tests for analysis metadata."""

    def test_metadata_populated(self) -> None:
        """Test that metadata fields are properly populated."""
        result = analyze_semantics(SAMPLE_FUNCTION, "python")

        metadata = result["metadata"]

        assert metadata["algorithm_version"] == ANALYSIS_VERSION_STR
        assert metadata["parser_used"] == "ast"
        assert metadata["processing_time_ms"] >= 0
        assert metadata["input_length"] == len(SAMPLE_FUNCTION)
        assert metadata["input_line_count"] == len(SAMPLE_FUNCTION.splitlines())

    def test_metadata_for_parse_error(self) -> None:
        """Test that metadata is populated even for parse errors."""
        bad_code = "def broken("

        result = analyze_semantics(bad_code, "python")

        metadata = result["metadata"]

        assert metadata["algorithm_version"] == ANALYSIS_VERSION_STR
        assert metadata["parser_used"] == "ast"
        assert metadata["processing_time_ms"] >= 0


# =============================================================================
# Result Structure Tests
# =============================================================================


class TestResultStructure:
    """Tests for result TypedDict structure compliance."""

    def test_returns_typed_dict_structure(self) -> None:
        """Result should match SemanticAnalysisResult TypedDict structure."""
        result = analyze_semantics("x = 1", "python")

        # Verify all required keys present
        expected_keys = {
            "success",
            "parse_ok",
            "entities",
            "relations",
            "warnings",
            "semantic_features",
            "metadata",
        }
        assert set(result.keys()) == expected_keys

    def test_entity_structure(self) -> None:
        """Test that entities follow EntityDict structure."""
        result = analyze_semantics(SAMPLE_FUNCTION, "python")

        for entity in result["entities"]:
            assert "name" in entity
            assert "entity_type" in entity
            assert "line_start" in entity
            assert "line_end" in entity
            assert "decorators" in entity
            assert "metadata" in entity
            assert isinstance(entity["decorators"], list)
            assert isinstance(entity["metadata"], dict)

    def test_relation_structure(self) -> None:
        """Test that relations follow RelationDict structure."""
        result = analyze_semantics(SAMPLE_CLASS, "python")

        for relation in result["relations"]:
            assert "source" in relation
            assert "target" in relation
            assert "relation_type" in relation
            assert "confidence" in relation
            assert isinstance(relation["confidence"], float)

    def test_confidence_scores_in_valid_range(self) -> None:
        """Test that all confidence scores are in [0.0, 1.0] range."""
        result = analyze_semantics(SAMPLE_REALISTIC_FILE, "python")

        for relation in result["relations"]:
            assert 0.0 <= relation["confidence"] <= 1.0, (
                f"Confidence {relation['confidence']} out of range for "
                f"{relation['source']} -> {relation['target']}"
            )


# =============================================================================
# Feature Flag Tests
# =============================================================================


class TestFeatureFlags:
    """Tests for include_call_graph and include_import_graph flags."""

    def test_exclude_call_graph(self) -> None:
        """Test that call relations are excluded when flag is False."""
        code = '''
def caller():
    callee()

def callee():
    pass
'''
        result_with = analyze_semantics(code, "python", include_call_graph=True)
        result_without = analyze_semantics(code, "python", include_call_graph=False)

        calls_with = [r for r in result_with["relations"] if r["relation_type"] == "calls"]
        calls_without = [r for r in result_without["relations"] if r["relation_type"] == "calls"]

        assert len(calls_with) > 0
        assert len(calls_without) == 0

    def test_exclude_import_graph(self) -> None:
        """Test that import relations are excluded when flag is False."""
        result_with = analyze_semantics(SAMPLE_WITH_IMPORTS, "python", include_import_graph=True)
        result_without = analyze_semantics(SAMPLE_WITH_IMPORTS, "python", include_import_graph=False)

        imports_with = [r for r in result_with["relations"] if r["relation_type"] == "imports"]
        imports_without = [r for r in result_without["relations"] if r["relation_type"] == "imports"]

        assert len(imports_with) > 0
        assert len(imports_without) == 0


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_line_code(self) -> None:
        """Test analysis of single line code."""
        result = analyze_semantics("x = 1", "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

    def test_comments_only(self) -> None:
        """Test analysis of code with only comments."""
        code = '''
# This is a comment
# Another comment
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True
        assert result["semantic_features"]["function_count"] == 0
        assert result["semantic_features"]["class_count"] == 0

    def test_unicode_content(self) -> None:
        """Test analysis of code with unicode content."""
        code = '''
def greet(name: str) -> str:
    """Return greeting with emoji."""
    return f"Hello {name}!"
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

    def test_deeply_nested_classes(self) -> None:
        """Test analysis of nested class definitions."""
        code = '''
class Outer:
    """Outer class."""
    class Inner:
        """Inner class."""
        def method(self) -> None:
            pass
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True

        classes = [e for e in result["entities"] if e["entity_type"] == "class"]
        class_names = {c["name"] for c in classes}
        assert "Outer" in class_names
        assert "Inner" in class_names

    def test_generator_and_comprehensions(self) -> None:
        """Test analysis of code with generators and comprehensions."""
        code = '''
def gen():
    """Generator function."""
    yield from range(10)

def comp():
    """Comprehension usage."""
    return [x for x in range(10) if x > 5]
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True
        assert result["parse_ok"] is True
        assert result["semantic_features"]["function_count"] == 2

    def test_decorators_with_arguments(self) -> None:
        """Test extraction of decorators with arguments."""
        code = '''
@decorator_factory("arg1", kwarg=True)
@simple_decorator
def decorated():
    pass
'''
        result = analyze_semantics(code, "python")

        assert result["success"] is True
        functions = [e for e in result["entities"] if e["entity_type"] == "function"]
        assert len(functions) == 1

        # Both decorators should be captured
        decorators = functions[0]["decorators"]
        assert "decorator_factory" in decorators
        assert "simple_decorator" in decorators

    def test_multiple_inheritance(self) -> None:
        """Test detection of multiple inheritance."""
        code = '''
class Base1:
    pass

class Base2:
    pass

class Child(Base1, Base2):
    pass
'''
        result = analyze_semantics(code, "python")

        inherits = [r for r in result["relations"] if r["relation_type"] == "inherits"]
        child_inherits = [r for r in inherits if r["source"] == "Child"]

        # Should have two inheritance relationships
        assert len(child_inherits) == 2
        targets = {r["target"] for r in child_inherits}
        assert "Base1" in targets
        assert "Base2" in targets

    def test_aliased_imports(self) -> None:
        """Test extraction of aliased imports."""
        code = '''
import numpy as np
from pandas import DataFrame as DF
'''
        result = analyze_semantics(code, "python")

        imports = [e for e in result["entities"] if e["entity_type"] == "import"]

        # Check numpy alias (`import numpy as np`)
        np_import = next((i for i in imports if i["name"] == "np"), None)
        assert np_import is not None
        assert np_import["metadata"]["source_module"] == "numpy"
        assert np_import["metadata"]["alias"] == "np"

        # Check DataFrame alias (`from pandas import DataFrame as DF`)
        df_import = next((i for i in imports if i["name"] == "DF"), None)
        assert df_import is not None
        assert df_import["metadata"]["source_module"] == "pandas"
        assert df_import["metadata"]["imported_name"] == "DataFrame"
        assert df_import["metadata"]["alias"] == "DF"


# =============================================================================
# Pattern and Framework Detection Tests
# =============================================================================


class TestPatternDetection:
    """Tests for design pattern and framework detection."""

    def test_detect_factory_pattern(self) -> None:
        """Test detection of factory pattern."""
        code = '''
class Product:
    pass

def product_factory(product_type: str) -> Product:
    """Create a product instance."""
    return Product()
'''
        result = analyze_semantics(code, "python")

        patterns = result["semantic_features"]["detected_patterns"]
        assert "factory" in patterns

    def test_detect_singleton_pattern(self) -> None:
        """Test detection of singleton pattern."""
        code = '''
class Singleton:
    """A singleton class."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
'''
        result = analyze_semantics(code, "python")

        patterns = result["semantic_features"]["detected_patterns"]
        assert "singleton" in patterns

    def test_detect_framework_pydantic(self) -> None:
        """Test detection of Pydantic framework."""
        code = '''
from pydantic import BaseModel, Field

class Config(BaseModel):
    """Pydantic model."""
    name: str = Field(..., min_length=1)
'''
        result = analyze_semantics(code, "python")

        frameworks = result["semantic_features"]["detected_frameworks"]
        assert "pydantic" in frameworks

    def test_detect_test_code_purpose(self) -> None:
        """Test detection of test code purpose."""
        code = '''
import pytest

def test_something():
    assert True

def test_another():
    assert 1 == 1
'''
        result = analyze_semantics(code, "python")

        assert result["semantic_features"]["code_purpose"] == "testing"
        assert result["semantic_features"]["test_coverage_indicator"] > 0.0


# =============================================================================
# Documentation Ratio Tests
# =============================================================================


class TestDocumentationRatio:
    """Tests for documentation ratio computation."""

    def test_fully_documented_code(self) -> None:
        """Test documentation ratio for fully documented code."""
        code = '''
"""Module docstring."""

def documented_func():
    """Function docstring."""
    pass

class DocumentedClass:
    """Class docstring."""
    pass
'''
        result = analyze_semantics(code, "python")

        # Should have high documentation ratio
        assert result["semantic_features"]["documentation_ratio"] >= 0.75

    def test_undocumented_code(self) -> None:
        """Test documentation ratio for undocumented code."""
        code = '''
def no_docs():
    pass

class NoDocs:
    pass
'''
        result = analyze_semantics(code, "python")

        # Should have low documentation ratio
        assert result["semantic_features"]["documentation_ratio"] < 0.5
