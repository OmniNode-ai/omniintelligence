# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for ModelPatternDefinition and ModelPatternRole."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)


@pytest.mark.unit
class TestModelPatternDefinition:
    """Tests for the four-node ONEX pattern definition model."""

    def test_four_node_onex_pattern_is_valid(self) -> None:
        """A four-node ONEX pattern with compute, effect, orchestrator, and reducer roles is valid."""
        roles = [
            ModelPatternRole(
                role_name="compute",
                base_class="NodeCompute",
                distinguishing_mixin="MixinHandlerRouting",
                required=True,
                description="Pure data processing, no side effects",
            ),
            ModelPatternRole(
                role_name="effect",
                base_class="NodeEffect",
                distinguishing_mixin="MixinEffectExecution",
                required=True,
                description="External I/O (Kafka, PostgreSQL)",
            ),
            ModelPatternRole(
                role_name="orchestrator",
                base_class="NodeOrchestrator",
                distinguishing_mixin="MixinWorkflowExecution",
                required=False,
                description="Coordinate workflows, route operations",
            ),
            ModelPatternRole(
                role_name="reducer",
                base_class="NodeReducer",
                distinguishing_mixin="MixinFSMExecution",
                required=False,
                description="Manage FSM state transitions",
            ),
        ]

        definition = ModelPatternDefinition(
            pattern_name="onex_four_node",
            pattern_type="node_family",
            description="Standard ONEX four-node architectural pattern",
            roles=roles,
            when_to_use="When implementing a new domain capability as an ONEX node family",
            canonical_instance="node_pattern_storage_effect",
        )

        assert definition.pattern_name == "onex_four_node"
        assert definition.pattern_type == "node_family"
        assert len(definition.roles) == 4
        assert definition.roles[0].role_name == "compute"
        assert definition.roles[1].role_name == "effect"
        assert definition.roles[2].role_name == "orchestrator"
        assert definition.roles[3].role_name == "reducer"
        assert definition.canonical_instance == "node_pattern_storage_effect"

    def test_pattern_role_is_frozen(self) -> None:
        """ModelPatternRole is frozen — attribute assignment raises ValidationError."""
        role = ModelPatternRole(
            role_name="compute",
            base_class="NodeCompute",
        )

        with pytest.raises(ValidationError):
            role.role_name = "effect"  # type: ignore[misc]
