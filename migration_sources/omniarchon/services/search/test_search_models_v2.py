"""
Test script for updated search models with unified entity types.
"""

import os
import sys

# Add the search service directory to path
search_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, search_dir)

from models.search_models_v2 import (
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResult,
    convert_legacy_entity_types,
    create_backwards_compatible_search_request,
)

# Import shared models
sys.path.insert(0, os.path.join(search_dir, "shared_models"))
from entity_types import EntityType as UnifiedEntityType


def test_unified_entity_types():
    """Test unified entity type handling."""
    print("🧪 Testing Unified Entity Type Support...")

    # Test creating search request with unified types
    request = SearchRequest(
        query="authentication patterns",
        entity_types=[
            UnifiedEntityType.FUNCTION,
            UnifiedEntityType.CLASS,
            UnifiedEntityType.DOCUMENT,
        ],
    )

    print(
        f"✅ Created request with unified types: {[t.value for t in request.entity_types]}"
    )

    # Test conversion to legacy types
    legacy_types = request.to_legacy_search_types()
    print(f"✅ Converted to legacy search types: {[t.value for t in legacy_types]}")

    # Test backwards compatibility function
    legacy_request = create_backwards_compatible_search_request(
        query="test query",
        legacy_entity_types=["source", "page", "FUNCTION"],  # Mixed formats
    )

    print(
        f"✅ Backwards compatible request created with types: {[t.value for t in legacy_request.entity_types]}"
    )

    print("✅ Unified entity type tests passed!\n")


def test_search_result_normalization():
    """Test search result entity type normalization."""
    print("🧪 Testing Search Result Type Normalization...")

    # Test creating result with various entity type formats
    result1 = SearchResult(
        entity_id="func-001",
        entity_type="function",  # lowercase string
        title="test_function",
        relevance_score=0.95,
    )

    result2 = SearchResult(
        entity_id="doc-001",
        entity_type=UnifiedEntityType.DOCUMENT,  # unified type
        title="API Documentation",
        relevance_score=0.88,
    )

    print(f"✅ Result 1 normalized type: {result1.entity_type.value}")
    print(f"✅ Result 2 unified type: {result2.entity_type.value}")
    print(f"✅ Result 1 legacy type: {result1.to_legacy_search_type().value}")
    print(f"✅ Result 2 legacy type: {result2.to_legacy_search_type().value}")

    print("✅ Search result normalization tests passed!\n")


def test_search_response():
    """Test search response with mixed entity types."""
    print("🧪 Testing Search Response...")

    results = [
        SearchResult(
            entity_id="func-001",
            entity_type=UnifiedEntityType.FUNCTION,
            title="authenticate_user",
            relevance_score=0.95,
        ),
        SearchResult(
            entity_id="doc-001",
            entity_type=UnifiedEntityType.DOCUMENT,
            title="Authentication Guide",
            relevance_score=0.88,
        ),
        SearchResult(
            entity_id="class-001",
            entity_type=UnifiedEntityType.CLASS,
            title="AuthManager",
            relevance_score=0.92,
        ),
    ]

    response = SearchResponse(
        query="authentication",
        mode=SearchMode.HYBRID,
        total_results=3,
        returned_results=3,
        results=results,
        search_time_ms=125.5,
        limit=10,
    )

    print(f"✅ Response created with {len(response.results)} results")

    # Test unified entity type counts
    unified_counts = response.entity_type_counts
    print(f"✅ Unified entity type counts: {unified_counts}")

    # Test legacy entity type counts
    legacy_counts = response.get_legacy_entity_type_counts()
    print(f"✅ Legacy entity type counts: {legacy_counts}")

    print("✅ Search response tests passed!\n")


def test_legacy_conversion():
    """Test conversion of legacy entity types."""
    print("🧪 Testing Legacy Entity Type Conversion...")

    # Test various legacy formats
    legacy_types = [
        "source",
        "page",
        "code_example",
        "FUNCTION",
        "CLASS",
        "invalid_type",
    ]
    unified_types = convert_legacy_entity_types(legacy_types)

    print(f"✅ Legacy types: {legacy_types}")
    print(f"✅ Converted to unified: {[t.value for t in unified_types]}")

    print("✅ Legacy conversion tests passed!\n")


def run_all_tests():
    """Run all test functions."""
    print("🚀 Running Search Models V2 Tests\n")

    try:
        test_unified_entity_types()
        test_search_result_normalization()
        test_search_response()
        test_legacy_conversion()

        print(
            "🎉 All search models v2 tests passed! Updated models are working correctly."
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
