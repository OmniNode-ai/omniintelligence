# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reads one event-bus topic from a node's ``contract.yaml`` (OMN-21623).

Code that needs a topic names the node and the event, never the topic string, so
the node contract stays the only place a topic is spelled out. The contract is
read as a package resource and the node package itself is not imported, so the
reader is safe to call while the runtime modules are still importing.
"""

from __future__ import annotations

import importlib.resources
import re
from functools import cache

import yaml
from pydantic import BaseModel, ConfigDict, Field

_TOPIC_FIELDS: tuple[str, ...] = ("subscribe_topics", "publish_topics")
_EVENT_FIELDS: tuple[str, ...] = ("consumed_events", "published_events")


def _load_contract(content: str) -> object:
    """Parse a contract with LibYAML's safe loader when it is available."""
    if yaml.__with_libyaml__:
        return yaml.load(content, Loader=yaml.CSafeLoader)
    return yaml.safe_load(content)


@cache
def _event_bus_topics(nodes_package: str, node: str) -> tuple[str, ...]:
    """Every topic the node's contract declares, in ``event_bus`` or its event lists."""
    contract_file = importlib.resources.files(nodes_package).joinpath(
        node, "contract.yaml"
    )
    contract = _load_contract(contract_file.read_text())
    document = contract if isinstance(contract, dict) else {}
    event_bus = document.get("event_bus")
    bus_topics = [
        topic
        for field in _TOPIC_FIELDS
        for topic in (event_bus.get(field) or [] if isinstance(event_bus, dict) else [])
    ]
    event_topics = [
        event["topic"]
        for field in _EVENT_FIELDS
        for event in document.get(field) or []
        if isinstance(event, dict) and isinstance(event.get("topic"), str)
    ]
    return tuple(topic.removeprefix("{env}.") for topic in (*bus_topics, *event_topics))


class ModelContractTopicReader(BaseModel):
    """Resolves the topic a node contract declares for a kind and event name.

    Attributes:
        nodes_package: Package holding one directory per node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    nodes_package: str = Field(default="omniintelligence.nodes", min_length=1)

    def read(self, node: str, kind: str, event_name: str) -> str:
        """Return the one topic ``onex.{kind}.{producer}.{event_name}.v{n}``.

        Args:
            node: Node directory name, e.g. ``"node_claude_hook_event_effect"``.
            kind: Topic kind segment, ``"cmd"`` or ``"evt"``.
            event_name: Event-name segment, e.g. ``"claude-hook-event"``.

        Raises:
            LookupError: The contract declares no matching topic, or more than
                one distinct matching topic.
        """
        pattern = re.compile(
            rf"^onex\.{re.escape(kind)}\.[a-z0-9_-]+\.{re.escape(event_name)}\.v[0-9]+$"
        )
        declared = {
            topic
            for topic in _event_bus_topics(self.nodes_package, node)
            if pattern.match(topic)
        }
        if len(declared) != 1:
            raise LookupError(
                f"{node} contract.yaml declares {len(declared)} topics for "
                f"kind={kind!r} event={event_name!r}: {sorted(declared)}"
            )
        return next(iter(declared))

    def event(self, node: str, event_name: str) -> str:
        """Return the one ``onex.evt`` topic the node contract declares for the event."""
        return self.read(node, "evt", event_name)

    def command(self, node: str, event_name: str) -> str:
        """Return the one ``onex.cmd`` topic the node contract declares for the event."""
        return self.read(node, "cmd", event_name)
