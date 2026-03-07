# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for EmbeddingGenerationEffect.

Ticket: OMN-2392, OMN-368
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.enum_embedding_provider import (
    EnumEmbeddingProvider,
)


class ModelEmbeddingGenerateInput(BaseModel):
    """Input for a batch embedding generation request.

    Wraps classified chunks from ChunkClassifierCompute with the embedding
    server configuration needed for I/O.

    Attributes:
        classified_chunks: Ordered sequence of classified chunks to embed.
        embedding_url: Base URL for the embedding server.
        embedding_provider: Which embedding backend to use (default: QWEN3).
        source_ref: Canonical document identifier, propagated from upstream.
        correlation_id: Optional tracing ID from upstream.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    classified_chunks: tuple[ModelClassifiedChunk, ...] = Field(
        description="Ordered sequence of classified chunks from ChunkClassifierCompute.",
    )
    embedding_url: str = Field(
        description="Base URL for the embedding server (from LLM_EMBEDDING_URL).",
    )
    embedding_provider: EnumEmbeddingProvider = Field(
        default=EnumEmbeddingProvider.QWEN3,
        description="Embedding provider backend to use. Defaults to QWEN3.",
    )
    source_ref: str = Field(
        description="Canonical document identifier, propagated from upstream.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelEmbeddingGenerateInput"]
