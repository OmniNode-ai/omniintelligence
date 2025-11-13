"""
Pattern Extraction Demo
========================

Demonstrates pattern extraction on real Python files.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pattern_extraction import PatternExtractor


def main():
    """Run pattern extraction demo."""
    extractor = PatternExtractor()

    # Get file path from command line or use classifier.py as default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = Path(__file__).parent / "classifier.py"

    print(f"Extracting patterns from: {file_path}\n")
    print("=" * 80)

    try:
        # Extract patterns
        patterns = extractor.extract_from_file(str(file_path))

        print(f"\nFound {len(patterns)} patterns:\n")

        # Display each pattern
        for i, pattern in enumerate(patterns, 1):
            print(f"\n{i}. {pattern['pattern_name']}")
            print(f"   {'=' * 70}")
            print(f"   Type: {pattern['pattern_type']}")
            print(f"   Category: {pattern['category']}")
            print(f"   Lines: {pattern['line_range'][0]}-{pattern['line_range'][1]}")
            print(
                f"   Complexity: {pattern['complexity']} (Grade: {pattern['complexity_grade']})"
            )
            print(f"   Maintainability: {pattern['maintainability_index']:.2f}")
            print(f"   Confidence: {pattern['confidence']:.2%}")
            print(f"   Tags: {', '.join(pattern['tags'])}")

            if pattern["docstring"]:
                print(f"   Doc: {pattern['docstring'][:60]}...")

            if "is_async" in pattern and pattern["is_async"]:
                print(f"   Async: Yes")

            if "decorators" in pattern and pattern["decorators"]:
                print(f"   Decorators: {', '.join(pattern['decorators'])}")

            if "methods" in pattern and pattern["methods"]:
                print(f"   Methods: {', '.join(pattern['methods'][:5])}")
                if len(pattern["methods"]) > 5:
                    print(f"            ... and {len(pattern['methods']) - 5} more")

        # Display summary
        print("\n" + "=" * 80)
        summary = extractor.get_pattern_summary(patterns)
        print("\n=== SUMMARY ===")
        print(f"Total patterns: {summary['total_patterns']}")
        print(f"Average complexity: {summary['avg_complexity']}")
        print(f"Average maintainability: {summary['avg_maintainability']}")

        print("\nPatterns by type:")
        for ptype, count in summary["by_type"].items():
            print(f"  - {ptype}: {count}")

        print("\nPatterns by category:")
        for category, count in sorted(
            summary["by_category"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  - {category}: {count}")

        if summary["high_complexity"]:
            print(f"\nHigh complexity patterns ({len(summary['high_complexity'])}):")
            for item in summary["high_complexity"]:
                print(f"  - {item['name']}: {item['complexity']}")

        # Export to JSON
        output_file = Path(__file__).parent / "extracted_patterns.json"
        extractor.export_patterns_json(patterns, str(output_file))
        print(f"\n✅ Patterns exported to: {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
