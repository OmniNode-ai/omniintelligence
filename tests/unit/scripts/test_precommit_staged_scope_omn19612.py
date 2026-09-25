# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.validation.check_kafka_no_hardcoded_fallback import main as kafka_main
from scripts.validation.validate_naming import IntelligenceNamingConventionValidator

REPO_ROOT = Path(__file__).resolve().parents[3]
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS = REPO_ROOT / ".github" / "required-checks.yaml"

JOB_ID = "pre-commit"
JOB_NAME = "Pre-commit Hooks"

pytestmark = pytest.mark.unit


def _load_mapping(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} did not parse to a mapping"
    return loaded


def _workflow() -> dict:
    return _load_mapping(CI_WORKFLOW)


def _job() -> dict:
    job = _workflow()["jobs"][JOB_ID]
    assert job["name"] == JOB_NAME
    return job


def _suite_step() -> dict:
    matches = [
        step
        for step in _job()["steps"]
        if "pre-commit run --all-files" in str(step.get("run", ""))
    ]
    assert len(matches) == 1, (
        f"expected one whole-tree pre-commit step in {JOB_ID}, found {len(matches)}"
    )
    return matches[0]


def _staged_scoped_hook_ids() -> set[str]:
    """Return pre-commit-stage hooks whose file input is the staged diff."""
    config = _load_mapping(PRECOMMIT_CONFIG)
    default_stages = config.get("default_stages", ["pre-commit"])
    hook_ids: set[str] = set()
    for repository in config["repos"]:
        for hook in repository.get("hooks", []):
            stages = hook.get("stages", default_stages)
            if "pre-commit" not in stages:
                continue
            if hook.get("pass_filenames", True) is False:
                continue
            hook_ids.add(str(hook["id"]))
    return hook_ids


def test_every_staged_scoped_hook_has_whole_tree_coverage() -> None:
    staged_ids = _staged_scoped_hook_ids()
    assert staged_ids, "expected at least one staged-file-scoped hook"

    step = _suite_step()
    command = str(step["run"])
    assert "SKIP" not in _job().get("env", {})
    assert "SKIP" not in step.get("env", {})
    assert "SKIP=" not in command

    for hook_id in sorted(staged_ids):
        assert "pre-commit run --all-files" in command, (
            f"{hook_id} is staged-file-scoped but has no whole-tree counterpart"
        )


def test_whole_tree_job_and_step_are_unconditional_and_blocking() -> None:
    job = _job()
    step = _suite_step()
    assert "if" not in job
    assert "needs" not in job
    assert job.get("continue-on-error") is not True
    assert "if" not in step
    assert step.get("continue-on-error") is not True


def test_whole_tree_job_is_required_through_fail_closed_gates() -> None:
    workflow = _workflow()
    quality_gate = workflow["jobs"]["quality-gate"]
    assert JOB_ID in quality_gate["needs"]
    quality_commands = "\n".join(
        str(step.get("run", "")) for step in quality_gate["steps"]
    )
    assert "needs.pre-commit.result" in quality_commands

    ci_summary = workflow["jobs"]["ci-summary"]
    assert "quality-gate" in ci_summary["needs"]

    manifest = _load_mapping(REQUIRED_CHECKS)
    required_gate_ids = {
        str(gate.get("workflow_job_key")) for gate in manifest["gates"]
    }
    assert {"quality-gate", "ci-summary"} <= required_gate_ids

    documented = [
        check for check in manifest["checks"] if check.get("workflow_job_key") == JOB_ID
    ]
    assert len(documented) == 1
    assert documented[0].get("aggregated_by") == "Quality Gate"

    excluded = [
        check
        for check in manifest.get("excluded_checks", [])
        if check.get("name") == JOB_NAME
    ]
    assert len(excluded) == 1
    assert "Aggregated by Quality Gate" in str(excluded[0].get("reason", ""))


def test_workflow_has_no_pull_request_paths_filter() -> None:
    workflow = _workflow()
    triggers = workflow[True] if True in workflow else workflow["on"]
    pull_request = triggers.get("pull_request") or {}
    assert "paths" not in pull_request
    assert "paths-ignore" not in pull_request


def test_kafka_guard_only_checks_supplied_files(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    dirty = tmp_path / "dirty.py"
    clean.write_text("value = 1\n", encoding="utf-8")
    dirty.write_text(
        'value = os.getenv("KAFKA_HOST", "localhost:9092")\n', encoding="utf-8"
    )

    assert kafka_main([str(clean)]) == 0
    assert kafka_main([str(dirty)]) == 1


def test_naming_validator_only_checks_supplied_files(tmp_path: Path) -> None:
    repo = tmp_path / "src" / "omniintelligence"
    models = repo / "models"
    models.mkdir(parents=True)
    clean = models / "model_clean.py"
    dirty = models / "wrong.py"
    clean.write_text("class ModelClean:\n    pass\n", encoding="utf-8")
    dirty.write_text("class Wrong:\n    pass\n", encoding="utf-8")

    validator = IntelligenceNamingConventionValidator(repo, [clean])
    assert validator.validate_naming_conventions()
    assert all(
        str(dirty) not in violation.file_path for violation in validator.violations
    )


def test_cloud_bus_guard_catches_staged_and_full_violation(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts/check_no_cloud_bus_wrapper.sh"
    clean = tmp_path / "clean.py"
    dirty = tmp_path / "dirty.py"
    clean.write_text("value = 'example.invalid'\n", encoding="utf-8")
    dirty.write_text(f"value = 'broker:{29_092}'\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "clean.py", "dirty.py"], cwd=tmp_path, check=True)

    assert (
        subprocess.run(["bash", str(script), str(clean)], check=False).returncode == 0
    )
    assert (
        subprocess.run(["bash", str(script), str(dirty)], check=False).returncode == 1
    )
    assert (
        subprocess.run(["bash", str(script)], cwd=tmp_path, check=False).returncode == 1
    )
