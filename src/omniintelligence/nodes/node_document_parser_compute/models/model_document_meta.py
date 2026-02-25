# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Document metadata model for DocumentParserCompute.

Ticket: OMN-2390
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_document_parser_compute.models.enum_doc_type import (
    EnumDocType,
)


class ModelDocumentMeta(BaseModel):
    """Metadata about the document being parsed.

    Attributes:
        source_ref: Canonical document identifier (path or Linear ID).
        crawl_scope: Logical scope of the document.
        doc_type: Detected document type — determines chunking strategy.
        source_version: Resolved source version (git SHA or updatedAt).
        correlation_id: Optional tracing ID from the fetch operation.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    source_ref: str = Field(
        description="Canonical document identifier (path or Linear ID)."
    )
    crawl_scope: str = Field(
        description="Logical scope of the document (e.g., 'omninode/omniintelligence')."
    )
    doc_type: EnumDocType = Field(
        default=EnumDocType.GENERAL_MARKDOWN,
        description="Detected document type. Determines chunking strategy.",
    )
    source_version: str | None = Field(
        default=None,
        description="Resolved git SHA or updatedAt timestamp. None if unavailable.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )


__all__ = ["ModelDocumentMeta"]
