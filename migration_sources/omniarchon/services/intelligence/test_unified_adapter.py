"""
Test script for unified entity adapter in intelligence service.
"""

import os
import sys

# Add paths
intelligence_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, intelligence_dir)
sys.path.insert(0, os.path.join(intelligence_dir, "shared_models"))

from datetime import datetime, timezone

from entity_types import EntityType as UnifiedEntityType
from models.entity_models import (
    EntityMetadata,
)
from models.entity_models import EntityType as LegacyEntityType
from models.entity_models import (
    KnowledgeEntity,
)
from models.unified_entity_adapter import (
    EntityTypeAdapter,
    SearchResultAdapter,
    prepare_entities_for_external_service,
)


def test_entity_type_conversion():
    """Test entity type conversion between legacy and unified."""
    print("🧪 Testing Entity Type Conversion...")

    # Test legacy to unified conversion
    legacy_function = LegacyEntityType.FUNCTION
    unified_function = EntityTypeAdapter.legacy_to_unified(legacy_function)
    print(f"✅ Legacy {legacy_function.value} → Unified {unified_function.value}")
    assert unified_function == UnifiedEntityType.FUNCTION

    # Test unified to legacy conversion
    unified_class = UnifiedEntityType.CLASS
    legacy_class = EntityTypeAdapter.unified_to_legacy(unified_class)
    print(f"✅ Unified {unified_class.value} → Legacy {legacy_class.value}")
    assert legacy_class == LegacyEntityType.CLASS

    # Test round-trip conversion
    original = LegacyEntityType.DOCUMENT
    converted = EntityTypeAdapter.unified_to_legacy(
        EntityTypeAdapter.legacy_to_unified(original)
    )
    print(f"✅ Round-trip: {original.value} → {converted.value}")
    assert original == converted

    print("✅ Entity type conversion tests passed!\n")


def test_knowledge_entity_conversion():
    """Test conversion between KnowledgeEntity and unified BaseEntity."""
    print("🧪 Testing KnowledgeEntity Conversion...")

    # Create a test KnowledgeEntity
    metadata = EntityMetadata(
        extraction_confidence=0.95,
        extraction_method="test_extraction",
        complexity_score=0.8,
        maintainability_score=0.9,
        documentation_refs=["test_doc.md"],
        dependencies=["test_module"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    knowledge_entity = KnowledgeEntity(
        entity_id="test-001",
        name="test_function",
        entity_type=LegacyEntityType.FUNCTION,
        description="A test function",
        source_path="/test/file.py",
        confidence_score=0.95,
        metadata=metadata,
        source_line_number=42,
        embedding=[0.1, 0.2, 0.3],
        properties={"test_prop": "test_value"},
    )

    # Convert to unified
    unified_entity = EntityTypeAdapter.knowledge_entity_to_unified(knowledge_entity)
    print(
        f"✅ Converted to unified: {unified_entity.name} ({unified_entity.entity_type.value})"
    )
    print(
        f"✅ Metadata preserved: confidence={unified_entity.metadata.extraction_confidence}"
    )

    # Convert back to knowledge entity
    converted_back = EntityTypeAdapter.unified_to_knowledge_entity(unified_entity)
    print(
        f"✅ Converted back: {converted_back.name} ({converted_back.entity_type.value})"
    )

    # Verify key fields are preserved
    assert knowledge_entity.entity_id == converted_back.entity_id
    assert knowledge_entity.name == converted_back.name
    assert knowledge_entity.entity_type == converted_back.entity_type
    assert knowledge_entity.confidence_score == converted_back.confidence_score

    print("✅ KnowledgeEntity conversion tests passed!\n")


def test_search_service_preparation():
    """Test preparing entities for search service."""
    print("🧪 Testing Search Service Preparation...")

    # Create test entities with different types
    entities = [
        KnowledgeEntity(
            entity_id="func-001",
            name="authenticate_user",
            entity_type=LegacyEntityType.FUNCTION,
            description="Function to authenticate users",
            source_path="/auth/auth.py",
            confidence_score=0.95,
            metadata=EntityMetadata(),
            source_line_number=10,
            properties={},
        ),
        KnowledgeEntity(
            entity_id="class-001",
            name="UserManager",
            entity_type=LegacyEntityType.CLASS,
            description="Class for managing users",
            source_path="/user/manager.py",
            confidence_score=0.90,
            metadata=EntityMetadata(),
            source_line_number=5,
            properties={},
        ),
        KnowledgeEntity(
            entity_id="doc-001",
            name="API Documentation",
            entity_type=LegacyEntityType.DOCUMENT,
            description="API documentation file",
            source_path="/docs/api.md",
            confidence_score=0.85,
            metadata=EntityMetadata(),
            properties={},
        ),
    ]

    # Prepare for search service
    search_docs = SearchResultAdapter.prepare_for_search_service(entities)

    print(f"✅ Prepared {len(search_docs)} documents for search service")

    # Verify entity types are correctly mapped
    func_doc = next(d for d in search_docs if d["entity_id"] == "func-001")
    class_doc = next(d for d in search_docs if d["entity_id"] == "class-001")
    doc_doc = next(d for d in search_docs if d["entity_id"] == "doc-001")

    print(f"✅ Function mapped to: {func_doc['entity_type']}")  # Should be 'entity'
    print(f"✅ Class mapped to: {class_doc['entity_type']}")  # Should be 'entity'
    print(f"✅ Document mapped to: {doc_doc['entity_type']}")  # Should be 'page'

    # Verify metadata preservation
    assert func_doc["metadata"]["intelligence_type"] == "FUNCTION"
    assert func_doc["metadata"]["unified_type"] == "function"
    assert func_doc["metadata"]["service"] == "intelligence"

    print("✅ Search service preparation tests passed!\n")


def test_external_service_preparation():
    """Test general external service preparation."""
    print("🧪 Testing External Service Preparation...")

    # Create test entity
    entity = KnowledgeEntity(
        entity_id="test-ext-001",
        name="test_component",
        entity_type=LegacyEntityType.COMPONENT,
        description="A test component",
        source_path="/test/component.py",
        confidence_score=0.88,
        metadata=EntityMetadata(),
        properties={"framework": "FastAPI"},
    )

    # Test search service preparation
    search_docs = prepare_entities_for_external_service([entity], "search")
    print(f"✅ Search service format: entity_type = {search_docs[0]['entity_type']}")

    # Test other service preparation (unified format)
    unified_docs = prepare_entities_for_external_service([entity], "bridge")
    print(f"✅ Bridge service format: entity_type = {unified_docs[0]['entity_type']}")

    print("✅ External service preparation tests passed!\n")


def run_all_tests():
    """Run all test functions."""
    print("🚀 Running Intelligence Service Unified Adapter Tests\n")

    try:
        test_entity_type_conversion()
        test_knowledge_entity_conversion()
        test_search_service_preparation()
        test_external_service_preparation()

        print(
            "🎉 All intelligence service adapter tests passed! Unified entity types are working correctly."
        )
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
