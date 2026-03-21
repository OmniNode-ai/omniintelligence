# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the AST extraction handler.

Ticket: OMN-5659
"""

from __future__ import annotations

import textwrap

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
    AstExtractInput,
    ExtractorConfig,
    handle_ast_extract,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FILE_HASH = "abc123def456"  # pragma: allowlist secret
_REPO = "test_repo"
_PATH = "src/mypackage/example.py"
_CRAWL = "crawl-001"


def _make_input(
    source: str,
    *,
    path: str = _PATH,
    config: ExtractorConfig | None = None,
) -> AstExtractInput:
    return AstExtractInput(
        source_content=textwrap.dedent(source),
        source_path=path,
        source_repo=_REPO,
        file_hash=_FILE_HASH,
        crawl_id=_CRAWL,
        config=config or ExtractorConfig(),
    )


# ---------------------------------------------------------------------------
# Test 1: class + function + import
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extracts_class_function_and_import() -> None:
    """Parse a file with a class, function, and import and verify entities."""
    source = """\
    import os

    class Greeter:
        \"\"\"A simple greeter.\"\"\"

        def greet(self, name: str) -> str:
            return f"Hello, {name}"

    def top_level_func(x: int) -> int:
        return x + 1
    """
    result = handle_ast_extract(_make_input(source))

    assert result.parse_status == "success"
    assert result.parse_error is None
    assert result.repo_name == _REPO
    assert result.file_hash == _FILE_HASH

    entity_types = {e.entity_type for e in result.entities}
    assert "class" in entity_types
    assert "function" in entity_types
    assert "import" in entity_types

    # Verify at least 3 entities (class + function + import)
    assert len(result.entities) >= 3

    # Check class details
    class_entities = [e for e in result.entities if e.entity_type == "class"]
    assert len(class_entities) == 1
    cls = class_entities[0]
    assert cls.entity_name == "Greeter"
    assert cls.qualified_name == "mypackage.example.Greeter"
    assert cls.docstring == "A simple greeter."
    assert len(cls.methods) == 1
    assert cls.methods[0]["name"] == "greet"

    # Check function details
    func_entities = [e for e in result.entities if e.entity_type == "function"]
    assert len(func_entities) == 1
    func = func_entities[0]
    assert func.entity_name == "top_level_func"
    assert func.signature is not None

    # Check import
    import_entities = [e for e in result.entities if e.entity_type == "import"]
    assert len(import_entities) == 1
    assert import_entities[0].entity_name == "os"

    # Relationships should include defines + imports
    rel_types = {r.relationship_type for r in result.relationships}
    assert "defines" in rel_types
    assert "imports" in rel_types


# ---------------------------------------------------------------------------
# Test 2: Protocol detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detects_protocol() -> None:
    """A class inheriting from Protocol should have entity_type='protocol'."""
    source = """\
    from typing import Protocol

    class MyProtocol(Protocol):
        def do_something(self) -> None:
            ...
    """
    result = handle_ast_extract(_make_input(source))

    assert result.parse_status == "success"

    protocol_entities = [e for e in result.entities if e.entity_type == "protocol"]
    assert len(protocol_entities) == 1
    proto = protocol_entities[0]
    assert proto.entity_name == "MyProtocol"
    assert "Protocol" in proto.bases
    assert len(proto.methods) == 1
    assert proto.methods[0]["name"] == "do_something"

    # Inheritance relationship
    inherits = [r for r in result.relationships if r.relationship_type == "inherits"]
    assert len(inherits) >= 1
    assert any(r.target_entity == "Protocol" for r in inherits)


# ---------------------------------------------------------------------------
# Test 3: Pydantic model detection with fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detects_pydantic_model_with_fields() -> None:
    """A class inheriting from BaseModel should have entity_type='model' with fields."""
    source = """\
    from pydantic import BaseModel

    class MyModel(BaseModel):
        name: str
        age: int = 0
        tags: list[str] = []
    """
    result = handle_ast_extract(_make_input(source))

    assert result.parse_status == "success"

    model_entities = [e for e in result.entities if e.entity_type == "model"]
    assert len(model_entities) == 1
    model = model_entities[0]
    assert model.entity_name == "MyModel"
    assert "BaseModel" in model.bases

    # Check extracted fields
    assert len(model.fields) == 3
    field_names = {f["name"] for f in model.fields}
    assert field_names == {"name", "age", "tags"}

    # Verify field types
    name_field = next(f for f in model.fields if f["name"] == "name")
    assert name_field["type"] == "str"


# ---------------------------------------------------------------------------
# Test 4: Syntax error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_syntax_error_returns_empty_entities() -> None:
    """A file with a syntax error should return parse_status='syntax_error'."""
    source = """\
    def broken(
        # missing closing paren and colon
    """
    result = handle_ast_extract(_make_input(source))

    assert result.parse_status == "syntax_error"
    assert result.parse_error is not None
    assert result.entities == []
    assert result.relationships == []
    assert result.repo_name == _REPO


# ---------------------------------------------------------------------------
# Test 5: Module constants
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extracts_module_constants() -> None:
    """UPPER_CASE assignments at module level should be extracted as constants."""
    source = """\
    MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 30.0
    _private = "not a constant"
    lower_case = "also not a constant"
    """
    result = handle_ast_extract(_make_input(source))

    assert result.parse_status == "success"
    constant_entities = [e for e in result.entities if e.entity_type == "constant"]
    constant_names = {e.entity_name for e in constant_entities}
    assert "MAX_RETRIES" in constant_names
    assert "DEFAULT_TIMEOUT" in constant_names
    assert "_private" not in constant_names
    assert "lower_case" not in constant_names


# ---------------------------------------------------------------------------
# Test 6: Config disables extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_config_disables_class_extraction() -> None:
    """When classes_enabled=False, classes should not be extracted."""
    source = """\
    class ShouldBeIgnored:
        pass

    def should_be_extracted():
        pass
    """
    cfg = ExtractorConfig(classes_enabled=False)
    result = handle_ast_extract(_make_input(source, config=cfg))

    assert result.parse_status == "success"
    entity_types = {e.entity_type for e in result.entities}
    assert "class" not in entity_types
    assert "function" in entity_types


# ---------------------------------------------------------------------------
# Test 7: Qualified name construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_qualified_name_from_path() -> None:
    """Verify qualified names are derived from file path correctly."""
    source = """\
    def hello():
        pass
    """
    result = handle_ast_extract(
        _make_input(source, path="src/omniintelligence/nodes/foo/bar.py")
    )

    func = next(e for e in result.entities if e.entity_type == "function")
    assert func.qualified_name == "omniintelligence.nodes.foo.bar.hello"


# ---------------------------------------------------------------------------
# Test 8: from-import extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_import_extraction() -> None:
    """from X import Y should produce qualified_name X.Y."""
    source = """\
    from os.path import join
    """
    result = handle_ast_extract(_make_input(source))

    import_entities = [e for e in result.entities if e.entity_type == "import"]
    assert len(import_entities) == 1
    assert import_entities[0].qualified_name == "os.path.join"

    import_rels = [r for r in result.relationships if r.relationship_type == "imports"]
    assert len(import_rels) == 1
    assert import_rels[0].target_entity == "os.path.join"
