# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-20074: ``contract-validation`` validates with omnibase_core, not onex_change_control.

The workflow used to check the change-control repository out at a sibling pin,
install its validators and run ``validate-yaml`` on the branch ticket's
contract. The model that validator relies on is ``omnibase_core``'s
``ModelTicketContract``, which from 0.47.39 also refuses the two shapes the
change-control validator refused and core used to admit: a ``binds_ac`` entry
that is not a criterion label, and a ``binds_ac`` item whose check type is
``command_exit_0``.

The workflow now validates the branch ticket's ``contracts/<ticket>.yaml`` with
the installed core model, under unchanged workflow, job and context names. These
tests run the step's own ``run`` block, extracted from the workflow file, against
this repository's contract and against planted ones; ``uv`` is a shim that runs
the step's Python with the interpreter running the tests, which already has the
locked core installed.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contract-validation.yml"
UV_LOCK = REPO_ROOT / "uv.lock"

_BASH = shutil.which("bash") or "/bin/bash"

WORKFLOW_NAME = "Contract Validation"
JOB_KEY = "contract-validation"
STEP_NAME = "Run contract validation"
CORE_WITH_BINDS_AC_RULES = (0, 47, 39)

_CONTRACT = """\
schema_version: "1.0.0"
ticket_id: "OMN-1"
title: "planted"
dod_evidence:
  - id: "dod-omn1-ac1"
    description: "planted"
    source: "manual"
    checks:
      - check_type: "{check_type}"
        check_value: "uv run pytest tests -q"
    binds_ac: ["{label}"]
"""
_CLEAN = _CONTRACT.format(check_type="test_passes", label="AC1")
_NON_LABEL = _CONTRACT.format(check_type="test_passes", label="AC1 trailing text")
_COMMAND_EXIT_0 = _CONTRACT.format(check_type="command_exit_0", label="AC1")
_MALFORMED = "schema_version: [unterminated\n"

# `uv` for the step: `sync` succeeds, `run [flags] python3 ...` runs the test
# interpreter in place of the project environment.
_UV_SHIM = """\
#!/bin/sh
case "$1" in
  sync) exit 0 ;;
  run)
    shift
    while [ "$#" -gt 0 ] && [ "$1" != "python3" ]; do shift; done
    shift
    exec "$VALIDATION_TEST_PYTHON" "$@"
    ;;
esac
echo "uv shim: unsupported: $*" >&2
exit 2
"""


def _workflow() -> dict[str, object]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _job() -> dict[str, object]:
    jobs = _workflow()["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[JOB_KEY]
    assert isinstance(job, dict)
    return job


def _step(name: str) -> dict[str, object]:
    steps = _job()["steps"]
    assert isinstance(steps, list)
    (step,) = [step for step in steps if step.get("name") == name]
    assert isinstance(step, dict)
    return step


def _run_block() -> str:
    run = _step(STEP_NAME)["run"]
    assert isinstance(run, str)
    return run


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """A repository root holding ``contracts/`` with ``files``."""
    root = tmp_path / "repo"
    contracts = root / "contracts"
    contracts.mkdir(parents=True)
    for name, text in files.items():
        (contracts / name).write_text(text, encoding="utf-8")
    return root


def _step_run(
    cwd: Path, branch: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    """Run the step's literal ``run`` block for ``branch`` in ``cwd``."""
    scratch = Path(tempfile.mkdtemp(prefix="contract-validation-step-"))
    bin_dir = scratch / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "uv"
    shim.write_text(_UV_SHIM, encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    outputs = scratch / "github_output"
    outputs.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(
        BRANCH=branch,
        GITHUB_OUTPUT=str(outputs),
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        VALIDATION_TEST_PYTHON=sys.executable,
    )
    result = subprocess.run(
        [_BASH, "-c", _run_block()],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    written = dict(
        line.split("=", 1)
        for line in outputs.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    return result, written


# --- the workflow shape: no change-control read, names unchanged ---------------


def test_workflow_names_no_onex_change_control() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "onex_change_control" not in text
    assert "validate-yaml" not in text
    assert "ModelTicketContract" in _run_block()


def test_workflow_and_job_names_are_unchanged() -> None:
    assert _workflow()["name"] == WORKFLOW_NAME
    assert _job()["name"] == JOB_KEY
    jobs = _workflow()["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {JOB_KEY}


def test_workflow_validates_at_the_locked_core_with_the_binds_ac_rules() -> None:
    run = _run_block()
    assert "uv sync --locked --no-dev" in run
    assert "uv run --no-sync" in run
    block = UV_LOCK.read_text(encoding="utf-8").split(
        'name = "omnibase-core"\nversion = "', 1
    )[1]
    version = tuple(int(part) for part in block.split('"', 1)[0].split("."))
    assert version >= CORE_WITH_BINDS_AC_RULES, version


# --- this repository's contract -------------------------------------------------


def test_branch_ticket_contract_of_this_repo_passes() -> None:
    result, outputs = _step_run(REPO_ROOT, "omn-20074-intel-contract-validation-core")
    assert result.returncode == 0, result.stdout + result.stderr
    assert outputs["ticket-id"] == "OMN-20074"
    assert outputs["validation-status"] == "passed"


# --- the step over planted contracts --------------------------------------------


def test_clean_planted_contract_passes(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"OMN-1.yaml": _CLEAN})
    result, outputs = _step_run(root, "feature/OMN-1-thing")
    assert result.returncode == 0, result.stdout + result.stderr
    assert outputs["validation-status"] == "passed"


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (_NON_LABEL, "DOD_EVIDENCE_BINDS_AC_LABEL"),
        (_COMMAND_EXIT_0, "DOD_EVIDENCE_BINDS_AC_CHECK_TYPE"),
    ],
    ids=["non-label-binds-ac", "command-exit-0-binds-ac"],
)
def test_refused_binds_ac_shape_fails_naming_file_and_rule(
    tmp_path: Path, text: str, rule: str
) -> None:
    root = _repo(tmp_path, {"OMN-2.yaml": text})
    result, outputs = _step_run(root, "OMN-2-planted")
    assert result.returncode == 1, result.stdout + result.stderr
    assert outputs["validation-status"] == "failed"
    assert "contracts/OMN-2.yaml" in result.stdout
    assert rule in result.stdout


def test_malformed_contract_fails_naming_the_file(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"OMN-3.yaml": _MALFORMED})
    result, outputs = _step_run(root, "OMN-3-planted")
    assert result.returncode == 1, result.stdout + result.stderr
    assert outputs["validation-status"] == "failed"
    assert "contracts/OMN-3.yaml" in result.stdout


def test_step_validates_only_the_branch_ticket_contract(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"OMN-1.yaml": _CLEAN, "OMN-2.yaml": _NON_LABEL})
    result, outputs = _step_run(root, "OMN-1-only")
    assert result.returncode == 0, result.stdout + result.stderr
    assert outputs["validation-status"] == "passed"


def test_branch_without_ticket_or_contract_is_skipped(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"OMN-1.yaml": _CLEAN})
    no_ticket, no_ticket_out = _step_run(root, "dependabot/bump-something")
    assert no_ticket.returncode == 0, no_ticket.stdout + no_ticket.stderr
    assert no_ticket_out["validation-status"] == "skipped"
    no_contract, no_contract_out = _step_run(root, "OMN-999-no-contract")
    assert no_contract.returncode == 0, no_contract.stdout + no_contract.stderr
    assert no_contract_out["validation-status"] == "skipped"
