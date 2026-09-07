# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The runner-IP gate must actually run, and must resolve a real scanner (OMN-17993).

`.github/workflows/ban-hardcoded-runner-ip.yml` calls a reusable gate that
rejects the literal lab runner address. Two independent defects made it inert
here, and both halves are required:

1. The caller's `paths:` filter listed `.github/workflows/**` only, so a
   tests-only change never triggered the job at all.
2. The `uses:` ref was `@main`. omniclaude's `main` is release-synced and lags
   `dev` by design, so `@main` resolved to the pre-widening scanner body that
   scans workflow files only and exits 0 on a tests-only diff.

This module asserts both halves. It deliberately does NOT assert the absence of
the literal under `tests/`: this repository carries pre-existing unannotated
occurrences that are a content fix tracked separately (OMN-17992), not a
pinning concern. Suppressing them here would re-create the defect this file
exists to close.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CALLER = REPO_ROOT / ".github" / "workflows" / "ban-hardcoded-runner-ip.yml"


@pytest.mark.unit
def test_caller_paths_filter_includes_tests() -> None:
    doc = yaml.safe_load(CALLER.read_text(encoding="utf-8"))
    paths = doc[True]["pull_request"]["paths"]  # YAML 1.1 parses `on:` as True
    assert "tests/**" in paths
    assert ".github/workflows/**" in paths


@pytest.mark.unit
def test_caller_pins_reusable_to_an_exact_sha() -> None:
    doc = yaml.safe_load(CALLER.read_text(encoding="utf-8"))
    uses = doc["jobs"]["ban-hardcoded-runner-ip"]["uses"]
    ref = uses.rsplit("@", 1)[1]
    assert re.fullmatch(r"[0-9a-f]{40}", ref), (
        f"ban-hardcoded-runner-ip must pin an exact 40-hex SHA, got {ref!r}. "
        "A branch or tag ref re-introduces the OMN-17993 inert-gate defect."
    )
