# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelNavigationRetrieveInput — embedding_url is required.

Ticket: OMN-2810
Verifies that embedding_url has no hardcoded default and raises
ValidationError when omitted.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_graph import (
    ContractGraph,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_contract_state import (
    ContractState,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_goal_condition import (
    GoalCondition,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_navigation_retrieve_input import (
    ModelNavigationRetrieveInput,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_goal() -> GoalCondition:
    """Minimal GoalCondition for input construction."""
    return GoalCondition(
        goal_id="goal-001",
        target_component_type="api_gateway",
        target_datasource_class="rest",
        target_policy_tier="tier_2",
    )


@pytest.fixture
def sample_state() -> ContractState:
    """Minimal ContractState for input construction."""
    return ContractState(
        node_id="node-start",
        component_type="api_gateway",
        datasource_class="rest",
        policy_tier="tier_2",
        graph_fingerprint="sha256:abc123",
    )


@pytest.fixture
def sample_graph() -> ContractGraph:
    """Minimal ContractGraph for input construction."""
    return ContractGraph(
        graph_id="graph-001",
        fingerprint="sha256:abc123",
    )


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.unit
class TestEmbeddingUrlRequired:
    """Verify embedding_url is a required field with no default."""

    def test_omitting_embedding_url_raises_validation_error(
        self,
        sample_goal: GoalCondition,
        sample_state: ContractState,
        sample_graph: ContractGraph,
    ) -> None:
        """Constructing without embedding_url must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelNavigationRetrieveInput(
                goal=sample_goal,
                current_state=sample_state,
                graph=sample_graph,
                # embedding_url intentionally omitted
            )

        # Verify the error is about the missing embedding_url field
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "embedding_url" in field_names

    def test_providing_embedding_url_succeeds(
        self,
        sample_goal: GoalCondition,
        sample_state: ContractState,
        sample_graph: ContractGraph,
    ) -> None:
        """Constructing with an explicit embedding_url must succeed."""
        model = ModelNavigationRetrieveInput(
            goal=sample_goal,
            current_state=sample_state,
            graph=sample_graph,
            embedding_url="http://localhost:8100",
        )

        assert model.embedding_url == "http://localhost:8100"

    def test_no_hardcoded_default_url(
        self,
        sample_goal: GoalCondition,
        sample_state: ContractState,
        sample_graph: ContractGraph,
    ) -> None:
        """The model must not contain the old hardcoded 192.168.86.200 default."""
        model = ModelNavigationRetrieveInput(
            goal=sample_goal,
            current_state=sample_state,
            graph=sample_graph,
            embedding_url="http://test:9999",
        )

        # The value should be exactly what was passed, not any hardcoded fallback
        assert model.embedding_url == "http://test:9999"
        assert "192.168.86.200" not in model.embedding_url
