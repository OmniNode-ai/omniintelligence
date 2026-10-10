# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-20074: omniintelligence's repo-evidence caller runs in S5 shadow mode.

The caller records the new-path verdict beside OCC's on the same head and must
block nothing: the reusable's ``shadow`` input makes ``repo-evidence / verify``
and ``repo-evidence / dod-verify`` conclude success, and no OCC caller is removed.

Failure modes this catches: the caller dropped ``shadow`` or ``compare-with-occ``
(the check-run would carry a real refusal); the pin moved to a branch name or an
older reusable; the caller moved to ``pull_request`` (a PR could then edit what
judges it); a job name was added (the context prefix would change); an OCC caller
was removed before the S6 ruling; the repo contract lost a falsifier.
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
CALLER = WORKFLOWS / "call-repo-evidence-gate.yml"
CONTRACT = REPO_ROOT / "contracts" / "OMN-20074.yaml"

# 8-character prefix of the squash commit of omnibase_core#1914 on that repository's dev branch: the pin
# omnibase_core's own caller uses. 0.4.305 is the first omnimarket release carrying
# omnimarket#3563, the verifier half of the contract-home marker, and it ships the
# node_dod_verify occ-difference classifier (omnimarket#3277, 0.4.294).
RECEIPT_GATE_PIN_PREFIX = "fb0c6c21"
VERIFIER_FLOOR = (0, 4, 305)


def _load(path: Path) -> dict[Any, Any]:
    assert path.is_file(), f"missing {path}"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _job() -> dict[str, Any]:
    job: dict[str, Any] = _load(CALLER)["jobs"]["repo-evidence"]
    return job


def test_caller_runs_from_the_base_branch_on_dev_and_main() -> None:
    doc = _load(CALLER)
    # YAML 1.1 reads a bare `on` as the boolean True.
    triggers = doc["on"] if "on" in doc else doc[True]
    assert set(triggers) == {"pull_request_target"}
    assert triggers["pull_request_target"]["branches"] == ["dev", "main"]
    assert triggers["pull_request_target"]["types"] == [
        "opened",
        "synchronize",
        "reopened",
        "edited",
        "ready_for_review",
    ]
    assert doc["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert set(doc["jobs"]) == {"repo-evidence"}


def test_caller_job_is_a_bare_call_with_no_secrets() -> None:
    job = _job()
    for key in ("steps", "secrets", "if", "name", "permissions"):
        assert key not in job, f"caller job must not declare {key}"
    assert "secrets: inherit" not in CALLER.read_text(encoding="utf-8")


def test_caller_pins_the_current_receipt_gate_by_full_sha() -> None:
    uses = _job()["uses"]
    assert re.fullmatch(
        r"OmniNode-ai/omnibase_core/\.github/workflows/receipt-gate\.yml@[0-9a-f]{40}",
        uses,
    )
    assert uses.split("@", 1)[1].startswith(RECEIPT_GATE_PIN_PREFIX)


def test_caller_is_in_shadow_mode_and_compares_with_occ() -> None:
    inputs = _job()["with"]
    assert inputs["evidence-source"] == "caller"
    # Quoted strings: the reusable's boolean-like inputs are string inputs.
    assert inputs["shadow"] == "true"
    assert inputs["compare-with-occ"] == "true"
    version = tuple(int(part) for part in inputs["verifier-version"].split("."))
    assert version >= VERIFIER_FLOOR


def test_shadow_caller_removes_no_occ_caller() -> None:
    for name in ("call-occ-autobind.yml", "call-occ-companion-effect.yml"):
        assert (WORKFLOWS / name).is_file(), f"{name} must stay until the S6 ruling"


def test_repo_contract_names_a_falsifier_per_criterion() -> None:
    contract = _load(CONTRACT)
    assert contract["ticket_id"] == "OMN-20074"
    criteria = [ac for req in contract["requirements"] for ac in req["acceptance"]]
    assert criteria, "contract must declare acceptance criteria"
    checks = [
        check["check_value"]
        for item in contract["dod_evidence"]
        for check in item["checks"]
    ]
    for criterion in criteria:
        assert "falsifier:" in criterion["statement"]
        falsifier = criterion["statement"].split("falsifier:", 1)[1].strip()
        assert falsifier in checks, f"{criterion['id']} falsifier has no dod check"
        test_file = falsifier.split()[3]
        assert (REPO_ROOT / test_file).is_file(), f"{test_file} does not exist"
