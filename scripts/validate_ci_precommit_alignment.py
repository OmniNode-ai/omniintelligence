#!/usr/bin/env python3
"""Validate alignment between CI path filters and pre-commit hook patterns.

This script ensures that the CI workflow path filters (.github/workflows/ci.yaml)
stay synchronized with pre-commit hook file patterns (.pre-commit-config.yaml).

SYNCHRONIZATION STRATEGY:
-------------------------
The patterns express the same scope in different formats:
- CI uses glob patterns (e.g., 'src/omniintelligence/tools/**')
- Pre-commit uses regex patterns (e.g., '^src/omniintelligence/(tools|utils|runtime)/')

This script extracts the source directories and test paths from both configuration
files and compares them against each other and the canonical expected values
defined in ALIGNED_SOURCE_DIRS and ALIGNED_TEST_PATHS below.

WHAT THIS SCRIPT VALIDATES:
---------------------------
1. CI production_code filter paths match pre-commit hook file patterns
2. Both configurations cover the same source directories
3. Both configurations cover the same test paths
4. Configurations match the canonical expected values
5. Mypy cache hashFiles patterns match mypy command scope

WHAT THIS SCRIPT DOES NOT VALIDATE:
------------------------------------
- Pytest command scope (intentionally narrower than path filter)
- Individual job command paths (validated by running the jobs)

ADDING A NEW MODULE:
--------------------
When adding a new source directory, update ALIGNED_SOURCE_DIRS below,
then run this script. It will report any drift in CI or pre-commit configs.

See .github/workflows/ci.yaml header for complete checklist of files to update.

Usage:
    uv run python scripts/validate_ci_precommit_alignment.py
    uv run python scripts/validate_ci_precommit_alignment.py --verbose
    uv run python scripts/validate_ci_precommit_alignment.py --json

Exit codes:
    0 - Patterns are aligned
    1 - Patterns are misaligned (drift detected)
    2 - File parsing error
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import yaml

# Configure logging for this module
logger = logging.getLogger(__name__)

# Repository root (parent of scripts/)
REPO_ROOT = Path(__file__).parent.parent

# Configuration files to validate
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yaml"
PRECOMMIT_CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

# =============================================================================
# CANONICAL SOURCE OF TRUTH - Update these when adding new modules
# =============================================================================
# These lists define the expected scope for CI and pre-commit configurations.
# When adding a new source directory:
# 1. Add to ALIGNED_SOURCE_DIRS below
# 2. Run this script to detect drift
# 3. Follow the checklist in .github/workflows/ci.yaml header
#
# Note: The mypy cache hashFiles patterns in ci.yaml should also include
# the new module to ensure proper cache invalidation.
# =============================================================================
ALIGNED_SOURCE_DIRS = ["tools", "utils", "runtime"]
ALIGNED_TEST_PATHS = ["tests/unit/tools", "tests/unit/test_log_sanitizer.py"]


@dataclass
class MypyCacheValidation:
    """Result of mypy cache pattern validation."""

    is_aligned: bool = True
    cache_patterns: list[str] = field(default_factory=list)
    command_paths: list[str] = field(default_factory=list)
    missing_in_cache: list[str] = field(default_factory=list)
    extra_in_cache: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of pattern alignment validation."""

    is_aligned: bool
    ci_source_dirs: list[str] = field(default_factory=list)
    ci_test_paths: list[str] = field(default_factory=list)
    precommit_source_dirs: list[str] = field(default_factory=list)
    precommit_test_paths: list[str] = field(default_factory=list)
    missing_in_ci: list[str] = field(default_factory=list)
    missing_in_precommit: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    mypy_cache: MypyCacheValidation = field(default_factory=MypyCacheValidation)


def extract_ci_patterns(ci_config: dict) -> tuple[list[str], list[str]]:
    """Extract source dirs and test paths from CI production_code filter.

    Args:
        ci_config: Parsed CI workflow YAML

    Returns:
        Tuple of (source_dirs, test_paths)
    """
    source_dirs: list[str] = []
    test_paths: list[str] = []

    # Navigate to changes job -> steps -> filter step -> with.filters
    jobs = ci_config.get("jobs", {})
    changes_job = jobs.get("changes", {})
    steps = changes_job.get("steps", [])

    for step in steps:
        if step.get("id") == "filter":
            filters_str = step.get("with", {}).get("filters", "")
            # Parse the YAML-in-string filters
            # Look for production_code patterns
            for raw_line in filters_str.split("\n"):
                stripped_line = raw_line.strip()
                if stripped_line.startswith("- '") and stripped_line.endswith("'"):
                    pattern = stripped_line[3:-1]  # Remove "- '" and "'"
                    # Extract source dirs from src/omniintelligence/<dir>/**
                    src_match = re.match(
                        r"src/omniintelligence/(\w+)/\*\*", pattern
                    )
                    if src_match:
                        source_dirs.append(src_match.group(1))
                    # Extract test paths
                    elif pattern.startswith("tests/"):
                        # Normalize: remove trailing /** for directories
                        normalized = re.sub(r"/\*\*$", "", pattern)
                        test_paths.append(normalized)

    return sorted(set(source_dirs)), sorted(set(test_paths))


def _normalize_quotes(pattern: str) -> str:
    """Normalize quotes in a pattern string.

    Handles both single and double quotes by converting double quotes to single.

    Args:
        pattern: The pattern string that may contain quotes

    Returns:
        Pattern with normalized quotes
    """
    if pattern is None:
        return ""
    # Replace double quotes with single quotes for consistent parsing
    return pattern.replace('"', "'")


def _extract_source_dirs_from_pattern(files_pattern: str) -> list[str]:
    """Extract source directories from a pre-commit files pattern.

    Handles patterns like:
    - ^src/omniintelligence/(tools|utils|runtime)/
    - ^(src/omniintelligence/(tools|utils)/|...)

    Args:
        files_pattern: The regex pattern from pre-commit files: field

    Returns:
        List of extracted source directory names
    """
    source_dirs: list[str] = []

    if not files_pattern:
        return source_dirs

    try:
        # Pattern: src/omniintelligence/(tools|utils|runtime)/
        # This handles the alternation group for source directories
        src_match = re.search(
            r"src/omniintelligence/\(([^)]+)\)/", files_pattern
        )
        if src_match:
            # Split by pipe to get individual directories
            raw_dirs = src_match.group(1).split("|")
            for dir_name in raw_dirs:
                # Validate directory name is alphanumeric with underscores
                cleaned = dir_name.strip()
                if cleaned and re.match(r"^[\w]+$", cleaned):
                    source_dirs.append(cleaned)
                elif cleaned:
                    logger.warning(
                        f"Unexpected source directory format in pattern: '{cleaned}' "
                        f"(from pattern: '{files_pattern[:80]}...')"
                    )
    except re.error as e:
        logger.warning(
            f"Failed to parse source dirs from pre-commit pattern: {e}. "
            f"Pattern: '{files_pattern[:80]}...'"
        )

    return source_dirs


def _extract_test_paths_from_pattern(files_pattern: str) -> list[str]:
    """Extract test paths from a pre-commit files pattern.

    Handles patterns like:
    - tests/unit/(tools/|test_log_sanitizer\\.py)
    - tests/unit/tools/
    - ^(src/.../|tests/unit/tools/.*\\.py|tests/unit/test_log_sanitizer\\.py)$

    Args:
        files_pattern: The regex pattern from pre-commit files: field

    Returns:
        List of extracted test paths
    """
    test_paths: list[str] = []

    if not files_pattern:
        return test_paths

    try:
        # Pattern 1: tests/unit/(tools/|test_log_sanitizer\.py) - nested group
        test_match = re.search(
            r"tests/unit/\(([^)]+)\)", files_pattern
        )
        if test_match:
            parts = test_match.group(1).split("|")
            for part in parts:
                if not part:
                    continue
                try:
                    # Clean up regex escapes and trailing slashes
                    # Handle both \. and literal . for .py extension
                    cleaned = part.replace("\\.py", ".py").rstrip("/")
                    if cleaned:
                        test_paths.append(f"tests/unit/{cleaned}")
                except Exception as e:
                    logger.warning(
                        f"Failed to clean test path part '{part}': {e}"
                    )

        # Pattern 2: tests/unit/tools/.*\.py or tests/unit/test_*.py as top-level alternatives
        # Matches patterns like: tests/unit/tools/.*\.py|tests/unit/test_log_sanitizer\.py
        if not test_paths:
            # Find all tests/unit/... patterns in the alternation
            test_alternatives = re.findall(
                r"tests/unit/([^\|$\)]+)", files_pattern
            )
            for alt in test_alternatives:
                if not alt:
                    continue
                # Clean up: remove regex suffixes like /.*\.py$ and escape sequences
                cleaned = alt
                # Remove trailing regex patterns like /.*\.py or .*\.py
                cleaned = re.sub(r"/?\.\*\\?\.py\$?$", "", cleaned)
                # Handle exact file match patterns
                cleaned = cleaned.replace("\\.py", ".py")
                cleaned = cleaned.rstrip("/")
                if cleaned:
                    test_paths.append(f"tests/unit/{cleaned}")

    except re.error as e:
        logger.warning(
            f"Failed to parse test paths from pre-commit pattern: {e}. "
            f"Pattern: '{files_pattern[:80]}...'"
        )

    return test_paths


def extract_precommit_patterns(precommit_config: dict) -> tuple[list[str], list[str]]:
    """Extract source dirs and test paths from pre-commit ruff hook patterns.

    This function looks for all ruff-related hooks (ruff, ruff-format, ruff-fix, etc.)
    and extracts the file patterns from them.

    This function includes defensive validation for:
    - Missing or malformed files: patterns in hooks
    - Unexpected regex structures that don't match expected format
    - Empty or None pattern values
    - Both single and double quote styles

    Args:
        precommit_config: Parsed pre-commit config YAML

    Returns:
        Tuple of (source_dirs, test_paths)

    Note:
        Warnings are logged for patterns that cannot be parsed.
        The function will not raise exceptions for malformed input.
    """
    source_dirs: list[str] = []
    test_paths: list[str] = []

    # Validate input is a dict
    if not isinstance(precommit_config, dict):
        logger.warning(
            f"Expected dict for precommit_config, got {type(precommit_config).__name__}. "
            "Returning empty patterns."
        )
        return [], []

    repos = precommit_config.get("repos")

    # Validate repos is a list
    if repos is None:
        logger.warning("No 'repos' key found in pre-commit config")
        return [], []

    if not isinstance(repos, list):
        logger.warning(
            f"Expected list for 'repos', got {type(repos).__name__}. "
            "Returning empty patterns."
        )
        return [], []

    for repo_idx, repo in enumerate(repos):
        # Validate repo is a dict
        if not isinstance(repo, dict):
            logger.warning(
                f"Repo at index {repo_idx} is not a dict, skipping"
            )
            continue

        hooks = repo.get("hooks")

        # Validate hooks is a list
        if hooks is None:
            continue  # No hooks in this repo is valid

        if not isinstance(hooks, list):
            logger.warning(
                f"Expected list for 'hooks' in repo at index {repo_idx}, "
                f"got {type(hooks).__name__}. Skipping."
            )
            continue

        for hook_idx, hook in enumerate(hooks):
            # Validate hook is a dict
            if not isinstance(hook, dict):
                logger.warning(
                    f"Hook at index {hook_idx} in repo {repo_idx} is not a dict, skipping"
                )
                continue

            # Check ruff hooks (ruff, ruff-format, ruff-fix, etc.)
            # All ruff-* hooks should have consistent file patterns
            hook_id = hook.get("id")
            if not hook_id or not hook_id.startswith("ruff"):
                continue

            # Get files pattern with defensive handling
            files_pattern = hook.get("files")

            # Handle None or missing files pattern
            if files_pattern is None:
                logger.warning(
                    f"Hook '{hook_id}' at repo index {repo_idx} has no 'files' pattern. "
                    "This hook will match all files."
                )
                continue

            # Handle non-string files pattern
            if not isinstance(files_pattern, str):
                logger.warning(
                    f"Expected string for 'files' in hook '{hook_id}', "
                    f"got {type(files_pattern).__name__}. Skipping."
                )
                continue

            # Handle empty string
            if not files_pattern.strip():
                logger.warning(
                    f"Hook '{hook_id}' has empty 'files' pattern. "
                    "This hook will match all files."
                )
                continue

            # Normalize quotes (handle both single and double quotes)
            normalized_pattern = _normalize_quotes(files_pattern)

            # Validate pattern is a valid regex (basic check)
            try:
                re.compile(normalized_pattern)
            except re.error as e:
                logger.warning(
                    f"Invalid regex in hook '{hook_id}' 'files' pattern: {e}. "
                    f"Pattern: '{files_pattern[:80]}...'"
                )
                continue

            # Extract source directories
            extracted_dirs = _extract_source_dirs_from_pattern(normalized_pattern)
            source_dirs.extend(extracted_dirs)

            # Extract test paths
            extracted_tests = _extract_test_paths_from_pattern(normalized_pattern)
            test_paths.extend(extracted_tests)

            # Log if we couldn't extract anything (might indicate pattern format change)
            if not extracted_dirs and not extracted_tests:
                logger.warning(
                    f"Could not extract any paths from hook '{hook_id}' pattern. "
                    f"Pattern may have unexpected format: '{files_pattern[:80]}...'"
                )

    return sorted(set(source_dirs)), sorted(set(test_paths))


def validate_mypy_cache_patterns(ci_config: dict, verbose: bool = False) -> MypyCacheValidation:
    """Validate that mypy cache hashFiles patterns match mypy command scope.

    The mypy cache key in CI uses hashFiles() patterns to determine when to
    invalidate the cache. These patterns MUST match the directories passed
    to the mypy command, otherwise:
    - Missing patterns: Source changes won't invalidate cache (stale results)
    - Extra patterns: Unnecessary cache invalidation (slower builds)

    Args:
        ci_config: Parsed CI workflow YAML
        verbose: Print detailed progress

    Returns:
        MypyCacheValidation with alignment status and details
    """
    result = MypyCacheValidation()

    # Navigate to type-check job
    jobs = ci_config.get("jobs", {})
    type_check_job = jobs.get("type-check", {})
    steps = type_check_job.get("steps", [])

    # Extract hashFiles patterns from mypy cache step
    cache_dirs: set[str] = set()
    for step in steps:
        if step.get("name") == "Cache mypy":
            cache_with = step.get("with", {})
            cache_key = cache_with.get("key", "")
            # Parse hashFiles patterns from the cache key
            #
            # Quote handling for hashFiles patterns:
            # -----------------------------------------
            # YAML and GitHub Actions support both single and double quotes:
            #   - Single quotes: hashFiles('pattern1', 'pattern2')
            #   - Double quotes: hashFiles("pattern1", "pattern2")
            #   - Mixed quotes:  hashFiles('pattern1', "pattern2")
            #
            # YAML multiline strings (using > or |) preserve the original quotes,
            # so we must handle both styles when parsing the cache key.
            #
            # Our approach:
            #   1. Extract everything inside hashFiles(...) parentheses
            #   2. Match all quoted strings using a pattern that handles both
            #      single-quoted ('content') and double-quoted ("content") strings
            #
            # The regex ['"]([^'"]+)['"] matches:
            #   - Opening quote (single or double): ['"]
            #   - Pattern content (any chars except quotes): ([^'"]+)
            #   - Closing quote (single or double): ['"]
            #
            # Note: This assumes patterns don't contain embedded quotes,
            # which is valid for file glob patterns like 'src/**/*.py'.
            hashfiles_content = re.search(r"hashFiles\(([^)]+)\)", cache_key)
            if hashfiles_content:
                patterns_str = hashfiles_content.group(1)
                # Extract patterns with either single or double quotes
                patterns = re.findall(r"""['"]([^'"]+)['"]""", patterns_str)
                for pattern in patterns:
                    result.cache_patterns.append(pattern)
                    # Extract directory name from pattern like 'src/omniintelligence/tools/**/*.py'
                    dir_match = re.match(r"src/omniintelligence/(\w+)/", pattern)
                    if dir_match:
                        cache_dirs.add(dir_match.group(1))

    # Extract directories from mypy command step
    command_dirs: set[str] = set()
    for step in steps:
        if step.get("name") == "Run mypy":
            run_cmd = step.get("run", "")
            # Parse mypy command arguments
            # Pattern: src/omniintelligence/tools/ src/omniintelligence/utils/ ...
            path_matches = re.findall(r"src/omniintelligence/(\w+)/", run_cmd)
            for dir_name in path_matches:
                result.command_paths.append(f"src/omniintelligence/{dir_name}/")
                command_dirs.add(dir_name)

    if verbose:
        print(f"\nMypy cache hashFiles patterns: {result.cache_patterns}")
        print(f"Mypy command paths: {result.command_paths}")

    # Compare cache patterns with command scope
    result.missing_in_cache = sorted(command_dirs - cache_dirs)
    result.extra_in_cache = sorted(cache_dirs - command_dirs)

    if result.missing_in_cache or result.extra_in_cache:
        result.is_aligned = False
        if verbose:
            if result.missing_in_cache:
                print(f"Directories in mypy command but not in cache: {result.missing_in_cache}")
            if result.extra_in_cache:
                print(f"Directories in cache but not in mypy command: {result.extra_in_cache}")

    return result


def validate_alignment(verbose: bool = False) -> ValidationResult:
    """Validate that CI and pre-commit patterns are aligned.

    Args:
        verbose: Print detailed progress

    Returns:
        ValidationResult with alignment status and details
    """
    result = ValidationResult(is_aligned=True)

    # Load CI workflow
    try:
        with open(CI_WORKFLOW_PATH) as f:
            ci_config = yaml.safe_load(f)
        if verbose:
            print(f"Loaded CI workflow: {CI_WORKFLOW_PATH}")
    except Exception as e:
        result.errors.append(f"Failed to load CI workflow: {e}")
        result.is_aligned = False
        return result

    # Load pre-commit config
    try:
        with open(PRECOMMIT_CONFIG_PATH) as f:
            precommit_config = yaml.safe_load(f)
        if verbose:
            print(f"Loaded pre-commit config: {PRECOMMIT_CONFIG_PATH}")
    except Exception as e:
        result.errors.append(f"Failed to load pre-commit config: {e}")
        result.is_aligned = False
        return result

    # Extract patterns
    result.ci_source_dirs, result.ci_test_paths = extract_ci_patterns(ci_config)
    result.precommit_source_dirs, result.precommit_test_paths = extract_precommit_patterns(
        precommit_config
    )

    if verbose:
        print(f"\nCI source dirs: {result.ci_source_dirs}")
        print(f"CI test paths: {result.ci_test_paths}")
        print(f"Pre-commit source dirs: {result.precommit_source_dirs}")
        print(f"Pre-commit test paths: {result.precommit_test_paths}")

    # Check source directory alignment
    ci_src_set = set(result.ci_source_dirs)
    precommit_src_set = set(result.precommit_source_dirs)

    if ci_src_set != precommit_src_set:
        result.is_aligned = False
        missing_in_ci_src = precommit_src_set - ci_src_set
        missing_in_precommit_src = ci_src_set - precommit_src_set
        for d in missing_in_ci_src:
            result.missing_in_ci.append(f"src/omniintelligence/{d}/")
        for d in missing_in_precommit_src:
            result.missing_in_precommit.append(f"src/omniintelligence/{d}/")

    # Check test path alignment
    ci_test_set = set(result.ci_test_paths)
    precommit_test_set = set(result.precommit_test_paths)

    if ci_test_set != precommit_test_set:
        result.is_aligned = False
        missing_in_ci_tests = precommit_test_set - ci_test_set
        missing_in_precommit_tests = ci_test_set - precommit_test_set
        result.missing_in_ci.extend(sorted(missing_in_ci_tests))
        result.missing_in_precommit.extend(sorted(missing_in_precommit_tests))

    # Validate against canonical expected values
    expected_src_set = set(ALIGNED_SOURCE_DIRS)
    expected_test_set = set(ALIGNED_TEST_PATHS)

    if ci_src_set != expected_src_set:
        if verbose:
            print(f"\nWarning: CI source dirs differ from expected: {expected_src_set}")

    if precommit_src_set != expected_src_set:
        if verbose:
            print(f"\nWarning: Pre-commit source dirs differ from expected: {expected_src_set}")

    # Validate mypy cache patterns match mypy command scope
    result.mypy_cache = validate_mypy_cache_patterns(ci_config, verbose=verbose)
    if not result.mypy_cache.is_aligned:
        # Mypy cache drift is a warning, not a hard failure
        # It causes suboptimal caching but doesn't break the build
        if verbose:
            print("\nWarning: Mypy cache patterns drift detected!")

    return result


def format_result(result: ValidationResult, output_json: bool = False) -> str:
    """Format validation result for output.

    Args:
        result: Validation result to format
        output_json: Output as JSON if True

    Returns:
        Formatted string
    """
    if output_json:
        return json.dumps(
            {
                "is_aligned": result.is_aligned,
                "ci_source_dirs": result.ci_source_dirs,
                "ci_test_paths": result.ci_test_paths,
                "precommit_source_dirs": result.precommit_source_dirs,
                "precommit_test_paths": result.precommit_test_paths,
                "missing_in_ci": result.missing_in_ci,
                "missing_in_precommit": result.missing_in_precommit,
                "errors": result.errors,
                "mypy_cache": {
                    "is_aligned": result.mypy_cache.is_aligned,
                    "cache_patterns": result.mypy_cache.cache_patterns,
                    "command_paths": result.mypy_cache.command_paths,
                    "missing_in_cache": result.mypy_cache.missing_in_cache,
                    "extra_in_cache": result.mypy_cache.extra_in_cache,
                },
            },
            indent=2,
        )

    lines = []

    if result.errors:
        lines.append("ERRORS:")
        for error in result.errors:
            lines.append(f"  - {error}")
        lines.append("")

    lines.append("CI-Precommit Pattern Alignment Validation")
    lines.append("=" * 45)
    lines.append("")

    lines.append("Source Directories:")
    lines.append(f"  CI:         {', '.join(result.ci_source_dirs) or '(none)'}")
    lines.append(f"  Pre-commit: {', '.join(result.precommit_source_dirs) or '(none)'}")
    lines.append("")

    lines.append("Test Paths:")
    lines.append(f"  CI:         {', '.join(result.ci_test_paths) or '(none)'}")
    lines.append(f"  Pre-commit: {', '.join(result.precommit_test_paths) or '(none)'}")
    lines.append("")

    if result.is_aligned:
        lines.append("Status: ALIGNED")
        lines.append("CI path filters and pre-commit patterns are synchronized.")
    else:
        lines.append("Status: MISALIGNED - Drift detected!")
        lines.append("")
        if result.missing_in_ci:
            lines.append("Missing in CI workflow:")
            for path in result.missing_in_ci:
                lines.append(f"  - {path}")
        if result.missing_in_precommit:
            lines.append("Missing in pre-commit config:")
            for path in result.missing_in_precommit:
                lines.append(f"  - {path}")
        lines.append("")
        lines.append("Action required: Update both files to maintain synchronization.")
        lines.append("See .pre-commit-config.yaml and .github/workflows/ci.yaml")

    # Mypy cache validation section
    lines.append("")
    lines.append("Mypy Cache Validation")
    lines.append("-" * 45)
    if result.mypy_cache.cache_patterns:
        lines.append("Cache hashFiles patterns:")
        for pattern in result.mypy_cache.cache_patterns:
            lines.append(f"  - {pattern}")
    if result.mypy_cache.command_paths:
        lines.append("Mypy command paths:")
        for path in result.mypy_cache.command_paths:
            lines.append(f"  - {path}")

    if result.mypy_cache.is_aligned:
        lines.append("")
        lines.append("Mypy Cache Status: ALIGNED")
        lines.append("Cache patterns match mypy command scope.")
    else:
        lines.append("")
        lines.append("Mypy Cache Status: DRIFT DETECTED (Warning)")
        if result.mypy_cache.missing_in_cache:
            lines.append("Directories in mypy command but not in cache (will cause stale cache):")
            for dir_name in result.mypy_cache.missing_in_cache:
                lines.append(f"  - {dir_name}")
        if result.mypy_cache.extra_in_cache:
            lines.append("Directories in cache but not in mypy command (unnecessary invalidation):")
            for dir_name in result.mypy_cache.extra_in_cache:
                lines.append(f"  - {dir_name}")
        lines.append("")
        lines.append("Action: Update mypy cache hashFiles patterns in .github/workflows/ci.yaml")
        lines.append("        to match the mypy command scope (~line 309 and ~line 319)")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments

    Returns:
        Exit code (0=aligned, 1=misaligned, 2=error)
    """
    parser = argparse.ArgumentParser(
        description="Validate CI and pre-commit pattern alignment"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args(argv)

    result = validate_alignment(verbose=args.verbose)

    print(format_result(result, output_json=args.json))

    if result.errors:
        return 2
    return 0 if result.is_aligned else 1


if __name__ == "__main__":
    sys.exit(main())
