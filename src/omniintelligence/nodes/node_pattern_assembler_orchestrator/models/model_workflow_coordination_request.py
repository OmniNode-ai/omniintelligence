# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerWorkflowCoordination."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    ProtocolComputeNode,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models.model_pattern_assembly_input import (
    ModelPatternAssemblyInput,
)


class ModelWorkflowCoordinationRequest(BaseModel):
    """Typed inputs for HandlerWorkflowCoordination."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    input_data: ModelPatternAssemblyInput
    trace_parser_node: ProtocolComputeNode | None = None
    intent_classifier_node: ProtocolComputeNode | None = None
    criteria_matcher_node: ProtocolComputeNode | None = None
