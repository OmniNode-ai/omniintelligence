#!/usr/bin/env python3
"""
Test script for enhanced language detection in bulk ingestion.

Verifies that language detection works correctly with both
extension-based and content-based detection.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.language_detector import (
    detect_language_enhanced,
    get_detection_metrics,
)


def test_extension_based():
    """Test extension-based detection (should use extension)."""
    print("\n" + "=" * 70)
    print("TEST 1: Extension-based Detection")
    print("=" * 70)

    test_cases = [
        ("test.py", "python", None),
        ("test.js", "javascript", None),
        ("test.ts", "typescript", None),
        ("test.go", "go", None),
        ("test.rs", "rust", None),
    ]

    for file_path, expected, content in test_cases:
        result = detect_language_enhanced(file_path, expected, content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {file_path}: {result} (expected: {expected})")


def test_content_based():
    """Test content-based detection for files with unknown extension."""
    print("\n" + "=" * 70)
    print("TEST 2: Content-based Detection")
    print("=" * 70)

    test_cases = [
        (
            "unknown_script",
            "unknown",
            "#!/usr/bin/env python3\nimport sys\ndef main():\n    pass\n",
            "python",
        ),
        (
            "build_script",
            "unknown",
            "#!/bin/bash\nexport PATH=/usr/bin\nfunction build() {\n    echo 'Building...'\n}\n",
            "shell",
        ),
        (
            "app.something",
            "unknown",
            "const express = require('express');\nconst app = express();\nlet port = 3000;\n",
            "javascript",
        ),
        (
            "Main.unknown",
            "unknown",
            'package main\nimport "fmt"\nfunc main() {\n    fmt.Println("Hello")\n}\n',
            "go",
        ),
    ]

    for file_path, ext_lang, content, expected in test_cases:
        result = detect_language_enhanced(file_path, ext_lang, content)
        status = "✅" if result == expected else "❌"
        print(f"{status} {file_path}: {result} (expected: {expected})")


def test_unknown_fallback():
    """Test fallback to unknown for unrecognizable files."""
    print("\n" + "=" * 70)
    print("TEST 3: Unknown Fallback")
    print("=" * 70)

    test_cases = [
        ("random.txt", "unknown", "This is just plain text with no code patterns."),
        ("data.bin", "unknown", "\x00\x01\x02\x03\x04\x05"),
        ("empty.file", "unknown", ""),
    ]

    for file_path, ext_lang, content in test_cases:
        result = detect_language_enhanced(file_path, ext_lang, content)
        status = "✅" if result == "unknown" else "❌"
        print(f"{status} {file_path}: {result} (expected: unknown)")


def test_metrics():
    """Test that metrics are tracked correctly."""
    print("\n" + "=" * 70)
    print("TEST 4: Metrics Tracking")
    print("=" * 70)

    metrics = get_detection_metrics()
    print(f"Total detections: {metrics['total_detections']}")
    print(
        f"Extension-based: {metrics['extension_only']} ({metrics['extension_rate']:.1%})"
    )
    print(f"Content-based: {metrics['content_based']} ({metrics['content_rate']:.1%})")
    print(f"Unknown: {metrics['unknown_fallback']} ({metrics['unknown_rate']:.1%})")

    if metrics["total_detections"] > 0:
        print("\n✅ Metrics tracking working")
    else:
        print("\n❌ No detections recorded")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ENHANCED LANGUAGE DETECTION TEST SUITE")
    print("=" * 70)

    try:
        test_extension_based()
        test_content_based()
        test_unknown_fallback()
        test_metrics()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
