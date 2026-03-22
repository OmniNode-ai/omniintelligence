# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for AST extraction handler (handler_extract_ast.py).

Validates that extract_entities_from_source produces ModelCodeEntity and
ModelCodeRelationship instances with correct field names aligned to the
model contract.
"""

import textwrap

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    extract_entities_from_source,
)


@pytest.mark.unit
class TestExtractEntitiesFromSource:
    def test_basic_extraction(self) -> None:
        """Python source with class, function, and import extracts expected entities."""
        source = textwrap.dedent("""\
            from pydantic import BaseModel

            class MyService(BaseModel):
                \"\"\"A service class.\"\"\"

                def execute(self) -> None:
                    pass

            def process_data(items: list) -> list:
                return items
        """)

        result = extract_entities_from_source(
            source,
            file_path="src/services/my_service.py",
            source_repo="omniintelligence",
        )

        # Should have: module, class, class.execute method, process_data function,
        # plus import entities
        entity_names = {e.entity_name for e in result.entities}
        assert "services.my_service" in entity_names  # MODULE
        assert "MyService" in entity_names  # CLASS
        assert "MyService.execute" in entity_names  # METHOD (via DEFINES)
        assert "process_data" in entity_names  # FUNCTION

        # Check entity types
        entities_by_name = {e.entity_name: e for e in result.entities}
        assert entities_by_name["MyService"].entity_type == "class"
        assert entities_by_name["MyService"].bases == ["BaseModel"]
        assert entities_by_name["MyService"].docstring == "A service class."
        assert entities_by_name["process_data"].entity_type == "function"

        # Check qualified names
        assert (
            entities_by_name["MyService"].qualified_name
            == "services.my_service.MyService"
        )
        assert (
            entities_by_name["process_data"].qualified_name
            == "services.my_service.process_data"
        )

        # Check model fields are present (contract alignment)
        my_service = entities_by_name["MyService"]
        assert my_service.id  # UUID string
        assert my_service.source_path == "src/services/my_service.py"
        assert my_service.source_repo == "omniintelligence"
        assert my_service.line_number is not None
        assert my_service.file_hash  # SHA256

        # Check relationships use string types
        rel_types = {(r.relationship_type, r.trust_tier) for r in result.relationships}
        assert ("imports", "strong") in rel_types
        assert ("inherits", "strong") in rel_types
        assert ("contains", "moderate") in rel_types
        assert ("defines", "moderate") in rel_types

        # All entities should have confidence=1.0
        for entity in result.entities:
            assert entity.confidence == 1.0

    def test_nested_class_with_decorators(self) -> None:
        """Class with decorators and constant extracts all metadata."""
        source = textwrap.dedent("""\
            MAX_RETRIES = 3

            @dataclass(frozen=True)
            class Config:
                \"\"\"Configuration container.\"\"\"
                timeout: int = 30

                @staticmethod
                def default() -> "Config":
                    return Config()
        """)

        result = extract_entities_from_source(
            source,
            file_path="src/config.py",
            source_repo="omnibase_core",
        )

        entities_by_name = {e.entity_name: e for e in result.entities}

        # Constant
        assert "MAX_RETRIES" in entities_by_name
        assert entities_by_name["MAX_RETRIES"].entity_type == "constant"

        # Class with decorators
        assert "Config" in entities_by_name
        config = entities_by_name["Config"]
        assert config.entity_type == "class"
        assert "dataclass" in config.decorators
        assert config.docstring == "Configuration container."
        # methods is list[dict] now
        method_names = [m["name"] for m in config.methods]
        assert "default" in method_names

        # Method with decorator
        assert "Config.default" in entities_by_name
        method = entities_by_name["Config.default"]
        assert method.entity_type == "function"
        assert "staticmethod" in method.decorators

        # Trust tiers on relationships
        for rel in result.relationships:
            if rel.relationship_type in ("defines", "contains"):
                assert rel.trust_tier == "moderate"

    def test_syntax_error_returns_empty(self) -> None:
        """Invalid Python returns empty result without raising."""
        result = extract_entities_from_source(
            "def broken(:\n  pass",
            file_path="bad.py",
            source_repo="test",
        )
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    def test_relationship_evidence(self) -> None:
        """Relationships include evidence strings."""
        source = textwrap.dedent("""\
            class Foo:
                pass
        """)

        result = extract_entities_from_source(
            source,
            file_path="src/foo.py",
            source_repo="test",
        )

        for rel in result.relationships:
            assert isinstance(rel.evidence, list)
            assert len(rel.evidence) > 0
            assert isinstance(rel.evidence[0], str)

    def test_import_from_extraction(self) -> None:
        """ImportFrom statements create import entities with correct fields."""
        source = textwrap.dedent("""\
            from os.path import join, exists
        """)

        result = extract_entities_from_source(
            source,
            file_path="src/util.py",
            source_repo="test",
        )

        import_entities = [e for e in result.entities if e.entity_type == "import"]
        assert len(import_entities) == 2

        import_names = {e.entity_name for e in import_entities}
        assert "join" in import_names
        assert "exists" in import_names

        # Check qualified names include module path
        for e in import_entities:
            assert e.qualified_name.startswith("os.path.")
