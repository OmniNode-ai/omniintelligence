#!/usr/bin/env python3
"""
Test script for Archon Intelligence + Metadata Stamping integration.

⚠️  REQUIRES EXTERNAL SERVICE: OmniNode Bridge Metadata Stamping Service (Port 8057)
This test suite expects the OmniNode Bridge Metadata Stamping Service to be running.
If the service is not available, these tests will fail.

For Bridge Intelligence API tests only, use:
- test_bridge_intelligence_corrected.py (positive tests)
- test_bridge_negative_cases.py (negative/edge case tests)

Tests the complete workflow:
1. Intelligence generation via HTTP (Port 8053)
2. Metadata enrichment
3. File stamping with enriched metadata (Port 8057 - requires OmniNode Bridge)
4. MCP tool integration

Note: Intelligence generation (test 1) will pass, but stamping tests (2-4) require
the external OmniNode Bridge Metadata Stamping Service.
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp_server.clients.metadata_stamping_client import MetadataStampingClient

# Test file content
TEST_FILE_CONTENT = '''"""
Example Python module for testing intelligence generation.

This module demonstrates ONEX architectural patterns.
"""

from typing import Dict, Any, Optional


class NodeDataTransformerCompute:
    """Example ONEX Compute node for data transformation."""

    async def execute_compute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data with validation.

        Args:
            data: Input data dictionary

        Returns:
            Transformed data dictionary
        """
        # Validate input
        if not data:
            raise ValueError("Data cannot be empty")

        # Transform
        result = {
            "transformed": True,
            "original_keys": list(data.keys()),
            "timestamp": "2025-10-06T12:00:00Z",
        }

        return result
'''


def calculate_blake3_hash(content: str) -> str:
    """Calculate BLAKE3 hash of content."""
    # Simple hash for testing (in real implementation, use BLAKE3)
    return hashlib.sha256(content.encode()).hexdigest()[:32]


async def test_intelligence_generation():
    """Test 1: Intelligence generation only."""
    print("\n" + "=" * 80)
    print("TEST 1: Intelligence Generation")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8057", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            # Generate intelligence
            result = await client.generate_intelligence(
                file_path="/test/example.py",
                content=TEST_FILE_CONTENT,
                include_semantic=True,
                include_compliance=True,
                include_patterns=True,
            )

            print("\n✅ Intelligence Generation Result:")
            print(json.dumps(result, indent=2))

            # Check success
            if result.get("success"):
                print("\n✅ SUCCESS: Intelligence generated successfully")
                print(
                    f"   Sources: {', '.join(result.get('intelligence_sources', []))}"
                )

                metadata = result.get("metadata", {})
                if metadata:
                    quality = metadata.get("quality_metrics", {})
                    classification = metadata.get("classification", {})

                    print("\n📊 Quality Metrics:")
                    print(f"   Quality Score: {quality.get('quality_score', 0):.2f}")
                    print(
                        f"   ONEX Compliance: {quality.get('onex_compliance', 0):.2f}"
                    )
                    print(f"   Maturity: {classification.get('maturity', 'unknown')}")
                    print(f"   Trust Score: {classification.get('trust_score', 0)}/100")

                return True
            else:
                print(f"\n❌ FAILED: {result.get('error')}")
                return False

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            return False


async def test_basic_stamping():
    """Test 2: Basic stamping without intelligence."""
    print("\n" + "=" * 80)
    print("TEST 2: Basic Stamping (No Intelligence)")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8057", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            file_hash = calculate_blake3_hash(TEST_FILE_CONTENT)

            # Basic stamping
            result = await client.stamp_file(
                file_hash=file_hash,
                metadata={
                    "file_path": "/test/example.py",
                    "test": "basic_stamping",
                },
                overwrite=True,
            )

            print("\n✅ Basic Stamping Result:")
            print(f"   Success: {result.success}")
            print(f"   File Hash: {result.file_hash}")
            print(f"   Stamped At: {result.stamped_at}")
            print(f"   Processing Time: {result.processing_time_ms:.2f}ms")

            return result.success

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            return False


async def test_intelligence_enriched_stamping():
    """Test 3: Intelligence-enriched stamping."""
    print("\n" + "=" * 80)
    print("TEST 3: Intelligence-Enriched Stamping")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8057", intelligence_url="http://localhost:8053"
    ) as client:
        try:
            file_hash = calculate_blake3_hash(TEST_FILE_CONTENT)

            # Intelligence-enriched stamping
            result = await client.stamp_with_intelligence(
                file_path="/test/example.py",
                file_hash=file_hash,
                content=TEST_FILE_CONTENT,
                overwrite=True,
                include_semantic=True,
                include_compliance=True,
                include_patterns=True,
                fallback_on_intelligence_failure=True,
            )

            print("\n✅ Intelligence-Enriched Stamping Result:")
            print(f"   Success: {result.success}")
            print(f"   File Hash: {result.file_hash}")
            print(f"   Stamped At: {result.stamped_at}")
            print(f"   Processing Time: {result.processing_time_ms:.2f}ms")

            # Check metadata enrichment
            metadata = result.metadata
            print("\n📋 Metadata Enrichment:")
            print(f"   Quality Score: {metadata.get('quality_score', 'N/A')}")
            print(f"   ONEX Compliance: {metadata.get('onex_compliance', 'N/A')}")
            print(f"   Maturity: {metadata.get('maturity', 'N/A')}")
            print(f"   Trust Score: {metadata.get('trust_score', 'N/A')}/100")
            print(
                f"   Intelligence Sources: {metadata.get('intelligence_sources', [])}"
            )

            if metadata.get("recommendations"):
                print("\n💡 Recommendations:")
                for i, rec in enumerate(metadata.get("recommendations", []), 1):
                    print(f"   {i}. {rec}")

            # Check fallback
            if metadata.get("intelligence_error"):
                print("\n⚠️  Intelligence Fallback Used:")
                print(f"   Error: {metadata.get('intelligence_error')}")

            return result.success

        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            return False


async def test_client_metrics():
    """Test 4: Client metrics tracking."""
    print("\n" + "=" * 80)
    print("TEST 4: Client Metrics")
    print("=" * 80)

    async with MetadataStampingClient(
        base_url="http://localhost:8057", intelligence_url="http://localhost:8053"
    ) as client:
        # Run some operations
        file_hash = calculate_blake3_hash(TEST_FILE_CONTENT)

        # Intelligence generation
        await client.generate_intelligence(
            file_path="/test/example.py",
            content=TEST_FILE_CONTENT,
        )

        # Intelligence-enriched stamping
        await client.stamp_with_intelligence(
            file_path="/test/example.py",
            file_hash=file_hash,
            content=TEST_FILE_CONTENT,
            overwrite=True,
        )

        # Get metrics
        metrics = client.get_client_metrics()

        print("\n📊 Client Metrics:")
        print(f"   Total Requests: {metrics['total_requests']}")
        print(f"   Successful Requests: {metrics['successful_requests']}")
        print(f"   Failed Requests: {metrics['failed_requests']}")
        print(f"   Success Rate: {metrics['success_rate']:.2%}")
        print(f"   Avg Duration: {metrics['avg_duration_ms']:.2f}ms")
        print(f"\n   Intelligence Requests: {metrics['intelligence_requests']}")
        print(f"   Intelligence Successes: {metrics['intelligence_successes']}")
        print(f"   Intelligence Failures: {metrics['intelligence_failures']}")
        print(
            f"   Intelligence-Enriched Stamps: {metrics['intelligence_enriched_stamps']}"
        )

        return True


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ARCHON INTELLIGENCE + METADATA STAMPING INTEGRATION TESTS")
    print("=" * 80)

    results = {
        "intelligence_generation": await test_intelligence_generation(),
        "basic_stamping": await test_basic_stamping(),
        "intelligence_enriched_stamping": await test_intelligence_enriched_stamping(),
        "client_metrics": await test_client_metrics(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
