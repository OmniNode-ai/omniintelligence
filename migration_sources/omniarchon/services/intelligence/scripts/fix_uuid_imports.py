#!/usr/bin/env python3
"""Fix misplaced UUID imports in Python files."""

import re
from pathlib import Path


def fix_uuid_import(file_path: Path) -> bool:
    """Fix misplaced UUID import in a file."""
    try:
        content = file_path.read_text()
        original = content

        # Pattern 1: UUID import inside another import block
        # Look for: "from X import (\n    <stuff>\nfrom uuid import UUID, uuid4\n    <stuff>\n)"
        pattern1 = (
            r"(from .+ import \(([^)]*)\nfrom uuid import UUID, uuid4\n([^)]*)\))"
        )

        def fix_pattern1(match):
            full_match = match.group(0)
            before = match.group(2)
            after = match.group(3)

            # Extract the original import statement
            import_line = full_match.split("(")[0] + "("

            # Reconstruct without UUID import
            fixed_import = f"{import_line}{before}\n{after})"
            return fixed_import

        # First, extract the uuid import line before removing it
        uuid_import_found = "from uuid import UUID, uuid4" in content

        # Remove misplaced UUID imports (inside other import blocks)
        content = re.sub(
            r"([^\n]*from .+ import \([^)]*)\nfrom uuid import UUID, uuid4\n",
            r"\1\n",
            content,
            flags=re.MULTILINE,
        )

        # If UUID import was found and removed, add it at the top after other imports
        if uuid_import_found and "from uuid import UUID, uuid4" not in content:
            # Find the last standard library or typing import
            lines = content.split("\n")
            last_import_idx = 0

            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    # Skip if it's a local import (starts with .)
                    if not line.startswith("from ."):
                        last_import_idx = i

            # Insert UUID import after last non-local import
            if last_import_idx > 0:
                lines.insert(last_import_idx + 1, "from uuid import UUID, uuid4")
                content = "\n".join(lines)

        if content != original:
            file_path.write_text(content)
            return True

        return False

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix all files with misplaced UUID imports."""
    from pathlib import Path

    problem_files = []

    # Find all Python files with misplaced UUID imports
    for py_file in Path("src").rglob("*.py"):
        try:
            content = py_file.read_text()
            # Check for misplaced UUID import
            if re.search(
                r"from .+ import \([^)]*\nfrom uuid import",
                content,
                re.MULTILINE | re.DOTALL,
            ):
                problem_files.append(py_file)
        except:
            pass

    print(f"Found {len(problem_files)} files with misplaced UUID imports")

    fixed_count = 0
    for file_path in problem_files:
        if fix_uuid_import(file_path):
            fixed_count += 1
            print(f"✅ Fixed: {file_path}")
        else:
            print(f"⚠️  Could not fix: {file_path}")

    print(f"\n📊 Fixed {fixed_count}/{len(problem_files)} files")


if __name__ == "__main__":
    main()
