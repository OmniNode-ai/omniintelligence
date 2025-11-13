#!/usr/bin/env python3
"""
Fix 'from src.' imports to relative imports in Intelligence service.

This script converts absolute imports like:
    from src.events.hybrid_event_router import HybridEventRouter
To relative imports like:
    from ..events.hybrid_event_router import HybridEventRouter

Based on file location within src/ directory.
"""

import os
import re
from pathlib import Path


def get_relative_import_prefix(file_path: Path, src_root: Path) -> str:
    """Calculate relative import prefix based on file depth from src root."""
    # Get relative path from src root
    rel_path = file_path.relative_to(src_root)

    # Count directory depth (excluding the file itself)
    depth = len(rel_path.parent.parts)

    # For depth 0 (files directly in src/), use single dot
    # For depth 1 (src/handlers/), use double dot
    # For depth 2 (src/services/pattern_learning/), use triple dot, etc.
    if depth == 0:
        return "."
    else:
        return "." * (depth + 1)


def fix_imports_in_file(file_path: Path, src_root: Path) -> bool:
    """Fix all 'from src.' imports in a single file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Get the correct relative import prefix for this file
        prefix = get_relative_import_prefix(file_path, src_root)

        # Pattern: from src.MODULE.SUBMODULE import ...
        # Replace with: from ..MODULE.SUBMODULE import ...
        pattern = r"^from src\."
        replacement = f"from {prefix}"

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
    """Fix all imports in Intelligence service."""
    # Get the src directory
    script_dir = Path(__file__).parent
    src_root = script_dir / "src"

    if not src_root.exists():
        print(f"Error: {src_root} does not exist")
        return 1

    # Find all Python files with 'from src.' imports
    fixed_count = 0
    error_count = 0

    for py_file in src_root.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        # Check if file has 'from src.' imports
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                if "from src." in f.read():
                    if fix_imports_in_file(py_file, src_root):
                        print(f"✓ Fixed: {py_file.relative_to(script_dir)}")
                        fixed_count += 1
        except Exception as e:
            print(f"✗ Error reading {py_file}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Import fix complete!")
    print(f"Files fixed: {fixed_count}")
    print(f"Errors: {error_count}")
    print(f"{'='*60}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
