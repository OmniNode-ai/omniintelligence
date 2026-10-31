# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern assembly handler for Pattern Assembler Orchestrator.

Final step (step 4) of the workflow:
assembling the pattern from all component results.

The assembly process:
1. Generates a unique pattern ID
2. Determines pattern type from intent classification
3. Extracts trigger, actions, conditions from trace data
4. Calculates confidence and completeness scores
5. Returns AssembledPatternOutputDict
"""

from __future__ import annotations

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.pattern_assembly_core import (
    _assemble_pattern,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    AssembledPatternOutputDict,
    AssemblyMetadataDict,
    ComponentResultsDict,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models.model_pattern_assembly_request import (
    ModelPatternAssemblyRequest,
)


class HandlerPatternAssembly:
    """Typed entry point for _assemble_pattern."""

    def handle(
        self, request: ModelPatternAssemblyRequest
    ) -> tuple[AssembledPatternOutputDict, ComponentResultsDict, AssemblyMetadataDict]:
        """Delegate to the preserved computation."""
        return _assemble_pattern(
            request.context, request.workflow_result, request.input_data
        )


__all__ = [
    "HandlerPatternAssembly",
]
