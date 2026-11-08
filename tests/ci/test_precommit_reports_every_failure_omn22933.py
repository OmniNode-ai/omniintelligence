# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One commit attempt reports every failing hook in omniintelligence (OMN-22933).

A config-level ``fail_fast: true`` makes pre-commit stop at the first failing
hook, so a lane with two problems commits, fixes one, commits again and reads
the second. The floor row ``stoppage:local-hooks-fail-one-per-attempt`` counts
those attempts. No hook is removed or loosened here: every hook still runs and
every failure is still a refusal; they are all reported in the same run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PRECOMMIT = REPO_ROOT / ".pre-commit-config.yaml"

PROBLEM_ONE = "PLANTED-PROBLEM-ONE"
PROBLEM_TWO = "PLANTED-PROBLEM-TWO"


def _repo_fail_fast() -> bool:
    loaded = yaml.safe_load(PRECOMMIT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return bool(loaded.get("fail_fast", False))


def _run_two_failing_hooks(tmp_path: Path, *, fail_fast: bool) -> tuple[int, str]:
    """Run two failing local hooks in a scratch repo under one fail_fast value."""
    hooks = [
        {
            "id": hook_id,
            "name": hook_id,
            "language": "system",
            "entry": f"sh -c 'echo {message}; exit 1'",
            "pass_filenames": False,
            "always_run": True,
        }
        for hook_id, message in (
            ("planted-one", PROBLEM_ONE),
            ("planted-two", PROBLEM_TWO),
        )
    ]
    config = {"fail_fast": fail_fast, "repos": [{"repo": "local", "hooks": hooks}]}
    config_path = tmp_path / "planted-config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pre_commit",
            "run",
            "--all-files",
            "--config",
            str(config_path),
        ],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def test_failing_control_fail_fast_true_reports_only_the_first_problem(
    tmp_path: Path,
) -> None:
    """The control: the setting this repo used to carry hides the second problem."""
    code, output = _run_two_failing_hooks(tmp_path, fail_fast=True)
    assert code != 0
    assert PROBLEM_ONE in output
    assert PROBLEM_TWO not in output


def test_fail_fast_false_reports_both_problems_in_one_run(tmp_path: Path) -> None:
    code, output = _run_two_failing_hooks(tmp_path, fail_fast=False)
    assert code != 0
    assert PROBLEM_ONE in output
    assert PROBLEM_TWO in output


def test_repo_config_runs_every_hook_not_stopping_at_the_first_failure() -> None:
    """The repo's own setting is the one under test: it must not stop at hook one."""
    assert _repo_fail_fast() is False


def test_repo_setting_reports_two_problems_at_once(tmp_path: Path) -> None:
    """Plant two problems under the repo's own fail_fast value and read both."""
    code, output = _run_two_failing_hooks(tmp_path, fail_fast=_repo_fail_fast())
    assert code != 0
    assert PROBLEM_ONE in output
    assert PROBLEM_TWO in output
