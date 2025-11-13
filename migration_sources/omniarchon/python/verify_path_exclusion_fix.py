#!/usr/bin/env python3
"""
Verification script for path exclusion fix in repository_analyzer.py

Tests that path exclusion patterns match only complete path components,
not substrings within filenames or directory names.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.utils.repository_analyzer import RepositoryAnalyzer


def test_path_exclusion():
    """Test path exclusion logic with various edge cases."""
    analyzer = RepositoryAnalyzer()

    # Test cases: (path, should_be_excluded, reason)
    test_cases = [
        # Should be EXCLUDED (exact component matches)
        (Path("/project/node_modules/package/file.js"), True, "node_modules directory"),
        (
            Path("/project/venv/lib/python3.11/site-packages/file.py"),
            True,
            "venv directory",
        ),
        (Path("/project/.venv/bin/python"), True, ".venv directory"),
        (Path("/project/build/output/app.js"), True, "build directory"),
        (Path("/project/dist/bundle.js"), True, "dist directory"),
        (Path("/project/.git/config"), True, ".git directory"),
        (Path("/project/src/__pycache__/module.pyc"), True, "__pycache__ directory"),
        (
            Path("/project/.pytest_cache/v/cache/lastfailed"),
            True,
            ".pytest_cache directory",
        ),
        (
            Path("/project/.mypy_cache/3.11/module.data.json"),
            True,
            ".mypy_cache directory",
        ),
        (Path("/project/target/release/binary"), True, "target directory (Rust/Java)"),
        # Should be INCLUDED (substring matches, not exact components)
        (
            Path("/project/src/my_venv_config.py"),
            False,
            "venv is substring in filename",
        ),
        (
            Path("/project/src/rebuild_utils.py"),
            False,
            "build is substring in filename",
        ),
        (
            Path("/project/distributed_data/config.json"),
            False,
            "dist is substring in directory name",
        ),
        (
            Path("/project/testing_framework/test.py"),
            False,
            "test is substring in directory name",
        ),
        (
            Path("/project/node_modules_backup/package.json"),
            False,
            "node_modules is substring in directory name",
        ),
        (
            Path("/project/src/environment_vars.py"),
            False,
            "env is substring in filename",
        ),
        (
            Path("/project/coverage_reports/report.html"),
            False,
            "coverage is substring in directory name",
        ),
        # Edge cases
        (Path("/project/src/main.py"), False, "normal source file"),
        (Path("/project/docs/README.md"), False, "documentation file"),
        (Path("/project/.vscode/settings.json"), True, ".vscode directory"),
        (Path("/project/.idea/workspace.xml"), True, ".idea directory"),
    ]

    print("=" * 80)
    print("PATH EXCLUSION FIX VERIFICATION")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for path, expected_excluded, reason in test_cases:
        result = analyzer._is_excluded_path(path)
        status = "✅ PASS" if result == expected_excluded else "❌ FAIL"

        if result == expected_excluded:
            passed += 1
        else:
            failed += 1

        expected_str = "EXCLUDED" if expected_excluded else "INCLUDED"
        actual_str = "EXCLUDED" if result else "INCLUDED"

        print(f"{status} | {path}")
        print(f"         Expected: {expected_str} ({reason})")
        print(f"         Actual:   {actual_str}")
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} total")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = test_path_exclusion()
    sys.exit(0 if success else 1)
