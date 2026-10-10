# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Exercise the contract gate's checkout boundary and validation outcomes."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit
WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github/workflows/contract-validation.yml"
)


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"]["contract-validation"]["steps"]
    return steps


def test_validator_checkout_uses_an_explicit_immutable_revision() -> None:
    checkouts = [step for step in _steps() if step.get("uses") == "actions/checkout@v4"]
    validator = next(
        step
        for step in checkouts
        if step["with"].get("repository") == "OmniNode-ai/onex_change_control"
    )
    assert re.fullmatch(r"[0-9a-f]{40}", validator["with"]["ref"])
    assert validator["with"]["path"] == ".onex_change_control_validators"
    assert "github.action_ref" not in validator["with"]["ref"]


@pytest.mark.parametrize(
    ("branch", "contract", "validator_exit", "expected_status"),
    [
        ("jonah/omn-20032-fix", "OMN-20032.yaml", 0, "passed"),
        ("jonah/omn-20032-fix", "OMN-20032.yaml", 1, "failed"),
        ("jonah/OMN-20032-fix", "omn-20032.yaml", 0, "passed"),
        ("jonah/omn-20032-fix", None, 0, "skipped"),
        ("dependabot/update", "OMN-20032.yaml", 0, "skipped"),
        ("release/main", None, 0, "skipped"),
    ],
)
def test_validation_outcomes(
    tmp_path: Path,
    branch: str,
    contract: str | None,
    validator_exit: int,
    expected_status: str,
) -> None:
    (tmp_path / "contracts").mkdir()
    if contract:
        (tmp_path / "contracts" / contract).write_text("ticket_id: OMN-20032\n")
    (tmp_path / ".onex_change_control_validators").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$PWD" "$@" > "$UV_CALL"\nexit "$UV_EXIT"\n'
    )
    uv.chmod(0o755)
    output = tmp_path / "output"
    uv_call = tmp_path / "uv-call"
    step = next(step for step in _steps() if step.get("id") == "validate-contract")
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "BRANCH_NAME": branch,
            "GITHUB_OUTPUT": str(output),
            "UV_CALL": str(uv_call),
            "UV_EXIT": str(validator_exit),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert f"validation-status={expected_status}" in output.read_text()
    assert result.returncode == (1 if expected_status == "failed" else 0)
    if expected_status == "skipped":
        assert not uv_call.exists()
    else:
        arguments = uv_call.read_text().splitlines()
        assert arguments[:-1] == [
            str(tmp_path / ".onex_change_control_validators"),
            "run",
            "--locked",
            "validate-yaml",
        ]
        assert contract is not None
        validator_dir = tmp_path / ".onex_change_control_validators"
        assert (validator_dir / arguments[-1]).samefile(
            tmp_path / "contracts" / contract
        )


def test_merge_group_skips_checkout_install_and_validation() -> None:
    steps = _steps()
    resolve = next(step for step in steps if step.get("id") == "resolve-branch")
    assert '"$EVENT_NAME" == "merge_group"' in resolve["run"]
    assert 'echo "skip_validation=true"' in resolve["run"]
    for step in steps[steps.index(resolve) + 1 : -1]:
        assert step["if"] == "steps.resolve-branch.outputs.skip_validation != 'true'"
