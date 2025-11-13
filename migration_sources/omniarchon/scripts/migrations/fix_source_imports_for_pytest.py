#!/usr/bin/env python3
"""
Fix source imports to work with pytest.ini pythonpath=src configuration.

Since pytest.ini has 'pythonpath = src', source code should use absolute imports
from the src root WITHOUT 'src.' prefix and WITHOUT relative imports:

WRONG (relative):  from ..events.hybrid_event_router import ...
WRONG (absolute):  from src.events.hybrid_event_router import ...
CORRECT:           from events.hybrid_event_router import ...

This allows both runtime (FastAPI) and pytest to import correctly.
"""

import re
from pathlib import Path


def convert_relative_to_absolute(file_path: Path, src_root: Path) -> bool:
    """Convert relative imports to absolute imports based on src root."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Get the current file's directory relative to src root
        rel_path = file_path.relative_to(src_root)
        current_dir = rel_path.parent

        # Pattern to match relative imports: from ..MODULE or from .MODULE
        # We need to convert these to absolute imports from src root

        # Match patterns like: from ..events.module import ...
        # or: from ...services.module import ...
        pattern = r"^from (\.+)([a-zA-Z_][a-zA-Z0-9_\.]*) import"

        def replace_relative_import(match):
            dots = match.group(1)  # The dots (. or .. or ...)
            module_path = match.group(2)  # The module path after dots

            # Calculate the absolute path from src root
            # Each dot represents going up one directory
            num_dots = len(dots)

            if num_dots == 1:
                # Single dot means current directory
                if current_dir == Path("."):
                    # File is directly in src/
                    absolute_module = module_path
                else:
                    absolute_module = (
                        f"{current_dir.as_posix().replace('/', '.')}.{module_path}"
                    )
            else:
                # Multiple dots mean go up (num_dots - 1) levels
                levels_up = num_dots - 1
                target_dir = current_dir

                for _ in range(levels_up):
                    target_dir = target_dir.parent

                if target_dir == Path("."):
                    # Reached src root
                    absolute_module = module_path
                else:
                    absolute_module = (
                        f"{target_dir.as_posix().replace('/', '.')}.{module_path}"
                    )

            return f"from {absolute_module} import"

        # Apply the replacement
        content = re.sub(pattern, replace_relative_import, content, flags=re.MULTILINE)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix all source imports."""
    script_dir = Path(__file__).parent
    # Navigate from scripts/migrations/ up to repository root, then to python/src/
    src_root = script_dir.parent.parent / "python" / "src"

    if not src_root.exists():
        print(f"Error: {src_root} does not exist")
        return 1

    fixed_count = 0
    error_count = 0

    for py_file in src_root.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        # Check if file has relative imports
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Look for patterns like "from .." or "from ."
                if re.search(r"^from \.+[a-zA-Z_]", content, re.MULTILINE):
                    if convert_relative_to_absolute(py_file, src_root):
                        print(f"✓ Fixed: {py_file.relative_to(src_root)}")
                        fixed_count += 1
        except Exception as e:
            print(f"✗ Error reading {py_file}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Source import fix complete!")
    print(f"Files fixed: {fixed_count}")
    print(f"Errors: {error_count}")
    print(f"{'='*60}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
