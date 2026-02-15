"""Pattern Assembler Orchestrator Node.

Thin shell orchestrator node for assembling patterns from components.
All logic is delegated to the handler function following ONEX declarative pattern.

Workflow (4 steps):
1. Parse traces (execution_trace_parser_compute)
2. Classify intent (node_intent_classifier_compute)
3. Match criteria (success_criteria_matcher_compute)
4. Assemble pattern (internal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omnibase_core.nodes.node_orchestrator import NodeOrchestrator

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers import (
    handle_pattern_assembly_orchestrate,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    ModelPatternAssemblyOutput,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternAssemblerOrchestrator(NodeOrchestrator):
    """Orchestrator node for assembling patterns from components.

    This node coordinates the 4-phase pattern assembly workflow:
    1. Parse execution traces for structured events
    2. Classify user intent from content
    3. Match results against success criteria
    4. Assemble final pattern from component results

    The node is a thin shell following the ONEX declarative pattern.
    All orchestration logic is delegated to the handler function.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the orchestrator node.

        Args:
            container: ONEX container with node configuration.
        """
        super().__init__(container)

    async def orchestrate(  # any-ok: dict invariance — orchestrator handles heterogeneous JSON payloads
        self, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Orchestrate pattern assembly by delegating to handler function.

        Args:
            input_data: Input dictionary to parse into ModelPatternAssemblyInput.

        Returns:
            Output dictionary from ModelPatternAssemblyOutput.
        """
        # Handler guarantees structured output (never raises); model_dump() is safe.
        result: ModelPatternAssemblyOutput = await handle_pattern_assembly_orchestrate(
            input_data
        )
        return result.model_dump()


__all__ = ["NodePatternAssemblerOrchestrator"]
