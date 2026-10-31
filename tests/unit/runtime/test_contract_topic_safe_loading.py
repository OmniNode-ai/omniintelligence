# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Topic resource readers must reject executable YAML tags."""

from pathlib import Path

import pytest
import yaml
from yaml.constructor import ConstructorError

from omniintelligence.models.topics import ModelContractTopicReader
from omniintelligence.models.topics.model_contract_topic_reader import _load_contract
from omniintelligence.runtime.contract_topics import (
    _has_subscribe_topics,
    _read_event_bus_topics,
)


@pytest.mark.unit
def test_python_loader_fallback_preserves_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(yaml, "__with_libyaml__", False)
    topic = "onex.cmd.example.event.v1"
    assert _load_contract(f"event_bus:\n  subscribe_topics: [{topic}]\n") == {
        "event_bus": {"subscribe_topics": [topic]}
    }
    with pytest.raises(ConstructorError):
        _load_contract("event_bus: !!python/object/apply:builtins.dict []\n")


@pytest.mark.unit
def test_topic_discovery_rejects_python_tags(tmp_path: Path) -> None:
    contract = tmp_path / "contract.yaml"
    contract.write_text("event_bus: !!python/object/apply:builtins.dict []\n")

    with pytest.raises(ConstructorError):
        _has_subscribe_topics(contract)


@pytest.mark.unit
def test_topic_resource_readers_reject_python_tags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "unsafe_topic_nodes"
    node = package / "node_unsafe"
    node.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (node / "__init__.py").write_text("")
    (node / "contract.yaml").write_text(
        "event_bus: !!python/object/apply:builtins.dict []\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ConstructorError):
        _read_event_bus_topics("unsafe_topic_nodes.node_unsafe", "subscribe_topics")
    with pytest.raises(ConstructorError):
        ModelContractTopicReader(nodes_package="unsafe_topic_nodes").read(
            "node_unsafe", "cmd", "anything"
        )
