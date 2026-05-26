# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Mutable in-memory intent graph state.

Holds the accumulated directed graph of intent transitions across sessions.
This is the working state for the NodeIntentGraphReducer — it is NOT frozen
(state is mutated as events arrive) and is NOT persisted directly (the Memgraph
adapter in omnimemory handles persistence).

Design:
    - Nodes keyed by EnumIntentClass (one node per intent class)
    - Edges keyed by (from_class, to_class) tuple (one edge per transition pair)
    - Mutable for accumulation; serialised to frozen ModelIntentGraphNode /
      ModelIntentTransition objects when queried or persisted

ONEX Compliance:
    - No try/except at this level
    - Pure data container, no I/O, no logging
"""

from __future__ import annotations

from uuid import UUID, uuid4

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "IntentGraphEdgeState",
    "IntentGraphNodeState",
    "ModelIntentGraphState",
]


class IntentGraphNodeState(BaseModel):
    """Mutable accumulator for a single intent graph node.

    Aggregates occurrence and outcome statistics for one intent class.
    """

    model_config = ConfigDict(frozen=False)

    node_id: UUID = Field(default_factory=uuid4)
    intent_class: EnumIntentClass = Field(default=EnumIntentClass.ANALYSIS)
    occurrence_count: int = 0
    total_cost_usd: float = 0.0
    total_successes: int = 0
    total_outcomes: int = 0

    @property
    def avg_cost_usd(self) -> float:
        """Average cost per session for this intent class."""
        if self.occurrence_count == 0:
            return 0.0
        return self.total_cost_usd / self.occurrence_count

    @property
    def success_rate(self) -> float:
        """Fraction of labeled outcomes that were successful, in [0.0, 1.0]."""
        if self.total_outcomes == 0:
            return 0.0
        return self.total_successes / self.total_outcomes


class IntentGraphEdgeState(BaseModel):
    """Mutable accumulator for a single intent graph transition (edge).

    Aggregates statistics for all observed transitions from one intent class
    to another within or across sessions.
    """

    model_config = ConfigDict(frozen=False)

    from_intent_class: EnumIntentClass = Field(default=EnumIntentClass.ANALYSIS)
    to_intent_class: EnumIntentClass = Field(default=EnumIntentClass.ANALYSIS)
    transition_count: int = 0
    total_success_rate_sum: float = 0.0
    total_cost_usd: float = 0.0
    total_cost_samples: int = 0

    @property
    def avg_success_rate(self) -> float:
        """Average success rate for sessions that followed this transition."""
        if self.transition_count == 0:
            return 0.0
        return self.total_success_rate_sum / self.transition_count

    @property
    def avg_cost_usd(self) -> float:
        """Average cost for sessions that included this transition."""
        if self.total_cost_samples == 0:
            return 0.0
        return self.total_cost_usd / self.total_cost_samples


class ModelIntentGraphState(BaseModel):
    """In-memory directed intent graph with accumulated statistics.

    Holds all node and edge accumulators for the intent graph. Updated by
    the graph update handlers as classification and outcome events arrive.

    Graph structure:
        - nodes: Dict keyed by EnumIntentClass — one node per intent class
        - edges: Dict keyed by (from_class, to_class) — one edge per transition pair
    """

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    nodes: dict[EnumIntentClass, IntentGraphNodeState] = Field(default_factory=dict)
    edges: dict[tuple[EnumIntentClass, EnumIntentClass], IntentGraphEdgeState] = Field(
        default_factory=dict
    )
    session_last_intent: dict[str, EnumIntentClass] = Field(default_factory=dict)
    session_previous_intent: dict[str, EnumIntentClass] = Field(default_factory=dict)
