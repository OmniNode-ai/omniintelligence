# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for EmbeddingGenerationEffect.

Ticket: OMN-2392
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)


class ModelEmbeddingGenerateInput(BaseModel):
    """Input for a batch embedding generation request.

    Wraps classified chunks from ChunkClassifierCompute with the embedding
    server configuration needed for I/O.

    Attributes:
        classified_chunks: Ordered sequence of classified chunks to embed.
        embedding_url: Base URL for the Qwen3-Embedding server.
        source_ref: Canonical document identifier, propagated from upstream.
        correlation_id: Optional tracing ID from upstream.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    classified_chunks: tuple[ModelClassifiedChunk, ...] = Field(
        description="Ordered sequence of classified chunks from ChunkClassifierCompute.",
    )
    embedding_url: str = Field(
        description="Base URL for the Qwen3-Embedding server (from LLM_EMBEDDING_URL).",
    )
    source_ref: str = Field(
        description="Canonical document identifier, propagated from upstream.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelEmbeddingGenerateInput"]
