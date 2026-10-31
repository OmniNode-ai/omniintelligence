# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Graph and intent class whose success rate is requested."""

from __future__ import annotations

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    ModelIntentGraphState,
)


class ModelGetNodeSuccessRateRequest(BaseModel):
    """Graph and intent class whose success rate is requested."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    graph: ModelIntentGraphState
    intent_class: EnumIntentClass
