# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Verify all intelligence effect-node contracts have event_bus_enabled: true.

Every package listed in contract_topics._INTELLIGENCE_EFFECT_NODE_PACKAGES must
ship a contract.yaml with ``event_bus.event_bus_enabled: true``.  If a new
effect node is added to the list but its contract is missing or has the flag
disabled, this test fails — keeping the contract_topics registry and the
actual contracts in sync.

Related: OMN-7142
"""

from __future__ import annotations

import importlib.resources

import pytest
import yaml

# ---------------------------------------------------------------------------
# Expected set — mirrors contract_topics._INTELLIGENCE_EFFECT_NODE_PACKAGES
# ---------------------------------------------------------------------------
EXPECTED_EFFECT_NODE_PACKAGES: list[str] = [
    "omniintelligence.nodes.node_bloom_eval_orchestrator",
    "omniintelligence.nodes.node_claude_hook_event_effect",
    "omniintelligence.nodes.node_compliance_evaluate_effect",
    "omniintelligence.nodes.node_crawl_scheduler_effect",
    "omniintelligence.nodes.node_pattern_feedback_effect",
    "omniintelligence.nodes.node_pattern_learning_effect",
    "omniintelligence.nodes.node_pattern_lifecycle_effect",
    "omniintelligence.nodes.node_pattern_projection_effect",
    "omniintelligence.nodes.node_pattern_storage_effect",
    "omniintelligence.nodes.node_code_crawler_effect",
    "omniintelligence.review_pairing",
    "omniintelligence.nodes.node_ci_failure_tracker_effect",
]


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
        """The hardcoded list here must match contract_topics at runtime."""
        from omniintelligence.runtime.contract_topics import (
            _INTELLIGENCE_EFFECT_NODE_PACKAGES,
        )

        assert set(EXPECTED_EFFECT_NODE_PACKAGES) == set(
            _INTELLIGENCE_EFFECT_NODE_PACKAGES
        ), (
            "EXPECTED_EFFECT_NODE_PACKAGES in this test is out of sync with "
            "contract_topics._INTELLIGENCE_EFFECT_NODE_PACKAGES"
        )

    def test_exactly_12_packages(self) -> None:
        assert len(EXPECTED_EFFECT_NODE_PACKAGES) == 12

    def test_all_contracts_discoverable(self) -> None:
        """Every listed package must have a loadable contract.yaml."""
        for package in EXPECTED_EFFECT_NODE_PACKAGES:
            contract = _load_contract(package)
            assert "name" in contract, f"{package}/contract.yaml missing 'name' field"
