# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output model for ChunkClassifierCompute.

Ticket: OMN-2391
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)


class ModelChunkClassifyOutput(BaseModel):
    """Result of a chunk classification operation.

    Passed directly to EmbeddingGenerationEffect in-process (not via Kafka).

    Attributes:
        classified_chunks: Ordered list of classified chunks.
        source_ref: Canonical document identifier, propagated from input.
        total_chunks: Total number of classified chunks.
        correlation_id: Optional tracing ID, propagated from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    classified_chunks: tuple[ModelClassifiedChunk, ...] = Field(
        description="Ordered list of classified chunks."
    )
    source_ref: str = Field(
        description="Canonical document identifier, propagated from input."
    )
    total_chunks: int = Field(description="Total number of classified chunks.")
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelChunkClassifyOutput"]
