# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Public-repository runner placement in omniintelligence (OMN-17427).

RULING 2026-10-16T07:07:09Z: "Ci runners should be for private repos only."
omniintelligence is public, so:

* every job in every workflow runs on a literal GitHub-hosted label; no
  ``runs-on`` falls back to the self-hosted fleet or computes its label from a
  variable (this repository has no entry in omnibase_core's baseline, so
  omnibase_core's check refuses a computed ``runs-on``);
* omnibase_core's check-public-runner-placement runs as a CI job that CI
  Summary requires and as a pre-commit hook, at the same core release.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
PRECOMMIT = REPO_ROOT / ".pre-commit-config.yaml"

FLEET_FALLBACK = '["self-hosted","omnibase-ci"]'
HOSTED_LABEL = re.compile(r"^(ubuntu|windows|macos)-[\w.\-]+$", re.IGNORECASE)
JOB_ID = "public-runner-placement"
JOB_NAME = "Public Runner Placement (OMN-17427)"
HOOK_ID = "check-public-runner-placement"
CORE_RELEASE = "0.47.46"


def _load(path: Path) -> dict[Any, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def fleet_lines(text: str) -> list[str]:
    """Code lines (not comments) that fall back to the fleet or read a runner variable."""
    return [
        line.strip()
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
        and (FLEET_FALLBACK in line or "_RUNS_ON_JSON" in line)
    ]


def not_hosted(runs_on: object) -> bool:
    """True when a ``runs-on`` value is not a literal GitHub-hosted label."""
    if isinstance(runs_on, str):
        return not HOSTED_LABEL.match(runs_on.strip())
    if isinstance(runs_on, list):
        return not runs_on or any(not_hosted(label) for label in runs_on)
    return True


def test_fleet_detector_positive_control() -> None:
    planted = (
        "    runs-on: ${{ fromJSON(vars.OMNI_TRUSTED_CI_RUNS_ON_JSON || "
        """'["self-hosted","omnibase-ci"]') }}\n"""
    )
    comment = "    # trusted events used the self-hosted omnibase-ci fleet\n"
    canary = "          printf 'runs-on: [self-hosted, omnibase-ci]\\n' > canary.yml\n"
    assert fleet_lines(planted) == [planted.strip()]
    assert fleet_lines(comment) == []
    assert fleet_lines(canary) == []
    assert not_hosted("${{ fromJSON(vars.OMNI_TRUSTED_CI_RUNS_ON_JSON) }}")
    assert not_hosted(["self-hosted", "omnibase-ci"])
    assert not_hosted({"group": "fleet"})
    assert not not_hosted("ubuntu-latest")
    assert not not_hosted(["ubuntu-latest"])


def test_no_workflow_names_the_self_hosted_fleet() -> None:
    offenders = {
        path.name: found
        for path in sorted(WORKFLOWS.glob("*.y*ml"))
        if (found := fleet_lines(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}, (
        "A public repository's CI must run on GitHub-hosted runners "
        "(RULING 2026-10-16T07:07:09Z): " + repr(offenders)
    )


def test_every_job_runs_on_a_literal_hosted_label() -> None:
    offenders: dict[str, str] = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        jobs = _load(path).get("jobs")
        assert isinstance(jobs, dict), path.name
        for job_id, job in jobs.items():
            if (
                isinstance(job, dict)
                and "runs-on" in job
                and not_hosted(job["runs-on"])
            ):
                offenders[f"{path.name}:{job_id}"] = repr(job["runs-on"])
    assert offenders == {}, offenders


def _ci_job() -> dict[str, Any]:
    jobs = _load(CI_WORKFLOW)["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[JOB_ID]
    assert isinstance(job, dict)
    return job


def _hooks() -> list[tuple[str, dict[str, Any]]]:
    repos = _load(PRECOMMIT)["repos"]
    assert isinstance(repos, list)
    return [
        (str(repo["rev"]), hook)
        for repo in repos
        if isinstance(repo, dict)
        for hook in repo.get("hooks", [])
        if isinstance(hook, dict) and hook.get("id") == HOOK_ID
    ]


def test_ci_job_runs_the_core_check_unconditionally_on_a_hosted_runner() -> None:
    job = _ci_job()
    assert job["name"] == JOB_NAME
    assert job["runs-on"] == "ubuntu-latest"
    assert "needs" not in job
    assert "if" not in job
    steps = job["steps"]
    assert isinstance(steps, list)
    runs = "\n".join(str(step.get("run", "")) for step in steps)
    assert "omnibase_core.handlers.handler_public_runner_placement_cli" in runs
    assert "POSITIVE CONTROL FAILED" in runs
    assert "--base-ref" in runs
    assert "--repo omniintelligence --visibility public" in runs
    assert "args=(--repo omniintelligence --visibility public)" in runs


def test_ci_job_and_hook_run_the_same_core_release() -> None:
    """The CI job installs 0.47.46 and the hook's rev is that release's tag."""
    env = _ci_job()["env"]
    assert isinstance(env, dict)
    assert env["RUNNER_PLACEMENT_CORE"] == f"omnibase-core=={CORE_RELEASE}"
    hooks = _hooks()
    assert len(hooks) == 1, f"expected one {HOOK_ID} hook, found {len(hooks)}"
    assert hooks[0][0] == f"v{CORE_RELEASE}"


def test_precommit_hook_names_this_public_repository() -> None:
    hooks = _hooks()
    assert hooks
    assert hooks[0][1]["args"] == [
        "--repo",
        "omniintelligence",
        "--visibility",
        "public",
    ]


def test_ci_summary_requires_the_job_to_succeed() -> None:
    summary = _load(CI_WORKFLOW)["jobs"]["ci-summary"]
    assert JOB_ID in summary["needs"]
    assert summary["if"] == "always()"
    step_text = "\n".join(str(step.get("run", "")) for step in summary["steps"])
    assert 'if [[ "${{ needs.public-runner-placement.result }}" != "success" ]]' in (
        step_text
    )


def _normalization_symmetry_module() -> str:
    repos = _load(PRECOMMIT)["repos"]
    assert isinstance(repos, list)
    entries = [
        str(hook["entry"])
        for repo in repos
        if isinstance(repo, dict)
        for hook in repo.get("hooks", [])
        if isinstance(hook, dict) and hook.get("id") == "normalization-symmetry"
    ]
    assert len(entries) == 1
    match = re.search(r"-m (\S+)", entries[0])
    assert match, entries[0]
    return match.group(1)


def test_normalization_symmetry_hook_runs_an_importable_module() -> None:
    """The hook's `python -m` target exists in the installed omnibase_core."""
    module = _normalization_symmetry_module()
    assert importlib.util.find_spec(module) is not None, module
    assert (
        importlib.util.find_spec("omnibase_core.validators.normalization-symmetry")
        is None
    )
