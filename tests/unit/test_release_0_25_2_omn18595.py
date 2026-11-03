# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Preserve the 0.25.2 release floor while permitting later releases (OMN-18595)."""

from __future__ import annotations

import tomllib
from contextlib import nullcontext
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSION = "0.25.2"


def _lock() -> dict:
    return tomllib.loads((_ROOT / "uv.lock").read_text())


def _release_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_pyproject_declares_0_25_2() -> None:
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    assert _release_tuple(project["version"]) >= _release_tuple(_VERSION)


def test_lock_root_entry_declares_0_25_2() -> None:
    root = [
        package
        for package in _lock()["package"]
        if package["name"] == "omninode-intelligence"
        and package.get("source") == {"editable": "."}
    ]
    assert len(root) == 1
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    assert root[0]["version"] == project["version"]
    assert _release_tuple(root[0]["version"]) >= _release_tuple(_VERSION)


def test_changelog_has_0_25_2_block() -> None:
    lines = (_ROOT / "CHANGELOG.md").read_text().splitlines()
    assert any(line.startswith(f"## v{_VERSION} ") for line in lines)
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    assert any(line.startswith(f"## v{project['version']} ") for line in lines)


def test_lock_keeps_transformers_5_10_1() -> None:
    packages = [p for p in _lock()["package"] if p["name"] == "transformers"]
    assert len(packages) == 1
    assert _release_tuple(packages[0]["version"]) >= (5, 10, 1)
    assert packages[0].get("sdist") or packages[0].get("wheels")


@pytest.mark.parametrize(
    ("version", "locked_version", "transformers", "changelog_version", "passes"),
    [
        ("0.25.2", "0.25.2", "5.10.1", "0.25.2", True),
        ("0.25.3", "0.25.3", "5.22.1", "0.25.3", True),
        ("0.25.10", "0.25.10", "5.22.1", "0.25.10", True),
        ("0.26.0", "0.26.0", "5.22.1", "0.26.0", True),
        ("0.25.1", "0.25.1", "5.10.1", "0.25.1", False),
        ("0.25.3", "0.25.2", "5.22.1", "0.25.3", False),
        ("0.25.3", "0.25.3", "5.10.0", "0.25.3", False),
        ("0.25.3", "0.25.3", "5.22.1", "0.25.2", False),
    ],
)
def test_release_check_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
    locked_version: str,
    transformers: str,
    changelog_version: str,
    passes: bool,
) -> None:
    """Later releases pass; downgrades, stale locks and missing entries fail."""
    monkeypatch.setattr(f"{__name__}._ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "omninode-intelligence"\n'
        f'version = "{locked_version}"\nsource = {{ editable = "." }}\n'
        '[[package]]\nname = "transformers"\n'
        f'version = "{transformers}"\nsdist = {{ url = "artifact" }}\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(
        f"## v{changelog_version} release\n## v0.25.2 historical release\n"
    )
    with nullcontext() if passes else pytest.raises(AssertionError):
        test_pyproject_declares_0_25_2()
        test_lock_root_entry_declares_0_25_2()
        test_changelog_has_0_25_2_block()
        test_lock_keeps_transformers_5_10_1()
