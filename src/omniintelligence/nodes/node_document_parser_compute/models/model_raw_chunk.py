# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Raw chunk output model for DocumentParserCompute.

Ticket: OMN-2390
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelRawChunk(BaseModel):
    """A single chunk of raw document content after parsing.

    Passed to ChunkClassifierCompute in-process (not via Kafka).

    Attributes:
        content: The chunk text, trimmed of leading/trailing whitespace.
        section_heading: The nearest parent ## or ### heading, or None if
            the chunk has no ancestor heading.
        character_offset_start: Byte offset of the chunk's first character
            in the original raw_content string (for deduplication).
        character_offset_end: Byte offset one past the chunk's last character.
        token_estimate: Estimated token count: len(content) // 4.
        has_code_fence: True if this chunk contains a complete code fence block.
        code_fence_language: The language tag of the first code fence in this
            chunk, or None if no code fence is present.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    content: str = Field(description="The chunk text, trimmed of whitespace.")
    section_heading: str | None = Field(
        default=None,
        description="Nearest parent ## or ### heading, or None.",
    )
    character_offset_start: int = Field(
        description="Byte offset of first character in original content."
    )
    character_offset_end: int = Field(
        description="Byte offset one past last character in original content."
    )
    token_estimate: int = Field(description="Token estimate: len(content) // 4.")
    has_code_fence: bool = Field(
        default=False,
        description="True if this chunk contains a complete code fence.",
    )
    code_fence_language: str | None = Field(
        default=None,
        description="Language tag of the first code fence, or None.",
    )


__all__ = ["ModelRawChunk"]
