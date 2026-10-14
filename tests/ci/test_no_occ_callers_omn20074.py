# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-20074 S6: omniintelligence has no OCC caller left.

Admission requires repo-owned evidence: no event-triggered workflow calls an OCC
reusable, no job waits on the OCC companion or preflight, and the repo-evidence
caller enforces without comparing with OCC. CI Summary judges no OCC job. Definitions
whose only trigger is workflow_call are hosted reusables, not event-triggered callers.

Assertions read parsed YAML, so historical comments do not count as callers.
OMN20074_BASE_TREE can select an archived base tree for the negative control.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(
    os.environ.get("OMN20074_BASE_TREE", Path(__file__).resolve().parents[2])
)
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REQUIRED_CHECKS = REPO_ROOT / ".github" / "required-checks.yaml"
CALLER_PATH = WORKFLOWS / "call-repo-evidence-gate.yml"

_OCC_REUSABLE = re.compile(r"^(?:call-)?occ-[a-z0-9-]+\.ya?ml$")
_OCC_JOB = re.compile(r"occ-(preflight|companion|autobind)")
_OCC_CONTEXTS = frozenset(
    {
        "occ-preflight / eligibility",
        "call-reject-skip-token / occ-preflight / eligibility",
        "verify / verify",
        "OCC Companion Merged Gate (OMN-15214)",
        "occ-companion-effect / Publish occ-companion-effect command",
        "occ-autobind / outcome",
        "occ-autobind / Publish occ-autobind command",
    }
)
_RETIRED_CALLERS = (
    "call-occ-preflight.yml",
    "call-occ-autobind.yml",
    "call-occ-companion-effect.yml",
    "call-receipt-gate.yml",
    "occ-autobind-cancel-recovery.yml",
)
_RETIRED_SCRIPTS = (
    "scripts/ci/occ_manual_replay_precheck.py",
    "scripts/ci/check_occ_companion_merged.py",
)
_RETIRED_PUBLISHERS = {
    "OCC Autobind Publisher",
    "OCC Companion Effect Publisher",
}


def _triggers(data: dict[str, Any]) -> set[str]:
    # PyYAML 1.1 resolves the bare `on:` key to the boolean True.
    on = data.get("on", data.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


def _workflows() -> dict[str, dict[str, Any]]:
    parsed = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path.name
        parsed[path.name] = data
    assert parsed, f"no workflows found in {WORKFLOWS}"
    return parsed


def _jobs() -> list[tuple[str, str, dict[str, Any]]]:
    rows = []
    for name, data in _workflows().items():
        for job_id, job in (data.get("jobs") or {}).items():
            assert isinstance(job, dict), f"{name}:{job_id}"
            rows.append((name, job_id, job))
    return rows


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def test_no_occ_callers_workflow_calls_an_occ_reusable() -> None:
    offenders = []
    for name, data in _workflows().items():
        if _triggers(data) == {"workflow_call"}:
            continue
        for job_id, job in (data.get("jobs") or {}).items():
            uses = job.get("uses")
            if not isinstance(uses, str):
                continue
            reusable = uses.split("@", 1)[0].rsplit("/", 1)[-1]
            if _OCC_REUSABLE.fullmatch(reusable):
                offenders.append(f"{name}:{job_id} -> {reusable}")
    assert not offenders, offenders


def test_no_occ_callers_receipt_gate_runs_only_in_caller_mode() -> None:
    offenders = []
    for name, job_id, job in _jobs():
        uses = job.get("uses")
        if not isinstance(uses, str) or not uses.split("@", 1)[0].endswith(
            "/receipt-gate.yml"
        ):
            continue
        if (job.get("with") or {}).get("evidence-source") != "caller":
            offenders.append(f"{name}:{job_id}")
    assert not offenders, offenders


def test_no_occ_callers_job_waits_on_an_occ_job() -> None:
    offenders = []
    for name, job_id, job in _jobs():
        if _OCC_JOB.search(job_id):
            offenders.append(f"{name}:{job_id} is an OCC job")
        for need in _needs(job):
            if _OCC_JOB.search(need):
                offenders.append(f"{name}:{job_id} needs {need}")
        if "needs.occ-" in str(job.get("if", "")):
            offenders.append(f"{name}:{job_id} conditions on an OCC job")
        for step in job.get("steps") or []:
            if "needs.occ-" in str(step.get("run", "")):
                offenders.append(f"{name}:{job_id} step reads an OCC job")
    assert not offenders, offenders


def test_no_occ_callers_retired_workflows_and_helpers_are_absent() -> None:
    present = [name for name in _RETIRED_CALLERS if (WORKFLOWS / name).exists()]
    assert not present, present
    present = [path for path in _RETIRED_SCRIPTS if (REPO_ROOT / path).exists()]
    assert not present, present


def test_no_occ_callers_workflow_run_recovers_retired_publishers() -> None:
    offenders = []
    for name, data in _workflows().items():
        if "workflow_run" not in _triggers(data):
            continue
        on = data.get("on", data.get(True))
        workflow_run = on.get("workflow_run") if isinstance(on, dict) else None
        publishers = (workflow_run or {}).get("workflows") or []
        if isinstance(publishers, str):
            publishers = [publishers]
        if _RETIRED_PUBLISHERS.intersection(publishers):
            offenders.append(name)
    assert not offenders, offenders


def test_no_occ_callers_ci_resolves_no_occ_evidence_source() -> None:
    ci_jobs = _workflows()["ci.yml"]["jobs"]
    assert "occ-companion-merged" not in ci_jobs
    offenders = []
    for job_id, job in ci_jobs.items():
        for step in job.get("steps") or []:
            run = str(step.get("run", ""))
            for token in ("Evidence-Source", "check_occ_companion_merged"):
                if token in run:
                    offenders.append(f"{job_id}: {step.get('name')} reads {token}")
    assert not offenders, offenders


def test_no_occ_callers_repo_evidence_caller_enforces_without_occ() -> None:
    job = yaml.safe_load(CALLER_PATH.read_text(encoding="utf-8"))["jobs"][
        "repo-evidence"
    ]
    assert job["with"].get("shadow") == "false"
    assert job["with"].get("compare-with-occ") == "false"
    assert "occ-context" not in job["with"]


def test_no_occ_callers_ci_summary_expects_no_occ_context() -> None:
    summary = _workflows()["ci.yml"]["jobs"]["ci-summary"]
    assert not [need for need in _needs(summary) if _OCC_JOB.search(need)]
    script = "\n".join(str(step.get("run", "")) for step in summary.get("steps") or [])
    assert not [context for context in _OCC_CONTEXTS if context in script]
    assert "occ-companion-merged" not in script
    assert "occ-preflight" not in script


def test_no_occ_callers_required_checks_manifest_names_no_occ_context() -> None:
    manifest = yaml.safe_load(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    names = {
        row["check_name"]
        for row in manifest["gates"]
        if isinstance(row, dict) and "check_name" in row
    }
    assert names, "the manifest lists no gate"
    assert not _OCC_CONTEXTS & names
