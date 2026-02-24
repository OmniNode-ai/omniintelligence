# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output model for DocStalenessDetectorEffect.

Summarizes staleness transitions triggered and stat carries applied
during a detection pass.

Ticket: OMN-2394
"""

from __future__ import annotations

from pydantic import BaseModel

from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_transition import (
    ModelStalenessTransition,
)


class ModelStalenessDetectOutput(BaseModel):
    """Result of a staleness detection pass."""

    model_config = {"frozen": True, "extra": "ignore"}

    transitions: tuple[ModelStalenessTransition, ...]
    """All transitions triggered or updated during this pass."""

    items_blacklisted: int = 0
    """Number of items transitioned to BLACKLISTED state."""

    items_moved: int = 0
    """Number of items updated with new source_ref (FILE_MOVED)."""

    items_reingested: int = 0
    """Number of items for which re-ingestion was triggered."""

    stat_carries_applied: int = 0
    """Number of stat carry operations performed."""

    items_failed: int = 0
    """Number of candidates that failed processing (non-fatal per item)."""

    dry_run: bool = False
    """True if this was a dry-run pass (no writes performed)."""

    correlation_id: str | None = None
    """Correlation ID propagated from input."""

    @property
    def total_candidates(self) -> int:
        """Total candidates processed."""
        return (
            self.items_blacklisted
            + self.items_moved
            + self.items_reingested
            + self.items_failed
        )


__all__ = ["ModelStalenessDetectOutput"]
