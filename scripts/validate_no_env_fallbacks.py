#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Validate that no localhost/private-IP default fallbacks exist in production code.

Scans src/ and scripts/ for patterns like:
  - os.environ.get("...", "localhost...")
  - os.environ.get("...", "http://192.168.x.x:...")
  - os.getenv("...", "http://192.168.x.x:...")
  - default="http://localhost:..."
  - = "localhost:..."  (as a default value in function signatures or assignments)

Exits 0 if clean, 1 if violations found.

Allowlist:
  - Test files (node_tests/, tests/)
  - Docstrings and comments
  - YAML/JSON examples that use ${...} interpolation syntax
  - verify_pattern_lifecycle_e2e.py (conditional checks and user messages)
  - backfill_episodes.py docstring (usage examples with --database-url arg)
  - embedding_client_local_openai.py (docstring examples only)
  - adapter_bolt.py (docstring examples only)

Tickets: OMN-7227, OMN-10736
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = [
    REPO_ROOT / "src",
    REPO_ROOT / "scripts",
]

# Files where localhost/private-IP references are acceptable
ALLOWLISTED_FILES = {
    "embedding_client_local_openai.py",
    "adapter_bolt.py",
    "verify_pattern_lifecycle_e2e.py",
    "backfill_episodes.py",
    "validate_no_env_fallbacks.py",
}

# Patterns that indicate a hardcoded fallback in production code
VIOLATION_PATTERNS = [
    # os.environ.get("...", "localhost...")
    re.compile(r'os\.environ\.get\([^)]*["\']localhost'),
    # os.environ.get("...", "http://192.168.x.x:...")
    re.compile(r'os\.environ\.get\([^)]*["\']http://192\.168\.'),
    # os.getenv("...", "http://192.168.x.x:...")
    re.compile(r'os\.getenv\([^)]*,\s*["\']http://192\.168\.'),
    # os.getenv("...", "localhost...")
    re.compile(r'os\.getenv\([^)]*,\s*["\']localhost'),
    # default="...localhost..."
    re.compile(r'default\s*=\s*["\'][^"\']*localhost'),
    # Function param defaults: = "localhost:..."
    re.compile(r':\s*str\s*=\s*["\']localhost'),
    re.compile(r':\s*str\s*=\s*["\']http://localhost'),
    re.compile(r':\s*str\s*=\s*["\']bolt://localhost'),
]


def _is_test_file(path: Path) -> bool:
    parts = path.parts
    return "node_tests" in parts or "tests" in parts


def _is_comment_or_docstring_line(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or stripped.startswith('"""')
        or stripped.startswith("'''")
    )


def scan() -> list[str]:
    violations: list[str] = []

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in sorted(scan_dir.rglob("*.py")):
            if _is_test_file(path):
                continue
            if path.name in ALLOWLISTED_FILES:
                continue

            try:
                content = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for i, line in enumerate(content.splitlines(), start=1):
                if _is_comment_or_docstring_line(line):
                    continue
                for pattern in VIOLATION_PATTERNS:
                    if pattern.search(line):
                        rel = path.relative_to(REPO_ROOT)
                        violations.append(f"{rel}:{i}: {line.strip()}")

    return violations


def main() -> None:
    violations = scan()
    if violations:
        print(f"FAIL: {len(violations)} hardcoded fallback(s) found:\n")  # noqa: T201
        for v in violations:
            print(f"  {v}")  # noqa: T201
        sys.exit(1)
    else:
        print("OK: No hardcoded fallbacks found in production code.")  # noqa: T201
        sys.exit(0)


if __name__ == "__main__":
    main()
