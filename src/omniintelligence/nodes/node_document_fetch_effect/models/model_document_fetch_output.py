# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for DocumentFetchEffect.

Ticket: OMN-2389
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_document_fetch_effect.models.enum_fetch_status import (
    EnumFetchStatus,
)


class ModelDocumentRemovedEvent(BaseModel):
    """Emitted when a document is not found at fetch time.

    Attributes:
        source_ref: Identifier of the missing document.
        crawl_scope: Logical scope of the document.
        correlation_id: Tracing ID from the originating event.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    event_type: str = Field(default="document.removed.v1")
    source_ref: str
    crawl_scope: str
    correlation_id: str | None = None


class ModelDocumentFetchOutput(BaseModel):
    """Result of a document fetch operation.

    Passed directly to ``DocumentParserCompute`` in-process (not via Kafka).

    Attributes:
        source_ref: Canonical document identifier.
        crawl_scope: Logical scope of the document.
        status: Fetch outcome (success, file_not_found, git_sha_unavailable, fetch_failed).
        raw_content: The fetched document content as a string. None when status
            is not SUCCESS or GIT_SHA_UNAVAILABLE.
        resolved_source_version: Resolved git SHA (for GIT_REPO documents) or
            the original updatedAt timestamp (for LINEAR). None when status is
            GIT_SHA_UNAVAILABLE or the source type does not have a version.
        removed_event: Set when status is FILE_NOT_FOUND — the caller should
            emit this event to Kafka.
        error: Human-readable error description when status is not SUCCESS.
        correlation_id: Tracing ID from the originating event.
    """

    model_config = {"extra": "ignore"}

    source_ref: str
    crawl_scope: str
    status: EnumFetchStatus
    raw_content: str | None = None
    resolved_source_version: str | None = None
    removed_event: ModelDocumentRemovedEvent | None = None
    error: str | None = None
    correlation_id: str | None = None


__all__ = [
    "ModelDocumentFetchOutput",
    "ModelDocumentRemovedEvent",
]
