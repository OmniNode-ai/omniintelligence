# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for event wire models.

Validates that ModelCodeFileDiscoveredEvent and ModelCodeEntitiesExtractedEvent
are frozen, serialization-roundtrip safe, and use correct model field names.
"""

import pytest

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
            id="550e8400-e29b-41d4-a716-446655440000",
            entity_name="Foo",
            entity_type="class",
            qualified_name="foo.Foo",
            source_repo="omniintelligence",
            source_path="src/foo.py",
            line_number=1,
            file_hash="hash1",
        )
        rel = ModelCodeRelationship(
            id="rel-001",
            source_entity="foo.Foo",
            target_entity="foo",
            relationship_type="contains",
            trust_tier="moderate",
            evidence=["module contains class Foo"],
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
        assert event.entities[0].entity_name == "Foo"

        # Serialization roundtrip
        json_str = event.model_dump_json()
        restored = ModelCodeEntitiesExtractedEvent.model_validate_json(json_str)
        assert restored.entity_count == 1
        assert restored.relationship_count == 1
        assert restored.entities[0].id == "550e8400-e29b-41d4-a716-446655440000"
        assert restored.relationships[0].id == "rel-001"
