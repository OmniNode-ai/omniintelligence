# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for ChunkClassifierCompute.

Ticket: OMN-2391
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelChunkClassifyInput(BaseModel):
    """Input for a chunk classification request.

    Wraps the raw chunks from DocumentParserCompute together with document
    metadata needed for tag extraction and fingerprinting.

    Attributes:
        source_ref: Canonical document identifier (path or Linear ID).
        crawl_scope: Logical scope of the document.
        source_version: Resolved source version (git SHA or updatedAt).
        doc_type: Document type string (passed through for tag extraction).
        raw_chunks: Sequence of raw chunks from DocumentParserCompute.
        correlation_id: Optional tracing ID from the fetch operation.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    source_ref: str = Field(description="Canonical document identifier.")
    crawl_scope: str = Field(
        description="Logical scope of the document (e.g., 'omninode/omniintelligence')."
    )
    source_version: str | None = Field(
        default=None,
        description="Resolved git SHA or updatedAt timestamp. None if unavailable.",
    )
    doc_type: str = Field(
        default="general_markdown",
        description="Document type string from EnumDocType (for tag extraction).",
    )
    raw_chunks: tuple[ModelRawChunkRef, ...] = Field(
        description="Sequence of raw chunks from DocumentParserCompute."
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


class ModelRawChunkRef(BaseModel):
    """Minimal raw chunk reference for classification input.

    Mirrors the fields of ModelRawChunk from node_document_parser_compute
    without creating a cross-node dependency. Classification only needs
    content and metadata, not the full parser output model.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    content: str
    section_heading: str | None = None
    character_offset_start: int = 0
    character_offset_end: int = 0
    token_estimate: int = 0
    has_code_fence: bool = False
    code_fence_language: str | None = None


__all__ = ["ModelChunkClassifyInput", "ModelRawChunkRef"]
