"""Ingestion Effect - STUB effect node for document ingestion."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/1"


class NodeIngestionEffect(NodeEffect):
    """STUB: Effect node for document ingestion operations.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Accept raw documents/code files for processing
        - Coordinate with vectorization and entity extraction
        - Store ingested content in Qdrant/Memgraph
        - Publish ingestion events to Kafka
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeIngestionEffect is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"ingestion operations. See {_STUB_TRACKING_URL} for implementation progress.",
            category=UserWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def process(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Process ingestion request (STUB - returns empty result).

        Args:
            _input_data: Input data for ingestion operation (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeIngestionEffect.process() is a stub that returns empty results. "
            f"No actual ingestion is performed. See {_STUB_TRACKING_URL} for progress.",
            category=UserWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeIngestionEffect is not yet implemented",
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeIngestionEffect"]
