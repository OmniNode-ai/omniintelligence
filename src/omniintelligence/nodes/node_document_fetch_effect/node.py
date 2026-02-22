# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node DocumentFetchEffect — raw document content fetcher.

Stream B entry node. Consumes document.discovered.v1 and document.changed.v1
events, fetches raw content from the appropriate source (disk or blob store),
and returns it for downstream processing by DocumentParserCompute.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic — all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Pattern: "Contract-driven, handlers wired externally"

Responsibilities:
    - Consume document.discovered.v1 and document.changed.v1 events
    - Fetch raw content based on crawler_type:
        FILESYSTEM / WATCHDOG: read from source_ref (absolute path on disk)
        GIT_REPO: read from disk, resolve file-level git SHA
        LINEAR: content is pre-fetched — fetch from blob store via ref
    - Emit document.removed.v1 if file is not found at fetch time
    - Return raw content to DocumentParserCompute (same-process, not Kafka)

Does NOT:
    - Parse, chunk, or classify content
    - Transform content in any way
    - Store content to blob store

Related:
    - OMN-2389: This node implementation
    - OMN-2390: DocumentParserCompute (downstream)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §8
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeDocumentFetchEffect(NodeEffect):
    """Declarative effect node for raw document content fetching.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - fetch_document: Fetch raw document content for downstream parsing

    Dependency Injection:
        The ``handle_document_fetch`` handler accepts a ``ProtocolBlobStore``
        instance for LINEAR documents. Resolved by the caller or RuntimeHostProcess.

    Example:
        ```python
        from omniintelligence.nodes.node_document_fetch_effect import (
            NodeDocumentFetchEffect,
            handle_document_fetch,
        )

        result = await handle_document_fetch(
            ModelDocumentFetchInput(
                source_ref="/path/to/file.md",
                crawler_type=CrawlerType.GIT_REPO,
                repo_path="/path/to/repo",
            ),
            blob_store=my_blob_store,
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeDocumentFetchEffect"]
