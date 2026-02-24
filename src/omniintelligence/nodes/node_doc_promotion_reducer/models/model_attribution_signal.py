# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Attribution signal model for ContextItem scoring.

Represents a single attribution event linking a session/run outcome to a ContextItem.

Ticket: OMN-2395
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_attribution_signal_type import (
    EnumAttributionSignalType,
)


class ModelAttributionSignal(BaseModel):
    """A single attribution signal linking an outcome to a ContextItem.

    Attributes:
        item_id:     UUID of the ContextItem receiving this signal.
        signal_type: Type of attribution event.
        strength:    Signal strength in [0.0, 1.0]. Caller sets strength per
                     the signal strength table in the ticket.
        session_id:  Optional session UUID for tracing.
        rule_id:     Optional rule identifier (for RULE_FOLLOWED / PATTERN_VIOLATED).
        similarity:  Optional similarity score (for DOC_SECTION_MATCHED).
                     Only present when signal_type == DOC_SECTION_MATCHED.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    signal_type: EnumAttributionSignalType
    strength: float = Field(ge=0.0, le=1.0)
    session_id: UUID | None = None
    rule_id: str | None = None
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)


__all__ = ["ModelAttributionSignal"]
