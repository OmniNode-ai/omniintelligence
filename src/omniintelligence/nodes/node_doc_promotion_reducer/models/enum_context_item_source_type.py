# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Source type enum for ContextItems.

Determines which promotion threshold set applies to a given item.

Ticket: OMN-2395
"""

from __future__ import annotations

from enum import Enum


class EnumContextItemSourceType(str, Enum):
    """Source type of a ContextItem — drives promotion threshold selection.

    Document-derived types (subject to OMN-2395 thresholds):
        STATIC_STANDARDS: Standards documents (e.g. CLAUDE.md, ONEX rules).
                          Starts at VALIDATED tier. Lower used_rate bar (0.10).
        REPO_DERIVED:     Repository-derived documentation.
                          Starts at QUARANTINE. Moderate bar (0.15).

    Hook-derived types (v0 thresholds unchanged):
        MEMORY_HOOK:      Hook-injected pattern from session memory.
        MEMORY_LEARNED:   Learned pattern from pattern learning pipeline.
        MEMORY_MANUAL:    Manually added pattern.
    """

    # Document-derived (OMN-2395)
    STATIC_STANDARDS = "static_standards"
    REPO_DERIVED = "repo_derived"

    # Hook-derived (v0, unchanged)
    MEMORY_HOOK = "memory_hook"
    MEMORY_LEARNED = "memory_learned"
    MEMORY_MANUAL = "memory_manual"


__all__ = ["EnumContextItemSourceType"]
