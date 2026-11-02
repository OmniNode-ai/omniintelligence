# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The 0.25.2 release declares its version, lock root entry, changelog block and transformers pin (OMN-18595)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSION = "0.25.2"


def _lock() -> dict:
    return tomllib.loads((_ROOT / "uv.lock").read_text())


def test_pyproject_declares_0_25_2() -> None:
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == _VERSION


def test_lock_root_entry_declares_0_25_2() -> None:
    root = [
        package
        for package in _lock()["package"]
        if package["name"] == "omninode-intelligence"
        and package.get("source") == {"editable": "."}
    ]
    assert len(root) == 1
    assert root[0]["version"] == _VERSION


def test_changelog_has_0_25_2_block() -> None:
    lines = (_ROOT / "CHANGELOG.md").read_text().splitlines()
    assert any(line.startswith(f"## v{_VERSION} ") for line in lines)


def test_lock_keeps_transformers_5_10_1() -> None:
    packages = [p for p in _lock()["package"] if p["name"] == "transformers"]
    assert len(packages) == 1
    assert packages[0]["version"] == "5.10.1"
    assert packages[0].get("sdist") or packages[0].get("wheels")
