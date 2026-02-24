# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node EmbeddingGenerationEffect — batch chunk embedding via Qwen3-Embedding-8B.

Stream B Effect node. Receives classified chunks from ChunkClassifierCompute,
generates 1024-dimensional embeddings via the Qwen3-Embedding server (port 8100),
and passes EmbeddedChunks to ContextItemWriterEffect.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - I/O effect: calls Qwen3-Embedding HTTP API
    - Lightweight shell that delegates to handle_embedding_generate

Responsibilities:
    - Receive classified chunks from ChunkClassifierCompute (in-process)
    - Skip chunks with empty content
    - Batch embed chunks via EmbeddingClient.get_embeddings_batch
    - On partial failure: retry failed chunks individually
    - On persistent failure: dead-letter chunk (log warning)
    - Return EmbeddedChunks with 1024-dim vectors for ContextItemWriterEffect

Does NOT:
    - Classify or parse chunks
    - Store embeddings to Qdrant
    - Emit Kafka events

Related:
    - OMN-2392: This node implementation
    - OMN-2391: ChunkClassifierCompute (upstream)
    - OMN-2393: ContextItemWriterEffect (downstream)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §10
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeEmbeddingGenerationEffect(NodeEffect):
    """Declarative effect node for batch chunk embedding.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - generate_embeddings: Batch embed classified chunks via Qwen3-Embedding

    Dependency Injection:
        The ``handle_embedding_generate`` handler accepts an optional
        ``EmbeddingClient`` instance for testing. In production, the client
        is created from the embedding_url field in the input model.

    Example:
        ```python
        import os
        from omniintelligence.nodes.node_embedding_generation_effect.handlers import (
            handle_embedding_generate,
        )
        from omniintelligence.nodes.node_embedding_generation_effect.models import (
            ModelEmbeddingGenerateInput,
        )

        result = await handle_embedding_generate(
            ModelEmbeddingGenerateInput(
                classified_chunks=classified_output.classified_chunks,
                embedding_url=os.environ["LLM_EMBEDDING_URL"],
                source_ref="docs/CLAUDE.md",
            )
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeEmbeddingGenerationEffect"]
