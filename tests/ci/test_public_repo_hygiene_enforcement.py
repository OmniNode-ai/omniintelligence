# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The public-repo hygiene gate blocks five content classes on added lines (OMN-20783).

This repository's ``.public-repo-hygiene.yaml`` declared ``mode: report`` with no
``enforce_classes``, so the gate recorded findings and blocked nothing. It now
declares the same enforcement the gate's home repository carries since OMN-19835:
``enforce_scope: added-lines`` plus the five internal-content classes, so a pull
request that ADDS a private repository name, internal-KB prose, a lab-config
literal, a person name or a private address goes red while the residue already in
the tree stays reported.

Asserted statically, in the same change that wires both halves of the check:

* the repo config enforces the five classes on added lines;
* the CI caller and the pre-commit hook run the gate at the SAME omniclaude
  revision, so a local verdict and a CI verdict cannot diverge;
* the pre-commit hook runs on every commit (no ``stages`` or ``files`` narrowing);
* the CI ``pre-commit`` job hands the hook the private vocabulary, because the
  hook fails closed without it and ``test_precommit_staged_scope_omn19612`` forbids
  skipping any hook in that job.

The live falsifiers are a scratch branch carrying one planted literal (CI) and
``pre-commit run public-repo-hygiene --files <planted file>`` (hook).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_CONFIG = REPO_ROOT / ".public-repo-hygiene.yaml"
HYGIENE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "public-repo-hygiene.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

GATE_REPO = "OmniNode-ai/omniclaude"
HOOK_ID = "public-repo-hygiene"
REUSABLE = ".github/workflows/public-repo-hygiene-reusable.yml"
ENFORCED_CLASSES = frozenset(
    {
        "private-repo-name",
        "internal-kb-prose",
        "lab-config",
        "person-name",
        "private-network",
    }
)
SHA = re.compile(r"^[0-9a-f]{40}$")


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} did not parse to a mapping"
    return loaded


def enforcement_gaps(config: dict[str, Any]) -> list[str]:
    """Return what ``config`` lacks to block the five classes on added lines."""
    gaps: list[str] = []
    if config.get("enforce_scope") != "added-lines":
        gaps.append(f"enforce_scope is {config.get('enforce_scope')!r}")
    declared = set(config.get("enforce_classes") or [])
    missing = sorted(ENFORCED_CLASSES - declared)
    if missing:
        gaps.append(f"enforce_classes lacks {missing}")
    unknown = sorted(declared - ENFORCED_CLASSES)
    if unknown:
        gaps.append(f"enforce_classes carries unexpected {unknown}")
    return gaps


def _caller_pin() -> str:
    jobs = _load(HYGIENE_WORKFLOW)["jobs"]
    uses = jobs["public-repo-hygiene"]["uses"]
    prefix = f"{GATE_REPO}/{REUSABLE}@"
    assert uses.startswith(prefix), (
        f"caller does not use the omniclaude reusable: {uses}"
    )
    pin = uses.removeprefix(prefix)
    assert SHA.match(pin), f"caller pin is not a 40-hex commit: {pin}"
    return pin


def _hook_entry() -> tuple[dict[str, Any], dict[str, Any]]:
    for repository in _load(PRECOMMIT_CONFIG)["repos"]:
        if repository.get("repo") != f"https://github.com/{GATE_REPO}":
            continue
        for hook in repository.get("hooks", []):
            if hook.get("id") == HOOK_ID:
                return repository, hook
    pytest.fail(f"no {HOOK_ID} hook from {GATE_REPO} in .pre-commit-config.yaml")


def test_detector_flags_a_report_only_config() -> None:
    """Positive control: the gap finder must flag the config this change replaces."""
    report_only = {"mode": "report", "allowed_top_level": [".github"]}
    assert enforcement_gaps(report_only) == [
        "enforce_scope is None",
        f"enforce_classes lacks {sorted(ENFORCED_CLASSES)}",
    ]
    partial = {
        "enforce_scope": "added-lines",
        "enforce_classes": ["lab-config", "private-network"],
    }
    assert enforcement_gaps(partial) == [
        "enforce_classes lacks ['internal-kb-prose', 'person-name', 'private-repo-name']"
    ]


def test_repo_config_enforces_five_classes_on_added_lines() -> None:
    assert enforcement_gaps(_load(HYGIENE_CONFIG)) == []


def test_ci_caller_and_hook_run_the_gate_at_the_same_revision() -> None:
    repository, _hook = _hook_entry()
    assert SHA.match(str(repository.get("rev"))), "hook rev is not a 40-hex commit"
    assert repository["rev"] == _caller_pin()


def test_hook_runs_on_every_commit() -> None:
    _repository, hook = _hook_entry()
    assert "pre-commit" in hook.get("stages", ["pre-commit"])
    assert "files" not in hook
    assert "exclude" not in hook
    assert "args" not in hook, (
        "the hook's own arguments (diff source) must not be overridden"
    )


def test_ci_pre_commit_job_hands_the_hook_the_vocabulary() -> None:
    job = _load(CI_WORKFLOW)["jobs"]["pre-commit"]
    text = yaml.safe_dump(job)
    assert "OMNI_HYGIENE_VOCAB_PATH" in text
    assert "SKIP" not in job.get("env", {})
    assert "SKIP=" not in text
