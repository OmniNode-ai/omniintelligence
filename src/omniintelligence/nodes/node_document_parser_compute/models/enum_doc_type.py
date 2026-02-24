# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Document type enum for DocumentParserCompute.

Ticket: OMN-2390
"""

from __future__ import annotations

from enum import Enum


class EnumDocType(str, Enum):
    """Detected document type that determines the chunking strategy.

    Attributes:
        CLAUDE_MD: CLAUDE.md files — section-boundary split with subsection
            merging and 800-token section cap.
        DESIGN_DOC: Design documents — heading split with code fence
            preservation and prose sliding window.
        ARCHITECTURE_DOC: Architecture documents — same strategy as DESIGN_DOC.
        GENERAL_MARKDOWN: General markdown — graceful fallback: headings,
            then paragraphs, then sliding window.
    """

    CLAUDE_MD = "claude_md"
    DESIGN_DOC = "design_doc"
    ARCHITECTURE_DOC = "architecture_doc"
    GENERAL_MARKDOWN = "general_markdown"


__all__ = ["EnumDocType"]
