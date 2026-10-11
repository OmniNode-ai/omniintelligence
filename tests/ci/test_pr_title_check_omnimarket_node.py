# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-21003: preserve the title context and the old bash verdicts with a release node.

The bash oracle below is the decision portion of the old reusable pinned at
c0c49e1240ffaa6db1fe36f74b50c0acd345d7b2. The node runs from a PyPI release in
an isolated venv, as the workflow does; no sibling clone or checkout is needed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/pr-title-check.yml"
MANIFEST = ROOT / ".github/required-checks.yaml"
CONTEXT = "pr-title / check-title"
NODE_MODULE = "omnimarket.nodes.node_pr_title_check_compute"
OMNIMARKET_VERSION = "0.4.310"
RUNS_ON = """${{
  (github.event_name == 'pull_request' &&
   github.event.pull_request.head.repo.full_name != github.repository)
  && fromJSON(vars.OMNI_PUBLIC_PR_RUNS_ON_JSON || '["ubuntu-latest"]')
  || fromJSON(vars.OMNI_TRUSTED_CI_RUNS_ON_JSON || '["self-hosted","omnibase-ci"]')
}}"""
OLD_BASH = r"""
if [[ -z "$PR_TITLE" ]]; then
  exit 1
fi
TITLE_LOWER=$(echo "$PR_TITLE" | tr '[:upper:]' '[:lower:]')
if [[ "$PR_AUTHOR" == *"[bot]" ]]; then
  exit 0
fi
if [[ "$TITLE_LOWER" =~ ^(chore\(deps|build\(deps|bump ) ]]; then
  exit 0
fi
if [[ "$TITLE_LOWER" =~ ^(chore:\ release|chore\(release\)|release:) ]]; then
  exit 0
fi
if echo "$PR_TITLE" | grep -qE 'OMN-[0-9]+'; then
  exit 0
fi
exit 1
"""


def _workflow() -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return loaded


def test_workflow_preserves_context_triggers_and_runner() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["pr-title"]
    assert "onex_change_control" not in WORKFLOW.read_text(encoding="utf-8")
    assert "uses" not in job
    assert job["name"] == CONTEXT
    assert "needs" not in job
    assert " ".join(job["runs-on"].split()) == " ".join(RUNS_ON.split())
    assert job["timeout-minutes"] == 10
    assert job["permissions"] == {"contents": "read"}
    assert workflow[True] == {
        "pull_request": {"types": ["opened", "edited", "synchronize", "reopened"]},
    }
    assert list(workflow["jobs"]) == ["pr-title"]


def test_workflow_runs_an_isolated_pinned_release_node() -> None:
    steps = _workflow()["jobs"]["pr-title"]["steps"]
    assert len(steps) == 2
    assert re.fullmatch(r"astral-sh/setup-uv@[0-9a-f]{40}", steps[0]["uses"])
    assert not any("actions/checkout" in step.get("uses", "") for step in steps)
    env = steps[1]["env"]
    assert env["OMNIMARKET_VERSION"] == OMNIMARKET_VERSION
    assert env["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    assert env["PR_AUTHOR"] == "${{ github.event.pull_request.user.login }}"
    script = steps[1]["run"]
    assert '"omnimarket==${OMNIMARKET_VERSION}"' in script
    assert "--no-deps" in script
    assert '"pydantic>=2.11"' in script
    assert "uv venv --quiet --python 3.12" in script
    assert f"-I -m {NODE_MODULE}" in script
    assert "json.dumps" in script
    assert "${{ github.event.pull_request.title }}" not in script


def test_manifest_names_the_local_producer() -> None:
    rows = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["gates"]
    matching = [row for row in rows if row["check_name"] == CONTEXT]
    assert len(matching) == 1
    row = matching[0]
    assert row["producer_kind"] == "local"
    assert row["workflow_file"] == "pr-title-check.yml"
    assert row["workflow_job_key"] == "pr-title"
    assert "cross_repo_ref" not in row
    assert "onex_change_control" not in row["rationale"]


@pytest.fixture(scope="session")
def node_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Install the same pinned wheel and minimal dependency as the workflow."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to exercise the workflow's release node"
    venv = tmp_path_factory.mktemp("pr-title-node") / "venv"
    python = venv / "bin/python"
    for argv in (
        [uv, "venv", "--quiet", "--python", "3.12", str(venv)],
        [
            uv,
            "pip",
            "install",
            "--quiet",
            "--python",
            str(python),
            "--no-deps",
            f"omnimarket=={OMNIMARKET_VERSION}",
        ],
        [uv, "pip", "install", "--quiet", "--python", str(python), "pydantic>=2.11"],
    ):
        result = subprocess.run(
            argv, text=True, capture_output=True, check=False, timeout=90
        )
        assert result.returncode == 0, result.stdout + result.stderr
    return python


@pytest.mark.parametrize(
    ("title", "author", "expected"),
    [
        ("Update dependencies", "dependabot[bot]", 0),
        ("Bare title", "manual[bot]", 0),
        ("chore(deps): update libraries", "human", 0),
        ("CHORE(DEPS): update libraries", "human", 0),
        ("chore(deps-extra): update libraries", "human", 0),
        ("build(deps): update libraries", "human", 0),
        ("BUILD(DEPS): update libraries", "human", 0),
        ("bump package", "human", 0),
        ("BUMP package", "human", 0),
        ("chore: release 1.2.3", "human", 0),
        ("CHORE: RELEASE 1.2.3", "human", 0),
        ("chore(release): 1.2.3", "human", 0),
        ("CHORE(RELEASE): 1.2.3", "human", 0),
        ("release: 1.2.3", "human", 0),
        ("RELEASE: 1.2.3", "human", 0),
        ("ci(OMN-21003): port title check", "human", 0),
        ("ticket OMN-1suffix", "human", 0),
        ("two references OMN-1 OMN-2", "human", 0),
        ("Bare title", "human", 1),
        ("lowercase omn-21003", "human", 1),
        ("missing digits OMN-", "human", 1),
        ("prefix chore(deps): update", "human", 1),
        ("chore(release-extra): update", "human", 1),
        ("bump", "human", 1),
        (" bare title", "human[bot]suffix", 1),
        ("Bare title", "human[BOT]", 1),
        ("", "dependabot[bot]", 1),
        ("", "human", 1),
        ('quotes " and $(false) OMN-21003', "human", 0),
    ],
)
def test_verdicts_equal_the_old_reusable(
    node_python: Path, title: str, author: str, expected: int
) -> None:
    old = subprocess.run(
        ["/bin/bash", "-c", OLD_BASH],
        env={**os.environ, "PR_TITLE": title, "PR_AUTHOR": author},
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    node = subprocess.run(
        [str(node_python), "-I", "-m", NODE_MODULE],
        input=json.dumps({"title": title, "author": author}),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert old.returncode == expected, old.stdout + old.stderr
    assert node.returncode == old.returncode, node.stdout + node.stderr


def test_malformed_request_refuses_with_exit_two(node_python: Path) -> None:
    result = subprocess.run(
        [str(node_python), "-I", "-m", NODE_MODULE],
        input="{",
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2, result.stdout + result.stderr
