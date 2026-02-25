# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Attribution signal types for document-derived ContextItems.

Extends the hook-derived signal vocabulary with 4 document-specific signal types.
These signals drive promotion and demotion decisions for document items.

Ticket: OMN-2395
"""

from __future__ import annotations

from enum import Enum


class EnumAttributionSignalType(str, Enum):
    """Signal types for document item attribution.

    Document-specific signals (new in OMN-2395):
        RULE_FOLLOWED:       Output complies with a stated rule in the document.
                             Strength: 0.9 (explicit compliance), 0.5 (implicit).
        STANDARD_CITED:      Model explicitly referenced the document in output.
                             Strength: 1.0 (exact), 0.8 (rule_id), 0.6 (title).
        PATTERN_VIOLATED:    Output violated a stated rule — drives hurt_rate.
                             Strength: 1.0 (enables VALIDATED→QUARANTINE demotion).
        DOC_SECTION_MATCHED: Embedding similarity at injection time.
                             Strength: = similarity score. Only emitted when
                             similarity >= doc_min_similarity (0.65).
    """

    # Document-specific signals (OMN-2395)
    RULE_FOLLOWED = "rule_followed"
    STANDARD_CITED = "standard_cited"
    PATTERN_VIOLATED = "pattern_violated"
    DOC_SECTION_MATCHED = "doc_section_matched"

    # Hook-derived signals (preserved for v0 compatibility)
    HOOK_USED = "hook_used"
    HOOK_SKIPPED = "hook_skipped"
    HOOK_SUCCEEDED = "hook_succeeded"
    HOOK_FAILED = "hook_failed"


# Minimum similarity threshold for DOC_SECTION_MATCHED emission.
# Do NOT emit for weaker matches — that pollutes stats with noise.
DOC_MIN_SIMILARITY: float = 0.65

# Positive signal types: increment used_rate / positive_signals
POSITIVE_SIGNAL_TYPES: frozenset[EnumAttributionSignalType] = frozenset(
    {
        EnumAttributionSignalType.RULE_FOLLOWED,
        EnumAttributionSignalType.STANDARD_CITED,
        EnumAttributionSignalType.DOC_SECTION_MATCHED,
        EnumAttributionSignalType.HOOK_USED,
        EnumAttributionSignalType.HOOK_SUCCEEDED,
    }
)

# Negative signal types: increment hurt_rate
NEGATIVE_SIGNAL_TYPES: frozenset[EnumAttributionSignalType] = frozenset(
    {
        EnumAttributionSignalType.PATTERN_VIOLATED,
        EnumAttributionSignalType.HOOK_FAILED,
    }
)


__all__ = [
    "DOC_MIN_SIMILARITY",
    "EnumAttributionSignalType",
    "NEGATIVE_SIGNAL_TYPES",
    "POSITIVE_SIGNAL_TYPES",
]
