# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Canonical-file-shape base selection on a release push to main (OMN-21164).

release.yml fast-forwards main to a dev sha, so the push-to-main run takes the
previous release as ``github.event.before`` and diffs every dev PR since then.
Exception files those PRs added (each checked on its own dev PR) read as new
against that old base, and the 0.25.0 release commit went red with
``[new-exception-file]``. The CI step now checks a push to main of a commit
already on dev against the baseline only; a genuinely new exception file is
still refused.

The tests run the workflow step's own shell against throwaway git repositories,
with the pinned validator module standing in behind a ``uv`` shim.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
JOB_ID = "canonical-file-shape"
STEP_NAME = "Refuse new non-canonical files and new exceptions"
LANDED_EXCEPTION_FILE = ".github/workflows/secrets-baseline-wiring.yml"
NEW_EXCEPTION_FILE = "config/new_allowlist.yaml"

# Stands in for `uv run --no-project --with <core> python -m <module> ...`: runs the
# module with the interpreter that runs this test.
UV_SHIM = f"""#!/bin/sh
while [ "$1" != "-m" ]; do shift; done
shift
exec {sys.executable} -m "$@"
"""


def _step_script() -> str:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"][JOB_ID]["steps"]
    matching = [step for step in steps if step.get("name") == STEP_NAME]
    assert len(matching) == 1, f"expected one {STEP_NAME!r} step"
    return str(matching[0]["run"])


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(work: Path, message: str, files: dict[str, str]) -> str:
    for relative, text in files.items():
        target = work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", message)
    return _git(work, "rev-parse", "HEAD")


class _Repo:
    """A working clone whose origin holds ``dev`` at the release commit."""

    def __init__(self, root: Path) -> None:
        origin = root / "origin.git"
        self.work = root / "work"
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
        subprocess.run(["git", "init", "-q", str(self.work)], check=True)
        _git(self.work, "checkout", "-q", "-b", "dev")
        _git(self.work, "remote", "add", "origin", str(origin))
        # The previous release on main.
        self.previous_release = _commit(
            self.work, "previous release", {"README.md": "a\n"}
        )
        # A dev PR that landed an exception file, checked on its own PR.
        _commit(self.work, "dev PR", {LANDED_EXCEPTION_FILE: "name: wiring\n"})
        # The release commit; main is fast-forwarded to it.
        self.release = _commit(self.work, "release", {"CHANGELOG.md": "v0.25.0\n"})
        _git(self.work, "push", "-q", "origin", "dev")
        shim = root / "bin" / "uv"
        shim.parent.mkdir()
        shim.write_text(UV_SHIM, encoding="utf-8")
        shim.chmod(0o755)
        self.shim_dir = shim.parent

    def run_step(self, **event: str) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "PATH": f"{self.shim_dir}{os.pathsep}{os.environ['PATH']}",
            "CANONICAL_FILE_SHAPE_CORE": "unused-by-the-uv-shim",
            "PR_BASE": "",
            "MQ_BASE": "",
            "PUSH_BEFORE": "",
            "PUSH_REF": "",
            **event,
        }
        return subprocess.run(
            ["bash", "-c", _step_script()],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    return _Repo(tmp_path)


def test_release_fast_forward_push_to_main_does_not_flag_existing_exception_file(
    repo: _Repo,
) -> None:
    result = repo.run_step(
        PUSH_BEFORE=repo.previous_release, PUSH_REF="refs/heads/main"
    )

    assert result.returncode == 0, result.stderr
    assert "already on dev" in result.stdout


def test_same_range_pushed_to_dev_is_still_diffed(repo: _Repo) -> None:
    """The range that is exempt on main is not exempt on dev: the exemption is narrow."""
    result = repo.run_step(PUSH_BEFORE=repo.previous_release, PUSH_REF="refs/heads/dev")

    assert result.returncode != 0
    assert f"{LANDED_EXCEPTION_FILE}: [new-exception-file]" in result.stderr


@pytest.mark.parametrize(
    "event",
    [
        pytest.param({"PR_BASE": "release"}, id="pull-request"),
        pytest.param({"MQ_BASE": "release"}, id="merge-group"),
        pytest.param(
            {"PUSH_BEFORE": "release", "PUSH_REF": "refs/heads/main"},
            id="push-to-main-of-a-commit-not-on-dev",
        ),
    ],
)
def test_newly_added_exception_file_is_still_refused(
    repo: _Repo, event: dict[str, str]
) -> None:
    _commit(repo.work, "adds an exception", {NEW_EXCEPTION_FILE: "entries:\n  - a\n"})

    result = repo.run_step(
        **{
            key: repo.release if value == "release" else value
            for key, value in event.items()
        }
    )

    assert result.returncode != 0
    assert f"{NEW_EXCEPTION_FILE}: [new-exception-file]" in result.stderr
