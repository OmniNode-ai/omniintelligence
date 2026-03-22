# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for ModelCodeEntity and ModelCodeRelationship.

Validates that the Pydantic models are frozen, forbid extra fields,
and accept the correct field names as defined in the model contract.
"""

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.models import (
    ModelCodeEntity,
    ModelCodeRelationship,
)


@pytest.mark.unit
class TestModelCodeEntity:
    def test_create_entity_with_all_fields(self) -> None:
        entity = ModelCodeEntity(
            id="550e8400-e29b-41d4-a716-446655440000",
            entity_name="MyService",
            entity_type="class",
            qualified_name="services.my_service.MyService",
            source_repo="omniintelligence",
            source_path="src/services/my_service.py",
            line_number=10,
            bases=["BaseModel"],
            methods=[{"name": "execute"}, {"name": "validate"}],
            fields=[{"name": "timeout", "type": "int"}],
            decorators=["frozen"],
            docstring="A service class.",
            signature=None,
            file_hash="abc123def456",  # pragma: allowlist secret
            source_language="python",
            confidence=1.0,
        )

        assert entity.id == "550e8400-e29b-41d4-a716-446655440000"
        assert entity.entity_name == "MyService"
        assert entity.entity_type == "class"
        assert entity.qualified_name == "services.my_service.MyService"
        assert entity.source_path == "src/services/my_service.py"
        assert entity.source_repo == "omniintelligence"
        assert entity.line_number == 10
        assert entity.bases == ["BaseModel"]
        assert entity.methods == [{"name": "execute"}, {"name": "validate"}]
        assert entity.decorators == ["frozen"]
        assert entity.docstring == "A service class."

        # Verify frozen
        with pytest.raises(Exception):
            entity.entity_name = "Changed"  # type: ignore[misc]

    def test_entity_defaults(self) -> None:
        entity = ModelCodeEntity(
            id="fn-001",
            entity_name="process",
            entity_type="function",
            qualified_name="main.process",
            source_repo="omnibase_core",
            source_path="src/main.py",
            file_hash="deadbeef",  # pragma: allowlist secret
        )

        assert entity.line_number is None
        assert entity.bases == []
        assert entity.methods == []
        assert entity.fields == []
        assert entity.decorators == []
        assert entity.docstring is None
        assert entity.signature is None
        assert entity.source_language == "python"
        assert entity.confidence == 1.0

    def test_entity_extra_forbid(self) -> None:
        with pytest.raises(Exception):
            ModelCodeEntity(
                id="fn-x",
                entity_name="x",
                entity_type="function",
                qualified_name="x",
                source_repo="repo",
                source_path="a.py",
                file_hash="abc",
                unknown_field="bad",  # type: ignore[call-arg]
            )


@pytest.mark.unit
class TestModelCodeRelationship:
    def test_create_relationship(self) -> None:
        rel = ModelCodeRelationship(
            id="rel-001",
            source_entity="services.my_service.MyService",
            target_entity="BaseModel",
            relationship_type="inherits",
            trust_tier="strong",
            confidence=1.0,
            evidence=["class MyService(BaseModel)"],
        )

        assert rel.id == "rel-001"
        assert rel.source_entity == "services.my_service.MyService"
        assert rel.target_entity == "BaseModel"
        assert rel.relationship_type == "inherits"
        assert rel.trust_tier == "strong"
        assert rel.confidence == 1.0
        assert rel.evidence == ["class MyService(BaseModel)"]
        assert rel.inject_into_context is True  # default

        # Verify frozen
        with pytest.raises(Exception):
            rel.trust_tier = "weak"  # type: ignore[misc]

    def test_relationship_defaults(self) -> None:
        rel = ModelCodeRelationship(
            id="rel-002",
            source_entity="mod_main",
            target_entity="fn_process",
            relationship_type="contains",
            trust_tier="moderate",
        )

        assert rel.confidence == 1.0
        assert rel.evidence == []
        assert rel.inject_into_context is True

    def test_relationship_extra_forbid(self) -> None:
        with pytest.raises(Exception):
            ModelCodeRelationship(
                id="rel-x",
                source_entity="a",
                target_entity="b",
                relationship_type="calls",
                trust_tier="weak",
                unknown="bad",  # type: ignore[call-arg]
            )
