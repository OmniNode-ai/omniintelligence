# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerAssemblyContext."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.protocols import (
    WorkflowResultDict,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models.model_pattern_assembly_input import (
    ModelPatternAssemblyInput,
)


class ModelAssemblyContextRequest(BaseModel):
    """Typed inputs for HandlerAssemblyContext."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    input_data: ModelPatternAssemblyInput
    workflow_result: WorkflowResultDict
