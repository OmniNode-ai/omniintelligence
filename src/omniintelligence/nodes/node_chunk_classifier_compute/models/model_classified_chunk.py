# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Classified chunk model for ChunkClassifierCompute.

Ticket: OMN-2391
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)


class ModelClassifiedChunk(BaseModel):
    """A chunk with type classification, tags, and fingerprints.

    Passed to EmbeddingGenerationEffect in-process (not via Kafka).

    Attributes:
        content: The chunk text (trimmed).
        section_heading: Nearest parent ## or ### heading, or None.
        item_type: Classified type from the v1 rule set.
        rule_version: Rule set version used for classification (e.g., "v1").
        tags: Extracted tags for attribution and retrieval.
        content_fingerprint: SHA-256 of normalized content (stable identity).
        version_hash: SHA-256 of content + source_ref + source_version.
        character_offset_start: Byte offset in original document content.
        character_offset_end: Byte offset one past chunk's last character.
        token_estimate: Token estimate: len(content) // 4.
        has_code_fence: True if this chunk contains a code fence.
        code_fence_language: Language tag of first code fence, or None.
        source_ref: Canonical document identifier, propagated from input.
        crawl_scope: Logical scope of the document.
        source_version: Resolved source version (git SHA or updatedAt).
        correlation_id: Optional tracing ID from the fetch operation.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    content: str = Field(description="The chunk text, trimmed of whitespace.")
    section_heading: str | None = Field(
        default=None,
        description="Nearest parent ## or ### heading, or None.",
    )
    item_type: EnumContextItemType = Field(
        description="Classified type from the v1 rule set."
    )
    rule_version: str = Field(
        default="v1",
        description="Rule set version used for classification.",
    )
    tags: tuple[str, ...] = Field(
        description="Extracted tags for attribution and retrieval.",
    )
    content_fingerprint: str = Field(
        description="SHA-256 of normalized content (stable identity)."
    )
    version_hash: str = Field(
        description="SHA-256 of content + source_ref + source_version."
    )
    character_offset_start: int = Field(
        description="Byte offset of first character in original content."
    )
    character_offset_end: int = Field(
        description="Byte offset one past last character in original content."
    )
    token_estimate: int = Field(description="Token estimate: len(content) // 4.")
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


__all__ = ["ModelClassifiedChunk"]
