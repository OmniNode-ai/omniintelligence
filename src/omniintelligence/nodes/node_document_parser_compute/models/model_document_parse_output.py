# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output model for DocumentParserCompute.

Ticket: OMN-2390
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_document_parser_compute.models.model_raw_chunk import (
    ModelRawChunk,
)


class ModelDocumentParseOutput(BaseModel):
    """Result of a document parse operation.

    Passed directly to ChunkClassifierCompute in-process (not via Kafka).

    Attributes:
        chunks: Ordered list of raw chunks from the document.
        source_ref: Canonical document identifier, propagated from input.
        total_token_estimate: Sum of token_estimate across all chunks.
        correlation_id: Optional tracing ID, propagated from doc_meta.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    chunks: tuple[ModelRawChunk, ...] = Field(
        description="Ordered list of raw chunks from the document."
    )
    source_ref: str = Field(
        description="Canonical document identifier, propagated from input."
    )
    total_token_estimate: int = Field(
        description="Sum of token_estimate across all chunks."
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelDocumentParseOutput"]
