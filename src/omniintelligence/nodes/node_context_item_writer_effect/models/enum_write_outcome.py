# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Write outcome enum for individual chunk write operations.

Tracks whether each chunk was freshly inserted, soft-updated (fingerprint
changed for same chunk position), or skipped (already up-to-date).

Ticket: OMN-2393
"""

from __future__ import annotations

from enum import Enum


class EnumWriteOutcome(str, Enum):
    """Outcome of a single chunk write attempt."""

    CREATED = "created"
    """Chunk written for the first time — no existing record found."""

    UPDATED = "updated"
    """Chunk position exists but content_fingerprint changed — soft update applied."""

    SKIPPED = "skipped"
    """Chunk already exists with the same content_fingerprint — no-op."""

    FAILED = "failed"
    """Chunk write failed after all attempts — logged as warning, not raised."""


__all__ = ["EnumWriteOutcome"]
