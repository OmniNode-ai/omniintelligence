# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The lockfile must select one transformers release, with hashed artifacts, that the rl group's lower bound admits (OMN-21878)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _release_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _transformers_packages() -> list[dict[str, object]]:
    packages = tomllib.loads((_ROOT / "uv.lock").read_text())["package"]
    return [p for p in packages if p["name"] == "transformers"]


def _floor() -> tuple[int, ...]:
    rl = tomllib.loads((_ROOT / "pyproject.toml").read_text())["dependency-groups"][
        "rl"
    ]
    specs = [s for s in rl if isinstance(s, str) and s.startswith("transformers")]
    assert len(specs) == 1, specs
    match = re.fullmatch(r"transformers>=(\d+)\.(\d+)\.(\d+)", specs[0])
    assert match, specs[0]
    return tuple(int(g) for g in match.groups())


def test_lock_selects_one_transformers_release() -> None:
    """One transformers entry, with sdist and wheel URLs naming the locked version."""
    matches = _transformers_packages()
    assert len(matches) == 1, matches
    package = matches[0]
    locked = package["version"]
    assert package["sdist"]["url"].endswith(f"/transformers-{locked}.tar.gz")
    assert package["wheels"]
    assert all(
        w["url"].endswith(f"/transformers-{locked}-py3-none-any.whl")
        for w in package["wheels"]
    )


def test_lock_transformers_artifacts_are_consistent() -> None:
    """Every transformers artifact in the lock carries a sha256 hash naming the locked version."""
    (package,) = _transformers_packages()
    locked = package["version"]
    assert package["sdist"]["hash"].startswith("sha256:")
    assert all(w["hash"].startswith("sha256:") for w in package["wheels"])
    assert locked in package["sdist"]["url"]
    assert all(locked in w["url"] for w in package["wheels"])


def test_rl_group_declares_transformers() -> None:
    """The rl group declares a transformers lower bound the locked release meets."""
    (package,) = _transformers_packages()
    assert _release_tuple(package["version"]) >= _floor()
