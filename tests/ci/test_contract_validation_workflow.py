# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Exercise the contract gate's merge_group skip boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit
WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github/workflows/contract-validation.yml"
)


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"]["contract-validation"]["steps"]
    return steps


def test_merge_group_skips_checkout_install_and_validation() -> None:
    steps = _steps()
    resolve = next(step for step in steps if step.get("id") == "resolve-branch")
    assert '"$EVENT_NAME" == "merge_group"' in resolve["run"]
    assert 'echo "skip_validation=true"' in resolve["run"]
    for step in steps[steps.index(resolve) + 1 : -1]:
        assert step["if"] == "steps.resolve-branch.outputs.skip_validation != 'true'"
