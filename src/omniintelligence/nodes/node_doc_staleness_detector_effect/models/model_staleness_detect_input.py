# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for DocStalenessDetectorEffect.

Accepts a batch of staleness candidates — either detected by consuming
document.indexed.v1 events or by the periodic crawl state scanner.

Ticket: OMN-2394
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ModelStalenessCandidate(BaseModel):
    """A single candidate for staleness evaluation."""

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    """UUID of the existing ContextItem to check."""

    source_ref: str
    """Current source_ref of the context item."""

    current_version_hash: str
    """version_hash currently stored in PostgreSQL for this item."""

    new_version_hash: str | None = None
    """New version hash if content has changed. None means the caller
    does not know (detector must compute it)."""

    new_source_ref: str | None = None
    """Set when caller detects a file move (new path for same content)."""

    file_exists: bool = True
    """False when the source file has been deleted."""

    current_embedding: tuple[float, ...] | None = None
    """Embedding vector for the old content (used for similarity check)."""

    new_embedding: tuple[float, ...] | None = None
    """Embedding vector for the new content (used for similarity check)."""

    is_static_standards: bool = False
    """True if source_ref is a STATIC_STANDARDS document (e.g. CLAUDE.md).
    Drives CONTENT_CHANGED_STATIC vs CONTENT_CHANGED_REPO policy."""


class ModelStalenessDetectInput(BaseModel):
    """Input for a staleness detection pass."""

    model_config = {"frozen": True, "extra": "ignore"}

    candidates: tuple[ModelStalenessCandidate, ...]
    """Candidates to evaluate. May come from event consumption or periodic scan."""

    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum embedding similarity for stat carry on REPO_DERIVED updates.",
    )

    stat_carry_fraction: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Fraction of old item stats to carry to new item on similarity >= threshold.",
    )

    dry_run: bool = False
    """If True, detect and classify only. Do not write transitions or blacklist."""

    correlation_id: str | None = None
    """Correlation ID for tracing."""


__all__ = ["ModelStalenessCandidate", "ModelStalenessDetectInput"]
