#!/usr/bin/env python3
"""Pre-commit hook to validate Memgraph label usage.

This script detects raw label strings in Cypher queries (e.g., :FILE, :PROJECT)
and enforces the use of MemgraphLabels enum constants instead.

Usage:
    python3 scripts/validate_memgraph_labels.py <file1> <file2> ...

Exit codes:
    0 - No violations found
    1 - Violations found
"""

import re
import sys
from pathlib import Path
from typing import List


def check_file(file_path: Path) -> List[str]:
    """Check file for raw label strings in Cypher queries.

    Args:
        file_path: Path to Python file to check

    Returns:
        List of violation messages
    """
    violations = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return violations

    # Pattern matches :LABEL (uppercase first letter, followed by alphanumeric)
    # Lookahead ensures it's followed by whitespace, {, ', ", or )
    pattern = r':([A-Z][A-Za-z_]+)(?=\s|\{|\'|"|\)|,|])'

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip lines that already use constants
        if "MemgraphLabels" in line or "LABEL_" in line:
            continue

        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        matches = re.finditer(pattern, line)
        for match in matches:
            label = match.group(1)
            violations.append(
                f"{file_path}:{line_num} - Raw label ':{label}' found. "
                f"Use MemgraphLabels.{label} instead."
            )

    return violations


def main(files: List[str]) -> int:
    """Main entry point.

    Args:
        files: List of file paths to check

    Returns:
        Exit code (0=success, 1=failures)
    """
    if not files:
        print("ℹ️  No files to check")
        return 0

    all_violations = []

    for file_path_str in files:
        path = Path(file_path_str)

        # Only check Python files
        if path.suffix != ".py":
            continue

        # Skip if file doesn't exist
        if not path.exists():
            continue

        violations = check_file(path)
        all_violations.extend(violations)

    if all_violations:
        print("❌ Memgraph label validation FAILED:")
        print()
        for violation in all_violations:
            print(f"  {violation}")
        print()
        print(
            "💡 Use constants from src.constants.MemgraphLabels instead of raw strings."
        )
        print("   Example: MemgraphLabels.FILE instead of :FILE")
        return 1

    print("✅ Memgraph label validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
