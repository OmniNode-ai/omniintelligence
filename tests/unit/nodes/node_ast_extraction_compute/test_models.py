# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for ModelCodeEntity and ModelCodeRelationship."""

import pytest

from omniintelligence.enums import EnumEntityType, EnumRelationshipType
from omniintelligence.models.model_entity import ModelEntity
from omniintelligence.models.model_relationship import ModelRelationship
from omniintelligence.nodes.node_ast_extraction_compute.models import (
    ModelCodeEntity,
    ModelCodeRelationship,
)


@pytest.mark.unit
class TestModelCodeEntity:
    def test_create_entity_and_project_to_graph(self) -> None:
        entity = ModelCodeEntity(
            entity_id="cls_MyService",
            entity_type=EnumEntityType.CLASS,
            name="MyService",
            file_path="src/services/my_service.py",
            file_hash="abc123def456",
            source_repo="omniintelligence",
            line_start=10,
            line_end=50,
            bases=["BaseModel"],
            methods=["execute", "validate"],
            decorators=["frozen"],
            docstring="A service class.",
            source_code="class MyService(BaseModel): ...",
            confidence=1.0,
        )

        assert entity.entity_id == "cls_MyService"
        assert entity.entity_type == EnumEntityType.CLASS
        assert entity.name == "MyService"
        assert entity.bases == ["BaseModel"]
        assert entity.methods == ["execute", "validate"]
        assert entity.decorators == ["frozen"]
        assert entity.docstring == "A service class."

        # Verify frozen
        with pytest.raises(Exception):
            entity.name = "Changed"  # type: ignore[misc]

        # Verify to_graph_entity projection
        graph_entity = entity.to_graph_entity()
        assert isinstance(graph_entity, ModelEntity)
        assert graph_entity.entity_id == "cls_MyService"
        assert graph_entity.entity_type == EnumEntityType.CLASS
        assert graph_entity.name == "MyService"
        assert graph_entity.metadata["file_path"] == "src/services/my_service.py"
        assert graph_entity.metadata["line_start"] == 10
        assert graph_entity.metadata["line_end"] == 50
        assert graph_entity.metadata["source"] == "omniintelligence"
        assert graph_entity.metadata["docstring"] == "A service class."

    def test_entity_defaults(self) -> None:
        entity = ModelCodeEntity(
            entity_id="fn_process",
            entity_type=EnumEntityType.FUNCTION,
            name="process",
            file_path="src/main.py",
            file_hash="deadbeef",
            source_repo="omnibase_core",
            line_start=1,
            line_end=5,
        )

        assert entity.bases == []
        assert entity.methods == []
        assert entity.decorators == []
        assert entity.docstring is None
        assert entity.source_code is None
        assert entity.confidence == 1.0

    def test_entity_extra_forbid(self) -> None:
        with pytest.raises(Exception):
            ModelCodeEntity(
                entity_id="fn_x",
                entity_type=EnumEntityType.FUNCTION,
                name="x",
                file_path="a.py",
                file_hash="abc",
                source_repo="repo",
                line_start=1,
                line_end=2,
                unknown_field="bad",  # type: ignore[call-arg]
            )


@pytest.mark.unit
class TestModelCodeRelationship:
    def test_create_relationship_and_project_to_graph(self) -> None:
        rel = ModelCodeRelationship(
            relationship_id="rel_001",
            source_entity_id="cls_MyService",
            target_entity_id="cls_BaseModel",
            relationship_type=EnumRelationshipType.EXTENDS,
            confidence=1.0,
            trust_tier="conservative",
            metadata={"file_path": "src/services/my_service.py"},
        )

        assert rel.relationship_id == "rel_001"
        assert rel.source_entity_id == "cls_MyService"
        assert rel.target_entity_id == "cls_BaseModel"
        assert rel.relationship_type == EnumRelationshipType.EXTENDS
        assert rel.trust_tier == "conservative"

        # Verify frozen
        with pytest.raises(Exception):
            rel.trust_tier = "weak"  # type: ignore[misc]

        # Verify to_graph_relationship projection
        graph_rel = rel.to_graph_relationship()
        assert isinstance(graph_rel, ModelRelationship)
        assert graph_rel.source_id == "cls_MyService"
        assert graph_rel.target_id == "cls_BaseModel"
        assert graph_rel.relationship_type == EnumRelationshipType.EXTENDS
        assert graph_rel.confidence == 1.0

    def test_relationship_defaults(self) -> None:
        rel = ModelCodeRelationship(
            relationship_id="rel_002",
            source_entity_id="mod_main",
            target_entity_id="fn_process",
            relationship_type=EnumRelationshipType.CONTAINS,
        )

        assert rel.confidence == 1.0
        assert rel.trust_tier == "conservative"
        assert rel.metadata == {}

    def test_relationship_extra_forbid(self) -> None:
        with pytest.raises(Exception):
            ModelCodeRelationship(
                relationship_id="rel_x",
                source_entity_id="a",
                target_entity_id="b",
                relationship_type=EnumRelationshipType.CALLS,
                unknown="bad",  # type: ignore[call-arg]
            )
