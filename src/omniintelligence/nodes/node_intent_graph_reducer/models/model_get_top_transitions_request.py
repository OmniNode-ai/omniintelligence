# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Graph and maximum transition count for a ranked query."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    ModelIntentGraphState,
)


class ModelGetTopTransitionsRequest(BaseModel):
    """Graph and maximum transition count for a ranked query."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    graph: ModelIntentGraphState
    top_n: int = 10
