#!/usr/bin/env python3
"""
Fix incorrect 'archon_services.intelligence.*' imports in test files.
These should be direct imports from 'onex' or 'models'.
"""
import re
from pathlib import Path


def fix_imports_in_file(filepath: Path) -> tuple[bool, int]:
    """
    Fix imports in a single file.
    Returns (was_modified, num_replacements)
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False, 0

    original_content = content
    replacements = 0

    # Pattern 1: from archon_services.intelligence.onex → from onex
    pattern1 = re.compile(r"\bfrom archon_services\.intelligence\.onex\b")
    content, count1 = pattern1.subn("from onex", content)
    replacements += count1

    # Pattern 2: from archon_services.intelligence.src.models → from models
    pattern2 = re.compile(r"\bfrom archon_services\.intelligence\.src\.models\b")
    content, count2 = pattern2.subn("from models", content)
    replacements += count2

    if content != original_content:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True, replacements
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False, 0

    return False, 0


def main():
    base_dir = Path(__file__).parent / "tests"

    total_files = 0
    total_modified = 0
    total_replacements = 0

    print("Fixing archon_services.intelligence.* imports...")
    for py_file in base_dir.rglob("*.py"):
        total_files += 1
        modified, replacements = fix_imports_in_file(py_file)
        if modified:
            total_modified += 1
            total_replacements += replacements
            print(
                f"  ✓ {py_file.relative_to(base_dir.parent)} ({replacements} replacements)"
            )

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total test files scanned: {total_files}")
    print(f"  Files modified: {total_modified}")
    print(f"  Total replacements: {total_replacements}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
