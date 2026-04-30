# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""No-drift tests for dispatch outcome evaluation topic contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit


def _dispatch_outcome_evaluated_topic() -> str:
    return ".".join(
        (
            "onex",
            "evt",
            "omniintelligence",
            "dispatch-outcome-evaluated",
            "v1",
        )
    )


def _load_contract(node_name: str) -> dict[str, Any]:
    repo_root = Path(__file__).parents[4]
    contract_path = (
        repo_root / "src" / "omniintelligence" / "nodes" / node_name / "contract.yaml"
    )
    with contract_path.open(encoding="utf-8") as contract_file:
        return yaml.safe_load(contract_file)


def test_dispatch_outcome_eval_effect_publishes_topicbase_topic() -> None:
    contract = _load_contract("node_dispatch_outcome_eval_effect")
    event_bus = contract["event_bus"]

    assert event_bus["publish_topics"] == [_dispatch_outcome_evaluated_topic()]
    assert _dispatch_outcome_evaluated_topic() in event_bus["publish_topic_metadata"]


def test_pattern_feedback_subscribes_to_dispatch_outcome_evaluated_topic() -> None:
    contract = _load_contract("node_pattern_feedback_effect")
    event_bus = contract["event_bus"]

    assert _dispatch_outcome_evaluated_topic() in event_bus["subscribe_topics"]
    metadata = event_bus["subscribe_topic_metadata"][
        _dispatch_outcome_evaluated_topic()
    ]
    assert (
        metadata["internal_publisher"]["topic_constant"]
        == "TopicBase.DISPATCH_OUTCOME_EVALUATED"
    )
