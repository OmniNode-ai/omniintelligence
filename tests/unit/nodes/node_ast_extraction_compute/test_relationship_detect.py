# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for handler_relationship_detect.

Ticket: OMN-5660
"""

from __future__ import annotations

import textwrap

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_relationship_detect import (
    detect_relationships,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)


def _make_entity(name: str, entity_type: str = "class") -> ModelCodeEntity:
    """Create a minimal ModelCodeEntity for testing."""
    return ModelCodeEntity(
        id="test-id",
        entity_name=name,
        entity_type=entity_type,
        qualified_name=f"test_module.{name}",
        source_repo="test-repo",
        source_path="src/test_module.py",
        file_hash="abc123",
    )


# ---------------------------------------------------------------------------
# Test: INHERITS (already emitted by handler_ast_extract, but the detector
# config path should leave them untouched — we test that inherits is NOT
# duplicated by detect_relationships since it only adds implements+calls)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInheritsRelationship:
    """INHERITS relationships are emitted by handler_ast_extract, not by
    detect_relationships.  Verify that detect_relationships does NOT
    re-emit inherits (it only adds implements and calls)."""

    def test_inherits_not_duplicated(self) -> None:
        source = textwrap.dedent("""\
            class BaseHandler:
                pass

            class Handler(BaseHandler):
                pass
        """)
        entities = [_make_entity("BaseHandler"), _make_entity("Handler")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        inherits_rels = [r for r in rels if r.relationship_type == "inherits"]
        assert len(inherits_rels) == 0, (
            "detect_relationships should NOT emit inherits — "
            "that is handled by handler_ast_extract"
        )


# ---------------------------------------------------------------------------
# Test: IMPORTS (same reasoning — emitted by handler_ast_extract)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestImportsRelationship:
    """IMPORTS relationships are emitted by handler_ast_extract, not by
    detect_relationships."""

    def test_imports_not_duplicated(self) -> None:
        source = textwrap.dedent("""\
            from omnibase_core import BaseModel
        """)
        entities = [_make_entity("BaseModel", "import")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        imports_rels = [r for r in rels if r.relationship_type == "imports"]
        assert len(imports_rels) == 0


# ---------------------------------------------------------------------------
# Test: IMPLEMENTS (conservative gate)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestImplementsRelationship:
    """Test the conservative IMPLEMENTS detection."""

    def test_implements_with_protocol_import(self) -> None:
        """Class implementing an explicitly imported Protocol is detected."""
        source = textwrap.dedent("""\
            from typing import Protocol

            class MyProtocol(Protocol):
                def foo(self) -> None: ...

            class MyImpl(MyProtocol):
                def foo(self) -> None:
                    pass
        """)
        entities = [_make_entity("MyProtocol", "protocol"), _make_entity("MyImpl")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        impl_rels = [r for r in rels if r.relationship_type == "implements"]
        # MyProtocol(Protocol) triggers: Protocol is imported from typing
        # MyImpl(MyProtocol) triggers: MyProtocol ends with "Protocol"
        # but MyProtocol itself inherits Protocol — that's an implements too

        # We expect MyImpl -> MyProtocol (MyProtocol ends with "Protocol"
        # and is locally defined, matching the heuristic for imported names)
        # AND MyProtocol -> Protocol (Protocol is imported from typing)
        assert len(impl_rels) >= 1
        # At minimum, MyProtocol -> Protocol should exist
        proto_impl = [r for r in impl_rels if r.target_entity == "Protocol"]
        assert len(proto_impl) == 1
        assert proto_impl[0].confidence == 0.8
        assert proto_impl[0].trust_tier == "conservative"
        assert "implements" in proto_impl[0].evidence[0]

    def test_implements_gate_rejects_non_protocol(self) -> None:
        """Class inheriting a non-Protocol base does NOT emit implements."""
        source = textwrap.dedent("""\
            from some_module import SomeBase

            class MyClass(SomeBase):
                def foo(self) -> None:
                    pass
        """)
        entities = [_make_entity("MyClass")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        impl_rels = [r for r in rels if r.relationship_type == "implements"]
        assert len(impl_rels) == 0, (
            "SomeBase is not a Protocol import — implements should NOT be emitted"
        )

    def test_implements_custom_protocol_import(self) -> None:
        """A base imported with a name ending in 'Protocol' is detected."""
        source = textwrap.dedent("""\
            from mylib.interfaces import StorageProtocol

            class DiskStorage(StorageProtocol):
                def read(self) -> bytes:
                    return b""
        """)
        entities = [_make_entity("DiskStorage")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        impl_rels = [r for r in rels if r.relationship_type == "implements"]
        assert len(impl_rels) == 1
        assert impl_rels[0].source_entity == "pkg.module.DiskStorage"
        assert impl_rels[0].target_entity == "StorageProtocol"
        assert impl_rels[0].confidence == 0.8


# ---------------------------------------------------------------------------
# Test: CALLS (weak tier)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCallsRelationship:
    """Test CALLS detection with entity name matching."""

    def test_calls_known_entity(self) -> None:
        """Function call matching a known entity name is detected."""
        source = textwrap.dedent("""\
            def main():
                result = do_something()
                return result
        """)
        entities = [_make_entity("do_something", "function")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        call_rels = [r for r in rels if r.relationship_type == "calls"]
        assert len(call_rels) == 1
        assert call_rels[0].target_entity == "do_something"
        assert call_rels[0].confidence == 0.5
        assert call_rels[0].trust_tier == "weak"
        assert call_rels[0].inject_into_context is False
        assert "calls do_something" in call_rels[0].evidence[0]

    def test_calls_unknown_entity_not_emitted(self) -> None:
        """Function call NOT matching a known entity is not emitted."""
        source = textwrap.dedent("""\
            def main():
                result = unknown_function()
                return result
        """)
        entities = [_make_entity("Handler")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        call_rels = [r for r in rels if r.relationship_type == "calls"]
        assert len(call_rels) == 0

    def test_calls_syntax_error_returns_empty(self) -> None:
        """Source with syntax errors returns empty list."""
        source = "def broken(:\n    pass"
        entities = [_make_entity("broken", "function")]
        rels = detect_relationships(
            source_code=source,
            file_path="src/pkg/module.py",
            repo_name="test-repo",
            entities=entities,
        )
        assert rels == []
