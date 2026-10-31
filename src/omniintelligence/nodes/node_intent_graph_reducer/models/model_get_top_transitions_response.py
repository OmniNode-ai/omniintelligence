# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Transitions ranked by descending occurrence count."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    IntentGraphEdgeState,
)


class ModelGetTopTransitionsResponse(BaseModel):
    """Transitions ranked by descending occurrence count."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    transitions: list[IntentGraphEdgeState]
