# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Staleness case enum for DocStalenessDetectorEffect.

Classifies the type of change detected between a stored ContextItem and
the current document state. Drives the staleness handling policy.

Ticket: OMN-2394
"""

from __future__ import annotations

from enum import Enum


class EnumStalenessCase(str, Enum):
    """Type of staleness condition detected for a context item."""

    FILE_DELETED = "file_deleted"
    """Source document no longer exists. Item transitions to BLACKLISTED immediately."""

    CONTENT_CHANGED_STATIC = "content_changed_static"
    """Content changed for a STATIC_STANDARDS source (e.g. CLAUDE.md).
    Atomic: index new at VALIDATED → verify → blacklist old."""

    CONTENT_CHANGED_REPO = "content_changed_repo"
    """Content changed for a REPO_DERIVED source.
    Atomic: index new at QUARANTINE → verify → blacklist old.
    Stat carry applied if embedding similarity >= 0.85."""

    FILE_MOVED = "file_moved"
    """Same content, different path. Update source_ref in-place.
    No tier change. No new item created."""


__all__ = ["EnumStalenessCase"]
