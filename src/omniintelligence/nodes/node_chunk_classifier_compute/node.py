# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node ChunkClassifierCompute — deterministic chunk type classification.

Stream B Compute node. Receives raw chunks from DocumentParserCompute and
classifies each chunk using the v1 frozen rule set.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute driven by contract.yaml
    - Zero I/O — pure function, no side effects
    - Fully deterministic — same input always produces same output
    - Lightweight shell that delegates to handler_chunk_classifier

Responsibilities:
    - Classify each chunk into one of 7 types (v1 frozen rule set)
    - Extract tags (source, section, repo, lang, svc, doctype)
    - Compute content fingerprint and version hash for dedup and replay
    - Return ordered list of ClassifiedChunk objects for EmbeddingGenerationEffect

Does NOT:
    - Perform any I/O
    - Call external APIs or LLMs
    - Embed or store chunks

Related:
    - OMN-2391: This node implementation
    - OMN-2390: DocumentParserCompute (upstream)
    - OMN-2392: EmbeddingGenerationEffect (downstream)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §9
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_input import (
    ModelChunkClassifyInput,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_output import (
    ModelChunkClassifyOutput,
)


class NodeChunkClassifierCompute(
    NodeCompute[ModelChunkClassifyInput, ModelChunkClassifyOutput]
):
    """Declarative compute node for deterministic chunk classification.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - classify_chunks: Apply v1 frozen rules to classify raw chunks

    Example:
        ```python
        from omniintelligence.nodes.node_chunk_classifier_compute.handlers import (
            handle_chunk_classify,
        )
        from omniintelligence.nodes.node_chunk_classifier_compute.models import (
            ModelChunkClassifyInput,
            ModelRawChunkRef,
        )

        result = handle_chunk_classify(
            ModelChunkClassifyInput(
                source_ref="docs/CLAUDE.md",
                crawl_scope="omninode/omniintelligence",
                raw_chunks=(
                    ModelRawChunkRef(
                        content="You MUST use frozen=True for all event models.",
                        section_heading="Rules",
                    ),
                ),
            )
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeChunkClassifierCompute"]
