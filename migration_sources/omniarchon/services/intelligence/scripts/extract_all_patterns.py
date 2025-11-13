#!/usr/bin/env python3
"""
Pattern Extraction Script for Migration
=========================================

Extracts REAL code patterns from 3 codebases:
- omniclaude
- Omniarchon
- omnidash

Uses AST-based PatternExtractor to identify genuine code patterns.
Filters by quality (confidence >= 0.6) and complexity (<= 15).

Output: /tmp/extracted_patterns.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pattern_extraction import PatternExtractor


def main():
    """Extract patterns from all codebases."""

    print("=" * 80)
    print("PATTERN EXTRACTION - Real Code Patterns from AST Analysis")
    print("=" * 80)
    print()

    # Initialize extractor
    extractor = PatternExtractor()

    # Define source directories
    source_dirs = [
        {
            "name": "omniclaude",
            "path": Path("/Volumes/PRO-G40/Code/omniclaude"),
        },
        {
            "name": "Omniarchon",
            "path": Path("/Volumes/PRO-G40/Code/Omniarchon"),
        },
        {
            "name": "omnidash",
            "path": Path("/Volumes/PRO-G40/Code/omnidash"),
        },
    ]

    # Quality thresholds
    MIN_CONFIDENCE = 0.6
    MAX_COMPLEXITY = 15

    # Track statistics
    stats = {
        "files_processed": 0,
        "files_skipped": 0,
        "patterns_found": 0,
        "patterns_filtered": 0,
        "errors": 0,
        "by_codebase": {},
    }

    all_patterns = []

    # Process each codebase
    for source in source_dirs:
        print(f"\n📂 Processing: {source['name']}")
        print(f"   Path: {source['path']}")
        print(f"   {'─' * 70}")

        if not source["path"].exists():
            print(f"   ❌ Directory not found: {source['path']}")
            stats["errors"] += 1
            continue

        codebase_stats = {
            "files_processed": 0,
            "patterns_found": 0,
            "patterns_filtered": 0,
        }

        try:
            # Extract patterns from directory
            print(f"   🔍 Scanning Python files...")
            results = extractor.extract_from_directory(
                str(source["path"]), recursive=True, pattern="*.py"
            )

            # Flatten results and filter by quality
            codebase_patterns = []

            for file_path, patterns in results.items():
                codebase_stats["files_processed"] += 1

                for pattern in patterns:
                    codebase_stats["patterns_found"] += 1

                    # Apply quality filters
                    confidence = pattern.get("confidence", 0.0)
                    complexity = pattern.get("complexity", 999)

                    if confidence >= MIN_CONFIDENCE and complexity <= MAX_COMPLEXITY:
                        # Add source metadata
                        pattern["source_codebase"] = source["name"]
                        pattern["source_project"] = source["name"]
                        codebase_patterns.append(pattern)
                    else:
                        codebase_stats["patterns_filtered"] += 1

            # Update global stats
            all_patterns.extend(codebase_patterns)
            stats["files_processed"] += codebase_stats["files_processed"]
            stats["patterns_found"] += codebase_stats["patterns_found"]
            stats["patterns_filtered"] += codebase_stats["patterns_filtered"]
            stats["by_codebase"][source["name"]] = codebase_stats

            print(f"   ✅ Files processed: {codebase_stats['files_processed']}")
            print(f"   📊 Patterns found: {codebase_stats['patterns_found']}")
            print(f"   🎯 Patterns kept (quality): {len(codebase_patterns)}")
            print(f"   🗑️  Patterns filtered: {codebase_stats['patterns_filtered']}")

        except Exception as e:
            print(f"   ❌ Error processing {source['name']}: {e}")
            stats["errors"] += 1
            import traceback

            traceback.print_exc()

    # Generate summary statistics
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print()

    print(f"📁 Total files processed: {stats['files_processed']}")
    print(f"📊 Total patterns found: {stats['patterns_found']}")
    print(f"🎯 Total patterns kept: {len(all_patterns)}")
    print(f"🗑️  Total patterns filtered: {stats['patterns_filtered']}")
    print(f"❌ Errors: {stats['errors']}")
    print()

    # Pattern type distribution
    if all_patterns:
        print("Pattern Type Distribution:")
        type_counts = {}
        for p in all_patterns:
            ptype = p.get("pattern_type", "unknown")
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

        for ptype, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / len(all_patterns)) * 100
            print(f"  - {ptype}: {count} ({percentage:.1f}%)")
        print()

        # Category distribution
        print("Pattern Category Distribution (Top 10):")
        category_counts = {}
        for p in all_patterns:
            category = p.get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1

        top_categories = sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
        for category, count in top_categories:
            percentage = (count / len(all_patterns)) * 100
            print(f"  - {category}: {count} ({percentage:.1f}%)")
        print()

        # Quality metrics
        confidences = [p.get("confidence", 0.0) for p in all_patterns]
        complexities = [p.get("complexity", 0) for p in all_patterns]
        maintainabilities = [
            p.get("maintainability_index", 0.0)
            for p in all_patterns
            if p.get("maintainability_index", 0.0) > 0
        ]

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0.0
        avg_maintainability = (
            sum(maintainabilities) / len(maintainabilities)
            if maintainabilities
            else 0.0
        )

        print("Quality Metrics:")
        print(f"  - Average Confidence: {avg_confidence:.2f}")
        print(f"  - Average Complexity: {avg_complexity:.2f}")
        print(f"  - Average Maintainability Index: {avg_maintainability:.2f}")
        print()

        # Top quality patterns
        print("Top 10 Highest Quality Patterns:")
        sorted_by_confidence = sorted(
            all_patterns, key=lambda x: x.get("confidence", 0.0), reverse=True
        )[:10]
        for i, pattern in enumerate(sorted_by_confidence, 1):
            name = pattern.get("pattern_name", "unnamed")
            confidence = pattern.get("confidence", 0.0)
            ptype = pattern.get("pattern_type", "unknown")
            category = pattern.get("category", "unknown")
            source = pattern.get("source_codebase", "unknown")
            print(
                f"  {i:2d}. {name[:40]:40s} | {confidence:.2f} | {ptype:20s} | {source}"
            )
        print()

    # Export to JSON
    output_path = Path("/tmp/extracted_patterns.json")

    output_data = {
        "metadata": {
            "extraction_date": "2025-10-28",
            "correlation_id": "672a37fa-02a2-40ab-989c-20b2c12daeee",
            "min_confidence": MIN_CONFIDENCE,
            "max_complexity": MAX_COMPLEXITY,
            "source_codebases": [s["name"] for s in source_dirs],
        },
        "statistics": stats,
        "patterns": all_patterns,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"✅ Patterns exported to: {output_path}")
    print(f"📦 File size: {output_path.stat().st_size / 1024:.1f} KB")
    print()

    # Validation checks
    print("=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)
    print()

    validation_passed = True

    # Check 1: Minimum pattern count
    if len(all_patterns) < 200:
        print(
            f"❌ FAIL: Only {len(all_patterns)} patterns extracted (expected 200-500)"
        )
        validation_passed = False
    elif len(all_patterns) > 500:
        print(
            f"⚠️  WARN: {len(all_patterns)} patterns extracted (expected 200-500, got more)"
        )
    else:
        print(f"✅ PASS: {len(all_patterns)} patterns extracted (within 200-500 range)")

    # Check 2: Average quality
    if avg_confidence < 0.6:
        print(f"❌ FAIL: Average confidence {avg_confidence:.2f} < 0.6")
        validation_passed = False
    else:
        print(f"✅ PASS: Average confidence {avg_confidence:.2f} >= 0.6")

    # Check 3: No filename patterns
    filename_patterns = [p for p in all_patterns if ".py" in p.get("pattern_name", "")]
    if filename_patterns:
        print(f"❌ FAIL: Found {len(filename_patterns)} patterns with .py in name")
        validation_passed = False
    else:
        print(f"✅ PASS: No patterns with .py in name")

    # Check 4: Required fields
    required_fields = ["pattern_name", "pattern_type", "confidence", "complexity"]
    missing_fields = []
    for field in required_fields:
        patterns_missing = [p for p in all_patterns if field not in p]
        if patterns_missing:
            missing_fields.append((field, len(patterns_missing)))

    if missing_fields:
        print(f"❌ FAIL: Missing required fields:")
        for field, count in missing_fields:
            print(f"   - {field}: missing in {count} patterns")
        validation_passed = False
    else:
        print(f"✅ PASS: All patterns have required fields")

    print()

    if validation_passed:
        print("🎉 All validation checks passed!")
        return 0
    else:
        print("⚠️  Some validation checks failed - review above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
