#!/usr/bin/env python3
"""
Fix imports after renaming src/services/ to src/archon_services/
"""
import os
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

    # Pattern 1: from services. → from archon_services.
    pattern1 = re.compile(r"\bfrom services\.")
    content, count1 = pattern1.subn("from archon_services.", content)
    replacements += count1

    # Pattern 2: import services. → import archon_services.
    pattern2 = re.compile(r"\bimport services\.")
    content, count2 = pattern2.subn("import archon_services.", content)
    replacements += count2

    # Pattern 3: from .services → from .archon_services (relative imports)
    pattern3 = re.compile(r"\bfrom \.services\b")
    content, count3 = pattern3.subn("from .archon_services", content)
    replacements += count3

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
    base_dir = Path(__file__).parent

    # Process src/ directory
    src_dir = base_dir / "src"
    test_dir = base_dir / "tests"

    total_files = 0
    total_modified = 0
    total_replacements = 0

    print("Processing source files (src/)...")
    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        modified, replacements = fix_imports_in_file(py_file)
        if modified:
            total_modified += 1
            total_replacements += replacements
            print(f"  ✓ {py_file.relative_to(base_dir)} ({replacements} replacements)")

    print(f"\nProcessing test files (tests/)...")
    for py_file in test_dir.rglob("*.py"):
        total_files += 1
        modified, replacements = fix_imports_in_file(py_file)
        if modified:
            total_modified += 1
            total_replacements += replacements
            print(f"  ✓ {py_file.relative_to(base_dir)} ({replacements} replacements)")

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total files scanned: {total_files}")
    print(f"  Files modified: {total_modified}")
    print(f"  Total replacements: {total_replacements}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
