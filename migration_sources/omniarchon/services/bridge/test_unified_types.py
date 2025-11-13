#!/usr/bin/env python3
"""
Test script for unified entity types in bridge service.
"""

import os
import sys

# Add paths
bridge_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, bridge_dir)
sys.path.insert(0, os.path.join(bridge_dir, "..", "..", "shared", "models"))

from entity_types import EntityType
from models.bridge_models import SyncDirection, SyncRequest


def test_entity_type_imports():
    """Test that EntityType can be imported and used correctly."""
    print("🧪 Testing Bridge Service EntityType Integration...")

    # Test that all expected entity types are available
    expected_types = [
        EntityType.SOURCE,
        EntityType.PROJECT,
        EntityType.PAGE,
        EntityType.CODE_EXAMPLE,
        EntityType.TASK,
        EntityType.DOCUMENT,
    ]

    print("✅ Available entity types:")
    for entity_type in expected_types:
        print(f"  - {entity_type.value}")

    # Test creating SyncRequest with EntityType
    sync_request = SyncRequest(
        entity_types=[EntityType.SOURCE, EntityType.PROJECT, EntityType.PAGE],
        direction=SyncDirection.BIDIRECTIONAL,
        dry_run=True,
    )

    print(
        f"✅ SyncRequest created with entity types: {[et.value for et in sync_request.entity_types]}"
    )

    # Test EntityType string values
    assert EntityType.SOURCE.value == "source"
    assert EntityType.PROJECT.value == "project"
    assert EntityType.PAGE.value == "page"
    assert EntityType.CODE_EXAMPLE.value == "code_example"
    assert EntityType.TASK.value == "task"
    assert EntityType.DOCUMENT.value == "document"

    print("✅ EntityType values match expected strings")

    print("🎉 Bridge service unified EntityType integration test passed!")
    return True


if __name__ == "__main__":
    try:
        success = test_entity_type_imports()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
