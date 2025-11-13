#!/usr/bin/env python3
"""
Remove 'src.' prefix from imports.
Since pytest.ini sets pythonpath=src, all imports should be without 'src.' prefix.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


def fix_imports_in_file(filepath: Path) -> Tuple[bool, int]:
    """
    Remove src. prefix from imports.

    Returns:
        (changed, num_fixes) - Whether file was changed and number of fixes
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        num_fixes = 0

        # Fix 'from src.services.' imports
        new_content, n = re.subn(
            r"^from src\.services\.", "from services.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.models.' imports
        new_content, n = re.subn(
            r"^from src\.models\.", "from models.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.api.' imports
        new_content, n = re.subn(
            r"^from src\.api\.", "from api.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.handlers.' imports
        new_content, n = re.subn(
            r"^from src\.handlers\.", "from handlers.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.effects.' imports
        new_content, n = re.subn(
            r"^from src\.effects\.", "from effects.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.events.' imports
        new_content, n = re.subn(
            r"^from src\.events\.", "from events.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.config.' imports
        new_content, n = re.subn(
            r"^from src\.config\.", "from config.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.integrations.' imports
        new_content, n = re.subn(
            r"^from src\.integrations\.",
            "from integrations.",
            content,
            flags=re.MULTILINE,
        )
        content = new_content
        num_fixes += n

        # Fix 'from src.pattern_ingestion.' imports
        new_content, n = re.subn(
            r"^from src\.pattern_ingestion\.",
            "from pattern_ingestion.",
            content,
            flags=re.MULTILINE,
        )
        content = new_content
        num_fixes += n

        # Fix 'import src.services.' imports
        new_content, n = re.subn(
            r"^import src\.services\.", "import services.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        # Fix 'import src.models.' imports
        new_content, n = re.subn(
            r"^import src\.models\.", "import models.", content, flags=re.MULTILINE
        )
        content = new_content
        num_fixes += n

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True, num_fixes

        return False, 0

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False, 0


def find_files_to_fix(base_path: Path) -> List[Path]:
    """Find all Python files that need import fixes."""
    files = []

    # Search in src/ directory
    src_path = base_path / "src"
    if src_path.exists():
        files.extend(src_path.rglob("*.py"))

    # Search in tests/ directory
    tests_path = base_path / "tests"
    if tests_path.exists():
        files.extend(tests_path.rglob("*.py"))

    return files


def main():
    base_path = Path(__file__).parent
    print(f"Removing src. prefix from imports in: {base_path}")

    files_to_check = find_files_to_fix(base_path)
    print(f"Found {len(files_to_check)} Python files to check")

    total_changed = 0
    total_fixes = 0

    for filepath in files_to_check:
        changed, num_fixes = fix_imports_in_file(filepath)
        if changed:
            total_changed += 1
            total_fixes += num_fixes
            print(f"✓ Fixed {num_fixes} imports in: {filepath.relative_to(base_path)}")

    print(f"\n{'='*80}")
    print(f"Summary:")
    print(f"  Files changed: {total_changed}")
    print(f"  Total fixes: {total_fixes}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
