# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Context item type enum for ChunkClassifierCompute.

Classification priority order is frozen at v1.
A change to order or trigger strings requires a version bump.

Ticket: OMN-2391
"""

from __future__ import annotations

from enum import Enum


class EnumContextItemType(str, Enum):
    """Type classification for a chunk of document content.

    Priority order (v1, frozen — first match wins):
        1. API_CONSTRAINT  - URL patterns, port numbers, infrastructure config
        2. CONFIG_NOTE     - Environment variables, service configuration
        3. RULE            - Mandatory rules, prohibitions, invariants
        4. FAILURE_PATTERN - Pitfalls, anti-patterns, common mistakes
        5. EXAMPLE         - Code examples, usage demonstrations
        6. REPO_MAP        - Repository layout, directory trees
        7. DOC_EXCERPT     - Default fallback (unmatched chunks)
    """

    API_CONSTRAINT = "api_constraint"
    CONFIG_NOTE = "config_note"
    RULE = "rule"
    FAILURE_PATTERN = "failure_pattern"
    EXAMPLE = "example"
    REPO_MAP = "repo_map"
    DOC_EXCERPT = "doc_excerpt"


__all__ = ["EnumContextItemType"]
