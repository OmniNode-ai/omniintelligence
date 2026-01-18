# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/5
# Status: Interface defined, implementation pending
"""Execution Trace Parser Compute - STUB compute node for trace parsing."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/5"


class NodeExecutionTraceParserCompute(NodeCompute):
    """STUB: Pure compute node for parsing execution traces.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Parse agent execution traces
        - Extract workflow steps and outcomes
        - Support pattern learning from traces
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeExecutionTraceParserCompute is a stub implementation and does not "
            f"provide full functionality. The node accepts inputs but performs no actual "
            f"trace parsing. See {_STUB_TRACKING_URL} for implementation progress.",
            category=UserWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute trace parsing (STUB - returns empty result).

        Args:
            _input_data: Input data for trace parsing (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeExecutionTraceParserCompute.compute() is a stub that returns empty "
            f"results. No actual trace parsing is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=UserWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeExecutionTraceParserCompute is not yet implemented",
            "parsed_traces": [],
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeExecutionTraceParserCompute"]
