#!/usr/bin/env python3
"""
Verify tree integration with OnexTree service

Tests the complete flow:
1. Hybrid score calculation
2. Tree info retrieval
3. Cache behavior

Run with: python3 verify_tree_integration.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import directly from tree_integration to avoid circular imports
import importlib.util

spec = importlib.util.spec_from_file_location(
    "tree_integration",
    Path(__file__).parent / "src" / "api" / "pattern_learning" / "tree_integration.py",
)
tree_integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tree_integration)


async def test_tree_info_retrieval():
    """Test tree info retrieval for a pattern"""
    print("=" * 70)
    print("Tree Integration Verification")
    print("=" * 70)

    # Test pattern
    pattern_name = "pattern_learning"
    pattern_type = "onex"
    node_type = "EFFECT"

    print(f"\n1. Testing tree info retrieval...")
    print(f"   Pattern: {pattern_name}")
    print(f"   Type: {pattern_type}")
    print(f"   Node Type: {node_type}")

    try:
        # Get tree info (first call - should query OnexTree)
        print("\n   → First call (cache miss expected)...")
        tree_info = await tree_integration.get_tree_info_for_pattern(
            pattern_name=pattern_name,
            pattern_type=pattern_type,
            node_type=node_type,
        )

        print(f"   ✅ Tree info retrieved:")
        print(f"      - Files found: {len(tree_info.relevant_files)}")
        print(f"      - From cache: {tree_info.from_cache}")
        print(f"      - Query time: {tree_info.query_time_ms:.2f}ms")
        print(f"      - Total files: {tree_info.tree_metadata.total_files}")

        if tree_info.relevant_files:
            print(f"\n   📁 Sample file:")
            file = tree_info.relevant_files[0]
            print(f"      - Path: {file.path}")
            print(f"      - Type: {file.file_type}")
            print(f"      - Relevance: {file.relevance:.2f}")
            print(f"      - Node Type: {file.node_type or 'N/A'}")

        # Get tree info again (second call - should hit cache)
        print("\n   → Second call (cache hit expected)...")
        tree_info2 = await tree_integration.get_tree_info_for_pattern(
            pattern_name=pattern_name,
            pattern_type=pattern_type,
            node_type=node_type,
        )

        print(f"   ✅ Tree info retrieved:")
        print(f"      - Files found: {len(tree_info2.relevant_files)}")
        print(f"      - From cache: {tree_info2.from_cache}")
        print(f"      - Query time: {tree_info2.query_time_ms:.2f}ms")

        # Verify cache hit
        if tree_info2.from_cache:
            print("   ✅ Cache is working correctly!")
        else:
            print("   ⚠️  Cache miss on second call (unexpected)")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("\n   Note: This is expected if OnexTree service is not running")
        print("   OnexTree should be available at: http://192.168.86.200:8058")
        return False

    return True


async def test_cache_metrics():
    """Test cache metrics reporting"""
    print("\n2. Testing cache metrics...")

    try:
        metrics = tree_integration.get_tree_cache_metrics()

        print("   ✅ Cache metrics retrieved:")
        print(f"      - Total requests: {metrics['total_requests']}")
        print(f"      - Cache hits: {metrics['hits']}")
        print(f"      - Cache misses: {metrics['misses']}")
        print(f"      - Hit rate: {metrics['hit_rate']:.2%}")
        print(f"      - Cache size: {metrics['cache_size']}/{metrics['max_size']}")
        print(f"      - Utilization: {metrics['utilization']:.2%}")

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_cache_clear():
    """Test cache clear operation"""
    print("\n3. Testing cache clear...")

    try:
        # Get metrics before clear
        metrics_before = tree_integration.get_tree_cache_metrics()
        print(f"   Cache size before clear: {metrics_before['cache_size']}")

        # Clear cache
        tree_integration.clear_tree_cache()

        # Get metrics after clear
        metrics_after = tree_integration.get_tree_cache_metrics()
        print(f"   Cache size after clear: {metrics_after['cache_size']}")

        if metrics_after["cache_size"] == 0:
            print("   ✅ Cache cleared successfully!")
            return True
        else:
            print(
                f"   ⚠️  Cache not empty after clear (size: {metrics_after['cache_size']})"
            )
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def main():
    """Run all verification tests"""
    results = []

    # Test tree info retrieval
    result1 = await test_tree_info_retrieval()
    results.append(("Tree info retrieval", result1))

    # Test cache metrics
    result2 = await test_cache_metrics()
    results.append(("Cache metrics", result2))

    # Test cache clear
    result3 = await test_cache_clear()
    results.append(("Cache clear", result3))

    # Summary
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 All verifications passed!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        print(
            "\nNote: Tree info retrieval may fail if OnexTree service is not running."
        )
        print("This is expected in local development. Other tests should pass.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
