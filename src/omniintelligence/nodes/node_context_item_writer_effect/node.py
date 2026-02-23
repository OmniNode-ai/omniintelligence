# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node ContextItemWriterEffect — Stream B terminal writer.

Idempotent write of EmbeddedChunks to PostgreSQL (context_items +
context_items_content), Qdrant (context_items_v1), and Memgraph, with
deterministic bootstrap tier assignment per source_ref pattern.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - I/O effect: writes to PG, Qdrant, and Memgraph
    - Lightweight shell that delegates to handle_context_item_write

Responsibilities:
    - Assign bootstrap tier per source_ref pattern
    - Idempotent upsert: CREATED / UPDATED / SKIPPED per chunk
    - Qdrant vector upsert (replace on UPDATED)
    - Memgraph MERGE edge upsert
    - Emit document-indexed.v1 event on success

Does NOT:
    - Parse or classify chunks
    - Generate embeddings
    - Own connection pool lifecycle (injected via protocols)

Related:
    - OMN-2393: This node implementation
    - OMN-2392: EmbeddingGenerationEffect (upstream)
    - OMN-2383: DB migrations for context_items tables
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md sections 10-11
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeContextItemWriterEffect(NodeEffect):
    """Declarative effect node for idempotent context item writing.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    All three storage backends (PostgreSQL, Qdrant, Memgraph) are injected
    via protocol interfaces defined in handler_context_item_writer.py.

    Supported Operations (defined in contract.yaml handler_routing):
        - write_context_items: Idempotent write to all 3 stores

    Example:
        ```python
        from omniintelligence.nodes.node_context_item_writer_effect.handlers import (
            handle_context_item_write,
        )
        from omniintelligence.nodes.node_context_item_writer_effect.models import (
            ModelContextItemWriteInput,
        )

        result = await handle_context_item_write(
            ModelContextItemWriteInput(
                embedded_chunks=embedding_output.embedded_chunks,
                source_ref="docs/CLAUDE.md",
                crawl_scope="omninode/omniintelligence",
            ),
            context_store=pg_store,
            vector_store=qdrant_store,
            graph_store=memgraph_store,
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeContextItemWriterEffect"]
