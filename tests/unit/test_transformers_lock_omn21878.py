# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The rl lock must retain the transformers 5.10.1 floor and consistent artifacts (OMN-21878)."""

from __future__ import annotations

import re
import tomllib
from contextlib import nullcontext
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSION = "5.10.1"


def _transformers_packages() -> list[dict[str, object]]:
    packages = tomllib.loads((_ROOT / "uv.lock").read_text())["package"]
    return [p for p in packages if p["name"] == "transformers"]


def test_lock_selects_transformers_5_10_1() -> None:
    """One entry at or above the floor, with URLs matching its selected version."""
    matches = _transformers_packages()
    assert len(matches) == 1, matches
    package = matches[0]
    version = package["version"]
    assert tuple(int(part) for part in version.split(".")) >= tuple(
        int(part) for part in _VERSION.split(".")
    )
    assert package["sdist"]["url"].endswith(f"/transformers-{version}.tar.gz")
    assert package["wheels"]
    assert all(
        w["url"].endswith(f"/transformers-{version}-py3-none-any.whl")
        for w in package["wheels"]
    )


def test_lock_transformers_artifacts_are_consistent() -> None:
    """Every artifact carries a hash and names the selected version."""
    (package,) = _transformers_packages()
    version = package["version"]
    assert package["sdist"]["hash"].startswith("sha256:")
    assert all(w["hash"].startswith("sha256:") for w in package["wheels"])
    assert package["sdist"]["url"].endswith(f"/transformers-{version}.tar.gz")
    assert all(
        w["url"].endswith(f"/transformers-{version}-py3-none-any.whl")
        for w in package["wheels"]
    )


def test_rl_group_declares_transformers() -> None:
    """The rl group's lower bound admits the actual locked version."""
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    rl = pyproject["dependency-groups"]["rl"]
    specs = [s for s in rl if isinstance(s, str) and s.startswith("transformers")]
    assert len(specs) == 1, specs
    match = re.fullmatch(r"transformers>=(\d+)\.(\d+)\.(\d+)", specs[0])
    assert match, specs[0]
    floor = tuple(int(g) for g in match.groups())
    (package,) = _transformers_packages()
    locked = tuple(int(g) for g in package["version"].split("."))
    assert locked >= floor


@pytest.mark.parametrize(
    ("version", "artifact_version", "hash_value", "floor", "passes"),
    [
        ("5.10.1", "5.10.1", "sha256:abc", "5.10.1", True),
        ("5.22.1", "5.22.1", "sha256:abc", "5.10.1", True),
        ("5.22.1", "5.22.1", "sha256:abc", "5.20.0", True),
        ("5.10.0", "5.10.0", "sha256:abc", "5.10.1", False),
        ("5.22.1", "5.10.1", "sha256:abc", "5.10.1", False),
        ("5.22.1", "5.22.1", "md5:abc", "5.10.1", False),
        ("5.22.1", "5.22.1", "sha256:abc", "5.23.0", False),
    ],
)
def test_transformers_check_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
    artifact_version: str,
    hash_value: str,
    floor: str,
    passes: bool,
) -> None:
    """Upgrades pass while stale artifacts, invalid hashes and floors fail."""
    monkeypatch.setattr(f"{__name__}._ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        f'[dependency-groups]\nrl = ["transformers>={floor}"]\n'
    )
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "transformers"\n'
        f'version = "{version}"\n'
        f'sdist = {{ url = "https://example.com/transformers-{artifact_version}.tar.gz", '
        f'hash = "{hash_value}" }}\n'
        f'wheels = [{{ url = "https://example.com/transformers-{artifact_version}-py3-none-any.whl", '
        f'hash = "{hash_value}" }}]\n'
    )
    with nullcontext() if passes else pytest.raises(AssertionError):
        test_lock_selects_transformers_5_10_1()
        test_lock_transformers_artifacts_are_consistent()
        test_rl_group_declares_transformers()
