#!/usr/bin/env python3
"""
Pattern Integration Test Script

Quick validation of pattern integration setup before running full integration.
Tests all components in isolation and together.
"""

import asyncio
import sys

import asyncpg
import httpx

# Test configuration
DB_URL = "postgresql://postgres:postgres@localhost:5436/omninode_bridge"
METADATA_STAMPING_URL = "http://localhost:8057"
ONEX_TREE_URL = "http://localhost:8058"


class TestColors:
    """Terminal colors for test output"""

    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"


async def test_database_connection():
    """Test PostgreSQL database connection"""
    print(f"\n{TestColors.BLUE}[1/5] Testing Database Connection...{TestColors.NC}")

    try:
        conn = await asyncpg.connect(DB_URL, timeout=10)

        # Test query
        count = await conn.fetchval("SELECT COUNT(*) FROM pattern_templates")
        print("  ✓ Connected to database")
        print(f"  ✓ Found {count:,} patterns in pattern_templates table")

        # Check for required columns
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'pattern_templates'
            ORDER BY ordinal_position
        """
        )

        required_columns = {
            "id",
            "pattern_name",
            "pattern_type",
            "language",
            "template_code",
            "confidence_score",
        }

        existing_columns = {col["column_name"] for col in columns}
        missing_columns = required_columns - existing_columns

        if missing_columns:
            print(
                f"  {TestColors.RED}✗ Missing required columns: {missing_columns}{TestColors.NC}"
            )
            return False

        print("  ✓ All required columns present")

        await conn.close()
        return True

    except Exception as e:
        print(f"  {TestColors.RED}✗ Database connection failed: {e}{TestColors.NC}")
        return False


async def test_metadata_stamping_service():
    """Test Metadata Stamping Service"""
    print(
        f"\n{TestColors.BLUE}[2/5] Testing Metadata Stamping Service...{TestColors.NC}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Health check
            response = await client.get(f"{METADATA_STAMPING_URL}/health")
            if response.status_code != 200:
                print(
                    f"  {TestColors.RED}✗ Health check failed: {response.status_code}{TestColors.NC}"
                )
                return False

            print("  ✓ Service is healthy")

            # Test hash generation
            test_data = b"test pattern code"
            hash_response = await client.post(
                f"{METADATA_STAMPING_URL}/hash",
                files={"file": ("test.py", test_data, "application/octet-stream")},
                params={"namespace": "test"},
            )

            if hash_response.status_code != 200:
                print(
                    f"  {TestColors.RED}✗ Hash generation failed: {hash_response.status_code}{TestColors.NC}"
                )
                return False

            hash_result = hash_response.json()
            file_hash = hash_result.get("data", {}).get("hash")

            if not file_hash:
                print(f"  {TestColors.RED}✗ No hash returned{TestColors.NC}")
                return False

            print(f"  ✓ Hash generation works (hash: {file_hash[:16]}...)")

            # Test stamp creation
            stamp_request = {
                "file_hash": file_hash,
                "file_path": "test/pattern.py",
                "file_size": len(test_data),
                "content_type": "text/x-python",
                "stamp_data": {"test": "data"},
                "namespace": "test",
            }

            stamp_response = await client.post(
                f"{METADATA_STAMPING_URL}/stamp", json=stamp_request
            )

            if stamp_response.status_code != 200:
                print(
                    f"  {TestColors.RED}✗ Stamp creation failed: {stamp_response.status_code}{TestColors.NC}"
                )
                return False

            print("  ✓ Stamp creation works")

            return True

    except Exception as e:
        print(f"  {TestColors.RED}✗ Service test failed: {e}{TestColors.NC}")
        return False


async def test_onex_tree_service():
    """Test OnexTree Service"""
    print(f"\n{TestColors.BLUE}[3/5] Testing OnexTree Service...{TestColors.NC}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Health check
            response = await client.get(f"{ONEX_TREE_URL}/health")
            if response.status_code != 200:
                print(
                    f"  {TestColors.RED}✗ Health check failed: {response.status_code}{TestColors.NC}"
                )
                return False

            print("  ✓ Service is healthy")
            return True

    except Exception as e:
        print(f"  {TestColors.RED}✗ Service test failed: {e}{TestColors.NC}")
        return False


async def test_pattern_extraction():
    """Test pattern extraction from database"""
    print(f"\n{TestColors.BLUE}[4/5] Testing Pattern Extraction...{TestColors.NC}")

    try:
        conn = await asyncpg.connect(DB_URL, timeout=10)

        # Extract a few sample patterns
        patterns = await conn.fetch(
            """
            SELECT
                id, pattern_name, pattern_type, language,
                template_code, confidence_score
            FROM pattern_templates
            WHERE is_deprecated = FALSE
            ORDER BY confidence_score DESC
            LIMIT 5
        """
        )

        if not patterns:
            print(f"  {TestColors.RED}✗ No patterns found{TestColors.NC}")
            await conn.close()
            return False

        print(f"  ✓ Extracted {len(patterns)} sample patterns")

        for pattern in patterns:
            print(
                f"    - {pattern['pattern_name']} ({pattern['pattern_type']}, {pattern['language']})"
            )

        await conn.close()
        return True

    except Exception as e:
        print(f"  {TestColors.RED}✗ Pattern extraction failed: {e}{TestColors.NC}")
        return False


async def test_end_to_end_integration():
    """Test end-to-end integration with a single pattern"""
    print(f"\n{TestColors.BLUE}[5/5] Testing End-to-End Integration...{TestColors.NC}")

    try:
        # Extract one pattern
        conn = await asyncpg.connect(DB_URL, timeout=10)
        pattern = await conn.fetchrow(
            """
            SELECT
                id, pattern_name, pattern_type, language,
                template_code, confidence_score
            FROM pattern_templates
            WHERE is_deprecated = FALSE
            ORDER BY RANDOM()
            LIMIT 1
        """
        )
        await conn.close()

        if not pattern:
            print(
                f"  {TestColors.RED}✗ No pattern available for testing{TestColors.NC}"
            )
            return False

        print(f"  ✓ Using pattern: {pattern['pattern_name']}")

        # Stamp the pattern
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Generate hash
            file_data = pattern["template_code"].encode("utf-8")
            hash_response = await client.post(
                f"{METADATA_STAMPING_URL}/hash",
                files={"file": ("pattern.py", file_data, "application/octet-stream")},
                params={"namespace": "integration_test"},
            )
            hash_response.raise_for_status()
            file_hash = hash_response.json()["data"]["hash"]

            print(f"  ✓ Generated hash: {file_hash[:16]}...")

            # Create stamp
            stamp_request = {
                "file_hash": file_hash,
                "file_path": f"patterns/test/{pattern['pattern_name']}",
                "file_size": len(file_data),
                "content_type": "text/x-python",
                "stamp_data": {
                    "pattern_id": str(pattern["id"]),
                    "pattern_name": pattern["pattern_name"],
                    "pattern_type": pattern["pattern_type"],
                    "language": pattern["language"],
                    "confidence_score": float(pattern["confidence_score"]),
                },
                "namespace": "integration_test",
            }

            stamp_response = await client.post(
                f"{METADATA_STAMPING_URL}/stamp", json=stamp_request
            )
            stamp_response.raise_for_status()
            stamp_id = stamp_response.json().get("data", {}).get("stamp_id")

            print(f"  ✓ Created stamp: {stamp_id}")

        print("  ✓ End-to-end integration successful")
        return True

    except Exception as e:
        print(f"  {TestColors.RED}✗ End-to-end test failed: {e}{TestColors.NC}")
        return False


async def main():
    """Run all tests"""
    print(f"\n{TestColors.GREEN}{'=' * 60}{TestColors.NC}")
    print(f"{TestColors.GREEN}Pattern Integration Test Suite{TestColors.NC}")
    print(f"{TestColors.GREEN}{'=' * 60}{TestColors.NC}")

    tests = [
        ("Database Connection", test_database_connection),
        ("Metadata Stamping Service", test_metadata_stamping_service),
        ("OnexTree Service", test_onex_tree_service),
        ("Pattern Extraction", test_pattern_extraction),
        ("End-to-End Integration", test_end_to_end_integration),
    ]

    results = []

    for test_name, test_func in tests:
        result = await test_func()
        results.append((test_name, result))

    # Summary
    print(f"\n{TestColors.GREEN}{'=' * 60}{TestColors.NC}")
    print(f"{TestColors.GREEN}Test Summary{TestColors.NC}")
    print(f"{TestColors.GREEN}{'=' * 60}{TestColors.NC}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = (
            f"{TestColors.GREEN}✓ PASS{TestColors.NC}"
            if result
            else f"{TestColors.RED}✗ FAIL{TestColors.NC}"
        )
        print(f"  {status}  {test_name}")

    print(f"\n{TestColors.BLUE}Results: {passed}/{total} tests passed{TestColors.NC}")

    if passed == total:
        print(
            f"\n{TestColors.GREEN}✓ All tests passed! Ready for full integration.{TestColors.NC}"
        )
        print("\nRun full integration with:")
        print("  ./run_pattern_integration.sh")
        return 0
    else:
        print(
            f"\n{TestColors.RED}✗ Some tests failed. Please fix issues before running full integration.{TestColors.NC}"
        )
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
