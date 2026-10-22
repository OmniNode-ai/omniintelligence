# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Serial mypy pre-push execution in omniintelligence (OMN-17427).

Pre-commit's concurrent file batches race on mypy 2.3.0's shared incremental
SQLite cache at PRAGMA journal_mode=WAL, raising database is locked and
INTERNAL ERROR (exit 2), which refuses pushes. Keep one mypy process while
preserving the incremental cache and the passed filenames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PRECOMMIT = REPO_ROOT / ".pre-commit-config.yaml"


def _mypy_hook() -> dict[str, Any]:
    loaded = yaml.safe_load(PRECOMMIT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    repos = loaded["repos"]
    assert isinstance(repos, list)
    hooks: list[dict[str, Any]] = [
        hook
        for repo in repos
        if isinstance(repo, dict)
        for hook in repo.get("hooks", [])
        if isinstance(hook, dict) and hook.get("id") == "mypy-type-check"
    ]
    assert len(hooks) == 1, f"expected one mypy-type-check hook, found {len(hooks)}"
    return hooks[0]


def test_mypy_hook_runs_one_process() -> None:
    hook = _mypy_hook()
    assert hook.get("require_serial") is True


def test_mypy_hook_still_passes_filenames_incrementally() -> None:
    hook = _mypy_hook()
    assert "--incremental" in hook["entry"]
    assert hook.get("pass_filenames", True) is True
