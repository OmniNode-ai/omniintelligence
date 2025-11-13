#!/usr/bin/env python3
"""
Update internal references to renamed markdown files.
Searches for references in all markdown files and updates them.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def get_renamed_files() -> List[Tuple[str, str, str, str]]:
    """
    Get list of renamed files from git status.
    Returns: [(old_path, new_path, old_basename, new_basename), ...]
    """
    result = subprocess.run(
        ["git", "status", "--short"], capture_output=True, text=True, check=True
    )

    renames = []
    for line in result.stdout.split("\n"):
        if line.startswith("R "):
            # Format: "R  old_path -> new_path"
            parts = line[3:].split(" -> ")
            if len(parts) == 2:
                old_path = parts[0].strip()
                new_path = parts[1].strip()
                old_basename = os.path.basename(old_path)
                new_basename = os.path.basename(new_path)
                renames.append((old_path, new_path, old_basename, new_basename))

    return renames


def find_references(root_dir: str, old_basename: str) -> List[Tuple[str, List[int]]]:
    """
    Find all references to old_basename in markdown files.
    Returns: [(filepath, [line_numbers]), ...]
    """
    # Use ripgrep for fast searching
    try:
        result = subprocess.run(
            [
                "rg",
                "--type",
                "md",
                "--line-number",
                "--fixed-strings",
                old_basename,
                root_dir,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 1:  # No matches
            return []

        references = {}
        for line in result.stdout.split("\n"):
            if ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    filepath = parts[0]
                    line_num = int(parts[1])
                    if filepath not in references:
                        references[filepath] = []
                    references[filepath].append(line_num)

        return [(fp, nums) for fp, nums in references.items()]

    except FileNotFoundError:
        # Fallback to grep if rg not available
        result = subprocess.run(
            ["grep", "-rn", "--include=*.md", old_basename, root_dir],
            capture_output=True,
            text=True,
        )

        if result.returncode == 1:  # No matches
            return []

        references = {}
        for line in result.stdout.split("\n"):
            if ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    filepath = parts[0]
                    line_num = int(parts[1])
                    if filepath not in references:
                        references[filepath] = []
                    references[filepath].append(line_num)

        return [(fp, nums) for fp, nums in references.items()]


def update_file_references(filepath: str, old_basename: str, new_basename: str) -> int:
    """
    Update all references in a file from old_basename to new_basename.
    Returns: number of replacements made
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Count occurrences before replacement
        count = content.count(old_basename)

        if count == 0:
            return 0

        # Replace all occurrences
        updated_content = content.replace(old_basename, new_basename)

        # Write back
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated_content)

        return count

    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return 0


def main():
    root_dir = "/Volumes/PRO-G40/Code/omniarchon"

    print("=== Updating Internal References to Renamed Files ===\n")

    renames = get_renamed_files()
    print(f"Found {len(renames)} renamed files\n")

    total_files_updated = 0
    total_replacements = 0

    for old_path, new_path, old_basename, new_basename in renames:
        if old_basename == new_basename:
            continue  # Skip if basename didn't change

        print(f"Checking references: {old_basename} -> {new_basename}")

        # Find all references to old basename
        references = find_references(root_dir, old_basename)

        if not references:
            print(f"  No references found")
            continue

        print(f"  Found references in {len(references)} file(s)")

        for ref_file, line_nums in references:
            # Skip the file itself (it was already renamed)
            if ref_file == old_path or ref_file == new_path:
                continue

            replacements = update_file_references(ref_file, old_basename, new_basename)
            if replacements > 0:
                print(f"    ✓ Updated {replacements} reference(s) in {ref_file}")
                total_files_updated += 1
                total_replacements += replacements

        print()

    print("=== Summary ===")
    print(f"Files with updated references: {total_files_updated}")
    print(f"Total replacements made: {total_replacements}")


if __name__ == "__main__":
    main()
