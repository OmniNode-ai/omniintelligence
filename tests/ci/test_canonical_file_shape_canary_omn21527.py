# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Canary for the canonical-file-shape node entry and its burn-down baseline (OMN-21527).

omniintelligence runs the ``node_canonical_file_shape_check_compute`` entry pinned
to an omnibase_core dev-merge tag. Findings that existed when the entry was
installed live in the ticketed burn-down file; the file only shrinks. These tests
run the job's own pin, resolved by the real ``uv``, against throwaway git
repositories:

* the base tree (one unbound handler, listed in the burn-down file) is accepted;
* a commit that adds one new unbound handler is refused as ``handler_outside_node``;
* a commit that adds a burn-down line for an existing refused file, against a
  base that does not list it, is refused as ``baseline-growth``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
BURNDOWN_FILE = ".onex_ratchets/canonical_file_shape_burndown_baseline.txt"
BASELINE_FILE = ".onex_ratchets/canonical_file_shape_baseline.txt"
BURNDOWN_HEADER = "# Burn-down ticket: OMN-21527"
ENTRY_MODULE = (
    "omnibase_core.nodes.node_canonical_file_shape_check_compute"
    ".runtime_canonical_file_shape_check"
)
EXISTING_REFUSED = (
    "src/omniintelligence/nodes/node_known_effect/handlers/handler_known.py"
)
PLANTED = "src/omniintelligence/nodes/node_known_effect/handlers/handler_planted.py"


def _core_pin() -> str:
    workflow: dict[str, Any] = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    return str(
        workflow["jobs"]["canonical-file-shape"]["env"]["CANONICAL_FILE_SHAPE_CORE"]
    )


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


def _ratchet(work: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--with",
            _core_pin(),
            "python",
            "-m",
            ENTRY_MODULE,
            "--rules",
            "file-shape",
            *args,
        ],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def work(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "dev", str(root)], check=True)
    return root


def _install_base(work: Path) -> str:
    return _commit(
        work,
        "base OMN-21527",
        {
            EXISTING_REFUSED: "VALUE = 1\n",
            BASELINE_FILE: "# existing baseline\n",
            BURNDOWN_FILE: f"{BURNDOWN_HEADER}\n{EXISTING_REFUSED}\n",
        },
    )


def test_base_tree_with_its_burn_down_entry_is_accepted(work: Path) -> None:
    _install_base(work)

    result = _ratchet(work, "--head", "HEAD")

    assert result.returncode == 0, result.stderr + result.stdout


def test_new_unbound_handler_is_refused(work: Path) -> None:
    base = _install_base(work)
    _commit(work, "plant OMN-21527", {PLANTED: "VALUE = 2\n"})

    result = _ratchet(work, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert f"{PLANTED}: [handler_outside_node]" in result.stderr + result.stdout


def test_burn_down_line_added_for_an_existing_refused_file_is_refused(
    work: Path,
) -> None:
    _install_base(work)
    base = _commit(
        work, "drop the line OMN-21527", {BURNDOWN_FILE: f"{BURNDOWN_HEADER}\n"}
    )
    _commit(
        work,
        "add the line back OMN-21527",
        {BURNDOWN_FILE: f"{BURNDOWN_HEADER}\n{EXISTING_REFUSED}\n"},
    )

    result = _ratchet(work, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert f"{BURNDOWN_FILE}: [baseline-growth]" in result.stderr + result.stdout


def test_committed_burn_down_file_names_this_ticket_and_lists_existing_paths() -> None:
    lines = (REPO_ROOT / BURNDOWN_FILE).read_text(encoding="utf-8").splitlines()
    entries = [line for line in lines if line and not line.startswith("#")]

    assert lines[0] == BURNDOWN_HEADER
    assert entries == sorted(set(entries))
    baseline = (REPO_ROOT / BASELINE_FILE).read_text(encoding="utf-8").splitlines()
    assert not set(entries) & set(baseline)
    missing = [entry for entry in entries if not (REPO_ROOT / entry).is_file()]
    assert missing == []
