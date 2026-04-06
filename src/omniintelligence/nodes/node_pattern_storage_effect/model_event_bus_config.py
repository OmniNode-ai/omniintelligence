# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""EventBusConfig - event bus configuration from contract."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class TopicMetadataDict(TypedDict, total=False):
    """Typed metadata for an individual event bus topic.

    Loaded from ONEX contract YAML. All fields are optional since
    contracts may define arbitrary subsets of these keys.
    """

    schema_ref: str


class EventBusConfig(BaseModel):
    """Event bus configuration from contract.

    Attributes:
        version: Event bus configuration version.
        subscribe_topics: Topics this node subscribes to.
        publish_topics: Topics this node publishes to.
        subscribe_topic_metadata: Per-topic metadata for subscribed topics.
        publish_topic_metadata: Per-topic metadata for published topics.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    version: dict[str, int] = Field(
        default_factory=lambda: {"major": 1, "minor": 0, "patch": 0}
    )
    subscribe_topics: list[str] = Field(default_factory=list)
    publish_topics: list[str] = Field(default_factory=list)
    subscribe_topic_metadata: dict[str, TopicMetadataDict] = Field(
        default_factory=dict,
    )
    publish_topic_metadata: dict[str, TopicMetadataDict] = Field(
        default_factory=dict,
    )
