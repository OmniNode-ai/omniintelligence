#!/usr/bin/env python3
"""
Single Codebase Pattern Extraction Test
=========================================

Extract patterns from one codebase to test performance.
"""

import json
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pattern_extraction import PatternExtractor


def main():
    """Extract patterns from omniclaude."""

    print("=" * 80)
    print("PATTERN EXTRACTION TEST - Single Codebase (omniclaude)")
    print("=" * 80)
    print()

    # Initialize extractor
    extractor = PatternExtractor()

    # Define source directory
    source_path = Path("/Volumes/PRO-G40/Code/omniclaude")

    # Quality thresholds
    MIN_CONFIDENCE = 0.6
    MAX_COMPLEXITY = 15

    print(f"Source: {source_path}")
    print(f"Min confidence: {MIN_CONFIDENCE}")
    print(f"Max complexity: {MAX_COMPLEXITY}")
    print()

    # Start extraction
    print("Starting extraction...")
    start_time = time.time()

    try:
        results = extractor.extract_from_directory(
            str(source_path), recursive=True, pattern="*.py"
        )

        extraction_time = time.time() - start_time
        print(f"Extraction completed in {extraction_time:.2f}s")
        print()

        # Flatten and filter
        all_patterns = []
        files_with_patterns = 0

        for file_path, patterns in results.items():
            has_quality_patterns = False

            for pattern in patterns:
                confidence = pattern.get("confidence", 0.0)
                complexity = pattern.get("complexity", 999)

                if confidence >= MIN_CONFIDENCE and complexity <= MAX_COMPLEXITY:
                    pattern["source_codebase"] = "omniclaude"
                    all_patterns.append(pattern)
                    has_quality_patterns = True

            if has_quality_patterns:
                files_with_patterns += 1

        print(f"Files processed: {len(results)}")
        print(f"Files with quality patterns: {files_with_patterns}")
        print(f"Quality patterns found: {len(all_patterns)}")
        print()

        # Save to file
        output_path = Path("/tmp/omniclaude_patterns.json")
        output_data = {
            "metadata": {
                "source": "omniclaude",
                "extraction_time_seconds": extraction_time,
                "min_confidence": MIN_CONFIDENCE,
                "max_complexity": MAX_COMPLEXITY,
            },
            "patterns": all_patterns,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        print(f"✅ Patterns saved to: {output_path}")
        print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")

        # Show some examples
        if all_patterns:
            print()
            print("Sample patterns:")
            for i, p in enumerate(all_patterns[:5], 1):
                print(
                    f"  {i}. {p['pattern_name']} ({p['pattern_type']}, confidence: {p['confidence']:.2f})"
                )

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
