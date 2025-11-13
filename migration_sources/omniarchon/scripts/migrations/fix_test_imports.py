#!/usr/bin/env python3
"""
Fix test imports to match pytest.ini pythonpath configuration.

Since pytest.ini has 'pythonpath = src', test files should import WITHOUT 'src.' prefix:
    from src.services.health_monitor import ...  # WRONG
    from services.health_monitor import ...      # CORRECT
"""

import re
from pathlib import Path


def fix_test_imports(file_path: Path) -> bool:
    """Fix 'from src.' imports in test files to remove src prefix."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Pattern: from src.MODULE import ...
        # Replace with: from MODULE import ...
        pattern = r"^from src\."
        replacement = "from "

        # Fix all imports
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix all test imports."""
    script_dir = Path(__file__).parent
    tests_dir = script_dir / "tests"

    if not tests_dir.exists():
        print(f"Error: {tests_dir} does not exist")
        return 1

    fixed_count = 0
    error_count = 0

    for py_file in tests_dir.rglob("*.py"):
        # Skip __pycache__
        if "__pycache__" in str(py_file):
            continue

        # Check if file has 'from src.' imports
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                if "from src." in f.read():
                    if fix_test_imports(py_file):
                        print(f"✓ Fixed: {py_file.relative_to(script_dir)}")
                        fixed_count += 1
        except Exception as e:
            print(f"✗ Error reading {py_file}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Test import fix complete!")
    print(f"Files fixed: {fixed_count}")
    print(f"Errors: {error_count}")
    print(f"{'='*60}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
