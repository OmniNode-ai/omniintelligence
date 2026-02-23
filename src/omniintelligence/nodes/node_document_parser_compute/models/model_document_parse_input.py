# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for DocumentParserCompute.

Ticket: OMN-2390
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_document_parser_compute.models.model_document_meta import (
    ModelDocumentMeta,
)


class ModelDocumentParseInput(BaseModel):
    """Input for a document parse request.

    Attributes:
        doc_meta: Metadata about the document (type, source, scope).
        raw_content: The full raw document content as a UTF-8 string.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    doc_meta: ModelDocumentMeta = Field(
        description="Document metadata including doc_type for strategy selection."
    )
    raw_content: str = Field(description="Full raw document content as a UTF-8 string.")


__all__ = ["ModelDocumentParseInput"]
