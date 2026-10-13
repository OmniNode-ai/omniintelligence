# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-20965: the boundary-parity job calls omnibase_core's validate-boundaries action.

OMN-20074 moved the validate-boundaries composite action out of the
change-control repository. The ``boundary-parity`` job in ci.yml keeps its job id, name
and check-run context and changes only its ``uses:`` line, to the full commit
sha of the merge that added the action (omnibase_core#1942).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

JOB_ID = "boundary-parity"
CONTEXT = "Cross-Repo Boundary Parity"
ACTION = "OmniNode-ai/omnibase_core/.github/actions/validate-boundaries"
# First eight hex digits of the omnibase_core#1942 merge; the rest must still be a full sha.
ACTION_SHA_PREFIX = "de3398d1"
_PINNED_USES = re.compile(rf"^{re.escape(ACTION)}@{ACTION_SHA_PREFIX}[0-9a-f]{{32}}$")
_RETIRED_ACTION = re.compile(
    r"onex_change_control/\.github/actions/validate-boundaries"
)


def _job() -> dict[str, Any]:
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    return workflow["jobs"][JOB_ID]


def _retired_references(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _RETIRED_ACTION.search(line)]


def test_job_calls_the_core_action_at_the_merge_sha() -> None:
    uses = [s["uses"].split(" ")[0] for s in _job()["steps"] if "uses" in s]

    assert [u for u in uses if _PINNED_USES.fullmatch(u)] != []


def test_no_workflow_calls_the_retired_change_control_action() -> None:
    offenders = {
        path.name: _retired_references(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.glob("*.yml"))
    }

    assert {name: refs for name, refs in offenders.items() if refs} == {}


def test_retired_action_reference_is_detected() -> None:
    old = (
        "      - uses: OmniNode-ai/onex_change_control/.github/actions/"
        "validate-boundaries@0123456789abcdef0123456789abcdef01234567"
    )

    assert _retired_references(old) == [old.strip()]


def test_inputs_and_job_name_are_unchanged() -> None:
    job = _job()
    step = next(s for s in job["steps"] if ACTION in s.get("uses", ""))

    assert job["name"] == CONTEXT
    assert step["with"] == {
        "checks": "boundary-parity,migration-conflicts",
        "warn-only": "false",
        "repos": "omniclaude,omnidash,omniintelligence,omnibase_infra,omnibase_core,omnimemory,omnimarket,onex_change_control",
    }


_CORE_GIT_PIN = re.compile(r"omnibase_core@([0-9a-f]{40})\b")
_PRECOMMIT_CORE_REV = re.compile(
    r"repo:\s*https://github\.com/OmniNode-ai/omnibase_core\s*\n\s*rev:\s*([0-9a-f]{40})\b"
)


def _core_git_pins(text: str) -> set[str]:
    return set(_CORE_GIT_PIN.findall(text))


def test_every_core_git_pin_in_ci_is_the_commit_the_hooks_pin() -> None:
    # A pin on a pre-squash commit that is on no omnibase_core branch cannot be
    # fetched, so every job that installs omnibase-core from it fails (the
    # shape-gate-independence job did, behind d17f5be8). The pre-commit hooks pin
    # commits already proven reachable on omnibase_core dev; ci.yml must use one
    # of them, and only one.
    precommit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    hook_revs = set(_PRECOMMIT_CORE_REV.findall(precommit))
    assert hook_revs != set()

    pins = _core_git_pins((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))

    assert len(pins) == 1
    assert pins <= hook_revs


def test_unfetchable_core_git_pin_is_detected() -> None:
    # The retired pin begins d17f5be8; the remaining digits are a stand-in.
    stand_in = "d17f5be8" + "0" * 32
    old = (
        "--with 'omnibase-core @ git+https://github.com/OmniNode-ai/omnibase_core"
        f"@{stand_in}'"
    )

    assert _core_git_pins(old) == {stand_in}
