# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerPatternAssembly."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    AssemblyContextDict,
    WorkflowResultDict,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models.model_pattern_assembly_input import (
    ModelPatternAssemblyInput,
)


class ModelPatternAssemblyRequest(BaseModel):
    """Typed inputs for HandlerPatternAssembly."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    context: AssemblyContextDict
    workflow_result: WorkflowResultDict
    input_data: ModelPatternAssemblyInput = Field(alias="_input_data")
