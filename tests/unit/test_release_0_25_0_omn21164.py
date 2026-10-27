# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""dev declares 0.25.0 and the changelog covers the window since v0.24.0 (OMN-21164)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSION = "0.25.0"


def test_pyproject_declares_release_version() -> None:
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == _VERSION


def test_lock_root_entry_declares_release_version() -> None:
    lock = tomllib.loads((_ROOT / "uv.lock").read_text())
    root = [
        package
        for package in lock["package"]
        if package["name"] == "omninode-intelligence"
        and package.get("source") == {"editable": "."}
    ]
    assert [package["version"] for package in root] == [_VERSION]


def test_changelog_has_release_entry_for_window() -> None:
    changelog = _ROOT / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md is missing"
    lines = changelog.read_text().splitlines()
    heading = f"## v{_VERSION} "
    starts = [i for i, line in enumerate(lines) if line.startswith(heading)]
    assert len(starts) == 1, f"expected one {heading!r} block"
    rest = lines[starts[0] + 1 :]
    end = next((i for i, line in enumerate(rest) if line.startswith("## ")), len(rest))
    block = "\n".join(rest[:end])
    assert "v0.24.0" in block, (
        "the release block does not name the window since v0.24.0"
    )
