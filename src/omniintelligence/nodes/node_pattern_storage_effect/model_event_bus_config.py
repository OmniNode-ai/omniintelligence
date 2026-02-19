# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""EventBusConfig - event bus configuration from contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventBusConfig(BaseModel):
    """Event bus configuration from contract.

    Attributes:
        version: Event bus configuration version.
        event_bus_enabled: Whether event bus is enabled.
        subscribe_topics: Topics this node subscribes to.
        publish_topics: Topics this node publishes to.
        subscribe_topic_metadata: Metadata for subscribed topics.
        publish_topic_metadata: Metadata for published topics.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: dict[str, int] = Field(
        default_factory=lambda: {"major": 1, "minor": 0, "patch": 0}
    )
    event_bus_enabled: bool = True
    subscribe_topics: list[str] = Field(default_factory=list)
    publish_topics: list[str] = Field(default_factory=list)
    subscribe_topic_metadata: dict[str, dict[str, Any]] = (
        Field(  # any-ok: YAML-loaded contract data is dynamically typed
            default_factory=dict
        )
    )
    publish_topic_metadata: dict[str, dict[str, Any]] = (
        Field(  # any-ok: YAML-loaded contract data is dynamically typed
            default_factory=dict
        )
    )
