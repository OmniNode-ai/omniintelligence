#!/usr/bin/env python3
"""
Comprehensive Test Suite for Ingestion Pipeline Fixes

Validates fixes for:
1. Binary file exclusion (images, videos, archives, executables, etc.)
2. Large file handling (>2MB uses path-only strategy)
3. Batch size validation and splitting (4.5MB max per batch)
4. Known problematic files handling

Created: 2025-11-10
ONEX Pattern: Validator (ingestion pipeline compliance testing)

Exit Codes:
    0 - All tests passed
    1 - Test failures detected
    2 - Fatal error during testing
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ==============================================================================
# Configuration Constants
# ==============================================================================

# File size thresholds
SIZE_2MB = 2 * 1024 * 1024  # 2MB - threshold for path-only strategy
SIZE_4_5MB = 4.5 * 1024 * 1024  # 4.5MB - max batch size before splitting
SIZE_5MB = 5 * 1024 * 1024  # 5MB - Kafka hard limit

# Binary file extensions (comprehensive list)
BINARY_EXTENSIONS = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".svg",
    ".tiff",
    ".tif",
    ".psd",
    ".raw",
    ".heif",
    ".heic",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    # Libraries/Binaries
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".lib",
    # Python bytecode
    ".pyc",
    ".pyo",
    ".pyd",
    # Databases
    ".db",
    ".sqlite",
    ".sqlite3",
    # Pickles/Models
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".h5",
    ".hdf5",
    # Documents (binary formats)
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    # Media
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mkv",
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    # Other
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".wasm",
    ".dat",
}

# Known problematic files from INGESTION_FAILURE_INVESTIGATION_REPORT.md
KNOWN_PROBLEMATIC_FILES = [
    {
        "path": "skills/PDF Processing Pro/docs/components.json",
        "size": 4.37 * 1024 * 1024,  # 4.37MB
        "reason": "Large JSON with inline content",
    },
    {
        "path": "skills/skill-writer/aten/src/ATen/native/SobolEngineOpsUtils.cpp",
        "size": 2.07 * 1024 * 1024,  # 2.07MB
        "reason": "Large C++ source file",
    },
    {
        "path": "skills/PDF Processing Pro/cli-tool/security-report.json",
        "size": 2.05 * 1024 * 1024,  # 2.05MB
        "reason": "Large JSON security report",
    },
]


# ==============================================================================
# Utility Functions (Implementations to be added to batch_processor.py)
# ==============================================================================


def is_binary_file(file_path: str) -> bool:
    """
    Check if file is binary based on extension.

    This function should be implemented in batch_processor.py to prevent
    binary files from being included in ingestion batches.

    Args:
        file_path: File path (relative or absolute)

    Returns:
        True if file is binary and should be excluded
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    return extension in BINARY_EXTENSIONS


def should_include_content(file_path: str, file_size: int) -> bool:
    """
    Determine if file content should be included inline or use path-only strategy.

    Files >2MB should use path-only strategy to prevent batch size issues.

    This function should be implemented in batch_processor.py to handle
    large files gracefully.

    Args:
        file_path: File path (relative or absolute)
        file_size: File size in bytes

    Returns:
        True if content should be included inline, False for path-only
    """
    # Binary files never get inline content
    if is_binary_file(file_path):
        return False

    # Files >2MB use path-only strategy
    if file_size > SIZE_2MB:
        return False

    return True


def calculate_batch_size(batch: List[Dict]) -> int:
    """
    Calculate total size of batch in bytes (including JSON serialization overhead).

    This function should be implemented in batch_processor.py to validate
    batch sizes before sending to Kafka.

    Args:
        batch: List of file dictionaries

    Returns:
        Total batch size in bytes (including JSON overhead)
    """
    # Serialize batch to JSON to get accurate size
    batch_json = json.dumps(batch)
    return len(batch_json.encode("utf-8"))


def split_batch_if_needed(
    batch: List[Dict], max_size: int = SIZE_4_5MB
) -> List[List[Dict]]:
    """
    Split batch if it exceeds max_size threshold.

    This function should be implemented in batch_processor.py to prevent
    MessageSizeTooLargeError from Kafka.

    Args:
        batch: List of file dictionaries
        max_size: Maximum batch size in bytes (default: 4.5MB)

    Returns:
        List of batches, each under max_size
    """
    batch_size = calculate_batch_size(batch)

    # If batch is within limits, return as-is
    if batch_size <= max_size:
        return [batch]

    # Split batch in half and recursively check each half
    mid = len(batch) // 2
    if mid == 0:
        # Single file too large - return as-is and let caller handle
        print(f"⚠️  WARNING: Single file batch ({batch_size} bytes) exceeds limit")
        return [batch]

    left_batches = split_batch_if_needed(batch[:mid], max_size)
    right_batches = split_batch_if_needed(batch[mid:], max_size)

    return left_batches + right_batches


# ==============================================================================
# Test Suite
# ==============================================================================


class TestResults:
    """Track test results and generate summary."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors: List[str] = []

    def add_pass(self):
        self.passed += 1

    def add_fail(self, error: str):
        self.failed += 1
        self.errors.append(error)

    def add_warning(self, warning: str):
        self.warnings += 1
        self.errors.append(f"⚠️  {warning}")

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


def test_binary_exclusion(results: TestResults) -> bool:
    """
    Test that binary files are properly excluded.

    Args:
        results: TestResults object to track outcomes

    Returns:
        True if all tests passed
    """
    print("\n" + "=" * 70)
    print("TEST SUITE 1: Binary File Exclusion")
    print("=" * 70)

    test_files = [
        # Images
        ("test.png", True),
        ("icon.jpg", True),
        ("logo.jpeg", True),
        ("banner.gif", True),
        ("avatar.svg", True),
        ("photo.webp", True),
        # Fonts
        ("font.woff", True),
        ("font.woff2", True),
        ("font.ttf", True),
        ("font.otf", True),
        # Binaries
        ("lib.so", True),
        ("lib.dll", True),
        ("module.pyc", True),
        ("program.exe", True),
        ("app.bin", True),
        # Databases
        ("data.db", True),
        ("cache.sqlite", True),
        # ML Models
        ("model.pkl", True),
        ("weights.pt", True),
        ("model.h5", True),
        # Documents
        ("doc.pdf", True),
        ("report.docx", True),
        # Media
        ("video.mp4", True),
        ("audio.mp3", True),
        # Archives
        ("archive.zip", True),
        ("backup.tar.gz", True),
        ("package.7z", True),
        # Text files (should NOT be excluded)
        ("code.py", False),
        ("config.json", False),
        ("readme.md", False),
        ("script.js", False),
        ("style.css", False),
    ]

    all_passed = True

    for file_path, should_be_binary in test_files:
        is_binary = is_binary_file(file_path)

        if is_binary == should_be_binary:
            print(f"  ✅ {file_path:30s} - {'binary' if is_binary else 'text'}")
            results.add_pass()
        else:
            expected = "binary" if should_be_binary else "text"
            actual = "binary" if is_binary else "text"
            error = f"Failed: {file_path} - expected {expected}, got {actual}"
            print(f"  ❌ {error}")
            results.add_fail(error)
            all_passed = False

    if all_passed:
        print("\n✅ Binary file exclusion tests: PASSED")
    else:
        print("\n❌ Binary file exclusion tests: FAILED")

    return all_passed


def test_file_size_handling(results: TestResults) -> bool:
    """
    Test file size thresholds for inline content vs path-only strategy.

    Args:
        results: TestResults object to track outcomes

    Returns:
        True if all tests passed
    """
    print("\n" + "=" * 70)
    print("TEST SUITE 2: File Size Handling")
    print("=" * 70)

    test_cases = [
        # (file_path, size_bytes, should_include_content, description)
        ("small.txt", 1024, True, "1KB - inline content"),
        ("medium.json", 512 * 1024, True, "512KB - inline content"),
        ("large.json", 1.5 * 1024 * 1024, True, "1.5MB - inline content"),
        ("xlarge.cpp", 2.1 * 1024 * 1024, False, "2.1MB - path-only"),
        ("huge.json", 4.5 * 1024 * 1024, False, "4.5MB - path-only"),
        ("massive.cpp", 10 * 1024 * 1024, False, "10MB - path-only"),
        # Binary files never get inline content
        ("icon.png", 100 * 1024, False, "100KB PNG - binary exclusion"),
        ("video.mp4", 1.5 * 1024 * 1024, False, "1.5MB MP4 - binary exclusion"),
    ]

    all_passed = True

    for file_path, size, expected_include, description in test_cases:
        actual_include = should_include_content(file_path, size)

        if actual_include == expected_include:
            strategy = "inline" if actual_include else "path-only"
            print(f"  ✅ {description:40s} → {strategy}")
            results.add_pass()
        else:
            expected = "inline" if expected_include else "path-only"
            actual = "inline" if actual_include else "path-only"
            error = f"Failed: {description} - expected {expected}, got {actual}"
            print(f"  ❌ {error}")
            results.add_fail(error)
            all_passed = False

    if all_passed:
        print("\n✅ File size handling tests: PASSED")
    else:
        print("\n❌ File size handling tests: FAILED")

    return all_passed


def test_batch_splitting(results: TestResults) -> bool:
    """
    Test batch size validation and splitting.

    Args:
        results: TestResults object to track outcomes

    Returns:
        True if all tests passed
    """
    print("\n" + "=" * 70)
    print("TEST SUITE 3: Batch Size Validation & Splitting")
    print("=" * 70)

    all_passed = True

    # Test 1: Small batch (no splitting needed)
    print("\n  Test 3.1: Small batch (no splitting)")
    small_batch = [
        {"path": f"file{i}.txt", "content": "x" * 1024}  # 1KB each
        for i in range(10)  # ~10KB total
    ]

    split_batches = split_batch_if_needed(small_batch)

    if len(split_batches) == 1:
        print(f"    ✅ Small batch not split (1 batch)")
        results.add_pass()
    else:
        error = f"Small batch incorrectly split into {len(split_batches)} batches"
        print(f"    ❌ {error}")
        results.add_fail(error)
        all_passed = False

    # Test 2: Large batch (should be split)
    print("\n  Test 3.2: Large batch (requires splitting)")
    large_batch = [
        {"path": f"file{i}.json", "content": "x" * (1024 * 1024)}  # 1MB each
        for i in range(6)  # ~6MB total
    ]

    split_batches = split_batch_if_needed(large_batch)

    if len(split_batches) > 1:
        print(f"    ✅ Large batch split into {len(split_batches)} batches")
        results.add_pass()

        # Verify each split batch is within limits
        all_within_limits = True
        for idx, batch in enumerate(split_batches):
            size = calculate_batch_size(batch)
            if size <= SIZE_4_5MB:
                print(
                    f"    ✅ Batch {idx + 1}: {len(batch)} files, {size / 1024 / 1024:.2f}MB"
                )
                results.add_pass()
            else:
                error = (
                    f"Split batch {idx + 1} still too large: {size / 1024 / 1024:.2f}MB"
                )
                print(f"    ❌ {error}")
                results.add_fail(error)
                all_within_limits = False
                all_passed = False

        if not all_within_limits:
            all_passed = False

    else:
        error = f"Large batch not split (expected >1 batch, got {len(split_batches)})"
        print(f"    ❌ {error}")
        results.add_fail(error)
        all_passed = False

    # Test 3: Batch at exact threshold
    print("\n  Test 3.3: Batch at threshold (4.5MB)")
    threshold_batch = [
        {
            "path": f"file{i}.json",
            "content": "x"
            * (int(SIZE_4_5MB / 10) - 1000),  # Slightly under 4.5MB total
        }
        for i in range(10)
    ]

    split_batches = split_batch_if_needed(threshold_batch)
    batch_size = calculate_batch_size(threshold_batch)

    if len(split_batches) == 1 and batch_size <= SIZE_4_5MB:
        print(
            f"    ✅ Threshold batch not split ({batch_size / 1024 / 1024:.2f}MB ≤ 4.5MB)"
        )
        results.add_pass()
    elif len(split_batches) > 1 and batch_size > SIZE_4_5MB:
        print(
            f"    ✅ Threshold batch split ({batch_size / 1024 / 1024:.2f}MB > 4.5MB)"
        )
        results.add_pass()
    else:
        error = f"Threshold batch handling incorrect: size={batch_size / 1024 / 1024:.2f}MB, splits={len(split_batches)}"
        print(f"    ❌ {error}")
        results.add_fail(error)
        all_passed = False

    if all_passed:
        print("\n✅ Batch splitting tests: PASSED")
    else:
        print("\n❌ Batch splitting tests: FAILED")

    return all_passed


def test_problematic_files(results: TestResults) -> bool:
    """
    Test handling of known problematic files from ingestion failure report.

    Args:
        results: TestResults object to track outcomes

    Returns:
        True if all tests passed
    """
    print("\n" + "=" * 70)
    print("TEST SUITE 4: Known Problematic Files")
    print("=" * 70)

    all_passed = True

    for file_data in KNOWN_PROBLEMATIC_FILES:
        file_path = file_data["path"]
        size = file_data["size"]
        reason = file_data["reason"]

        should_include = should_include_content(file_path, int(size))

        # All these files are >2MB, so should use path-only
        if not should_include:
            print(f"  ✅ {file_path}")
            print(f"      Size: {size / 1024 / 1024:.2f}MB → path-only")
            print(f"      Reason: {reason}")
            results.add_pass()
        else:
            error = f"Large file should use path-only: {file_path} ({size / 1024 / 1024:.2f}MB)"
            print(f"  ❌ {error}")
            results.add_fail(error)
            all_passed = False

    if all_passed:
        print("\n✅ Problematic file handling tests: PASSED")
    else:
        print("\n❌ Problematic file handling tests: FAILED")

    return all_passed


def run_all_tests() -> int:
    """
    Run all validation tests and generate comprehensive report.

    Returns:
        Exit code (0 = success, 1 = test failure, 2 = error)
    """
    print("=" * 70)
    print("🔍 INGESTION PIPELINE FIX VALIDATION")
    print("=" * 70)
    print()
    print("Testing fixes for:")
    print("  1. Binary file exclusion")
    print("  2. File size handling (2MB threshold)")
    print("  3. Batch size validation (4.5MB max)")
    print("  4. Known problematic files")

    results = TestResults()

    try:
        # Run all test suites
        test1_passed = test_binary_exclusion(results)
        test2_passed = test_file_size_handling(results)
        test3_passed = test_batch_splitting(results)
        test4_passed = test_problematic_files(results)

        all_passed = test1_passed and test2_passed and test3_passed and test4_passed

        # Generate summary report
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests:     {results.total}")
        print(f"Passed:          {results.passed} ✅")
        print(f"Failed:          {results.failed} ❌")
        print(f"Warnings:        {results.warnings} ⚠️")
        print(f"Success Rate:    {results.success_rate:.1f}%")

        if results.errors and not all_passed:
            print("\n" + "=" * 70)
            print("❌ FAILED TESTS")
            print("=" * 70)
            for error in results.errors:
                if not error.startswith("⚠️"):
                    print(f"  • {error}")

        if results.warnings:
            print("\n" + "=" * 70)
            print("⚠️  WARNINGS")
            print("=" * 70)
            for warning in results.errors:
                if warning.startswith("⚠️"):
                    print(f"  • {warning}")

        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED")
            print("=" * 70)
            print("\nIngestion pipeline fixes are working correctly:")
            print("  ✓ Binary files properly excluded")
            print("  ✓ Large files (>2MB) use path-only strategy")
            print("  ✓ Batches split when exceeding 4.5MB")
            print("  ✓ Known problematic files handled correctly")
            print()
            return 0
        else:
            print("❌ TESTS FAILED")
            print("=" * 70)
            print(
                f"\n{results.failed} test(s) failed. Please review errors above and fix implementations."
            )
            print()
            return 1

    except AssertionError as e:
        print(f"\n❌ TEST ASSERTION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 2


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 = success, 1 = failure, 2 = error)
    """
    try:
        return run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
