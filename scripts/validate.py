#!/usr/bin/env python3
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
from dataclasses import dataclass
from pathlib import Path

# Project root detection
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src" / "omniintelligence"
TOOLS_DIR = SRC_DIR / "tools"
NODES_DIR = SRC_DIR / "nodes"


@dataclass
class ValidationResult:
    """Result of a single validation run."""

    name: str
    passed: bool
    blocking: bool
    message: str = ""


def run_omnibase_validator(
    validator: str,
    directory: Path | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> ValidationResult:
    """Run an omnibase_core validator.

    Args:
        validator: Name of the validator (architecture, union-usage, contracts, patterns)
        directory: Directory to validate (defaults to project SRC_DIR)
        strict: If True, don't use --exit-zero
        verbose: If True, add --verbose flag

    Returns:
        ValidationResult with pass/fail status
    """
    if directory is None:
        directory = SRC_DIR

    cmd = [
        sys.executable,
        "-m",
        "omnibase_core.validation.cli",
        validator,
        str(directory),
    ]

    if not strict:
        cmd.append("--exit-zero")
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(cmd, check=False, capture_output=not verbose, timeout=300)
        passed = result.returncode == 0
        message = "" if passed else f"Exit code: {result.returncode}"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Validator timed out after 300 seconds"

    return ValidationResult(
        name=f"omnibase:{validator}",
        passed=passed,
        blocking=strict,
        message=message,
    )


def run_contract_linter(verbose: bool = False) -> ValidationResult:
    """Run our custom contract linter.

    Returns:
        ValidationResult with pass/fail status
    """
    contract_files = list(NODES_DIR.glob("*/v1_0_0/contracts/*.yaml"))

    if not contract_files:
        return ValidationResult(
            name="contract_linter",
            passed=True,
            blocking=False,
            message="No contract files found",
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
        result = subprocess.run(cmd, check=False, capture_output=not verbose, timeout=300)
        passed = result.returncode == 0
        message = (
            f"All {len(contract_files)} contracts validated successfully"
            if passed
            else f"Contract validation failed (exit code: {result.returncode})"
        )
    except subprocess.TimeoutExpired:
        passed = False
        message = "Contract linter timed out after 300 seconds"

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
        result = subprocess.run(cmd, check=False, capture_output=not verbose, timeout=300)
        passed = result.returncode == 0
        message = "" if passed else "Type errors found"
    except subprocess.TimeoutExpired:
        passed = False
        message = "MyPy timed out after 300 seconds"

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
        result = subprocess.run(cmd, check=False, capture_output=not verbose, timeout=300)
        passed = result.returncode == 0
        message = "" if passed else "Linting errors found"
    except subprocess.TimeoutExpired:
        passed = False
        message = "Ruff linter timed out after 300 seconds"

    return ValidationResult(
        name="ruff",
        passed=passed,
        blocking=True,
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
        help="Run only fast validators (skip architecture)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ONEX Validation Suite for OmniIntelligence")
    print("=" * 60)

    results: list[ValidationResult] = []

    # Blocking validators (must pass)
    print("\n[Phase 1] Blocking Validators")
    print("-" * 40)

    # Ruff linting
    print("▶ Running ruff...")
    results.append(run_ruff(verbose=args.verbose))

    # MyPy on tools module
    print("▶ Running mypy on tools...")
    results.append(run_mypy(verbose=args.verbose))

    # omnibase validators that pass
    for validator in ["union-usage", "patterns"]:
        print(f"▶ Running omnibase:{validator}...")
        results.append(
            run_omnibase_validator(validator, strict=True, verbose=args.verbose)
        )

    # Our contract linter
    print("▶ Running contract linter...")
    results.append(run_contract_linter(verbose=args.verbose))

    # Non-blocking validators (report only)
    if not args.quick:
        print("\n[Phase 2] Non-Blocking Validators (informational)")
        print("-" * 40)

        for validator in ["architecture", "contracts"]:
            print(f"▶ Running omnibase:{validator}...")
            result = run_omnibase_validator(
                validator, strict=args.strict, verbose=args.verbose
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
            status = "✅ PASSED"
        elif r.blocking:
            status = "❌ FAILED (blocking)"
            blocking_failures.append(r.name)
        else:
            status = "⚠️  FAILED (non-blocking)"

        msg = f" - {r.message}" if r.message else ""
        print(f"  {r.name}: {status}{msg}")

    print()
    if blocking_failures:
        print(f"❌ {len(blocking_failures)} blocking failure(s): {', '.join(blocking_failures)}")
        return 1
    else:
        print("✅ All blocking validators passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
