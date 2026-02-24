# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Event model for pattern discovery events from external systems.

Published by external systems (e.g., omniclaude) when a new pattern
is discovered during code analysis or session execution.

Two-level idempotency:
- discovery_id: exact replay protection (same event delivered twice)
- signature_hash: semantic dedup (same pattern from different sessions)

Reference:
    - OMN-2059: DB-SPLIT-08 own learned_patterns + add pattern.discovered consumer
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelPatternDiscoveredEvent(BaseModel):
    """Frozen event model for pattern.discovered events.

    Published by external systems (e.g., omniclaude) when a new pattern
    is discovered during code analysis or session execution.

    Two-level idempotency:
    - discovery_id: exact replay protection (same event delivered twice)
    - signature_hash: semantic dedup (same pattern from different sessions)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["PatternDiscovered"] = "PatternDiscovered"
    discovery_id: UUID  # Idempotency key for exact replay protection
    pattern_signature: str = Field(min_length=1, max_length=500)  # Pattern content
    signature_hash: str = Field(min_length=1)  # SHA256 of signature for semantic dedup
    domain: str = Field(min_length=1)  # Domain classification
    # ge=0.5 matches PatternStorageGovernance.MIN_CONFIDENCE in model_pattern_state.py
    confidence: float = Field(ge=0.5, le=1.0)  # Discovery confidence
    source_session_id: UUID  # Session where pattern was discovered
    source_system: str = Field(min_length=1)  # e.g., "omniclaude"
    source_agent: str | None = None  # Optional agent identifier
    correlation_id: UUID  # Distributed tracing
    discovered_at: datetime  # MUST be timezone-aware
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Arbitrary key-value pairs. Only string values are propagated "
            "to pattern storage; non-string values are silently dropped."
        ),
    )

    @field_validator("discovered_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that discovered_at is timezone-aware.

        Note: This check only verifies that ``tzinfo`` is present (not None).
        It does not validate that the timezone is unambiguous -- for example,
        datetimes with ``fold=1`` (representing the second occurrence of an
        ambiguous local time during a DST transition) are accepted.

        Raises:
            ValueError: If discovered_at has no timezone info.
        """
        if v.tzinfo is None:
            raise ValueError("discovered_at must be timezone-aware")
        return v


__all__ = ["ModelPatternDiscoveredEvent"]
