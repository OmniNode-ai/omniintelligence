# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Bind the Contract Compliance Check to this repository's own contracts (OMN-20074)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

_REPOSITORY_ROOT = Path(__file__).parents[3]
_WORKFLOW_PATH = _REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
_STEP_NAME = "Validate contract YAML files"


def _job() -> dict[str, Any]:
    workflow = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["contract-compliance"]
    assert isinstance(job, dict)
    return job


def _validation_script() -> str:
    steps = _job()["steps"]
    assert isinstance(steps, list)
    matching_steps = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == _STEP_NAME
    ]
    assert len(matching_steps) == 1
    script = matching_steps[0]["run"]
    assert isinstance(script, str)
    return script


def _write_uv_probe(path: Path) -> None:
    # `uv run python3 - <files>` becomes `<this interpreter> - <files>`.
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "shift\n"  # run
        "shift\n"  # python3
        'exec "$PROBE_PYTHON" "$@"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_validation_script(
    script: str, *, workspace: Path, probe_directory: Path
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PROBE_PYTHON": sys.executable,
        "PATH": f"{probe_directory}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    (workspace / "contracts" / "v1").mkdir(parents=True)
    probe_directory = tmp_path / "bin"
    probe_directory.mkdir()
    _write_uv_probe(probe_directory / "uv")
    return workspace, probe_directory


def _valid_contract() -> Path:
    return _REPOSITORY_ROOT / "contracts" / "OMN-20074.yaml"


def test_contract_compliance_does_not_read_onex_change_control() -> None:
    job = _job()
    assert "onex_change_control" not in yaml.safe_dump(job)
    assert "onex-change-control" not in yaml.safe_dump(job)


def test_onex_change_control_is_not_a_dependency() -> None:
    pyproject = (_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (_REPOSITORY_ROOT / "uv.lock").read_text(encoding="utf-8")
    for text in (pyproject, lock):
        assert "onex-change-control" not in text
        assert "onex_change_control" not in text


def test_contract_compliance_validates_the_repository_contracts_with_locked_core() -> (
    None
):
    script = _validation_script()
    steps = _job()["steps"]
    assert any(
        isinstance(step, dict) and step.get("run") == "uv sync --frozen"
        for step in steps
    )
    assert 'find contracts -maxdepth 1 -type f -name "OMN-*.yaml"' in script
    assert "ModelTicketContract" in script
    assert "working-directory" not in yaml.safe_dump(steps)

    syntax = subprocess.run(
        ["bash", "-n"], input=script, capture_output=True, text=True, check=False
    )
    assert syntax.returncode == 0, syntax.stderr


def test_contract_compliance_accepts_a_valid_contract_and_skips_nested_v1(
    tmp_path: Path,
) -> None:
    workspace, probe_directory = _workspace(tmp_path)
    shutil.copy(_valid_contract(), workspace / "contracts" / "OMN-20074.yaml")
    # contracts/v1 holds a different shape; selecting it would fail this run.
    (workspace / "contracts" / "v1" / "OMN-15669.yaml").write_text(
        "schema_version: occ-contract/v1\n", encoding="utf-8"
    )

    result = _run_validation_script(
        _validation_script(), workspace=workspace, probe_directory=probe_directory
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: 1 ticket contract(s)" in result.stdout


def test_contract_compliance_rejects_a_malformed_contract(tmp_path: Path) -> None:
    workspace, probe_directory = _workspace(tmp_path)
    shutil.copy(_valid_contract(), workspace / "contracts" / "OMN-20074.yaml")
    (workspace / "contracts" / "OMN-99999.yaml").write_text(
        "schema_version: 1.0.0\n", encoding="utf-8"
    )

    result = _run_validation_script(
        _validation_script(), workspace=workspace, probe_directory=probe_directory
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "contracts/OMN-99999.yaml" in result.stdout


def test_contract_compliance_fails_when_no_contract_is_present(tmp_path: Path) -> None:
    workspace, probe_directory = _workspace(tmp_path)

    result = _run_validation_script(
        _validation_script(), workspace=workspace, probe_directory=probe_directory
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "holds no OMN-*.yaml ticket contract" in result.stdout
