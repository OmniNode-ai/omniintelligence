# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""No contract name this package announces is announced by a sibling package.

The dev runtime discovers contracts from the ``onex.nodes`` entry points of every
installed first-party package. When two packages announce the same entry-point
name, discovery logs ``DUPLICATE_REGISTRATION prevented`` for the loser and
marks the runtime DEGRADED (``discovery_errors``). Two of this package's
announcements clashed that way: omnibase_infra announces
``node_pattern_lifecycle_effect`` first, and omnimarket announces
``node_retrieval_eval_compute`` as a bus node while this package's copy is an
offline eval harness with no event_bus topics. Both are left unannounced in
``pyproject.toml`` (the ``# not announced`` lines in that table), and this test
fails the moment a clash reappears.

Ticket: OMN-23523
"""

from __future__ import annotations

import tomllib
from importlib.metadata import distribution
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).parent.parent.parent / "pyproject.toml"

SIBLING_DISTRIBUTIONS = ("omnibase-infra", "omnimarket")


def _sibling_onex_node_names() -> dict[str, set[str]]:
    """Each sibling's announced names, from the installed distribution's metadata."""
    return {
        name: {
            ep.name
            for ep in distribution(name).entry_points
            if ep.group == "onex.nodes"
        }
        for name in SIBLING_DISTRIBUTIONS
    }


@pytest.mark.unit
def test_no_announced_name_is_announced_by_another_runtime_package() -> None:
    """The dev boot announcer reads this table; no name in it may clash with a sibling."""
    data = tomllib.loads(PYPROJECT.read_text())
    announced = set(data["project"]["entry-points"]["onex.nodes"])
    clashes = {
        sibling: sorted(announced & names)
        for sibling, names in _sibling_onex_node_names().items()
        if announced & names
    }
    assert not clashes, (
        "the runtime refuses duplicate registrations (DUPLICATE_REGISTRATION "
        f"prevented, discovery_errors) for: {clashes}"
    )


@pytest.mark.unit
def test_the_sibling_packages_announce_nodes() -> None:
    """Positive control: each sibling announces enough that an empty read cannot pass."""
    for sibling, names in _sibling_onex_node_names().items():
        assert len(names) >= 50, (
            f"{sibling} announces only {len(names)} onex.nodes entry points"
        )
