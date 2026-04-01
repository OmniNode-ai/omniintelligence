# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Verify all intelligence effect-node contracts have event_bus_enabled: true.

Every package discovered by ``_discover_effect_node_packages()`` must ship a
contract.yaml with ``event_bus.event_bus_enabled: true``.  If a new effect node
is added but its contract is missing or has the flag disabled, this test fails.

Related: OMN-7142
"""

from __future__ import annotations

import importlib.resources

import pytest
import yaml

from omniintelligence.runtime.contract_topics import _discover_effect_node_packages

# ---------------------------------------------------------------------------
# Dynamically discovered packages with event_bus_enabled subscribe_topics
# ---------------------------------------------------------------------------
EXPECTED_EFFECT_NODE_PACKAGES: list[str] = _discover_effect_node_packages()


def _load_contract(package: str) -> dict:
    """Load contract.yaml from a package via importlib.resources."""
    ref = importlib.resources.files(package).joinpath("contract.yaml")
    return yaml.safe_load(ref.read_text(encoding="utf-8"))


@pytest.mark.unit
class TestContractEventBusEnabled:
    """All intelligence effect-node contracts must have event_bus_enabled."""

    @pytest.mark.parametrize("package", EXPECTED_EFFECT_NODE_PACKAGES)
    def test_event_bus_enabled(self, package: str) -> None:
        contract = _load_contract(package)
        event_bus = contract.get("event_bus", {})
        assert event_bus.get("event_bus_enabled") is True, (
            f"{package}/contract.yaml: event_bus.event_bus_enabled is not true "
            f"(got {event_bus.get('event_bus_enabled')!r})"
        )

    def test_expected_set_matches_contract_topics(self) -> None:
        """The discovered list must match a fresh discovery call."""
        fresh = _discover_effect_node_packages()
        assert set(EXPECTED_EFFECT_NODE_PACKAGES) == set(fresh), (
            "EXPECTED_EFFECT_NODE_PACKAGES is out of sync with "
            "_discover_effect_node_packages()"
        )

    def test_at_least_12_packages(self) -> None:
        assert len(EXPECTED_EFFECT_NODE_PACKAGES) >= 12

    def test_all_contracts_discoverable(self) -> None:
        """Every listed package must have a loadable contract.yaml."""
        for package in EXPECTED_EFFECT_NODE_PACKAGES:
            contract = _load_contract(package)
            assert "name" in contract, f"{package}/contract.yaml missing 'name' field"
