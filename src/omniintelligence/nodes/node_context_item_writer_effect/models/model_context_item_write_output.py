# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output model for ContextItemWriterEffect.

Tracks per-document write statistics and whether the document-indexed.v1
event was emitted.

Ticket: OMN-2393
"""

from __future__ import annotations

from pydantic import BaseModel


class ModelContextItemWriteOutput(BaseModel):
    """Result of writing one document's embedded chunks to all stores."""

    model_config = {"frozen": True, "extra": "ignore"}

    source_ref: str
    """Source document reference that was written."""

    items_created: int = 0
    """Number of chunks freshly inserted across all stores."""

    items_updated: int = 0
    """Number of chunks soft-updated (fingerprint changed for same position)."""

    items_skipped: int = 0
    """Number of chunks skipped (already up-to-date, no-op)."""

    items_failed: int = 0
    """Number of chunks that failed to write after all attempts."""

    event_emitted: bool = False
    """True if document-indexed.v1 event was successfully emitted."""

    correlation_id: str | None = None
    """Correlation ID propagated from upstream."""

    @property
    def total_chunks(self) -> int:
        """Total chunks processed (created + updated + skipped + failed)."""
        return (
            self.items_created
            + self.items_updated
            + self.items_skipped
            + self.items_failed
        )


__all__ = ["ModelContextItemWriteOutput"]
