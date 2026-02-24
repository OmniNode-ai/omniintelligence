# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for EmbeddingGenerationEffect — batch chunk embedding via Qwen3-Embedding.

Behavior:
  - Receives classified chunks from ChunkClassifierCompute
  - Skips chunks with empty content (logs warning)
  - Generates 1024-dimensional embeddings via EmbeddingClient.get_embeddings_batch
  - On partial batch failure: retries failed chunks individually
  - On persistent failure: dead-letters chunk (logs warning, increments failed_chunks)
  - Attaches embedding vector to each successfully embedded chunk
  - Returns ModelEmbeddingGenerateOutput with embedded_chunks, skip/fail counts

Error handling:
  - EmbeddingClientError on empty text: skip chunk (counted in skipped_chunks)
  - EmbeddingClientError on batch failure: retry individually
  - Persistent individual failure: dead-letter (counted in failed_chunks)
  - Connection/timeout errors propagate (batch-level failure, dead-letter entire document)

Ticket: OMN-2392
"""

from __future__ import annotations

import logging

from omniintelligence.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
    ModelEmbeddingClientConfig,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_generate_input import (
    ModelEmbeddingGenerateInput,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_generate_output import (
    ModelEmbeddingGenerateOutput,
)

logger = logging.getLogger(__name__)


def _chunk_to_embedded(
    chunk: ModelClassifiedChunk,
    embedding: list[float],
) -> ModelEmbeddedChunk:
    """Attach an embedding vector to a classified chunk."""
    return ModelEmbeddedChunk(
        content=chunk.content,
        section_heading=chunk.section_heading,
        item_type=chunk.item_type,
        rule_version=chunk.rule_version,
        tags=chunk.tags,
        content_fingerprint=chunk.content_fingerprint,
        version_hash=chunk.version_hash,
        character_offset_start=chunk.character_offset_start,
        character_offset_end=chunk.character_offset_end,
        token_estimate=chunk.token_estimate,
        has_code_fence=chunk.has_code_fence,
        code_fence_language=chunk.code_fence_language,
        source_ref=chunk.source_ref,
        crawl_scope=chunk.crawl_scope,
        source_version=chunk.source_version,
        correlation_id=chunk.correlation_id,
        embedding=tuple(embedding),
    )


async def handle_embedding_generate(
    input_data: ModelEmbeddingGenerateInput,
    *,
    client: EmbeddingClient | None = None,
) -> ModelEmbeddingGenerateOutput:
    """Generate embeddings for all classified chunks in the input.

    Algorithm:
      1. Separate chunks into embeddable (non-empty content) and skip (empty).
      2. Attempt batch embedding via client.get_embeddings_batch.
      3. On batch failure, retry each embeddable chunk individually.
      4. Chunks that fail individually are dead-lettered (counted in failed_chunks).
      5. Return output with embedded_chunks, skipped_chunks, failed_chunks counts.

    Args:
        input_data: Embedding request with classified chunks and server URL.
        client: Optional pre-configured EmbeddingClient (for testing).
                If None, a new client is created from input_data.embedding_url.

    Returns:
        ModelEmbeddingGenerateOutput with embedded chunks and error counts.
    """
    embedded: list[ModelEmbeddedChunk] = []
    skipped = 0
    failed = 0

    # Partition chunks: skip empty, queue the rest for embedding
    embeddable: list[ModelClassifiedChunk] = []
    for chunk in input_data.classified_chunks:
        if not chunk.content or not chunk.content.strip():
            logger.warning(
                "Skipping empty chunk (source_ref=%s, fingerprint=%s)",
                chunk.source_ref,
                chunk.content_fingerprint,
            )
            skipped += 1
        else:
            embeddable.append(chunk)

    if not embeddable:
        return ModelEmbeddingGenerateOutput(
            embedded_chunks=tuple(embedded),
            source_ref=input_data.source_ref,
            total_chunks=0,
            skipped_chunks=skipped,
            failed_chunks=failed,
            correlation_id=input_data.correlation_id,
        )

    # Create client if not injected (production path)
    config = ModelEmbeddingClientConfig(base_url=input_data.embedding_url)
    own_client = client is None
    active_client = client if client is not None else EmbeddingClient(config)

    try:
        if own_client:
            await active_client.connect()

        texts = [chunk.content for chunk in embeddable]

        try:
            # Attempt batch embedding
            vectors = await active_client.get_embeddings_batch(texts)
            for chunk, vector in zip(embeddable, vectors, strict=True):
                embedded.append(_chunk_to_embedded(chunk, vector))

        except EmbeddingClientError:
            # Batch failed — retry each chunk individually
            logger.warning(
                "Batch embedding failed for source_ref=%s, retrying individually (%d chunks)",
                input_data.source_ref,
                len(embeddable),
            )
            for chunk in embeddable:
                try:
                    vector = await active_client.get_embedding(chunk.content)
                    embedded.append(_chunk_to_embedded(chunk, vector))
                except EmbeddingClientError:
                    logger.warning(
                        "Dead-lettering chunk (source_ref=%s, fingerprint=%s): "
                        "failed after individual retry",
                        chunk.source_ref,
                        chunk.content_fingerprint,
                    )
                    failed += 1

    finally:
        if own_client:
            await active_client.close()

    return ModelEmbeddingGenerateOutput(
        embedded_chunks=tuple(embedded),
        source_ref=input_data.source_ref,
        total_chunks=len(embedded),
        skipped_chunks=skipped,
        failed_chunks=failed,
        correlation_id=input_data.correlation_id,
    )


__all__ = ["handle_embedding_generate"]
