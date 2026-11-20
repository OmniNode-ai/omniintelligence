# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-25070: no CI step or hook runs the onex launcher.

omnibase-core stops declaring the onex console script once the customer
package omninode-onex carries it, so a CI step or hook that runs
`uv run onex ...` would fail. Callers run the core CLI as a module.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CALLER_FILES = (".github/workflows/ci.yml", ".pre-commit-config.yaml")
LAUNCHER = re.compile(r"^[^#]*\buv run onex ", re.MULTILINE)
MODULE = "python -m omnibase_core.cli.cli_commands"


@pytest.mark.unit
@pytest.mark.parametrize("name", CALLER_FILES)
def test_no_ci_step_or_hook_runs_the_onex_launcher(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert LAUNCHER.findall(text) == []


@pytest.mark.unit
def test_the_callers_run_the_core_cli_as_a_module() -> None:
    assert any(
        MODULE in (ROOT / name).read_text(encoding="utf-8") for name in CALLER_FILES
    )
