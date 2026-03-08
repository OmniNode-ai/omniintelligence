# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Unit tests for bloom eval Kafka topic registration.

Verifies that:
- TOPIC_BLOOM_EVAL_RUN_V1 is declared in node_bloom_eval_orchestrator/contract.yaml
  subscribe_topics (OMN-4028).
- TOPIC_BLOOM_EVAL_COMPLETED_V1 is declared in node_bloom_eval_orchestrator/contract.yaml
  publish_topics (OMN-4028).
"""

from __future__ import annotations

import importlib.resources

import pytest
import yaml

from omniintelligence.constants import (
    TOPIC_BLOOM_EVAL_COMPLETED_V1,
    TOPIC_BLOOM_EVAL_RUN_V1,
)


def _load_bloom_eval_contract() -> dict[object, object]:
    """Load and parse node_bloom_eval_orchestrator/contract.yaml."""
    package_files = importlib.resources.files(
        "omniintelligence.nodes.node_bloom_eval_orchestrator"
    )
    contract_file = package_files.joinpath("contract.yaml")
    content = contract_file.read_text()
    result = yaml.safe_load(content)
    assert isinstance(result, dict), "contract.yaml must be a YAML mapping"
    return result  # type: ignore[return-value]


@pytest.mark.unit
def test_bloom_eval_subscribe_topic_in_contract() -> None:
    """TOPIC_BLOOM_EVAL_RUN_V1 must appear in subscribe_topics of the contract."""
    contract = _load_bloom_eval_contract()
    event_bus = contract.get("event_bus", {})
    assert isinstance(event_bus, dict), "event_bus section must be a mapping"
    subscribe_topics: list[str] = event_bus.get("subscribe_topics", [])
    assert TOPIC_BLOOM_EVAL_RUN_V1 in subscribe_topics, (
        f"Expected {TOPIC_BLOOM_EVAL_RUN_V1!r} in subscribe_topics, "
        f"got: {subscribe_topics!r}"
    )


@pytest.mark.unit
def test_bloom_eval_completed_topic_in_contract() -> None:
    """TOPIC_BLOOM_EVAL_COMPLETED_V1 must appear in publish_topics of the contract."""
    contract = _load_bloom_eval_contract()
    event_bus = contract.get("event_bus", {})
    assert isinstance(event_bus, dict), "event_bus section must be a mapping"
    publish_topics: list[str] = event_bus.get("publish_topics", [])
    assert TOPIC_BLOOM_EVAL_COMPLETED_V1 in publish_topics, (
        f"Expected {TOPIC_BLOOM_EVAL_COMPLETED_V1!r} in publish_topics, "
        f"got: {publish_topics!r}"
    )
