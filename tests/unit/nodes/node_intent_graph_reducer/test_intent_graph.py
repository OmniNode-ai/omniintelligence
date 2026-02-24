"""Unit tests for the Intent Graph Reducer — transition accumulation.

Tests cover:
    - ModelIntentGraphState structure and initialization
    - IntentGraphNodeState occurrence/cost/success accumulation
    - IntentGraphEdgeState transition counting and averaging
    - update_graph_on_classification: node upsert, transition detection
    - update_graph_on_outcome: success rate accumulation
    - get_top_transitions: ordering and limit
    - get_node_success_rate: query function

Pytest marks: unit, intent_graph, transition
"""

from __future__ import annotations

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

from omniintelligence.nodes.node_intent_graph_reducer.handlers.handler_intent_graph_update import (
    get_node_success_rate,
    get_top_transitions,
    update_graph_on_classification,
    update_graph_on_outcome,
)
from omniintelligence.nodes.node_intent_graph_reducer.models.model_intent_graph_state import (
    IntentGraphEdgeState,
    IntentGraphNodeState,
    ModelIntentGraphState,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def empty_graph() -> ModelIntentGraphState:
    """Return a fresh, empty graph state."""
    return ModelIntentGraphState()


@pytest.fixture
def single_classification_graph() -> ModelIntentGraphState:
    """Graph after one REFACTOR classification in session-1."""
    graph = ModelIntentGraphState()
    update_graph_on_classification(
        graph,
        session_id="session-1",
        intent_class=EnumIntentClass.REFACTOR,
    )
    return graph


# =============================================================================
# ModelIntentGraphState initialisation
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
class TestModelIntentGraphStateInit:
    """Tests for ModelIntentGraphState initialization."""

    def test_empty_graph_has_no_nodes(self, empty_graph: ModelIntentGraphState) -> None:
        """A new graph has no nodes."""
        assert len(empty_graph.nodes) == 0

    def test_empty_graph_has_no_edges(self, empty_graph: ModelIntentGraphState) -> None:
        """A new graph has no edges."""
        assert len(empty_graph.edges) == 0

    def test_empty_graph_has_no_session_history(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """A new graph has no session last-intent entries."""
        assert len(empty_graph.session_last_intent) == 0


# =============================================================================
# IntentGraphNodeState
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
class TestIntentGraphNodeState:
    """Tests for IntentGraphNodeState accumulator."""

    def test_node_defaults(self) -> None:
        """Node starts with zero counters."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.BUGFIX)
        assert node.occurrence_count == 0
        assert node.total_cost_usd == 0.0
        assert node.total_successes == 0
        assert node.total_outcomes == 0

    def test_avg_cost_zero_when_no_occurrences(self) -> None:
        """avg_cost_usd returns 0.0 when occurrence_count is 0."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.FEATURE)
        assert node.avg_cost_usd == 0.0

    def test_avg_cost_computed_correctly(self) -> None:
        """avg_cost_usd divides total_cost_usd by occurrence_count."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.FEATURE)
        node.occurrence_count = 4
        node.total_cost_usd = 0.08
        assert node.avg_cost_usd == pytest.approx(0.02)

    def test_success_rate_zero_when_no_outcomes(self) -> None:
        """success_rate returns 0.0 when no outcomes recorded."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.ANALYSIS)
        assert node.success_rate == 0.0

    def test_success_rate_computed_correctly(self) -> None:
        """success_rate divides total_successes by total_outcomes."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.ANALYSIS)
        node.total_outcomes = 10
        node.total_successes = 7
        assert node.success_rate == pytest.approx(0.7)

    def test_success_rate_full_success(self) -> None:
        """success_rate is 1.0 when all outcomes are successes."""
        node = IntentGraphNodeState(intent_class=EnumIntentClass.SECURITY)
        node.total_outcomes = 5
        node.total_successes = 5
        assert node.success_rate == pytest.approx(1.0)

    def test_node_has_stable_uuid(self) -> None:
        """node_id is assigned a UUID on creation."""
        import uuid

        node = IntentGraphNodeState(intent_class=EnumIntentClass.MIGRATION)
        assert isinstance(node.node_id, uuid.UUID)


# =============================================================================
# IntentGraphEdgeState
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
@pytest.mark.transition
class TestIntentGraphEdgeState:
    """Tests for IntentGraphEdgeState accumulator."""

    def test_edge_defaults(self) -> None:
        """Edge starts with zero counters."""
        edge = IntentGraphEdgeState(
            from_intent_class=EnumIntentClass.ANALYSIS,
            to_intent_class=EnumIntentClass.REFACTOR,
        )
        assert edge.transition_count == 0
        assert edge.total_success_rate_sum == 0.0
        assert edge.total_cost_usd == 0.0
        assert edge.total_cost_samples == 0

    def test_avg_success_rate_zero_when_no_transitions(self) -> None:
        """avg_success_rate returns 0.0 when transition_count is 0."""
        edge = IntentGraphEdgeState(
            from_intent_class=EnumIntentClass.BUGFIX,
            to_intent_class=EnumIntentClass.FEATURE,
        )
        assert edge.avg_success_rate == 0.0

    def test_avg_success_rate_computed(self) -> None:
        """avg_success_rate averages success rates over transitions."""
        edge = IntentGraphEdgeState(
            from_intent_class=EnumIntentClass.REFACTOR,
            to_intent_class=EnumIntentClass.FEATURE,
        )
        edge.transition_count = 2
        edge.total_success_rate_sum = 1.5  # 0.75 + 0.75
        assert edge.avg_success_rate == pytest.approx(0.75)

    def test_avg_cost_zero_when_no_samples(self) -> None:
        """avg_cost_usd returns 0.0 when total_cost_samples is 0."""
        edge = IntentGraphEdgeState(
            from_intent_class=EnumIntentClass.FEATURE,
            to_intent_class=EnumIntentClass.BUGFIX,
        )
        assert edge.avg_cost_usd == 0.0

    def test_avg_cost_computed(self) -> None:
        """avg_cost_usd divides total_cost_usd by total_cost_samples."""
        edge = IntentGraphEdgeState(
            from_intent_class=EnumIntentClass.FEATURE,
            to_intent_class=EnumIntentClass.BUGFIX,
        )
        edge.total_cost_usd = 0.06
        edge.total_cost_samples = 3
        assert edge.avg_cost_usd == pytest.approx(0.02)


# =============================================================================
# update_graph_on_classification — Node upsert
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
class TestUpdateGraphOnClassificationNodeUpsert:
    """Tests for node upsert behaviour in update_graph_on_classification."""

    def test_first_classification_creates_node(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """First classification for a class creates a node."""
        update_graph_on_classification(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.REFACTOR,
        )
        assert EnumIntentClass.REFACTOR in empty_graph.nodes

    def test_first_classification_sets_occurrence_count_to_one(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """First classification sets occurrence_count to 1."""
        update_graph_on_classification(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.FEATURE,
        )
        assert empty_graph.nodes[EnumIntentClass.FEATURE].occurrence_count == 1

    def test_repeated_classifications_increment_count(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Repeated classification events increment occurrence_count."""
        for _ in range(3):
            update_graph_on_classification(
                empty_graph,
                session_id="s1",
                intent_class=EnumIntentClass.BUGFIX,
            )
        assert empty_graph.nodes[EnumIntentClass.BUGFIX].occurrence_count == 3

    def test_cost_accumulates_on_node(self, empty_graph: ModelIntentGraphState) -> None:
        """cost_usd accumulates across classification events."""
        update_graph_on_classification(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.ANALYSIS,
            cost_usd=0.01,
        )
        update_graph_on_classification(
            empty_graph,
            session_id="s2",
            intent_class=EnumIntentClass.ANALYSIS,
            cost_usd=0.02,
        )
        assert empty_graph.nodes[
            EnumIntentClass.ANALYSIS
        ].total_cost_usd == pytest.approx(0.03)

    def test_multiple_intent_classes_create_separate_nodes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Each distinct intent class gets its own node."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_classification(
            empty_graph, session_id="s2", intent_class=EnumIntentClass.BUGFIX
        )
        assert EnumIntentClass.REFACTOR in empty_graph.nodes
        assert EnumIntentClass.BUGFIX in empty_graph.nodes
        assert len(empty_graph.nodes) == 2

    def test_no_edge_on_first_classification(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """No transition edge is created on the first classification for a session."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        assert len(empty_graph.edges) == 0

    def test_session_last_intent_updated(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Session last-intent tracking is updated after classification."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.SECURITY
        )
        assert empty_graph.session_last_intent["s1"] == EnumIntentClass.SECURITY


# =============================================================================
# update_graph_on_classification — Transition detection
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
@pytest.mark.transition
class TestUpdateGraphOnClassificationTransitions:
    """Tests for transition (edge) creation in update_graph_on_classification."""

    def test_two_sequential_intents_create_edge(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Two sequential intents in the same session create a transition edge."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        assert (EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR) in empty_graph.edges

    def test_transition_edge_has_count_one(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """A newly created transition edge has transition_count == 1."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.BUGFIX
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.FEATURE
        )
        edge = empty_graph.edges[(EnumIntentClass.BUGFIX, EnumIntentClass.FEATURE)]
        assert edge.transition_count == 1

    def test_repeated_same_transition_increments_count(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """The same A→B transition observed twice increments count to 2."""
        for _ in range(2):
            update_graph_on_classification(
                empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
            )
            update_graph_on_classification(
                empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
            )
        edge = empty_graph.edges[(EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR)]
        assert edge.transition_count == 2

    def test_different_sessions_independent_transitions(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Transitions in different sessions are independent."""
        # Session 1: ANALYSIS -> REFACTOR
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        # Session 2: BUGFIX -> FEATURE (no cross-session transition)
        update_graph_on_classification(
            empty_graph, session_id="s2", intent_class=EnumIntentClass.BUGFIX
        )
        update_graph_on_classification(
            empty_graph, session_id="s2", intent_class=EnumIntentClass.FEATURE
        )
        # Exactly 2 edges, no cross-session edge
        assert len(empty_graph.edges) == 2
        assert (EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR) in empty_graph.edges
        assert (EnumIntentClass.BUGFIX, EnumIntentClass.FEATURE) in empty_graph.edges

    def test_same_intent_twice_in_session_no_self_loop(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Same intent class twice in one session does NOT create a self-loop edge."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        # No edge because from == to; self-loops are not recorded
        assert (
            EnumIntentClass.REFACTOR,
            EnumIntentClass.REFACTOR,
        ) not in empty_graph.edges

    def test_three_sequential_intents_create_two_edges(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """A -> B -> C creates two edges: A->B and B->C."""
        for cls in [
            EnumIntentClass.ANALYSIS,
            EnumIntentClass.REFACTOR,
            EnumIntentClass.FEATURE,
        ]:
            update_graph_on_classification(
                empty_graph, session_id="s1", intent_class=cls
            )
        assert (EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR) in empty_graph.edges
        assert (EnumIntentClass.REFACTOR, EnumIntentClass.FEATURE) in empty_graph.edges
        assert len(empty_graph.edges) == 2

    def test_session_last_intent_updates_on_each_classification(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """session_last_intent is updated to the most recent intent class."""
        for cls in [
            EnumIntentClass.ANALYSIS,
            EnumIntentClass.REFACTOR,
            EnumIntentClass.BUGFIX,
        ]:
            update_graph_on_classification(
                empty_graph, session_id="s1", intent_class=cls
            )
        assert empty_graph.session_last_intent["s1"] == EnumIntentClass.BUGFIX


# =============================================================================
# update_graph_on_outcome
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
class TestUpdateGraphOnOutcome:
    """Tests for update_graph_on_outcome — success rate accumulation."""

    def test_outcome_creates_node_if_missing(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Outcome event creates a node if none exists yet."""
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.CONFIGURATION,
            success=True,
        )
        assert EnumIntentClass.CONFIGURATION in empty_graph.nodes

    def test_successful_outcome_increments_successes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Successful outcome increments total_successes and total_outcomes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.FEATURE
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.FEATURE,
            success=True,
        )
        node = empty_graph.nodes[EnumIntentClass.FEATURE]
        assert node.total_successes == 1
        assert node.total_outcomes == 1

    def test_failed_outcome_does_not_increment_successes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Failed outcome increments total_outcomes but not total_successes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.FEATURE
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.FEATURE,
            success=False,
        )
        node = empty_graph.nodes[EnumIntentClass.FEATURE]
        assert node.total_successes == 0
        assert node.total_outcomes == 1

    def test_success_rate_after_mixed_outcomes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Success rate reflects ratio of successes to total outcomes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        for success in [True, True, False, True]:
            update_graph_on_outcome(
                empty_graph,
                session_id="s1",
                intent_class=EnumIntentClass.ANALYSIS,
                success=success,
            )
        node = empty_graph.nodes[EnumIntentClass.ANALYSIS]
        assert node.total_successes == 3
        assert node.total_outcomes == 4
        assert node.success_rate == pytest.approx(0.75)

    def test_outcome_updates_edge_success_rate(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Outcome event updates transition edge success rates."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.REFACTOR,
            success=True,
        )
        edge = empty_graph.edges.get(
            (EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR)
        )
        assert edge is not None
        assert edge.total_success_rate_sum == pytest.approx(1.0)
        assert edge.avg_success_rate == pytest.approx(1.0)

    def test_outcome_with_cost_updates_edge_cost(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Outcome cost is accumulated on the transition edge."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.BUGFIX
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.REFACTOR,
            success=True,
            cost_usd=0.05,
        )
        edge = empty_graph.edges[(EnumIntentClass.BUGFIX, EnumIntentClass.REFACTOR)]
        assert edge.total_cost_usd == pytest.approx(0.05)
        assert edge.total_cost_samples == 1
        assert edge.avg_cost_usd == pytest.approx(0.05)

    def test_outcome_without_prior_transition_does_not_update_edge(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Outcome with no prior session intent does not touch edges."""
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.SECURITY,
            success=True,
        )
        assert len(empty_graph.edges) == 0


# =============================================================================
# get_top_transitions
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
@pytest.mark.transition
class TestGetTopTransitions:
    """Tests for get_top_transitions query function."""

    def test_empty_graph_returns_empty_list(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """No transitions in empty graph."""
        result = get_top_transitions(empty_graph)
        assert result == []

    def test_returns_edges_sorted_by_count_descending(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Edges are sorted by transition_count in descending order."""
        # ANALYSIS->REFACTOR: 3 times (use distinct session IDs to avoid back-edges)
        for i in range(3):
            update_graph_on_classification(
                empty_graph, session_id=f"sA-{i}", intent_class=EnumIntentClass.ANALYSIS
            )
            update_graph_on_classification(
                empty_graph, session_id=f"sA-{i}", intent_class=EnumIntentClass.REFACTOR
            )
        # BUGFIX->FEATURE: 1 time
        update_graph_on_classification(
            empty_graph, session_id="sB", intent_class=EnumIntentClass.BUGFIX
        )
        update_graph_on_classification(
            empty_graph, session_id="sB", intent_class=EnumIntentClass.FEATURE
        )
        result = get_top_transitions(empty_graph)
        assert result[0].transition_count == 3
        assert result[1].transition_count == 1

    def test_top_n_limits_results(self, empty_graph: ModelIntentGraphState) -> None:
        """top_n parameter limits the number of results."""
        classes = [
            EnumIntentClass.ANALYSIS,
            EnumIntentClass.REFACTOR,
            EnumIntentClass.BUGFIX,
            EnumIntentClass.FEATURE,
        ]
        for cls in classes:
            update_graph_on_classification(
                empty_graph, session_id="s1", intent_class=cls
            )
        # 3 edges: ANALYSIS->REFACTOR, REFACTOR->BUGFIX, BUGFIX->FEATURE
        result = get_top_transitions(empty_graph, top_n=2)
        assert len(result) == 2

    def test_default_top_n_is_ten(self, empty_graph: ModelIntentGraphState) -> None:
        """Default top_n is 10."""
        # Create 12 distinct transitions
        session = "s1"
        classes = list(EnumIntentClass)[:8]  # up to 8 classes
        for i, cls in enumerate(classes):
            update_graph_on_classification(
                empty_graph, session_id=session, intent_class=cls
            )
        result = get_top_transitions(empty_graph)
        # 7 edges (8 classes, 7 transitions), all returned since < 10
        assert len(result) == 7


# =============================================================================
# get_node_success_rate
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
class TestGetNodeSuccessRate:
    """Tests for get_node_success_rate query function."""

    def test_unknown_class_returns_zero(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Returns 0.0 for unknown intent class."""
        rate = get_node_success_rate(empty_graph, EnumIntentClass.REFACTOR)
        assert rate == 0.0

    def test_no_outcomes_returns_zero(self, empty_graph: ModelIntentGraphState) -> None:
        """Returns 0.0 if node exists but has no outcomes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.BUGFIX
        )
        rate = get_node_success_rate(empty_graph, EnumIntentClass.BUGFIX)
        assert rate == 0.0

    def test_returns_correct_success_rate(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Returns correct success rate after outcomes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.SECURITY
        )
        for success in [True, False]:
            update_graph_on_outcome(
                empty_graph,
                session_id="s1",
                intent_class=EnumIntentClass.SECURITY,
                success=success,
            )
        rate = get_node_success_rate(empty_graph, EnumIntentClass.SECURITY)
        assert rate == pytest.approx(0.5)

    def test_full_success_returns_one(self, empty_graph: ModelIntentGraphState) -> None:
        """Returns 1.0 when all outcomes are successes."""
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.DOCUMENTATION
        )
        for _ in range(3):
            update_graph_on_outcome(
                empty_graph,
                session_id="s1",
                intent_class=EnumIntentClass.DOCUMENTATION,
                success=True,
            )
        rate = get_node_success_rate(empty_graph, EnumIntentClass.DOCUMENTATION)
        assert rate == pytest.approx(1.0)


# =============================================================================
# Multi-session integration scenario
# =============================================================================


@pytest.mark.unit
@pytest.mark.intent_graph
@pytest.mark.transition
class TestIntentGraphIntegrationScenario:
    """Integration-style tests with realistic multi-session sequences."""

    def test_bugfix_then_refactor_pattern(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Simulates 3 sessions where BUGFIX leads to REFACTOR.

        Expected:
            - BUGFIX node: occurrence=3
            - REFACTOR node: occurrence=3
            - BUGFIX->REFACTOR edge: count=3
        """
        for i in range(3):
            session = f"session-{i}"
            update_graph_on_classification(
                empty_graph, session_id=session, intent_class=EnumIntentClass.BUGFIX
            )
            update_graph_on_classification(
                empty_graph, session_id=session, intent_class=EnumIntentClass.REFACTOR
            )
        assert empty_graph.nodes[EnumIntentClass.BUGFIX].occurrence_count == 3
        assert empty_graph.nodes[EnumIntentClass.REFACTOR].occurrence_count == 3
        edge = empty_graph.edges[(EnumIntentClass.BUGFIX, EnumIntentClass.REFACTOR)]
        assert edge.transition_count == 3

    def test_outcome_success_rates_across_sessions(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Mixed outcomes across sessions produce correct aggregate success rates."""
        for i, success in enumerate([True, True, False]):
            session = f"session-{i}"
            update_graph_on_classification(
                empty_graph, session_id=session, intent_class=EnumIntentClass.FEATURE
            )
            update_graph_on_outcome(
                empty_graph,
                session_id=session,
                intent_class=EnumIntentClass.FEATURE,
                success=success,
            )
        rate = get_node_success_rate(empty_graph, EnumIntentClass.FEATURE)
        assert rate == pytest.approx(2 / 3)

    def test_top_transitions_reflects_common_workflow(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Top transition is ANALYSIS->REFACTOR after 5 such sessions."""
        # ANALYSIS->REFACTOR: 5 times
        for i in range(5):
            update_graph_on_classification(
                empty_graph, session_id=f"ar-{i}", intent_class=EnumIntentClass.ANALYSIS
            )
            update_graph_on_classification(
                empty_graph, session_id=f"ar-{i}", intent_class=EnumIntentClass.REFACTOR
            )
        # BUGFIX->FEATURE: 2 times
        for i in range(2):
            update_graph_on_classification(
                empty_graph, session_id=f"bf-{i}", intent_class=EnumIntentClass.BUGFIX
            )
            update_graph_on_classification(
                empty_graph, session_id=f"bf-{i}", intent_class=EnumIntentClass.FEATURE
            )
        top = get_top_transitions(empty_graph, top_n=1)
        assert len(top) == 1
        assert top[0].from_intent_class == EnumIntentClass.ANALYSIS
        assert top[0].to_intent_class == EnumIntentClass.REFACTOR
        assert top[0].transition_count == 5

    def test_all_eight_intent_classes_can_be_graph_nodes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """All 8 EnumIntentClass values can appear as graph nodes."""
        for i, cls in enumerate(EnumIntentClass):
            update_graph_on_classification(
                empty_graph, session_id=f"session-{i}", intent_class=cls
            )
        assert len(empty_graph.nodes) == 8

    def test_transition_avg_success_rate_after_multiple_outcomes(
        self, empty_graph: ModelIntentGraphState
    ) -> None:
        """Transition avg_success_rate is the mean of per-outcome rates."""
        # Session 1: ANALYSIS -> REFACTOR, success
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.ANALYSIS
        )
        update_graph_on_classification(
            empty_graph, session_id="s1", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s1",
            intent_class=EnumIntentClass.REFACTOR,
            success=True,
        )
        # Session 2: ANALYSIS -> REFACTOR, failure
        update_graph_on_classification(
            empty_graph, session_id="s2", intent_class=EnumIntentClass.ANALYSIS
        )
        update_graph_on_classification(
            empty_graph, session_id="s2", intent_class=EnumIntentClass.REFACTOR
        )
        update_graph_on_outcome(
            empty_graph,
            session_id="s2",
            intent_class=EnumIntentClass.REFACTOR,
            success=False,
        )
        edge = empty_graph.edges[(EnumIntentClass.ANALYSIS, EnumIntentClass.REFACTOR)]
        # 2 transitions, 1 success + 1 failure → avg 0.5
        assert edge.transition_count == 2
        assert edge.avg_success_rate == pytest.approx(0.5)
