# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Bind the legacy OCC contract validator to its top-level namespace."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_REPOSITORY_ROOT = Path(__file__).parents[3]
_WORKFLOW_PATH = _REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
_STEP_NAME = "Validate contract YAML files"


def _validation_script() -> str:
    workflow = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["contract-compliance"]
    assert isinstance(job, dict)
    steps = job["steps"]
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
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf \'%s\\n\' "$@" > "$CAPTURE_PATH"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_validation_script(
    script: str,
    *,
    workspace: Path,
    capture_path: Path,
    probe_directory: Path,
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "CAPTURE_PATH": str(capture_path),
        "GITHUB_WORKSPACE": str(workspace),
        "PATH": f"{probe_directory}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=workspace / "onex_change_control",
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_contract_compliance_uses_root_only_array_safe_selection() -> None:
    script = _validation_script()

    assert "mapfile -t CONTRACTS < <(" in script
    assert (
        'find "$GITHUB_WORKSPACE/onex_change_control/contracts" '
        '-maxdepth 1 -type f -name "OMN-*.yaml"' in script
    )
    assert 'if [ "${#CONTRACTS[@]}" -eq 0 ]; then' in script
    assert 'uv run validate-yaml "${CONTRACTS[@]}"' in script
    assert "CONTRACTS=$(find" not in script
    assert "uv run validate-yaml $CONTRACTS" not in script

    syntax = subprocess.run(
        ["bash", "-n"],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_contract_compliance_excludes_v1_and_preserves_argv_boundaries(
    tmp_path: Path,
) -> None:
    script = _validation_script()
    workspace = tmp_path / "workspace"
    contract_root = workspace / "onex_change_control" / "contracts"
    nested_v1 = contract_root / "v1"
    probe_directory = tmp_path / "bin"
    nested_v1.mkdir(parents=True)
    probe_directory.mkdir()

    first = contract_root / "OMN-16062.yaml"
    spaced = contract_root / "OMN-16062 fixture.yaml"
    nested = nested_v1 / "OMN-15669.yaml"
    for path in (first, spaced, nested):
        path.write_text("schema_version: 1.0.0\n", encoding="utf-8")

    capture_path = tmp_path / "captured-argv.txt"
    _write_uv_probe(probe_directory / "uv")
    result = _run_validation_script(
        script,
        workspace=workspace,
        capture_path=capture_path,
        probe_directory=probe_directory,
    )

    assert result.returncode == 0, result.stderr
    captured = capture_path.read_text(encoding="utf-8").splitlines()
    assert captured[:2] == ["run", "validate-yaml"]
    assert set(captured[2:]) == {str(first), str(spaced)}
    assert str(nested) not in captured


def test_contract_compliance_zero_match_exits_without_invoking_validator(
    tmp_path: Path,
) -> None:
    script = _validation_script()
    workspace = tmp_path / "workspace"
    nested_v1 = workspace / "onex_change_control" / "contracts" / "v1"
    probe_directory = tmp_path / "bin"
    nested_v1.mkdir(parents=True)
    probe_directory.mkdir()
    (nested_v1 / "OMN-15669.yaml").write_text(
        "schema_version: occ-contract/v1\n",
        encoding="utf-8",
    )

    capture_path = tmp_path / "captured-argv.txt"
    _write_uv_probe(probe_directory / "uv")
    result = _run_validation_script(
        script,
        workspace=workspace,
        capture_path=capture_path,
        probe_directory=probe_directory,
    )

    assert result.returncode == 0, result.stderr
    assert "No contract YAML files found" in result.stdout
    assert not capture_path.exists()
