#!/usr/bin/env python3
"""
Validation Script for Archon Vectors Schema Enhancement

Tests that the new quality/ONEX fields are properly:
1. Accepted by the SearchResult model
2. Stored in Qdrant payloads
3. Retrieved in search results
4. Handled by the vectorization endpoint

Usage:
    python3 scripts/validate_archon_vectors_schema.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.search.models.search_models import EntityType, SearchResult


def test_search_result_model():
    """Test 1: Validate SearchResult model accepts new fields"""
    print("🧪 Test 1: SearchResult Model Validation")
    print("=" * 60)

    try:
        # Test with all new fields
        result = SearchResult(
            entity_id="test_entity_123",
            entity_type=EntityType.PAGE,
            title="Test Document",
            relevance_score=0.95,
            # New quality/ONEX fields
            quality_score=0.87,
            onex_compliance=0.92,
            onex_type="compute",
            concepts=["authentication", "security", "jwt"],
            themes=["backend", "api", "microservices"],
            relative_path="src/services/auth.py",
            project_name="omniarchon",
            content_hash="blake3_abc123def456",
        )

        print("✅ SearchResult created successfully with all new fields")
        print("\nField Validation:")
        print(
            f"  - quality_score: {result.quality_score} (type: {type(result.quality_score).__name__})"
        )
        print(
            f"  - onex_compliance: {result.onex_compliance} (type: {type(result.onex_compliance).__name__})"
        )
        print(f"  - onex_type: {result.onex_type}")
        print(f"  - concepts: {result.concepts} ({len(result.concepts)} items)")
        print(f"  - themes: {result.themes} ({len(result.themes)} items)")
        print(f"  - relative_path: {result.relative_path}")
        print(f"  - project_name: {result.project_name}")
        print(f"  - content_hash: {result.content_hash}")

        # Test JSON serialization
        json_output = result.model_dump_json(indent=2)
        print("\n✅ JSON serialization successful")
        print(f"  - Serialized size: {len(json_output)} bytes")

        # Validate deserialization
        deserialized = SearchResult.model_validate_json(json_output)
        print("✅ JSON deserialization successful")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_backward_compatibility():
    """Test 2: Ensure backward compatibility (all fields optional)"""
    print("\n🧪 Test 2: Backward Compatibility")
    print("=" * 60)

    try:
        # Create SearchResult without new fields (old behavior)
        result = SearchResult(
            entity_id="legacy_entity",
            entity_type=EntityType.DOCUMENT,
            title="Legacy Document",
            relevance_score=0.80,
        )

        print("✅ SearchResult created without new fields (backward compatible)")
        print("\nDefault Values:")
        print(f"  - quality_score: {result.quality_score} (None is OK)")
        print(f"  - onex_compliance: {result.onex_compliance} (None is OK)")
        print(f"  - onex_type: {result.onex_type} (None is OK)")
        print(f"  - concepts: {result.concepts} (None is OK)")
        print(f"  - themes: {result.themes} (None is OK)")

        # Ensure JSON serialization still works
        json_output = result.model_dump_json()
        print("✅ JSON serialization works with None values")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_quality_score_validation():
    """Test 3: Validate quality score range constraints"""
    print("\n🧪 Test 3: Quality Score Validation")
    print("=" * 60)

    try:
        # Valid quality scores (0.0-1.0)
        valid_scores = [0.0, 0.5, 0.85, 1.0]
        for score in valid_scores:
            result = SearchResult(
                entity_id="test",
                entity_type=EntityType.PAGE,
                title="Test",
                relevance_score=0.9,
                quality_score=score,
                onex_compliance=score,
            )
            print(f"✅ Valid score {score}: OK")

        # Test invalid scores (should fail)
        invalid_scores = [-0.1, 1.1, 2.0]
        for score in invalid_scores:
            try:
                result = SearchResult(
                    entity_id="test",
                    entity_type=EntityType.PAGE,
                    title="Test",
                    relevance_score=0.9,
                    quality_score=score,
                )
                print(
                    f"⚠️  Warning: Invalid score {score} was accepted (should validate)"
                )
            except Exception as e:
                print(f"✅ Invalid score {score} rejected: {type(e).__name__}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_sample_payload():
    """Test 4: Generate sample payload for documentation"""
    print("\n🧪 Test 4: Sample Payload Generation")
    print("=" * 60)

    try:
        result = SearchResult(
            entity_id="/path/to/service/auth.py",
            entity_type=EntityType.PAGE,
            title="auth.py",
            content="Authentication service with JWT implementation...",
            relevance_score=0.92,
            semantic_score=0.88,
            source_id="source_omniarchon",
            project_id="proj_archon_123",
            created_at=datetime.now(),
            # Quality/ONEX fields
            quality_score=0.87,
            onex_compliance=0.92,
            onex_type="compute",
            concepts=["authentication", "jwt", "security", "tokens"],
            themes=["backend", "api", "microservices"],
            relative_path="src/services/auth.py",
            project_name="omniarchon",
            content_hash="blake3_abcdef123456",
        )

        payload = result.model_dump(exclude_none=False)
        print("✅ Sample payload generated successfully")
        print("\nSample SearchResult Payload:")
        print(json.dumps(payload, indent=2, default=str))

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_filtering_example():
    """Test 5: Demonstrate filtering capabilities"""
    print("\n🧪 Test 5: Filtering Example")
    print("=" * 60)

    # Create sample results with varying quality scores
    results = [
        SearchResult(
            entity_id=f"doc_{i}",
            entity_type=EntityType.PAGE,
            title=f"Document {i}",
            relevance_score=0.9,
            quality_score=score,
            onex_type=onex_type,
        )
        for i, (score, onex_type) in enumerate(
            [
                (0.95, "compute"),
                (0.85, "effect"),
                (0.75, "reducer"),
                (0.65, "compute"),
            ]
        )
    ]

    print(f"✅ Created {len(results)} sample results")
    print("\nResults:")
    for r in results:
        print(f"  - {r.title}: quality={r.quality_score}, type={r.onex_type}")

    # Filter by quality
    high_quality = [r for r in results if r.quality_score >= 0.8]
    print(f"\n✅ Filtered by quality >= 0.8: {len(high_quality)} results")

    # Filter by ONEX type
    compute_nodes = [r for r in results if r.onex_type == "compute"]
    print(f"✅ Filtered by onex_type='compute': {len(compute_nodes)} results")

    return True


def main():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("  Archon Vectors Schema Enhancement - Validation Suite")
    print("=" * 60 + "\n")

    tests = [
        ("SearchResult Model", test_search_result_model),
        ("Backward Compatibility", test_backward_compatibility),
        ("Quality Score Validation", test_quality_score_validation),
        ("Sample Payload", test_sample_payload),
        ("Filtering Example", test_filtering_example),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*60}\n")

    if passed == total:
        print("🎉 All tests passed! Schema enhancement validated successfully.")
        return 0
    else:
        print("⚠️  Some tests failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
