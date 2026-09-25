# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

import subprocess
from pathlib import Path

from scripts.validation.check_kafka_no_hardcoded_fallback import main as kafka_main
from scripts.validation.validate_naming import IntelligenceNamingConventionValidator

REPO_ROOT = Path(__file__).resolve().parents[3]


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
