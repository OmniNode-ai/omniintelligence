# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The lockfile must select transformers 5.10.1 for the opt-in rl group (OMN-21878)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSION = "5.10.1"


def _transformers_packages() -> list[dict[str, object]]:
    packages = tomllib.loads((_ROOT / "uv.lock").read_text())["package"]
    return [p for p in packages if p["name"] == "transformers"]


def test_lock_selects_transformers_5_10_1() -> None:
    """One transformers entry, with sdist and wheel URLs for 5.10.1."""
    matches = _transformers_packages()
    assert len(matches) == 1, matches
    package = matches[0]
    assert package["version"] == _VERSION
    assert package["sdist"]["url"].endswith(f"/transformers-{_VERSION}.tar.gz")
    assert package["wheels"]
    assert all(
        w["url"].endswith(f"/transformers-{_VERSION}-py3-none-any.whl")
        for w in package["wheels"]
    )


def test_lock_transformers_artifacts_are_consistent() -> None:
    """Every transformers artifact in the lock carries a hash and names 5.10.1."""
    (package,) = _transformers_packages()
    assert package["sdist"]["hash"].startswith("sha256:")
    assert all(w["hash"].startswith("sha256:") for w in package["wheels"])
    assert _VERSION in package["sdist"]["url"]
    assert all(_VERSION in w["url"] for w in package["wheels"])


def test_rl_group_declares_transformers() -> None:
    """The rl group declares transformers with a lower bound the locked 5.10.1 meets."""
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    rl = pyproject["dependency-groups"]["rl"]
    specs = [s for s in rl if isinstance(s, str) and s.startswith("transformers")]
    assert len(specs) == 1, specs
    match = re.fullmatch(r"transformers>=(\d+)\.(\d+)\.(\d+)", specs[0])
    assert match, specs[0]
    floor = tuple(int(g) for g in match.groups())
    locked = tuple(int(g) for g in _VERSION.split("."))
    assert locked >= floor
