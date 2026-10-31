# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Graph and classification event data for an in-place update."""

from __future__ import annotations

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    ModelIntentGraphState,
)


class ModelUpdateGraphOnClassificationRequest(BaseModel):
    """Graph and classification event data for an in-place update."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    graph: ModelIntentGraphState
    session_id: str
    intent_class: EnumIntentClass
    cost_usd: float = 0.0
