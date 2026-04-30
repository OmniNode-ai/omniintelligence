# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract tests for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

CONTRACT_PATH = (
    Path(__file__).parents[4]
    / "src/omniintelligence/nodes/node_dispatch_outcome_eval_effect/contract.yaml"
)


def test_contract_loads() -> None:
    """The dispatch outcome eval contract is valid YAML with expected identity."""
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["name"] == "node_dispatch_outcome_eval_effect"
    assert contract["node_type"] == "EFFECT_GENERIC"
    assert contract["input_model"] == {
        "name": "ModelInput",
        "module": "omniintelligence.nodes.node_dispatch_outcome_eval_effect.models",
        "description": "Dispatch worker completion event consumed from omniclaude.",
    }
    assert contract["output_model"] == {
        "name": "ModelOutput",
        "module": "omniintelligence.nodes.node_dispatch_outcome_eval_effect.models",
        "description": "Normalized dispatch outcome evaluation event.",
    }


def test_contract_declares_dispatch_topics_and_handler() -> None:
    """Contract subscribes to dispatch completions and routes to the skeleton handler."""
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["event_bus"]["subscribe_topics"] == [
        "onex.evt.omniclaude.dispatch_worker-completed.v1"
    ]
    assert contract["event_bus"]["publish_topics"] == [
        "onex.evt.omniintelligence.dispatch-outcome-evaluated.v1"
    ]
    handler = contract["handler_routing"]["handlers"][0]["handler"]
    assert handler == {
        "function": "handle_dispatch_outcome",
        "module": "omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers.handler_dispatch_outcome",
        "type": "async",
    }
