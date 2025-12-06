"""
Unit tests for Pydantic model configuration validation.

These tests ensure that all models using Field(alias=...) have the required
model_config = ConfigDict(populate_by_name=True) setting. Without this setting,
models cannot be instantiated using both the field name and its alias.

This is a critical architectural requirement for backward compatibility
as the codebase uses aliases to maintain legacy API compatibility.

Example of the issue:
    class BadModel(BaseModel):
        # Missing: model_config = ConfigDict(populate_by_name=True)
        timeout_ms: int = Field(alias="timeout_seconds")

    # This will FAIL without populate_by_name=True:
    BadModel(timeout_ms=5000)  # Raises ValidationError

    # This will WORK without populate_by_name=True:
    BadModel(timeout_seconds=5000)  # Works, but we want both to work

Reference:
    https://docs.pydantic.dev/latest/concepts/fields/#field-aliases
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

# Project source path
SRC_PATH = Path(__file__).parent.parent.parent / "src" / "omniintelligence"


class ModelWithAlias(NamedTuple):
    """Information about a model class that uses Field(alias=...)."""

    file_path: Path
    class_name: str
    alias_fields: list[str]  # Fields that use alias=...
    has_populate_by_name: bool
    line_number: int


class AliasFieldVisitor(ast.NodeVisitor):
    """AST visitor that finds Pydantic models with Field(alias=...) usage."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.models: list[ModelWithAlias] = []
        self._current_class: str | None = None
        self._current_class_line: int = 0
        self._current_alias_fields: list[str] = []
        self._current_has_populate_by_name: bool = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition to check for Pydantic models."""
        # Check if this is likely a Pydantic model (inherits from BaseModel)
        is_pydantic_model = any(
            (isinstance(base, ast.Name) and base.id == "BaseModel")
            or (isinstance(base, ast.Attribute) and base.attr == "BaseModel")
            for base in node.bases
        )

        if is_pydantic_model:
            self._current_class = node.name
            self._current_class_line = node.lineno
            self._current_alias_fields = []
            self._current_has_populate_by_name = False

            # First pass: check for model_config with populate_by_name
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "model_config":
                            self._check_model_config(item.value)

            # Second pass: check for fields with alias
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    self._check_field_for_alias(item)

            # If we found alias fields, record this model
            if self._current_alias_fields:
                self.models.append(
                    ModelWithAlias(
                        file_path=self.file_path,
                        class_name=self._current_class,
                        alias_fields=self._current_alias_fields.copy(),
                        has_populate_by_name=self._current_has_populate_by_name,
                        line_number=self._current_class_line,
                    )
                )

            self._current_class = None

        # Continue visiting nested classes
        self.generic_visit(node)

    def _check_model_config(self, value: ast.expr) -> None:
        """Check if model_config contains populate_by_name=True."""
        # Handle ConfigDict(...) call
        if isinstance(value, ast.Call):
            for keyword in value.keywords:
                if keyword.arg == "populate_by_name":
                    if isinstance(keyword.value, ast.Constant):
                        self._current_has_populate_by_name = keyword.value.value is True

    def _check_field_for_alias(self, node: ast.AnnAssign) -> None:
        """Check if an annotated assignment uses Field(alias=...)."""
        if not isinstance(node.target, ast.Name):
            return

        field_name = node.target.id

        # Check if the value is a Field() call with alias
        if isinstance(node.value, ast.Call):
            func = node.value.func

            # Check if it's a Field call
            is_field_call = (
                (isinstance(func, ast.Name) and func.id == "Field")
                or (isinstance(func, ast.Attribute) and func.attr == "Field")
            )

            if is_field_call:
                for keyword in node.value.keywords:
                    if keyword.arg == "alias":
                        self._current_alias_fields.append(field_name)
                        break


def find_models_with_aliases(src_path: Path) -> list[ModelWithAlias]:
    """
    Scan all Python files in the source directory for Pydantic models
    that use Field(alias=...).

    Args:
        src_path: Path to the source directory to scan

    Returns:
        List of ModelWithAlias objects describing each model found
    """
    models: list[ModelWithAlias] = []

    for py_file in src_path.rglob("*.py"):
        # Skip __pycache__ directories
        if "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))

            visitor = AliasFieldVisitor(py_file)
            visitor.visit(tree)
            models.extend(visitor.models)
        except (SyntaxError, UnicodeDecodeError) as e:
            # Skip files that can't be parsed
            print(f"Warning: Could not parse {py_file}: {e}", file=sys.stderr)
            continue

    return models


@pytest.mark.unit
class TestModelConfigValidation:
    """Test suite for validating Pydantic model configurations."""

    def test_models_with_aliases_have_populate_by_name(self):
        """
        Ensure all models using Field(alias=...) have populate_by_name=True.

        This test scans all Python files in the source directory and:
        1. Identifies Pydantic models (classes inheriting from BaseModel)
        2. Finds fields that use Field(alias=...)
        3. Verifies each such model has model_config with populate_by_name=True

        Why this matters:
        - Without populate_by_name=True, models cannot be instantiated using
          the actual field name, only the alias
        - This breaks our backward compatibility pattern where we use aliases
          for legacy API compatibility while using ONEX naming internally
        - Example: timeout_ms with alias="timeout_seconds" should accept both names
        """
        models = find_models_with_aliases(SRC_PATH)

        # Collect models missing populate_by_name
        missing_config: list[ModelWithAlias] = []
        for model in models:
            if not model.has_populate_by_name:
                missing_config.append(model)

        # Build detailed error message
        if missing_config:
            error_lines = [
                "\n\nThe following models use Field(alias=...) but are missing "
                "model_config = ConfigDict(populate_by_name=True):\n"
            ]

            for model in missing_config:
                relative_path = model.file_path.relative_to(SRC_PATH.parent.parent)
                error_lines.append(f"\n  {relative_path}:{model.line_number}")
                error_lines.append(f"    Class: {model.class_name}")
                error_lines.append(f"    Fields with alias: {', '.join(model.alias_fields)}")
                error_lines.append("    Fix: Add 'model_config = ConfigDict(populate_by_name=True)'")

            error_lines.append("\n\nExample fix:")
            error_lines.append("    from pydantic import BaseModel, ConfigDict, Field")
            error_lines.append("")
            error_lines.append("    class MyModel(BaseModel):")
            error_lines.append("        model_config = ConfigDict(populate_by_name=True)")
            error_lines.append("")
            error_lines.append("        timeout_ms: int = Field(alias='timeout_seconds')")

            pytest.fail("\n".join(error_lines))

    def test_at_least_one_model_with_alias_found(self):
        """
        Verify that the test actually finds models with aliases.

        This is a meta-test to ensure our AST parsing is working correctly
        and the test is not vacuously passing because no models are found.
        """
        models = find_models_with_aliases(SRC_PATH)

        # We know the codebase has models with aliases, so this should not be empty
        assert len(models) > 0, (
            "No models with Field(alias=...) were found. "
            "This might indicate a bug in the AST parsing logic, "
            "or all alias usages have been removed from the codebase."
        )

    def test_known_models_are_detected(self):
        """
        Verify that known models with aliases are detected.

        This test ensures specific models we know use aliases are found
        by the scanning logic.
        """
        models = find_models_with_aliases(SRC_PATH)

        # Build a set of (filename, classname) tuples for easy lookup
        found_models = {
            (model.file_path.name, model.class_name)
            for model in models
        }

        # Known models that should be detected
        # These are models we know use Field(alias=...) based on code inspection
        # NOTE: ModelIntelligenceConfig was removed as its aliases were deprecated
        expected_models = [
            ("model_workflow.py", "ModelWorkflowStep"),
            ("model_workflow.py", "ModelWorkflowExecution"),
            ("model_reducer.py", "ModelReducerConfig"),
            ("model_orchestrator.py", "ModelOrchestratorConfig"),
        ]

        missing_models = []
        for filename, classname in expected_models:
            if (filename, classname) not in found_models:
                missing_models.append(f"{filename}:{classname}")

        if missing_models:
            # List what was found for debugging
            found_list = [f"{f}:{c}" for f, c in sorted(found_models)]
            pytest.fail(
                f"Expected models not found by scanner:\n"
                f"  Missing: {missing_models}\n"
                f"  Found: {found_list}\n\n"
                f"This might indicate a bug in the AST parsing logic."
            )

    def test_all_found_models_have_correct_config(self):
        """
        Report on all models found and their configuration status.

        This test provides visibility into what models were scanned
        and their populate_by_name status.
        """
        models = find_models_with_aliases(SRC_PATH)

        # Log what was found (will show in pytest -v output)
        print("\n\nModels with Field(alias=...) found:")
        for model in sorted(models, key=lambda m: (str(m.file_path), m.class_name)):
            relative_path = model.file_path.relative_to(SRC_PATH.parent.parent)
            status = "OK" if model.has_populate_by_name else "MISSING populate_by_name"
            print(f"  [{status}] {relative_path}:{model.line_number} - {model.class_name}")
            print(f"           Alias fields: {', '.join(model.alias_fields)}")

        # The actual assertion is in test_models_with_aliases_have_populate_by_name
        # This test is just for reporting


@pytest.mark.unit
class TestASTParsingLogic:
    """Test the AST parsing logic itself."""

    def test_visitor_detects_alias_in_field(self):
        """Test that the visitor correctly detects Field(alias=...)."""
        source = '''
from pydantic import BaseModel, ConfigDict, Field

class TestModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    my_field: int = Field(alias="myField")
    another: str = Field(description="no alias here")
'''
        tree = ast.parse(source)
        visitor = AliasFieldVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.models) == 1
        model = visitor.models[0]
        assert model.class_name == "TestModel"
        assert model.alias_fields == ["my_field"]
        assert model.has_populate_by_name is True

    def test_visitor_detects_missing_populate_by_name(self):
        """Test that visitor detects when populate_by_name is missing."""
        source = '''
from pydantic import BaseModel, Field

class BadModel(BaseModel):
    my_field: int = Field(alias="myField")
'''
        tree = ast.parse(source)
        visitor = AliasFieldVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.models) == 1
        model = visitor.models[0]
        assert model.class_name == "BadModel"
        assert model.has_populate_by_name is False

    def test_visitor_ignores_non_pydantic_classes(self):
        """Test that visitor ignores classes not inheriting from BaseModel."""
        source = '''
class RegularClass:
    pass

class AnotherClass:
    alias: str = "not a pydantic field"
'''
        tree = ast.parse(source)
        visitor = AliasFieldVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.models) == 0

    def test_visitor_handles_multiple_alias_fields(self):
        """Test that visitor detects multiple alias fields in one model."""
        source = '''
from pydantic import BaseModel, ConfigDict, Field

class MultiAliasModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field_one: int = Field(alias="fieldOne")
    field_two: str = Field(alias="fieldTwo")
    field_three: bool = Field(description="no alias")
'''
        tree = ast.parse(source)
        visitor = AliasFieldVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.models) == 1
        model = visitor.models[0]
        assert set(model.alias_fields) == {"field_one", "field_two"}

    def test_visitor_handles_configdict_with_other_options(self):
        """Test that visitor detects populate_by_name among other options."""
        source = '''
from pydantic import BaseModel, ConfigDict, Field

class ConfiguredModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        frozen=True,
    )

    my_field: int = Field(alias="myField")
'''
        tree = ast.parse(source)
        visitor = AliasFieldVisitor(Path("test.py"))
        visitor.visit(tree)

        assert len(visitor.models) == 1
        assert visitor.models[0].has_populate_by_name is True
