# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-20074: the handler contract compliance job runs omnibase_core's validator.

OCC retirement S8, slice F: the validator moved from onex_change_control into
omnibase_core (``handler_arch_handler_contract_compliance``). The job installs
omnibase_core at a full commit sha and runs the module with the same flags and the
same allowlist file; nothing is installed from change-control any more.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "omni-standards-compliance.yml"
JOB = "handler-contract-compliance"
ALLOWLIST = "arch-handler-contract-compliance-allowlist.yaml"
CORE_INSTALL = re.compile(
    r"uv pip install --system \"omnibase-core @ "
    r"git\+https://github\.com/OmniNode-ai/omnibase_core\.git@(?P<sha>[0-9a-f]{40})\""
)
CORE_MODULE = "omnibase_core.handlers.handler_arch_handler_contract_compliance"


def _steps() -> list[dict[str, object]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"][JOB]["steps"]
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, dict)]


def _runs() -> list[str]:
    return [str(step["run"]) for step in _steps() if "run" in step]


def test_job_installs_omnibase_core_at_a_full_sha() -> None:
    installs = [match for run in _runs() if (match := CORE_INSTALL.search(run))]
    assert len(installs) == 1


def test_job_installs_nothing_from_change_control() -> None:
    for step in _steps():
        assert "onex_change_control" not in yaml.safe_dump(step)


def test_job_runs_the_core_module_with_the_same_flags_and_allowlist() -> None:
    runs = [run for run in _runs() if CORE_MODULE in run]
    assert len(runs) == 1
    command = " ".join(runs[0].replace("\\", " ").split())
    assert command == (
        f"python -m {CORE_MODULE} --repo-root . --allowlist-path {ALLOWLIST}"
    )


def test_allowlist_file_the_job_names_exists() -> None:
    assert (REPO_ROOT / ALLOWLIST).is_file()
    assert yaml.safe_load((REPO_ROOT / ALLOWLIST).read_text(encoding="utf-8"))[
        "allowlisted_handlers"
    ]
