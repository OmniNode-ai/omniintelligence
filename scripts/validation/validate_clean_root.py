#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Root directory cleanliness validation for omniintelligence.

Validates that the project root directory contains ONLY allowed files
and directories. Enforces a clean, organized repository structure.

Ported from omnibase_infra with omniintelligence-specific allowlists.

Usage:
    python scripts/validation/validate_clean_root.py
    python scripts/validation/validate_clean_root.py --verbose
    python scripts/validation/validate_clean_root.py /path/to/repo

Exit Codes:
    0 - Root directory is clean
    1 - Violations found
    2 - Script error
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# =============================================================================
# Root Directory Allowlist
# =============================================================================

ALLOWED_ROOT_FILES: frozenset[str] = frozenset(
    {
        # Version control
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        # Python packaging
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
        "setup.py",
        "setup.cfg",
        "MANIFEST.in",
        # Type checking
        "mypy.ini",
        ".mypy.ini",
        "pyrightconfig.json",
        "py.typed",
        # Linting/formatting
        ".pre-commit-config.yaml",
        ".yamlfmt",
        ".yamllint.yaml",
        ".ruff.toml",
        ".editorconfig",
        # Markdown link validation
        ".markdown-link-check.json",
        # Standard documentation
        "README.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        # ONEX-specific
        "CLAUDE.md",
        # Environment
        ".env",
        ".env.example",
        ".env.template",
        # Docker
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".dockerignore",
        # Build
        "Makefile",
        "justfile",
        "Taskfile.yml",
        # CI/CD
        "tox.ini",
        "noxfile.py",
        # Security
        ".secretresolver_allowlist",
        ".secrets.baseline",
        # Special files
        ".migration_freeze",
        ".mcp.json",
        ".tool-versions",
        ".python-version",
        # ONEX cross-repo policy
        ".cross-repo-policy.yaml",
    }
)

ALLOWED_ROOT_DIRECTORIES: frozenset[str] = frozenset(
    {
        # Required directories
        "src",
        "tests",
        "docs",
        "scripts",
        # Common optional directories
        "deployment",
        "contracts",
        "docker",
        "examples",
        "benchmarks",
        "tools",
        "bin",
        # Hidden directories
        ".git",
        ".github",
        ".gitlab",
        ".vscode",
        ".idea",
        ".claude",
        # Cache directories (should be gitignored)
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".tox",
        ".nox",
        "__pycache__",
        # Virtual environments (should be gitignored)
        ".venv",
        "venv",
        # Build directories (should be gitignored)
        "build",
        "dist",
        "tmp",
        "htmlcov",
        "coverage",
        ".coverage",
    }
)

ALLOWED_ROOT_PATTERNS: tuple[str, ...] = (
    ".env.*",
    "*.egg-info",
)


@dataclass
class RootViolation:
    """A root directory violation."""

    path: Path
    suggestion: str
    is_directory: bool = False

    def __str__(self) -> str:
        item_type = "Directory" if self.is_directory else "File"
        return f"  {item_type}: {self.path.name}\n    -> {self.suggestion}"


@dataclass
class ValidationResult:
    """Result of root directory validation."""

    violations: list[RootViolation] = field(default_factory=list)
    checked_items: int = 0

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0

    def __bool__(self) -> bool:
        return self.is_valid


def _matches_pattern(name: str, patterns: tuple[str, ...]) -> bool:
    """Check if a name matches any glob patterns."""
    import fnmatch

    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _suggest_action(item: Path) -> str:
    """Generate a suggestion for a misplaced item."""
    name = item.name.lower()

    if item.suffix.lower() == ".md":
        if any(
            keyword in name
            for keyword in [
                "plan",
                "execution",
                "summary",
                "enhancement",
                "fix",
                "audit",
                "wiring",
                "error",
                "migration",
                "design",
                "architecture",
                "mvp",
                "todo",
                "notes",
                "inventory",
                "reference",
                "review",
                "status",
            ]
        ):
            return "Move to docs/ or delete if no longer relevant"
        return "Move to docs/ or rename to follow standard conventions"

    if any(
        keyword in name
        for keyword in ["coverage", "report", "audit", "log", ".tmp", ".bak"]
    ):
        return "Delete (build/test artifact) or add to .gitignore"

    if item.is_file():
        return "Move to appropriate directory (src/, docs/, scripts/) or delete"

    return "Move contents to appropriate location or add to ALLOWED_ROOT_DIRECTORIES"


def validate_root_directory(
    repo_path: Path,
    verbose: bool = False,
) -> ValidationResult:
    """Validate that the project root contains only allowed files and directories."""
    result = ValidationResult()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

    for item in sorted(repo_path.iterdir()):
        result.checked_items += 1
        name = item.name

        if name.startswith(".") and (
            name in ALLOWED_ROOT_FILES or name in ALLOWED_ROOT_DIRECTORIES
        ):
            if verbose:
                print(f"  OK {name} (allowed)")
            continue

        if item.is_file():
            if name in ALLOWED_ROOT_FILES:
                if verbose:
                    print(f"  OK {name} (allowed file)")
                continue
            if _matches_pattern(name, ALLOWED_ROOT_PATTERNS):
                if verbose:
                    print(f"  OK {name} (matches allowed pattern)")
                continue

        if item.is_dir():
            if name in ALLOWED_ROOT_DIRECTORIES:
                if verbose:
                    print(f"  OK {name}/ (allowed directory)")
                continue

        result.violations.append(
            RootViolation(
                path=item,
                suggestion=_suggest_action(item),
                is_directory=item.is_dir(),
            )
        )

    return result


def generate_report(result: ValidationResult, repo_path: Path) -> str:
    """Generate a validation report."""
    if result.is_valid:
        return f"Clean Root: PASS ({result.checked_items} items checked)"

    report_lines = [
        "ROOT DIRECTORY VALIDATION FAILED",
        "=" * 60,
        "",
        f"Found {len(result.violations)} item(s) that should not be in the project root:",
        "",
    ]

    for violation in result.violations:
        report_lines.append(str(violation))
        report_lines.append("")

    report_lines.extend(
        [
            "=" * 60,
            "WHY THIS MATTERS:",
            "  The root directory is the repository's 'front door'.",
            "  It should contain ONLY essential configuration and documentation.",
            "  Working documents belong in docs/.",
            "",
            "HOW TO FIX:",
            "  1. Move documentation to docs/",
            "  2. Delete obsolete files",
            "  3. Add build artifacts to .gitignore",
            "",
            "To add a new allowed file/directory, edit:",
            f"  {repo_path / 'scripts/validation/validate_clean_root.py'}",
            "",
        ]
    )

    return "\n".join(report_lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate that project root contains only allowed files/directories"
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=None,
        help="Path to repository root (default: auto-detect)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all checked items",
    )

    args = parser.parse_args()

    if args.repo_path:
        repo_path = Path(args.repo_path).resolve()
    else:
        script_path = Path(__file__).resolve()
        repo_path = script_path.parent.parent.parent

    try:
        if args.verbose:
            print(f"Validating root directory: {repo_path}\n")

        result = validate_root_directory(repo_path, verbose=args.verbose)
        report = generate_report(result, repo_path)
        print(report)

        return 0 if result.is_valid else 1

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
