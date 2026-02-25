#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unified validation script for omniintelligence.

This script runs the ONEX validation suite from omnibase_core plus
our custom contract linter to ensure code quality standards.

Usage:
    uv run python scripts/validate.py
    uv run python scripts/validate.py --strict
    uv run python scripts/validate.py --verbose
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# Project root detection - works from any directory
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src" / "omniintelligence"
TOOLS_DIR = SRC_DIR / "tools"

# Standalone omnibase_core ValidatorBase validators.
# Maps CLI name -> (module, display_name) for validators invoked via
# ``python -m omnibase_core.validation.{module} {directory}``.
STANDALONE_VALIDATORS: dict[str, tuple[str, str]] = {
    "any-type": ("validator_any_type", "any-type"),
    "pydantic": ("validator_pydantic_conventions", "pydantic"),
    "naming-convention": ("validator_naming_convention", "naming-convention"),
    "enum-governance": ("checker_enum_governance", "enum-governance"),
    "enum-casing": ("checker_enum_member_casing", "enum-casing"),
    "literal-duplication": (
        "checker_literal_duplication",
        "literal-duplication",
    ),
}


def find_nodes_directories() -> list[Path]:
    """Find all nodes directories in the project.

    Returns directories named 'nodes' under src/omniintelligence/,
    including legacy locations like _legacy/nodes/.
    """
    nodes_dirs = []
    for path in SRC_DIR.rglob("nodes"):
        if path.is_dir():
            nodes_dirs.append(path)
    return nodes_dirs


@dataclass
class ValidationResult:
    """Result of a single validation run."""

    name: str
    passed: bool
    blocking: bool
    message: str = ""


class ValidatorFn(Protocol):
    """Protocol for validator functions that accept an optional verbose flag."""

    def __call__(self, *, verbose: bool = False) -> ValidationResult: ...


def _parse_violation_count(output: str) -> int | None:
    """Parse violation count from omnibase validator output.

    The CLI emits lines like ``🚨 Violations: 6``. Returns the count,
    or None if the line is not found (so callers can fall back to exit code).
    """
    import re

    match = re.search(r"Violations:\s*(\d+)", output)
    return int(match.group(1)) if match else None


def run_omnibase_validator(
    validator: str,
    directory: Path | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> ValidationResult:
    """Run an omnibase_core CLI-registered validator.

    These are validators registered in ServiceValidationSuite, invoked via
    ``python -m omnibase_core.validation.validator_cli {name}``.

    Pass/fail is determined by parsing the ``🚨 Violations: N`` line from
    the validator output rather than relying solely on exit codes, because
    the upstream CLI has a bug where some validators (e.g. union-usage)
    exit 1 even with 0 violations.

    Args:
        validator: Name of the validator (architecture, union-usage, contracts, patterns)
        directory: Directory to validate (defaults to project SRC_DIR)
        strict: If True, treat as blocking
        verbose: If True, add --verbose flag

    Returns:
        ValidationResult with pass/fail status
    """
    if directory is None:
        directory = SRC_DIR

    cmd = [
        sys.executable,
        "-m",
        "omnibase_core.validation.validator_cli",
        validator,
        str(directory),
        "--exit-zero",
    ]

    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, timeout=300, text=True
        )
        if verbose:
            print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")

        # Parse violation count from output (more reliable than exit code)
        violation_count = _parse_violation_count(result.stdout)
        if violation_count is not None:
            passed = violation_count == 0
            message = "" if passed else f"{violation_count} violation(s)"
        else:
            # Fallback to exit code if output format is unexpected
            passed = result.returncode == 0
            message = "" if passed else f"Exit code: {result.returncode}"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Validator timed out after 300 seconds"
    except FileNotFoundError:
        passed = False
        message = "Validator module not found - check omnibase_core installation"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name=f"omnibase:{validator}",
        passed=passed,
        blocking=strict,
        message=message,
    )


def run_standalone_validator(
    module: str,
    display_name: str,
    directory: Path | None = None,
    verbose: bool = False,
) -> ValidationResult:
    """Run a standalone ValidatorBase subclass from omnibase_core.

    These validators are invoked directly as modules
    (``python -m omnibase_core.validation.{module} {directory}``).
    They do NOT support --exit-zero; exit code 0 = pass, 1 = errors, 2 = warnings.

    Args:
        module: Module name under omnibase_core.validation (e.g. "validator_any_type")
        display_name: Human-readable name for reporting (e.g. "any-type")
        directory: Directory to validate (defaults to project SRC_DIR)
        verbose: If True, add --verbose flag

    Returns:
        ValidationResult with pass/fail status (always non-blocking)
    """
    if directory is None:
        directory = SRC_DIR

    cmd = [
        sys.executable,
        "-m",
        f"omnibase_core.validation.{module}",
        str(directory),
    ]

    if verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=300, text=True
        )
        passed = result.returncode == 0
        if result.returncode == 2:
            message = "Warnings found (no errors)"
        elif not passed:
            message = f"Exit code: {result.returncode}"
        else:
            message = ""
    except subprocess.TimeoutExpired:
        passed = False
        message = "Validator timed out after 300 seconds"
    except FileNotFoundError:
        passed = False
        message = "Validator module not found - check omnibase_core installation"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name=f"omnibase:{display_name}",
        passed=passed,
        blocking=False,
        message=message,
    )


def run_contract_linter(verbose: bool = False) -> ValidationResult:
    """Run our custom contract linter.

    Discovers contract files in all nodes directories (including _legacy/nodes/).
    Matches pattern: {node_dir}/contract.yaml for each node directory.

    Returns:
        ValidationResult with pass/fail status
    """
    start_time = time.monotonic()

    # Find all nodes directories
    nodes_dirs = find_nodes_directories()
    if not nodes_dirs:
        return ValidationResult(
            name="contract_linter",
            passed=False,
            blocking=True,
            message="No nodes directories found in src/omniintelligence/",
        )

    # Collect contract files from all nodes directories
    contract_files: list[Path] = []
    for nodes_dir in nodes_dirs:
        # Pattern: */contract.yaml (matches node_*/contract.yaml layout)
        for contract_path in nodes_dir.glob("*/contract.yaml"):
            contract_files.append(contract_path)

    # Sort for consistent ordering
    contract_files = sorted(set(contract_files))

    if not contract_files:
        return ValidationResult(
            name="contract_linter",
            passed=False,
            blocking=True,
            message=f"No contract files found in {len(nodes_dirs)} nodes director(y/ies)",
        )

    cmd = [
        sys.executable,
        "-m",
        "omniintelligence.tools.contract_linter",
        *[str(f) for f in contract_files],
    ]

    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=300
        )
        elapsed = time.monotonic() - start_time
        passed = result.returncode == 0
        message = (
            f"Validated {len(contract_files)} contracts in {elapsed:.2f}s"
            if passed
            else f"Contract validation failed (exit code: {result.returncode})"
        )
    except subprocess.TimeoutExpired:
        passed = False
        message = "Contract linter timed out after 300 seconds"
    except FileNotFoundError:
        passed = False
        message = (
            "Contract linter module not found - check omniintelligence installation"
        )
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name="contract_linter",
        passed=passed,
        blocking=True,
        message=message,
    )


def run_mypy(verbose: bool = False) -> ValidationResult:
    """Run mypy type checking on the tools module.

    Returns:
        ValidationResult with pass/fail status
    """
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        str(TOOLS_DIR),
        "--strict",
    ]

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=300
        )
        passed = result.returncode == 0
        message = "" if passed else "Type errors found"
    except subprocess.TimeoutExpired:
        passed = False
        message = "MyPy timed out after 300 seconds"
    except FileNotFoundError:
        passed = False
        message = "MyPy not found - check installation (uv sync --group dev)"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name="mypy:tools",
        passed=passed,
        blocking=True,
        message=message,
    )


def run_ruff(verbose: bool = False) -> ValidationResult:
    """Run ruff linting on new code only.

    Returns:
        ValidationResult with pass/fail status
    """
    # Only check new code (tools), nodes are legacy and will be refactored
    paths_to_check = [
        str(TOOLS_DIR),
    ]

    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        *paths_to_check,
    ]

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=300
        )
        passed = result.returncode == 0
        message = "" if passed else "Linting errors found"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Ruff linter timed out after 300 seconds"
    except FileNotFoundError:
        passed = False
        message = "Ruff not found - check installation (uv sync --group dev)"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name="ruff",
        passed=passed,
        blocking=True,
        message=message,
    )


def run_clean_root(verbose: bool = False) -> ValidationResult:
    """Run root directory cleanliness validation."""
    validator_path = SCRIPT_DIR / "validation" / "validate_clean_root.py"

    if not validator_path.exists():
        return ValidationResult(
            name="clean_root",
            passed=False,
            blocking=True,
            message=f"Validator script missing: {validator_path}",
        )

    cmd = [sys.executable, str(validator_path), str(PROJECT_ROOT)]
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=60
        )
        passed = result.returncode == 0
        message = "" if passed else "Root directory has disallowed files"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Validator timed out"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name="clean_root",
        passed=passed,
        blocking=True,
        message=message,
    )


def run_naming(verbose: bool = False) -> ValidationResult:
    """Run naming convention validation."""
    validator_path = SCRIPT_DIR / "validation" / "validate_naming.py"

    if not validator_path.exists():
        return ValidationResult(
            name="naming",
            passed=False,
            blocking=True,
            message=f"Validator script missing: {validator_path}",
        )

    cmd = [sys.executable, str(validator_path), str(SRC_DIR)]
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=not verbose, timeout=60
        )
        passed = result.returncode == 0
        message = "" if passed else "Naming convention violations found"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Validator timed out"
    except subprocess.SubprocessError as e:
        passed = False
        message = f"Subprocess error: {e}"

    return ValidationResult(
        name="naming",
        passed=passed,
        blocking=False,  # Non-blocking until existing violations are fixed
        message=message,
    )


def main() -> int:
    """Run the validation suite.

    Returns:
        Exit code (0 for success, 1 for blocking failures)
    """
    parser = argparse.ArgumentParser(
        description="Run ONEX validation suite for omniintelligence"
    )
    parser.add_argument(
        "validator",
        nargs="?",
        default="all",
        choices=[
            "all",
            "clean_root",
            "naming",
            "ruff",
            "mypy",
            "contracts",
            "any-type",
            "pydantic",
            "naming-convention",
            "enum-governance",
            "enum-casing",
            "literal-duplication",
        ],
        help="Which validator to run (default: all)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat all validators as blocking",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Run only fast validators",
    )

    args = parser.parse_args()

    # Single validator mode
    if args.validator != "all":
        # Direct function validators
        validator_map: dict[str, ValidatorFn] = {
            "clean_root": run_clean_root,
            "naming": run_naming,
            "ruff": run_ruff,
            "mypy": run_mypy,
            "contracts": run_contract_linter,
        }

        if args.validator in validator_map:
            result = validator_map[args.validator](verbose=args.verbose)
        elif args.validator in STANDALONE_VALIDATORS:
            module, display = STANDALONE_VALIDATORS[args.validator]
            result = run_standalone_validator(module, display, verbose=args.verbose)
        else:
            print(f"Unknown validator: {args.validator}")
            return 1

        status = "PASS" if result.passed else "FAIL"
        msg = f" - {result.message}" if result.message else ""
        print(f"{result.name}: {status}{msg}")
        return 0 if result.passed else 1

    print("=" * 60)
    print("ONEX Validation Suite for OmniIntelligence")
    print("=" * 60)

    results: list[ValidationResult] = []

    # Blocking validators (must pass)
    print("\n[Phase 1] Blocking Validators")
    print("-" * 40)

    # Root directory cleanliness
    print("  Running clean_root...")
    results.append(run_clean_root(verbose=args.verbose))

    # Ruff linting
    print("  Running ruff...")
    results.append(run_ruff(verbose=args.verbose))

    # MyPy on tools module
    print("  Running mypy on tools...")
    results.append(run_mypy(verbose=args.verbose))

    # omnibase validators that pass
    for validator in ["union-usage", "patterns", "architecture"]:
        print(f"  Running omnibase:{validator}...")
        results.append(
            run_omnibase_validator(validator, strict=True, verbose=args.verbose)
        )

    # Our contract linter
    print("  Running contract linter...")
    results.append(run_contract_linter(verbose=args.verbose))

    # Non-blocking validators (report only)
    if not args.quick:
        print("\n[Phase 2] Non-Blocking Validators (informational)")
        print("-" * 40)

        # Naming conventions (custom)
        print("  Running naming conventions...")
        result = run_naming(verbose=args.verbose)
        result.blocking = args.strict
        results.append(result)

        # CLI-registered omnibase validators (non-blocking)
        for validator in ["contracts"]:
            print(f"  Running omnibase:{validator}...")
            result = run_omnibase_validator(
                validator, strict=args.strict, verbose=args.verbose
            )
            result.blocking = args.strict
            results.append(result)

        # Standalone omnibase_core ValidatorBase validators (non-blocking)
        for module, display_name in STANDALONE_VALIDATORS.values():
            print(f"  Running omnibase:{display_name}...")
            result = run_standalone_validator(
                module, display_name, verbose=args.verbose
            )
            result.blocking = args.strict
            results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    blocking_failures = []
    for r in results:
        if r.passed:
            status = "PASSED"
        elif r.blocking:
            status = "FAILED (blocking)"
            blocking_failures.append(r.name)
        else:
            status = "FAILED (non-blocking)"

        msg = f" - {r.message}" if r.message else ""
        print(f"  {r.name}: {status}{msg}")

    print()
    if blocking_failures:
        print(
            f"{len(blocking_failures)} blocking failure(s): {', '.join(blocking_failures)}"
        )
        return 1
    else:
        print("All blocking validators passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
