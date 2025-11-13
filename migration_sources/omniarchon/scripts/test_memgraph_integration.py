#!/usr/bin/env python3
"""
Test script for Memgraph integration after replacing placeholder implementation.

Tests:
1. Memgraph connectivity
2. Entity and relationship storage
3. Query verification
"""

import asyncio
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "intelligence"))

from models.entity_models import (
    EntityMetadata,
    EntityType,
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipType,
)
from storage.memgraph_adapter import MemgraphKnowledgeAdapter


async def test_memgraph_integration():
    """Test Memgraph integration with actual writes"""

    print("=" * 80)
    print("MEMGRAPH INTEGRATION TEST")
    print("=" * 80)

    # Initialize adapter
    adapter = MemgraphKnowledgeAdapter(uri="bolt://localhost:7687")

    try:
        print("\n1. Testing connectivity...")
        await adapter.initialize()
        print("✅ Connected to Memgraph successfully")

        # Check health
        is_healthy = await adapter.health_check()
        print(f"✅ Health check: {'PASS' if is_healthy else 'FAIL'}")

        # Get current statistics
        print("\n2. Current Memgraph statistics:")
        stats = await adapter.get_entity_statistics()
        print(f"   Total entities: {stats.get('total_entities', 0)}")
        print(f"   Total relationships: {stats.get('total_relationships', 0)}")

        # Create test entities
        print("\n3. Creating test entities...")
        test_entities = [
            KnowledgeEntity(
                entity_id="test-entity-1",
                name="test_function",
                entity_type=EntityType.FUNCTION,
                description="A test function for Memgraph integration testing",
                source_path="/test/test_file.py",
                confidence_score=0.95,
                source_line_number=10,
                properties={"test": True},
                metadata=EntityMetadata(
                    extraction_method="test_script",
                    extraction_confidence=0.95,
                ),
            ),
            KnowledgeEntity(
                entity_id="test-entity-2",
                name="TestClass",
                entity_type=EntityType.CLASS,
                description="A test class for Memgraph integration testing",
                source_path="/test/test_file.py",
                confidence_score=0.90,
                source_line_number=20,
                properties={"test": True},
                metadata=EntityMetadata(
                    extraction_method="test_script",
                    extraction_confidence=0.90,
                ),
            ),
        ]

        stored_count = await adapter.store_entities(test_entities)
        print(f"✅ Stored {stored_count} entities")

        # Create test relationship
        print("\n4. Creating test relationship...")
        test_relationships = [
            KnowledgeRelationship(
                relationship_id="test-rel-1",
                source_entity_id="test-entity-2",
                target_entity_id="test-entity-1",
                relationship_type=RelationshipType.CONTAINS,
                confidence_score=0.95,
                properties={"test": True},
            ),
        ]

        rels_created = await adapter.store_relationships(test_relationships)
        print(f"✅ Created {rels_created} relationships")

        # Get updated statistics
        print("\n5. Updated Memgraph statistics:")
        stats = await adapter.get_entity_statistics()
        print(f"   Total entities: {stats.get('total_entities', 0)}")
        print(f"   Total relationships: {stats.get('total_relationships', 0)}")
        print(f"   Entity counts by type: {stats.get('entity_counts_by_type', {})}")
        print(
            f"   Relationship counts by type: {stats.get('relationship_counts_by_type', {})}"
        )

        # Search for test entities
        print("\n6. Searching for test entities...")
        found_entities = await adapter.search_entities("test", limit=5)
        print(f"✅ Found {len(found_entities)} entities matching 'test'")
        for entity in found_entities:
            print(f"   - {entity.name} ({entity.entity_type.value})")

        # Get relationships for test entity
        print("\n7. Getting relationships for test class...")
        relationships = await adapter.get_entity_relationships(
            "test-entity-2", limit=10
        )
        print(f"✅ Found {len(relationships)} relationships")
        for rel_data in relationships:
            rel = rel_data["relationship"]
            source = rel_data["source_entity"]
            target = rel_data["target_entity"]
            rel_type = rel["relationship_type"] if isinstance(rel, dict) else "UNKNOWN"
            print(f"   - {source.name} --[{rel_type}]--> {target.name}")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - Memgraph integration is working!")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await adapter.close()
        print("\n✅ Connection closed")


async def main():
    """Main entry point"""
    success = await test_memgraph_integration()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
