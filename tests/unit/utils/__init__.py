# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the utils module.

Contains unit tests for src/omniintelligence/utils/.

MIGRATION TODO: Move test_log_sanitizer.py here.

tests/unit/test_log_sanitizer.py tests src/omniintelligence/utils/log_sanitizer.py
but lives in tests/unit/ instead of tests/unit/utils/ for historical reasons.
Moving it requires coordinated pattern updates across multiple config files.

Files requiring pattern updates when moving:

  .pre-commit-config.yaml (6 locations) -- ruff lint/format 'files', pytest hook
  .github/workflows/ci.yml (4 locations) -- paths-filter, pytest commands
  scripts/validate_ci_precommit_alignment.py (3 locations) -- ALIGNED_TEST_PATHS

Preferred approach: update patterns to use tests/unit/utils/ as a directory
(like tests/unit/tools/) which is simpler and more future-proof.
"""
