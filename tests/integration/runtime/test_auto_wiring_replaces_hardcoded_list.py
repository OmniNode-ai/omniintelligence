# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity test: auto-wiring discovers all nodes from the hardcoded list.

Proves that dynamic discovery via directory scanning finds every package
that was formerly in _INTELLIGENCE_EFFECT_NODE_PACKAGES, making the
hardcoded list redundant.

Reference: OMN-7142
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest
import yaml

from omniintelligence.runtime.contract_topics import (
    _INTELLIGENCE_EFFECT_NODE_PACKAGES,
    collect_subscribe_topics_from_contracts,
)


def _discover_subscribing_packages() -> list[str]:
    """Dynamically discover all packages with event_bus subscribe_topics.

    Scans omniintelligence.nodes.* subpackages and omniintelligence.review_pairing
    for contract.yaml files with event_bus_enabled and subscribe_topics.
    """
    discovered: list[str] = []

    # Scan nodes directory
    nodes_path = importlib.resources.files("omniintelligence.nodes")
    # Resolve to actual filesystem path for directory listing
    nodes_dir = Path(str(nodes_path))

    for child in sorted(nodes_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name.startswith("."):
            continue
        contract_path = child / "contract.yaml"
        if not contract_path.exists():
            continue

        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        if not isinstance(contract, dict):
            continue
        event_bus = contract.get("event_bus", {})
        if not isinstance(event_bus, dict):
            continue
        if not event_bus.get("event_bus_enabled", False):
            continue
        topics = event_bus.get("subscribe_topics", [])
        if topics:
            discovered.append(f"omniintelligence.nodes.{child.name}")

    # Also check review_pairing (lives outside nodes/)
    review_path = importlib.resources.files("omniintelligence.review_pairing")
    review_dir = Path(str(review_path))
    contract_path = review_dir / "contract.yaml"
    if contract_path.exists():
        with open(contract_path) as f:
            contract = yaml.safe_load(f)
        if isinstance(contract, dict):
            event_bus = contract.get("event_bus", {})
            if isinstance(event_bus, dict) and event_bus.get(
                "event_bus_enabled", False
            ):
                topics = event_bus.get("subscribe_topics", [])
                if topics:
                    discovered.append("omniintelligence.review_pairing")

    return discovered


@pytest.mark.integration
class TestAutoWiringReplacesHardcodedList:
    """Verify dynamic discovery is a superset of the hardcoded list."""

    def test_hardcoded_list_is_subset_of_discovery(self) -> None:
        """Every package in the hardcoded list must be found by discovery."""
        discovered = set(_discover_subscribing_packages())
        hardcoded = set(_INTELLIGENCE_EFFECT_NODE_PACKAGES)

        missing = hardcoded - discovered
        assert missing == set(), (
            f"Hardcoded packages not found by discovery: {missing}. "
            "These packages may be missing contract.yaml or event_bus_enabled."
        )

    def test_discovery_finds_new_nodes_not_in_hardcoded_list(self) -> None:
        """Discovery should find nodes added after the hardcoded list was written."""
        discovered = set(_discover_subscribing_packages())
        hardcoded = set(_INTELLIGENCE_EFFECT_NODE_PACKAGES)

        extra = discovered - hardcoded
        # This is informational -- extra nodes prove the list is stale
        # and dynamic discovery is needed.
        assert len(discovered) >= len(hardcoded), (
            f"Discovery found {len(discovered)} packages, "
            f"hardcoded list has {len(hardcoded)}"
        )

    def test_collect_topics_from_discovered_packages(self) -> None:
        """Dynamically discovered packages produce valid topics."""
        discovered = _discover_subscribing_packages()
        topics = collect_subscribe_topics_from_contracts(node_packages=discovered)

        assert len(topics) > 0, "No topics collected from discovered packages"
        for topic in topics:
            assert topic.startswith("onex."), f"Topic {topic} missing onex. prefix"

    def test_discovered_topics_superset_of_hardcoded_topics(self) -> None:
        """Topics from discovery must be a superset of topics from hardcoded list."""
        hardcoded_topics = set(
            collect_subscribe_topics_from_contracts(
                node_packages=_INTELLIGENCE_EFFECT_NODE_PACKAGES
            )
        )
        discovered = _discover_subscribing_packages()
        discovered_topics = set(
            collect_subscribe_topics_from_contracts(node_packages=discovered)
        )

        missing = hardcoded_topics - discovered_topics
        assert missing == set(), (
            f"Topics from hardcoded list not found in discovered topics: {missing}"
        )


__all__ = ["TestAutoWiringReplacesHardcodedList"]
