# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/1
# Status: Interface defined, implementation pending
"""Ingestion Effect - STUB effect node for document ingestion.

WARNING: This is a STUB implementation. The node interface is defined but actual
ingestion operations are not yet implemented. All method calls return stub responses.
See tracking issue for implementation progress.
"""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import ClassVar
from uuid import uuid4

from omnibase_core.enums.enum_effect_types import EnumTransactionState
from omnibase_core.models.effect.model_effect_input import ModelEffectInput
from omnibase_core.models.effect.model_effect_output import ModelEffectOutput
from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.ingestion_effect.models import (
    ContentMetadataDict,
    IngestionOperationMetadataDict,
    ModelIngestionOutput,
)

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

    Note:
        This node follows the declarative node pattern - no custom __init__ is needed.
        The base NodeEffect class handles initialization. Stub warnings are emitted
        only when the process() method is called, not on instantiation.
    """

    is_stub: ClassVar[bool] = True

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
        # Use typed output model for consistent contract compliance
        # Explicitly type metadata for type safety and contract compliance
        stub_content_metadata: ContentMetadataDict = {}
        stub_metadata: IngestionOperationMetadataDict = {
            "status": "stub",
            "message": "NodeIngestionEffect is not yet implemented",
            "tracking_url": _STUB_TRACKING_URL,
        }
        typed_output = ModelIngestionOutput(
            success=True,
            ingested_content=None,
            content_metadata=stub_content_metadata,
            metadata=stub_metadata,
        )
        return ModelEffectOutput(
            result=typed_output.model_dump(),
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
