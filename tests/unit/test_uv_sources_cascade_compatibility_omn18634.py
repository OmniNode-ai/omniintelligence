# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Recurrence guard for the dependency-cascade deadlock (OMN-18634 / OMN-18673).

Every ``omnibase_infra`` release cascade failed on the ``Bump omniintelligence``
leg, and only that leg, for roughly two months. The cause was not the
``--check-movable`` guard, which PASSED on every run: this repo had already
removed its ``omnibase-infra`` git override. It was a *different* entry in the
same table. ``[tool.uv.sources]`` pinned ``omnimarket`` to rev ``54fa07dd``
(omnimarket 0.4.3, 2026-07-10), and that frozen revision declares
``omnibase-compat==0.5.6`` exactly, while every ``omnibase-infra`` release from
0.38.22 on declares ``omnibase-compat==0.5.7`` exactly. Two exact pins on one
distribution cannot both hold, so ``uv lock --upgrade-package
omnibase-infra==<ver>`` was unsatisfiable and the repo sat at 0.38.21.

A git-rev override on a distribution that IS published to PyPI freezes that
distribution's transitive exact pins at the revision's moment. The foundation
packages underneath it keep moving. The deadlock is therefore not a question of
whether a given pin is currently stale — it is structural, and the only safe
overrides are on distributions with no published release to resolve instead.

``scripts/check_dep_provenance.py`` already refuses first-party git overrides,
but it honours a ``# raw-override-ok: <token>`` escape on the line, and the
omnimarket entry carried one naming a refresh ticket that was never actioned.
The escape is what let a 217-commit-stale pin survive a dedicated gate. These
tests close that specific hole for this table: membership of the allowlist
below is the only permission, and an annotation cannot grant it.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_UV_LOCK = _REPO_ROOT / "uv.lock"

#: The ONLY distributions this repo may pin by git revision. Membership means
#: the distribution publishes no release that could be resolved instead, so a
#: git source is the only way to depend on it at all -- NOT that its pin is
#: currently fresh, and NOT that a ticket promises to refresh it later.
#:
#: onex-change-control: not published to PyPI (``GET /pypi/onex-change-control/json``
#: returns 404, checked 2026-09-18), so there is no registry release to resolve.
#:
#: omnimarket is deliberately ABSENT: it publishes to PyPI (0.4.126 at the time
#: of this fix) and its releases carry the current ``omnibase-compat`` pin.
_GIT_OVERRIDE_ALLOWLIST: frozenset[str] = frozenset({"onex-change-control"})


#: uv's own source-kind keys that make an entry a version-control checkout
#: rather than a registry release. Mirrors ``_GIT_SOURCE_KEYS`` in
#: ``scripts/check_dep_provenance.py``; asserted equal to it below, so the two
#: cannot drift apart silently.
_GIT_SOURCE_KEYS: frozenset[str] = frozenset({"git", "rev", "tag", "branch"})


def _normalize(name: str) -> str:
    """Canonicalise a distribution name to the hyphen form PyPI compares on."""
    return name.strip().replace("_", "-").lower()


def _git_overrides(pyproject_text: str) -> dict[str, dict[str, Any]]:
    """Return {normalised name: attrs} for every git-sourced uv.sources entry.

    Parsed with ``tomllib`` rather than by regex: TOML forbids redefining a
    table, so the real document has exactly one ``[tool.uv.sources]``, and a
    parser that reads the document cannot be shadowed by a commented example
    or slip past an entry written in a spelling a pattern did not anticipate.
    """
    doc = tomllib.loads(pyproject_text)
    sources = doc.get("tool", {}).get("uv", {}).get("sources", {})
    return {
        _normalize(name): attrs
        for name, attrs in sources.items()
        if isinstance(attrs, dict) and _GIT_SOURCE_KEYS & set(attrs)
    }


def _insert_into_uv_sources(pyproject_text: str, entry_line: str) -> str:
    """Return the document with ``entry_line`` added inside [tool.uv.sources]."""
    header = "\n[tool.uv.sources]\n"
    at = pyproject_text.index(header) + len(header)
    return pyproject_text[:at] + entry_line + "\n" + pyproject_text[at:]


def test_git_source_keys_match_the_provenance_gate() -> None:
    """Drift-proofing: this module and the gate must agree on what 'git' means."""
    script = _REPO_ROOT / "scripts" / "check_dep_provenance.py"
    spec = importlib.util.spec_from_file_location("check_dep_provenance", script)
    assert spec and spec.loader, f"could not load {script}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module._GIT_SOURCE_KEYS) == set(_GIT_SOURCE_KEYS), (
        "scripts/check_dep_provenance.py changed its git-source key set; this "
        "module would then classify entries differently from the gate it "
        "backstops. Update both together."
    )


def test_no_git_override_outside_the_not_on_pypi_allowlist() -> None:
    """A git-rev override on a PyPI-published distribution deadlocks the cascade."""
    offenders = sorted(
        set(_git_overrides(_PYPROJECT.read_text())) - _GIT_OVERRIDE_ALLOWLIST
    )
    assert offenders == [], (
        f"[tool.uv.sources] git overrides outside the allowlist: {offenders}. "
        "A frozen revision of a published distribution freezes its transitive "
        "exact pins, which deadlocks `uv lock --upgrade-package omnibase-infra"
        "==<ver>` and turns every omnibase_infra release cascade red on this "
        "repo (OMN-18634). Depend on the published release instead. Adding a "
        "name to _GIT_OVERRIDE_ALLOWLIST requires showing the distribution has "
        "no release on PyPI at all."
    )


def test_the_allowlist_check_trips_on_a_reintroduced_override() -> None:
    """Positive control: an empty result above must mean 'clean', not 'unparsed'.

    Re-adds the exact entry that was removed, WITH the escape annotation that
    let the original survive the provenance gate, and asserts it is still seen.
    """
    reintroduced = _insert_into_uv_sources(
        _PYPROJECT.read_text(),
        'omnimarket = { git = "https://github.com/OmniNode-ai/omnimarket.git", '
        'rev = "54fa07dd0d46e7ba719a201a950626a041ad6433" }'  # pragma: allowlist secret
        "  # raw-override-ok: OMN-15145",
    )
    offenders = set(_git_overrides(reintroduced)) - _GIT_OVERRIDE_ALLOWLIST
    assert "omnimarket" in offenders, (
        "the parser did not see a reintroduced omnimarket git override, so a "
        "clean result from the test above would prove nothing"
    )


def test_an_underscore_spelling_is_not_a_way_around_the_allowlist() -> None:
    """Second positive control: normalisation, not literal-name matching."""
    reintroduced = _insert_into_uv_sources(
        _PYPROJECT.read_text(),
        'omni_market = { git = "https://github.com/OmniNode-ai/omnimarket.git", '
        'rev = "54fa07dd0d46e7ba719a201a950626a041ad6433" }',  # pragma: allowlist secret
    )
    assert "omni-market" in set(_git_overrides(reintroduced))


@pytest.mark.parametrize("distribution", ["omnimarket", "omnibase-infra"])
def test_cascade_moved_distributions_resolve_from_the_registry(
    distribution: str,
) -> None:
    """Readback of the resolution itself, not of the declaration that shapes it."""
    locked = tomllib.loads(_UV_LOCK.read_text())
    matches = [p for p in locked["package"] if p["name"] == distribution]
    assert len(matches) == 1, (
        f"expected exactly one locked {distribution}, found {len(matches)}"
    )
    source = matches[0].get("source", {})
    assert "registry" in source, (
        f"{distribution} resolves from {source} in uv.lock, not from a "
        f"registry. The cascade upgrades registry releases; it cannot move a "
        f"git-pinned revision (OMN-15604, OMN-18634)."
    )
