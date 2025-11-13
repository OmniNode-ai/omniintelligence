"""
Test script for Archon shared models.

Run this to verify that the shared models work correctly and that
entity type mapping functions as expected.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_models import BaseEntity, ServiceHealth
from communication import (
    EntitySyncRequest,
    OperationStatus,
    ServiceRequest,
    ServiceResponse,
)
from entity_types import (
    EntityType,
    EntityTypeMapper,
    IntelligenceEntityType,
    SearchEntityType,
    normalize_entity_type,
)


def test_entity_type_mapping():
    """Test entity type mapping between services."""
    print("🧪 Testing EntityType Mapping...")

    # Test unified to intelligence mapping
    unified_func = EntityType.FUNCTION
    intelligence_func = EntityTypeMapper.to_intelligence_type(unified_func)
    print(f"✅ {unified_func} → {intelligence_func}")
    assert intelligence_func == IntelligenceEntityType.FUNCTION

    # Test unified to search mapping
    unified_doc = EntityType.DOCUMENT
    search_doc = EntityTypeMapper.to_search_type(unified_doc)
    print(f"✅ {unified_doc} → {search_doc} (documents map to pages)")
    assert search_doc == SearchEntityType.PAGE

    # Test auto conversion
    converted = EntityTypeMapper.auto_convert("FUNCTION")  # Intelligence format
    print(f"✅ Auto-convert 'FUNCTION' → {converted}")
    assert converted == EntityType.FUNCTION

    converted2 = EntityTypeMapper.auto_convert("source")  # Search format
    print(f"✅ Auto-convert 'source' → {converted2}")
    assert converted2 == EntityType.SOURCE

    # Test normalize function
    normalized = normalize_entity_type("CODE_EXAMPLE")
    print(f"✅ Normalize 'CODE_EXAMPLE' → {normalized}")
    assert normalized == EntityType.CODE_EXAMPLE

    print("✅ Entity type mapping tests passed!\n")


def test_base_entity():
    """Test base entity model."""
    print("🧪 Testing BaseEntity...")

    entity = BaseEntity(
        entity_id="test-001",
        entity_type=EntityType.FUNCTION,
        name="test_function",
        description="A test function",
        content="def test_function(): pass",
    )

    print(f"✅ Created entity: {entity.name} ({entity.entity_type})")
    print(f"✅ Metadata created_at: {entity.metadata.created_at}")
    print(f"✅ Default validation_status: {entity.metadata.validation_status}")

    # Test serialization
    entity_dict = entity.model_dump()
    entity_restored = BaseEntity.model_validate(entity_dict)
    print("✅ Serialization/deserialization successful")
    assert entity_restored.entity_id == entity.entity_id

    print("✅ Base entity tests passed!\n")


def test_service_communication():
    """Test service communication models."""
    print("🧪 Testing Service Communication...")

    # Test service request
    request = ServiceRequest(
        request_id="req-001",
        requesting_service="mcp-service",
        target_service="intelligence-service",
        operation="extract_entities",
        data={"content": "test content", "source_path": "/test/file.py"},
    )

    print(f"✅ Created request: {request.operation}")
    print(f"✅ Request ID: {request.request_id}")

    # Test service response
    response = ServiceResponse(
        request_id=request.request_id,
        responding_service="intelligence-service",
        status=OperationStatus.SUCCESS,
        data={"entities_extracted": 5},
        processing_time_ms=150.5,
    )

    print(f"✅ Created response: {response.status}")
    print(f"✅ Processing time: {response.processing_time_ms}ms")

    # Test entity sync request
    sync_request = EntitySyncRequest(
        entities=[
            BaseEntity(
                entity_id="sync-001",
                entity_type=EntityType.CLASS,
                name="TestClass",
                description="A test class",
            )
        ],
        sync_mode="incremental",
        entity_types=[EntityType.CLASS, EntityType.FUNCTION],
    )

    print(f"✅ Created sync request with {len(sync_request.entities)} entities")
    print(f"✅ Sync mode: {sync_request.sync_mode}")

    print("✅ Service communication tests passed!\n")


def test_service_health():
    """Test service health model."""
    print("🧪 Testing ServiceHealth...")

    health = ServiceHealth(
        status="healthy",
        service_name="test-service",
        service_version="1.0.0",
        database_connected=True,
        external_services={"memgraph": True, "qdrant": True, "ollama": False},
        uptime_seconds=3600.0,
        response_time_ms=25.5,
        warnings=["Ollama connection intermittent"],
        memory_usage_mb=256.8,
    )

    print(f"✅ Service: {health.service_name} v{health.service_version}")
    print(f"✅ Status: {health.status}")
    print(f"✅ Uptime: {health.uptime_seconds}s")
    print(f"✅ Warnings: {len(health.warnings)}")
    print(f"✅ External services: {health.external_services}")

    print("✅ Service health tests passed!\n")


def run_all_tests():
    """Run all test functions."""
    print("🚀 Running Archon Shared Models Tests\n")

    try:
        test_entity_type_mapping()
        test_base_entity()
        test_service_communication()
        test_service_health()

        print("🎉 All tests passed! Shared models are working correctly.")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
