# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pure graph update handlers for the Intent Graph Reducer.

Implements transition accumulation logic for the directed intent graph.
Each handler accepts a typed request and returns the updated graph state
or a typed query response. Updates mutate the supplied graph in place.

Two event types drive graph updates:

1. Intent Classification events — update node occurrence counts and detect
   transitions (when the same session classifies two sequential intents).

2. Outcome Label events — update node and edge success rates after a session
   is labeled as succeeded or failed.

Design:
    - Config-table-driven: no hardcoded class conditionals
    - Pure functions (no I/O, no logging, no side effects beyond state mutation)
    - Deterministic: same input sequence always produces same graph state

ONEX Compliance:
    - No try/except at this level — errors propagate to the orchestrating handler
    - Pure computation, no logging
"""

from __future__ import annotations

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_graph_reducer.models.model_get_node_success_rate_request import (
    ModelGetNodeSuccessRateRequest,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_get_node_success_rate_response import (
    ModelGetNodeSuccessRateResponse,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_get_top_transitions_request import (
    ModelGetTopTransitionsRequest,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_get_top_transitions_response import (
    ModelGetTopTransitionsResponse,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    IntentGraphEdgeState,
    IntentGraphNodeState,
    ModelIntentGraphState,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_update_graph_on_classification_request import (
    ModelUpdateGraphOnClassificationRequest,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_update_graph_on_outcome_request import (
    ModelUpdateGraphOnOutcomeRequest,
)

__all__ = [
    "HandlerUpdateGraphOnClassification",
    "HandlerUpdateGraphOnOutcome",
    "HandlerGetTopTransitions",
    "HandlerGetNodeSuccessRate",
]


# =============================================================================
# Graph Upsert Helpers
# =============================================================================


def _upsert_node(
    graph: ModelIntentGraphState,
    intent_class: EnumIntentClass,
    session_id: str,
) -> IntentGraphNodeState:
    """Ensure a node exists for the given intent class and return it.

    Args:
        graph: The mutable graph state to update.
        intent_class: The intent class to upsert a node for.
        session_id: Session ID used for provenance (ignored after first creation).

    Returns:
        The existing or newly created IntentGraphNodeState.
    """
    if intent_class not in graph.nodes:
        graph.nodes[intent_class] = IntentGraphNodeState(
            intent_class=intent_class,
        )
    _ = session_id  # session_id is accepted for API consistency; not stored on the node
    return graph.nodes[intent_class]


def _upsert_edge(
    graph: ModelIntentGraphState,
    from_class: EnumIntentClass,
    to_class: EnumIntentClass,
) -> IntentGraphEdgeState:
    """Ensure an edge exists for the given transition pair and return it.

    Args:
        graph: The mutable graph state to update.
        from_class: Source intent class.
        to_class: Target intent class.

    Returns:
        The existing or newly created IntentGraphEdgeState.
    """
    key = (from_class, to_class)
    if key not in graph.edges:
        graph.edges[key] = IntentGraphEdgeState(
            from_intent_class=from_class,
            to_intent_class=to_class,
        )
    return graph.edges[key]


# =============================================================================
# Public Update Handlers
# =============================================================================


class HandlerUpdateGraphOnClassification:
    """Handle update graph on classification requests."""

    def handle(
        self, request: ModelUpdateGraphOnClassificationRequest
    ) -> ModelIntentGraphState:
        """Update the intent graph when a new classification event is received.

        Upserts the node for the classified intent class, increments its
        occurrence count, and accumulates cost. If the same session previously
        classified an intent, a transition edge is recorded between the prior
        and current intent classes.
        """
        graph = request.graph
        session_id = request.session_id
        intent_class = request.intent_class
        cost_usd = request.cost_usd

        # Upsert the node
        node = _upsert_node(graph, intent_class, session_id)
        node.occurrence_count += 1
        node.total_cost_usd += cost_usd

        # If there is a prior intent for this session, record the transition
        prior_class = graph.session_last_intent.get(session_id)
        if prior_class is not None and prior_class is not intent_class:
            edge = _upsert_edge(graph, prior_class, intent_class)
            edge.transition_count += 1
            # Track penultimate intent so outcome events can locate this edge
            graph.session_previous_intent[session_id] = prior_class
        elif prior_class is None:
            # No previous intent — clear any stale penultimate entry
            graph.session_previous_intent.pop(session_id, None)

        # Update the session's last-seen intent
        graph.session_last_intent[session_id] = intent_class

        return graph


class HandlerUpdateGraphOnOutcome:
    """Handle update graph on outcome requests."""

    def handle(
        self, request: ModelUpdateGraphOnOutcomeRequest
    ) -> ModelIntentGraphState:
        """Update the intent graph when an outcome label event is received.

        Recalculates the node's success rate and updates transition edge success
        rates for any transition that ended at this intent class in this session.
        """
        graph = request.graph
        session_id = request.session_id
        intent_class = request.intent_class
        success = request.success
        cost_usd = request.cost_usd

        # Update node outcome statistics
        node = _upsert_node(graph, intent_class, session_id)
        node.total_outcomes += 1
        if success:
            node.total_successes += 1
        if cost_usd > 0.0:
            # Outcome cost supplements the running total; occurrence_count was already
            # incremented at classification time and is not changed here.
            node.total_cost_usd += cost_usd

        # Update transition edge success rates for the transition that led to this
        # intent class. The penultimate intent (session_previous_intent) is the
        # from_class; the current intent_class is the to_class.
        previous_class = graph.session_previous_intent.get(session_id)
        if previous_class is not None:
            key = (previous_class, intent_class)
            if key in graph.edges:
                edge = graph.edges[key]
                outcome_rate = 1.0 if success else 0.0
                edge.total_success_rate_sum += outcome_rate
                edge.total_cost_usd += cost_usd
                edge.total_cost_samples += 1

        return graph


# =============================================================================
# Query Helpers
# =============================================================================


class HandlerGetTopTransitions:
    """Handle get top transitions requests."""

    def handle(
        self, request: ModelGetTopTransitionsRequest
    ) -> ModelGetTopTransitionsResponse:
        """Return the top N most common intent transitions, by transition_count."""
        graph = request.graph
        top_n = request.top_n

        sorted_edges = sorted(
            graph.edges.values(),
            key=lambda e: e.transition_count,
            reverse=True,
        )
        return ModelGetTopTransitionsResponse(transitions=sorted_edges[:top_n])


class HandlerGetNodeSuccessRate:
    """Handle get node success rate requests."""

    def handle(
        self, request: ModelGetNodeSuccessRateRequest
    ) -> ModelGetNodeSuccessRateResponse:
        """Return the node success rate, or zero for missing or unlabeled nodes."""
        graph = request.graph
        intent_class = request.intent_class

        node = graph.nodes.get(intent_class)
        if node is None:
            return ModelGetNodeSuccessRateResponse(success_rate=0.0)
        return ModelGetNodeSuccessRateResponse(success_rate=node.success_rate)
