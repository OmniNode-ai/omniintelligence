# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

r"""Unit tests for the utils module.

This package contains unit tests for src/omniintelligence/utils/.

MIGRATION TODO: Move test_log_sanitizer.py Here
=====================================================

The file tests/unit/test_log_sanitizer.py tests src/omniintelligence/utils/log_sanitizer.py
but currently lives in tests/unit/ instead of tests/unit/utils/ for historical reasons.

For structural consistency with the source code layout, test_log_sanitizer.py should be
moved to this directory. However, this requires coordinated updates to multiple files
that have regex patterns referencing its current location.

Files Requiring Pattern Updates When Moving:
--------------------------------------------

1. .pre-commit-config.yaml (6 locations):
   - Line ~146: Comment listing test paths
   - Line ~257-259: ruff lint hook 'files' pattern
   - Line ~265-266: ruff format hook 'files' pattern
   - Line ~342-346: pytest hook 'entry' command
   - Line ~351-357: pytest hook 'files' pattern

   Pattern changes needed:
   - tests/unit/test_log_sanitizer\.py -> tests/unit/utils/test_log_sanitizer\.py
   - tests/unit/(tools/|test_log_sanitizer\.py) -> tests/unit/(tools|utils)/

2. .github/workflows/ci.yaml (4 locations):
   - Line ~25: Comment listing test directories
   - Line ~106: paths-filter 'tools_utils' filter
   - Line ~254: pytest command in lint job
   - Line ~263: pytest command in test job

   Pattern changes needed:
   - tests/unit/test_log_sanitizer.py -> tests/unit/utils/test_log_sanitizer.py
   - Or simplify to: tests/unit/utils/

3. scripts/validate_ci_precommit_alignment.py (3 locations):
   - Line ~85: ALIGNED_TEST_PATHS list
   - Line ~174: Pattern documentation comment
   - Line ~183: Test path extraction logic

   Pattern changes needed:
   - "tests/unit/test_log_sanitizer.py" -> "tests/unit/utils"
   - Update regex parsing logic for new structure

Migration Steps:
----------------
1. Create a PR that updates all patterns FIRST (this is safer)
2. Move the file: git mv tests/unit/test_log_sanitizer.py tests/unit/utils/
3. Run validation: python scripts/validate_ci_precommit_alignment.py
4. Run tests: pytest tests/unit/utils/ -v
5. Verify pre-commit: pre-commit run --all-files

Alternative Approach:
--------------------
Update patterns to use tests/unit/utils/ as a directory (like tests/unit/tools/),
which would be simpler and more future-proof for additional utils tests.

New patterns would be:
- files: ^(src/omniintelligence/(tools|utils|runtime)/|tests/unit/(tools|utils)/)
- entry: uv run pytest tests/unit/tools/ tests/unit/utils/ -v --tb=short
"""
