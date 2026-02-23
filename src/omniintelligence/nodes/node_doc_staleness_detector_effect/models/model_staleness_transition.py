# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Staleness transition model for DocStalenessDetectorEffect.

Represents a single staleness transition record stored in the
staleness_transition_log table. Used for crash-safe idempotent
resume of the atomic 3-step sequence.

Ticket: OMN-2394
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_case import (
    EnumStalenessCase,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_transition_step import (
    EnumStalenessTransitionStep,
)


class ModelStalenessTransition(BaseModel):
    """A single staleness transition record.

    Persisted in staleness_transition_log for crash-safe idempotent resume.
    Each row tracks the 3-step atomic sequence for CONTENT_CHANGED cases.
    FILE_DELETED and FILE_MOVED cases complete in a single step.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    transition_id: UUID
    """Unique ID for this transition. Idempotency key for resume."""

    old_item_id: UUID
    """UUID of the existing ContextItem being replaced or blacklisted."""

    source_ref: str
    """Source document path of the old item."""

    new_source_ref: str | None = None
    """New source_ref for FILE_MOVED case. None for all other cases."""

    new_item_id: UUID | None = None
    """UUID of the newly created ContextItem. Set after INDEX_NEW step."""

    staleness_case: EnumStalenessCase
    """Classification of this staleness event."""

    current_step: EnumStalenessTransitionStep = Field(
        default=EnumStalenessTransitionStep.PENDING,
        description="Current step in the atomic sequence.",
    )

    stat_carry_applied: bool = False
    """True if 70% stat carry was applied from old item to new item."""

    embedding_similarity: float | None = None
    """Cosine similarity between old and new content embeddings.
    Used to decide stat carry (>= 0.85 triggers carry). None if not computed."""

    correlation_id: str | None = None
    """Correlation ID propagated from the triggering event."""


__all__ = ["ModelStalenessTransition"]
