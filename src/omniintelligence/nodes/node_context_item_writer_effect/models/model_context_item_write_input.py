# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input model for ContextItemWriterEffect.

Receives embedded chunks from EmbeddingGenerationEffect and writes them
to PostgreSQL, Qdrant, and Memgraph with idempotent upsert semantics.

Ticket: OMN-2393
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_context_item_writer_effect.models.model_tier_policy import (
    DEFAULT_TIER_POLICIES,
    ModelTierPolicy,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)


class ModelContextItemWriteInput(BaseModel):
    """Input for a single document write pass.

    Contains all embedded chunks for one source document, along with
    connection configuration and optional tier policy override.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    embedded_chunks: tuple[ModelEmbeddedChunk, ...]
    """Embedded chunks from EmbeddingGenerationEffect to write."""

    source_ref: str
    """Source document reference (e.g. 'docs/CLAUDE.md')."""

    crawl_scope: str
    """Repository/scope that produced these chunks (e.g. 'omninode/omniintelligence')."""

    qdrant_collection: str = Field(default="context_items_v1")
    """Qdrant collection name."""

    qdrant_url: str = Field(default="http://localhost:6333")
    """Qdrant server URL."""

    emit_event: bool = Field(default=True)
    """If True, emit document-indexed.v1 event after successful write."""

    tier_policies: tuple[ModelTierPolicy, ...] = Field(
        default=DEFAULT_TIER_POLICIES,
        description="Ordered tier policy table. First match wins.",
    )

    correlation_id: str | None = None
    """Correlation ID propagated from upstream pipeline stages."""


__all__ = ["ModelContextItemWriteInput"]
