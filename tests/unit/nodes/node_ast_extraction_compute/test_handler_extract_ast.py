# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for AST extraction handler."""

import textwrap

import pytest

from omniintelligence.enums import EnumEntityType, EnumRelationshipType
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

        # Should have: module, class, class.execute method, process_data function
        entity_names = {e.name for e in result.entities}
        assert "src.services.my_service" in entity_names  # MODULE
        assert "MyService" in entity_names  # CLASS
        assert "MyService.execute" in entity_names  # METHOD (via DEFINES)
        assert "process_data" in entity_names  # FUNCTION

        # Check entity types
        entities_by_name = {e.name: e for e in result.entities}
        assert entities_by_name["MyService"].entity_type == EnumEntityType.CLASS
        assert entities_by_name["MyService"].bases == ["BaseModel"]
        assert entities_by_name["MyService"].methods == ["execute"]
        assert entities_by_name["MyService"].docstring == "A service class."
        assert entities_by_name["process_data"].entity_type == EnumEntityType.FUNCTION

        # Check relationships
        rel_types = {(r.relationship_type, r.trust_tier) for r in result.relationships}
        assert (EnumRelationshipType.IMPORTS, "conservative") in rel_types
        assert (EnumRelationshipType.EXTENDS, "conservative") in rel_types
        assert (EnumRelationshipType.CONTAINS, "moderate") in rel_types
        assert (EnumRelationshipType.DEFINES, "moderate") in rel_types

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

        entities_by_name = {e.name: e for e in result.entities}

        # Constant
        assert "MAX_RETRIES" in entities_by_name
        assert entities_by_name["MAX_RETRIES"].entity_type == EnumEntityType.CONSTANT

        # Class with decorators
        assert "Config" in entities_by_name
        config = entities_by_name["Config"]
        assert config.entity_type == EnumEntityType.CLASS
        assert "dataclass" in config.decorators
        assert config.docstring == "Configuration container."
        assert "default" in config.methods

        # Method with decorator
        assert "Config.default" in entities_by_name
        method = entities_by_name["Config.default"]
        assert method.entity_type == EnumEntityType.FUNCTION
        assert "staticmethod" in method.decorators

        # Trust tiers
        for rel in result.relationships:
            if (
                rel.relationship_type == EnumRelationshipType.DEFINES
                or rel.relationship_type == EnumRelationshipType.CONTAINS
            ):
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
