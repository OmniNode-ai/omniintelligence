#!/usr/bin/env python3
"""
Remove manual sys.path manipulations from test files.
conftest.py already handles path setup correctly.
"""
import re
from pathlib import Path


def clean_test_file(filepath: Path) -> tuple[bool, int]:
    """
    Remove sys.path.insert and related lines from test file.
    Returns (was_modified, num_lines_removed)
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False, 0

    original_count = len(lines)
    new_lines = []
    skip_next = False
    lines_removed = 0

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        # Skip sys.path.insert lines
        if re.search(r"sys\.path\.insert\(", line):
            lines_removed += 1
            continue

        # Skip "# Add paths" comment if followed by sys.path
        if re.search(r"#\s*Add paths?\s*$", line):
            # Check if next line is sys.path.insert
            if i + 1 < len(lines) and re.search(r"sys\.path\.insert\(", lines[i + 1]):
                lines_removed += 1
                continue

        # Skip blank lines that were likely grouping sys.path statements
        # Only if previous line was removed and next line is also sys.path
        if line.strip() == "" and lines_removed > 0 and i + 1 < len(lines):
            if re.search(r"sys\.path\.insert\(", lines[i + 1]):
                continue

        new_lines.append(line)

    if len(new_lines) != original_count:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True, original_count - len(new_lines)
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False, 0

    return False, 0


def main():
    base_dir = Path(__file__).parent / "tests"

    total_files = 0
    total_modified = 0
    total_lines_removed = 0

    print("Removing manual sys.path manipulations from test files...")
    for py_file in base_dir.rglob("*.py"):
        # Skip conftest.py files (they need path manipulation)
        if py_file.name == "conftest.py":
            continue

        total_files += 1
        modified, lines_removed = clean_test_file(py_file)
        if modified:
            total_modified += 1
            total_lines_removed += lines_removed
            print(
                f"  ✓ {py_file.relative_to(base_dir.parent)} ({lines_removed} lines removed)"
            )

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total test files scanned: {total_files}")
    print(f"  Files modified: {total_modified}")
    print(f"  Total lines removed: {total_lines_removed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
