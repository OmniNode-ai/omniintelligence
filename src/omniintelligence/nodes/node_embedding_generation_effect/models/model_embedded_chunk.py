# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""EmbeddedChunk model — classified chunk with embedding vector.

Ticket: OMN-2392
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)


class ModelEmbeddedChunk(BaseModel):
    """A classified chunk augmented with a 1024-dimensional embedding vector.

    Passed to ContextItemWriterEffect for storage in Qdrant.

    Attributes:
        content: The chunk text (trimmed).
        section_heading: Nearest parent heading, or None.
        item_type: Classification type from ChunkClassifierCompute.
        rule_version: Rule set version used for classification.
        tags: Extracted tags for attribution and retrieval.
        content_fingerprint: SHA-256 of normalized content.
        version_hash: SHA-256 of content + source_ref + source_version.
        character_offset_start: Byte offset of first character.
        character_offset_end: Byte offset one past last character.
        token_estimate: Token estimate (len(content) // 4).
        has_code_fence: True if this chunk contains a code fence.
        code_fence_language: Language tag of first code fence, or None.
        source_ref: Canonical document identifier.
        crawl_scope: Logical scope of the document.
        source_version: Resolved git SHA or updatedAt timestamp.
        correlation_id: Optional tracing ID.
        embedding: 1024-dimensional embedding vector from Qwen3-Embedding-8B.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    content: str = Field(description="The chunk text, trimmed of whitespace.")
    section_heading: str | None = Field(
        default=None,
        description="Nearest parent ## or ### heading, or None.",
    )
    item_type: EnumContextItemType = Field(
        description="Classified type from the v1 rule set.",
    )
    rule_version: str = Field(
        default="v1",
        description="Rule set version used for classification.",
    )
    tags: tuple[str, ...] = Field(
        description="Extracted tags for attribution and retrieval.",
    )
    content_fingerprint: str = Field(
        description="SHA-256 of normalized content (stable identity).",
    )
    version_hash: str = Field(
        description="SHA-256 of content + source_ref + source_version.",
    )
    character_offset_start: int = Field(
        description="Byte offset of first character in original content.",
    )
    character_offset_end: int = Field(
        description="Byte offset one past last character in original content.",
    )
    token_estimate: int = Field(
        description="Token estimate: len(content) // 4.",
    )
    has_code_fence: bool = Field(
        default=False,
        description="True if this chunk contains a code fence.",
    )
    code_fence_language: str | None = Field(
        default=None,
        description="Language tag of first code fence, or None.",
    )
    source_ref: str = Field(description="Canonical document identifier.")
    crawl_scope: str = Field(description="Logical scope of the document.")
    source_version: str | None = Field(
        default=None,
        description="Resolved git SHA or updatedAt timestamp.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing.",
    )
    embedding: tuple[float, ...] = Field(
        description="1024-dimensional embedding vector from Qwen3-Embedding-8B.",
    )


__all__ = ["ModelEmbeddedChunk"]
