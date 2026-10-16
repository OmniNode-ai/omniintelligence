# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-20074: the last live OCC dependencies of omniintelligence are gone.

After the S6 caller cut-over four pieces still leaned on the retired change-control
repository:

* ``scripts/check_dep_provenance.py`` exempted the ``onex-change-control`` package from
  its staleness check, though no such dependency exists;
* ``main-target-guard.yml`` admitted a ``dev`` head that carried a
  ``promotion-receipt: OCC-<n>`` line, a receipt id nothing mints any more;
* ``architecture-handshakes/validator-requirements.yaml`` listed that repository as a
  fleet member and as the source of two hooks that omnibase_core now exports;
* ``scripts/validation/reject_deploy_gate_skip_token.sh`` told the author to push OCC
  receipts.

Each test runs the shipped artifact, and each has a negative control so a check that
refused everything (or nothing) fails here.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED_PACKAGE = "onex-change-control"
RETIRED_REPO = "onex_change_control"
PROVENANCE_SCRIPT = REPO_ROOT / "scripts" / "check_dep_provenance.py"
GUARD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "main-target-guard.yml"
VALIDATOR_REQUIREMENTS = (
    REPO_ROOT / "architecture-handshakes" / "validator-requirements.yaml"
)
SKIP_TOKEN_HOOK = (
    REPO_ROOT / "scripts" / "validation" / "reject_deploy_gate_skip_token.sh"
)

GUARD_STEP = "Check PR target branch"
PINNED_SHA = "a1" * 20


def _provenance_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_dep_provenance", PROVENANCE_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pin_block(package: str, repo: str) -> str:
    return (
        "[tool.uv.sources]\n"
        f'{package} = {{ git = "https://github.com/OmniNode-ai/{repo}.git", '
        f'rev = "{PINNED_SHA}" }}\n'
    )


@pytest.mark.parametrize(
    ("package", "repo"),
    [
        pytest.param(RETIRED_PACKAGE, RETIRED_REPO, id="retired-package"),
        pytest.param("omnimarket", "omnimarket", id="live-package-control"),
    ],
)
def test_no_package_is_exempt_from_the_staleness_check(package: str, repo: str) -> None:
    module = _provenance_module()
    resolved: list[str] = []

    def resolver(git_url: str, pinned_sha: str, base_ref: str) -> int:
        resolved.append(pinned_sha)
        return 217

    violations = module.find_staleness_violations(
        '[project]\nname = "x"\n\n' + _pin_block(package, repo),
        max_commits_behind=50,
        resolver=resolver,
    )

    assert resolved == [PINNED_SHA], f"{package} was never resolved: exempted"
    assert len(violations) == 1


def _guard_program() -> str:
    workflow = yaml.safe_load(GUARD_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["main-target-guard"]["steps"]
    named = [step for step in steps if step.get("name") == GUARD_STEP]
    assert len(named) == 1, f"expected exactly one step named {GUARD_STEP!r}"
    return str(named[0]["run"])


def _run_guard(base: str, head: str, body: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "BASE_REF": base,
        "HEAD_REF": head,
        "PR_BODY": body,
    }
    return subprocess.run(
        ["bash", "-e", "-c", _guard_program()],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("head", "body"),
    [
        pytest.param("dev", "promotion-receipt: OCC-1234", id="promotion-from-dev"),
        pytest.param(
            "promotion/next", "promotion-receipt: OCC-1234", id="promotion-branch"
        ),
        pytest.param("dev", "", id="dev-without-receipt"),
        pytest.param("feature/OMN-1-thing", "", id="feature-branch"),
    ],
)
def test_main_target_guard_refuses_every_pr_onto_main(head: str, body: str) -> None:
    result = _run_guard("main", head, body)

    assert result.returncode != 0, f"PR from {head!r} onto main admitted"
    assert "::error::" in result.stdout
    assert "dev" in result.stdout, "the refusal must name dev as the base to use"


@pytest.mark.parametrize(
    "head",
    [
        pytest.param("automation/bump-dependency", id="automation-head"),
        pytest.param("feature/OMN-1-thing", id="feature-branch"),
    ],
)
def test_main_target_guard_admits_a_pr_onto_dev(head: str) -> None:
    result = _run_guard("dev", head, "")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "::error::" not in result.stdout


def test_main_target_guard_asks_for_no_occ_receipt() -> None:
    text = GUARD_WORKFLOW.read_text(encoding="utf-8")

    assert "OCC-" not in text
    assert "promotion-receipt" not in yaml.safe_dump(_guard_program())


def test_validator_requirements_names_no_change_control_repo() -> None:
    text = VALIDATOR_REQUIREMENTS.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    assert RETIRED_REPO not in text
    assert RETIRED_PACKAGE not in text
    # Control: the fleet list still names the repositories that are live.
    assert "omniintelligence" in data["known_repos"]
    assert "omnibase_core" in data["known_repos"]
    for name in ("no-hardcoded-topics", "no-untracked-todos"):
        assert data["required_validators"][name]["central_source"].startswith(
            "omnibase_core"
        )


def test_skip_token_hook_points_at_repo_owned_evidence() -> None:
    text = SKIP_TOKEN_HOOK.read_text(encoding="utf-8")

    assert "OCC" not in text
    assert "contracts/" in text, "the hook must still say where the evidence lives"
