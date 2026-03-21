# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for event wire models."""

import pytest

from omniintelligence.enums import EnumEntityType, EnumRelationshipType
from omniintelligence.nodes.node_ast_extraction_compute.models import (
    ModelCodeEntitiesExtractedEvent,
    ModelCodeEntity,
    ModelCodeFileDiscoveredEvent,
    ModelCodeRelationship,
)


@pytest.mark.unit
class TestModelCodeFileDiscoveredEvent:
    def test_create_and_roundtrip(self) -> None:
        event = ModelCodeFileDiscoveredEvent(
            event_id="evt_001",
            crawl_id="crawl_001",
            repo_name="omniintelligence",
            file_path="src/main.py",
            file_hash="abc123",
            file_extension=".py",
        )

        assert event.event_id == "evt_001"
        assert event.repo_name == "omniintelligence"
        assert event.file_extension == ".py"

        # Verify frozen
        with pytest.raises(Exception):
            event.repo_name = "changed"  # type: ignore[misc]

        # Serialization roundtrip
        json_str = event.model_dump_json()
        restored = ModelCodeFileDiscoveredEvent.model_validate_json(json_str)
        assert restored.event_id == event.event_id
        assert restored.crawl_id == event.crawl_id
        assert restored.file_path == event.file_path
        assert restored.file_hash == event.file_hash


@pytest.mark.unit
class TestModelCodeEntitiesExtractedEvent:
    def test_create_with_entities_and_roundtrip(self) -> None:
        entity = ModelCodeEntity(
            entity_id="cls_Foo",
            entity_type=EnumEntityType.CLASS,
            name="Foo",
            file_path="src/foo.py",
            file_hash="hash1",
            source_repo="omniintelligence",
            line_start=1,
            line_end=10,
        )
        rel = ModelCodeRelationship(
            relationship_id="rel_001",
            source_entity_id="cls_Foo",
            target_entity_id="mod_foo",
            relationship_type=EnumRelationshipType.CONTAINS,
            trust_tier="moderate",
        )
        event = ModelCodeEntitiesExtractedEvent(
            event_id="evt_002",
            crawl_id="crawl_001",
            repo_name="omniintelligence",
            file_path="src/foo.py",
            file_hash="hash1",
            entities=[entity],
            relationships=[rel],
            entity_count=1,
            relationship_count=1,
        )

        assert event.entity_count == len(event.entities)
        assert event.relationship_count == len(event.relationships)
        assert event.entities[0].name == "Foo"

        # Serialization roundtrip
        json_str = event.model_dump_json()
        restored = ModelCodeEntitiesExtractedEvent.model_validate_json(json_str)
        assert restored.entity_count == 1
        assert restored.relationship_count == 1
        assert restored.entities[0].entity_id == "cls_Foo"
        assert restored.relationships[0].relationship_id == "rel_001"
