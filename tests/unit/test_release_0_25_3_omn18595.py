# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A release declares one version in pyproject.toml, the uv.lock root entry and a CHANGELOG block, and keeps transformers locked (OMN-18595)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _release_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _pyproject() -> dict:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text())


def _lock() -> dict:
    return tomllib.loads((_ROOT / "uv.lock").read_text())


def _project_version() -> str:
    return _pyproject()["project"]["version"]


def test_pyproject_version_is_not_below_0_25_3() -> None:
    """The declared version is a three-part number at or above 0.25.3."""
    version = _project_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    assert _release_tuple(version) >= (0, 25, 3)


def test_lock_root_entry_matches_pyproject_version() -> None:
    """The uv.lock editable root entry carries exactly the declared version."""
    root = [
        package
        for package in _lock()["package"]
        if package["name"] == "omninode-intelligence"
        and package.get("source") == {"editable": "."}
    ]
    assert len(root) == 1
    assert root[0]["version"] == _project_version()


def test_changelog_has_block_for_pyproject_version() -> None:
    """CHANGELOG.md has a heading for the declared version."""
    lines = (_ROOT / "CHANGELOG.md").read_text().splitlines()
    version = _project_version()
    assert any(line.startswith(f"## v{version} ") for line in lines)


def test_lock_keeps_transformers_at_or_above_declared_floor() -> None:
    """The lock keeps one transformers entry at or above the rl group's floor."""
    rl = _pyproject()["dependency-groups"]["rl"]
    specs = [s for s in rl if isinstance(s, str) and s.startswith("transformers")]
    assert len(specs) == 1, specs
    match = re.fullmatch(r"transformers>=(\d+)\.(\d+)\.(\d+)", specs[0])
    assert match, specs[0]
    floor = tuple(int(g) for g in match.groups())
    packages = [p for p in _lock()["package"] if p["name"] == "transformers"]
    assert len(packages) == 1
    assert packages[0].get("sdist") or packages[0].get("wheels")
    assert _release_tuple(packages[0]["version"]) >= floor
