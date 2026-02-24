# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output model for EmbeddingGenerationEffect.

Ticket: OMN-2392
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)


class ModelEmbeddingGenerateOutput(BaseModel):
    """Result of a batch embedding generation operation.

    Passed directly to ContextItemWriterEffect in-process (not via Kafka).

    Attributes:
        embedded_chunks: Ordered sequence of chunks with embeddings attached.
        source_ref: Canonical document identifier, propagated from input.
        total_chunks: Total number of successfully embedded chunks.
        skipped_chunks: Number of chunks skipped (empty content).
        failed_chunks: Number of chunks that failed after all retries.
        correlation_id: Optional tracing ID, propagated from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    embedded_chunks: tuple[ModelEmbeddedChunk, ...] = Field(
        description="Ordered sequence of chunks with embedding vectors attached.",
    )
    source_ref: str = Field(
        description="Canonical document identifier, propagated from input.",
    )
    total_chunks: int = Field(
        description="Total number of successfully embedded chunks.",
    )
    skipped_chunks: int = Field(
        default=0,
        description="Number of chunks skipped (empty content).",
    )
    failed_chunks: int = Field(
        default=0,
        description="Number of chunks that failed after all retries (dead-lettered).",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelEmbeddingGenerateOutput"]
