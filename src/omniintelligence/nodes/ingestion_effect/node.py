# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/1
# Status: Interface defined, implementation pending
"""Ingestion Effect - STUB effect node for document ingestion."""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

from omnibase_core.enums.enum_effect_types import EnumTransactionState
from omnibase_core.models.effect.model_effect_input import ModelEffectInput
from omnibase_core.models.effect.model_effect_output import ModelEffectOutput
from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/1"


class NodeIngestionEffect(NodeEffect):
    """STUB: Effect node for document ingestion operations.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Accept raw documents/code files for processing
        - Coordinate with vectorization and entity extraction
        - Store ingested content in Qdrant/Memgraph
        - Publish ingestion events to Kafka
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeIngestionEffect is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"ingestion operations. See {_STUB_TRACKING_URL} for implementation progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def process(self, input_data: ModelEffectInput) -> ModelEffectOutput:
        """Process ingestion request (STUB - returns empty result).

        Args:
            input_data: Effect input data (unused in stub, but signature matches base class).

        Returns:
            ModelEffectOutput with stub result indicating no content was ingested.
        """
        warnings.warn(
            f"NodeIngestionEffect.process() is a stub that returns empty results. "
            f"No actual ingestion is performed. See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return ModelEffectOutput(
            result={
                "success": True,
                "ingested_content": None,
                "content_metadata": {},
                "metadata": {
                    "status": "stub",
                    "message": "NodeIngestionEffect is not yet implemented",
                    "tracking_url": _STUB_TRACKING_URL,
                },
            },
            operation_id=input_data.operation_id or uuid4(),
            effect_type=input_data.effect_type,
            transaction_state=EnumTransactionState.COMMITTED,
            processing_time_ms=0.0,
            retry_count=0,
            side_effects_applied=[],
            rollback_operations=[],
            timestamp=datetime.now(),
        )


__all__ = ["NodeIngestionEffect"]
