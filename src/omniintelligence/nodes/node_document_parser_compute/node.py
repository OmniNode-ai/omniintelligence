# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node DocumentParserCompute — pure markdown chunking.

Stream B Compute node. Receives raw document content from DocumentFetchEffect
and splits it into structured chunks for downstream classification and embedding.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute driven by contract.yaml
    - Zero I/O — pure function, no side effects
    - Fully deterministic — same input always produces same output
    - Lightweight shell that delegates to handler_document_parser

Responsibilities:
    - Receive raw document content and document metadata (type, source, scope)
    - Select chunking strategy based on doc_type:
        CLAUDE_MD: section-boundary split
        DESIGN_DOC / ARCHITECTURE_DOC: heading + fence preservation
        GENERAL_MARKDOWN: graceful fallback
    - Return ordered list of RawChunk objects for ChunkClassifierCompute

Does NOT:
    - Perform any I/O
    - Call external APIs
    - Classify or embed chunks

Related:
    - OMN-2390: This node implementation
    - OMN-2389: DocumentFetchEffect (upstream)
    - OMN-2391: ChunkClassifierCompute (downstream)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §8
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_input import (
    ModelDocumentParseInput,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_output import (
    ModelDocumentParseOutput,
)


class NodeDocumentParserCompute(
    NodeCompute[ModelDocumentParseInput, ModelDocumentParseOutput]
):
    """Declarative compute node for pure markdown chunking.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - parse_document: Split raw markdown into typed chunks

    Example:
        ```python
        from omniintelligence.nodes.node_document_parser_compute.handlers import (
            handle_document_parse,
        )
        from omniintelligence.nodes.node_document_parser_compute.models import (
            ModelDocumentMeta,
            ModelDocumentParseInput,
            EnumDocType,
        )

        result = handle_document_parse(
            ModelDocumentParseInput(
                doc_meta=ModelDocumentMeta(
                    source_ref="docs/CLAUDE.md",
                    crawl_scope="omninode/omniintelligence",
                    doc_type=EnumDocType.CLAUDE_MD,
                ),
                raw_content="## Overview\\n\\nContent here...",
            )
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeDocumentParserCompute"]
