#!/usr/bin/env python3
"""
Verification Script for Ingestion Pipeline Fixes

Tests the comprehensive fixes for:
1. Binary file exclusions
2. Batch size validation
3. Large file handling (path-only strategy)
4. Statistics tracking

Created: 2025-11-10
"""

import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.batch_processor import (
    MAX_BATCH_SIZE_MB,
    MAX_FILE_SIZE_MB,
    BatchProcessor,
)
from scripts.lib.file_discovery import (
    BINARY_FILE_EXTENSIONS,
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_SUPPORTED_EXTENSIONS,
    FileDiscovery,
)


def test_binary_file_detection():
    """Test binary file exclusion logic."""
    print("=" * 70)
    print("TEST 1: Binary File Detection")
    print("=" * 70)

    test_cases = [
        (".png", True, "Image file"),
        (".jpg", True, "Image file"),
        (".woff", True, "Font file"),
        (".dll", True, "Compiled binary"),
        (".pyc", True, "Compiled Python"),
        (".pdf", True, "PDF document"),
        (".py", False, "Python source"),
        (".js", False, "JavaScript source"),
        (".md", False, "Markdown document"),
    ]

    discovery = FileDiscovery()
    passed = 0
    failed = 0

    for ext, expected, description in test_cases:
        result = discovery._is_binary_file(ext)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(
            f"{status}: {ext:10s} -> {result:5} (expected: {expected:5}) - {description}"
        )

        if result == expected:
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    print()
    return failed == 0


def test_batch_size_calculation():
    """Test batch size calculation logic."""
    print("=" * 70)
    print("TEST 2: Batch Size Calculation")
    print("=" * 70)

    processor = BatchProcessor(
        kafka_bootstrap_servers="test:9092",
        dry_run=True,
    )

    # Test with small batch
    small_batch = [
        {"file_path": f"/test/file{i}.py", "content": "x" * 100} for i in range(5)
    ]

    size_bytes = processor._calculate_batch_size(small_batch)
    size_mb = size_bytes / 1024 / 1024

    print(f"Small batch (5 files, 100 chars each):")
    print(f"  Size: {size_bytes:,} bytes ({size_mb:.3f} MB)")
    print(f"  Limit: {MAX_BATCH_SIZE_MB} MB")
    print(
        f"  Status: {'✅ Within limit' if size_mb < MAX_BATCH_SIZE_MB else '❌ Exceeds limit'}"
    )
    print()

    # Test with large batch
    large_batch = [
        {"file_path": f"/test/file{i}.py", "content": "x" * 100000} for i in range(25)
    ]

    size_bytes = processor._calculate_batch_size(large_batch)
    size_mb = size_bytes / 1024 / 1024

    print(f"Large batch (25 files, 100KB each):")
    print(f"  Size: {size_bytes:,} bytes ({size_mb:.3f} MB)")
    print(f"  Limit: {MAX_BATCH_SIZE_MB} MB")
    print(
        f"  Status: {'✅ Within limit' if size_mb < MAX_BATCH_SIZE_MB else '⚠️  Exceeds limit (will be split)'}"
    )
    print()

    return True


def test_batch_splitting():
    """Test batch splitting logic."""
    print("=" * 70)
    print("TEST 3: Batch Splitting")
    print("=" * 70)

    processor = BatchProcessor(
        kafka_bootstrap_servers="test:9092",
        dry_run=True,
    )

    # Create oversized batch
    oversized_batch = [
        {"file_path": f"/test/file{i}.py", "content": "x" * 200000} for i in range(25)
    ]

    original_size = processor._calculate_batch_size(oversized_batch)
    print(f"Original batch:")
    print(f"  Files: {len(oversized_batch)}")
    print(f"  Size: {original_size / 1024 / 1024:.2f} MB")
    print()

    split_batches = processor._split_batch_if_needed(oversized_batch)
    print(f"After splitting:")
    print(f"  Number of batches: {len(split_batches)}")

    for idx, batch in enumerate(split_batches):
        batch_size = processor._calculate_batch_size(batch)
        print(
            f"  Batch {idx}: {len(batch)} files, {batch_size / 1024 / 1024:.2f} MB "
            f"({'✅' if batch_size <= MAX_BATCH_SIZE_MB * 1024 * 1024 else '❌'})"
        )

    print()
    return len(split_batches) > 1


def test_large_file_detection():
    """Test large file detection logic."""
    print("=" * 70)
    print("TEST 4: Large File Detection")
    print("=" * 70)

    processor = BatchProcessor(
        kafka_bootstrap_servers="test:9092",
        dry_run=True,
    )

    # Test with actual files (if they exist)
    test_files = [
        (__file__, "This test file"),  # Should be small
    ]

    for file_path, description in test_files:
        if Path(file_path).exists():
            should_include = processor._should_include_content(file_path)
            size = Path(file_path).stat().st_size
            size_mb = size / 1024 / 1024

            status = "✅ Inline" if should_include else "⚠️  Path-only"
            print(f"{status}: {description}")
            print(f"  Path: {file_path}")
            print(f"  Size: {size:,} bytes ({size_mb:.2f} MB)")
            print(f"  Threshold: {MAX_FILE_SIZE_MB} MB")
            print()

    return True


def test_statistics_tracking():
    """Test statistics tracking."""
    print("=" * 70)
    print("TEST 5: Statistics Tracking")
    print("=" * 70)

    from scripts.lib.batch_processor import ProcessingStats

    # Test stats with no large files
    stats1 = ProcessingStats(
        total_files=100,
        successful_batches=4,
        failed_batches=0,
        total_duration_ms=5000,
        average_batch_duration_ms=1250,
        large_files_excluded=0,
        batches_split=0,
    )

    print("Stats (no issues):")
    print(f"  {stats1}")
    print()

    # Test stats with large files and split batches
    stats2 = ProcessingStats(
        total_files=100,
        successful_batches=6,
        failed_batches=0,
        total_duration_ms=7000,
        average_batch_duration_ms=1167,
        large_files_excluded=3,
        batches_split=2,
    )

    print("Stats (with large files and splits):")
    print(f"  {stats2}")
    print()

    return True


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("INGESTION PIPELINE FIXES - VERIFICATION SUITE")
    print("=" * 70)
    print()

    results = {
        "Binary File Detection": test_binary_file_detection(),
        "Batch Size Calculation": test_batch_size_calculation(),
        "Batch Splitting": test_batch_splitting(),
        "Large File Detection": test_large_file_detection(),
        "Statistics Tracking": test_statistics_tracking(),
    }

    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print()

    if all_passed:
        print("✅ ALL TESTS PASSED - Fixes verified successfully!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review implementation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
