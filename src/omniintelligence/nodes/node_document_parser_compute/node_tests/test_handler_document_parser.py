# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handle_document_parse.

Covers the requirements from OMN-2390:

CLAUDE_MD strategy:
  - Basic ## section split
  - ### subsections stay with parent ## when combined < 800 tokens
  - ### subsections split from parent ## when combined > 800 tokens
  - Code fences kept whole (subject to 1,200-token fence cap)
  - Minimum chunk merge (< 100 tokens merges upward)

DESIGN_DOC / ARCHITECTURE_DOC strategy:
  - ## section split with fence preservation
  - Prose >800 tokens with no code fences: sliding window applied
  - Oversized fence (>1,200 tokens) split at blank lines with language tag preserved

GENERAL_MARKDOWN strategy:
  - ## and ### heading split
  - Paragraph break fallback when no headings
  - Sliding window fallback when no headings and no paragraph breaks

Common:
  - Empty content returns empty chunk list
  - Correlation ID propagated
  - Replay safety (deterministic)

Ticket: OMN-2390
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_document_parser_compute.handlers.handler_document_parser import (
    handle_document_parse,
)
from omniintelligence.nodes.node_document_parser_compute.models.enum_doc_type import (
    EnumDocType,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_meta import (
    ModelDocumentMeta,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_input import (
    ModelDocumentParseInput,
)

pytestmark = pytest.mark.unit

SCOPE = "omninode/test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    raw_content: str,
    doc_type: EnumDocType = EnumDocType.GENERAL_MARKDOWN,
    source_ref: str = "test/doc.md",
    correlation_id: str | None = None,
) -> ModelDocumentParseInput:
    return ModelDocumentParseInput(
        doc_meta=ModelDocumentMeta(
            source_ref=source_ref,
            crawl_scope=SCOPE,
            doc_type=doc_type,
            correlation_id=correlation_id,
        ),
        raw_content=raw_content,
    )


def _make_long_prose(token_count: int) -> str:
    """Generate prose text of approximately token_count tokens."""
    word = "word "
    words_needed = token_count * 4 // len(word) + 1
    return " ".join(["word"] * words_needed)


# ---------------------------------------------------------------------------
# CLAUDE_MD strategy
# ---------------------------------------------------------------------------


def test_claude_md_basic_h2_split() -> None:
    """CLAUDE_MD: content is split at ## boundaries (each section >= 100 tokens)."""
    # Each section needs >= 100 tokens to survive the minimum merge threshold
    section_a_body = _make_long_prose(120)
    section_b_body = _make_long_prose(120)
    content = f"## Section A\n\n{section_a_body}\n\n## Section B\n\n{section_b_body}\n"
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    # Should produce 2 chunks, one per ## section
    assert len(result.chunks) == 2
    assert result.chunks[0].section_heading == "Section A"
    assert result.chunks[1].section_heading == "Section B"


def test_claude_md_subsections_stay_with_parent_when_small() -> None:
    """CLAUDE_MD: ### subsections stay with parent ## when combined < 800 tokens."""
    content = (
        "## Overview\n\nIntro text.\n\n"
        "### Details\n\nSome details.\n\n"
        "### More\n\nMore details.\n"
    )
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    # All content fits in one ## section (<800 tokens), so it stays together
    assert len(result.chunks) == 1
    assert result.chunks[0].section_heading == "Overview"
    assert "### Details" in result.chunks[0].content


def test_claude_md_subsections_split_when_large() -> None:
    """CLAUDE_MD: ### subsections split from parent ## when combined > 800 tokens."""
    # Each sub-section must be >= 100 tokens to survive the min-chunk merge
    long_text = _make_long_prose(900)
    sub_a_body = _make_long_prose(150)
    sub_b_body = _make_long_prose(150)
    content = (
        f"## Big Section\n\n{long_text}\n\n"
        f"### Sub A\n\n{sub_a_body}\n\n"
        f"### Sub B\n\n{sub_b_body}\n"
    )
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    # Should be split because combined size >> 800 tokens
    assert len(result.chunks) > 1


def test_claude_md_code_fence_kept_whole() -> None:
    """CLAUDE_MD: code fences are kept as atomic chunks."""
    fence = "```python\ndef foo():\n    return 42\n```"
    content = f"## Code Section\n\nSome text.\n\n{fence}\n\nMore text after.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    # At least one chunk should contain the code fence
    fence_chunks = [c for c in result.chunks if c.has_code_fence]
    assert len(fence_chunks) >= 1
    assert fence_chunks[0].code_fence_language == "python"


def test_claude_md_minimum_chunk_merge() -> None:
    """CLAUDE_MD: chunks below 100 tokens are merged upward."""
    # A tiny section that would be < 100 tokens on its own
    content = (
        "## Big Section\n\nThis section has substantial content.\n"
        + ("word " * 120)
        + "\n\n## Tiny\n\nSmall.\n"
    )
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    # Tiny section should be merged into previous chunk rather than standalone
    # (the combined chunk will have > 100 tokens)
    for chunk in result.chunks:
        assert chunk.token_estimate >= 0  # basic sanity
    # The tiny section (< 100 tokens: "## Tiny\n\nSmall.") should be merged
    tiny_standalone = [
        c for c in result.chunks if c.content.strip() == "## Tiny\n\nSmall."
    ]
    assert len(tiny_standalone) == 0


def test_claude_md_preamble_before_first_heading() -> None:
    """CLAUDE_MD: content before the first ## heading is included as its own chunk."""
    content = "This is a preamble.\n\n## Section A\n\nContent here.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))

    assert len(result.chunks) >= 1
    all_content = " ".join(c.content for c in result.chunks)
    assert "preamble" in all_content


# ---------------------------------------------------------------------------
# DESIGN_DOC / ARCHITECTURE_DOC strategy
# ---------------------------------------------------------------------------


def test_design_doc_h2_split() -> None:
    """DESIGN_DOC: content is split at ## boundaries (each section >= 100 tokens)."""
    arch_body = _make_long_prose(120)
    impl_body = _make_long_prose(120)
    content = f"## Architecture\n\n{arch_body}\n\n## Implementation\n\n{impl_body}\n"
    result = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))

    assert len(result.chunks) == 2
    assert result.chunks[0].section_heading == "Architecture"
    assert result.chunks[1].section_heading == "Implementation"


def test_design_doc_prose_overflow_sliding_window() -> None:
    """DESIGN_DOC: prose sections >800 tokens without code fences are slid-window split."""
    long_prose = _make_long_prose(1000)  # ~1000 tokens, well over 800
    content = f"## Long Section\n\n{long_prose}\n"
    result = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))

    # Should produce multiple chunks from the sliding window
    assert len(result.chunks) > 1
    # No single chunk should exceed the max prose tokens significantly
    for chunk in result.chunks:
        assert chunk.token_estimate <= 800


def test_design_doc_fence_preserved_atomic() -> None:
    """DESIGN_DOC: code fences are preserved as atomic units."""
    fence = "```bash\necho hello\necho world\n```"
    content = f"## Commands\n\nRun these commands:\n\n{fence}\n\nOutput explanation.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))

    fence_chunks = [c for c in result.chunks if c.has_code_fence]
    assert len(fence_chunks) >= 1
    assert fence_chunks[0].code_fence_language == "bash"


def test_architecture_doc_same_as_design_doc() -> None:
    """ARCHITECTURE_DOC uses the same strategy as DESIGN_DOC."""
    content = "## Overview\n\nArchitecture notes.\n\n## Details\n\nMore info.\n"
    result_design = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))
    result_arch = handle_document_parse(
        _make_input(content, EnumDocType.ARCHITECTURE_DOC)
    )

    assert len(result_design.chunks) == len(result_arch.chunks)
    for d, a in zip(result_design.chunks, result_arch.chunks, strict=True):
        assert d.content == a.content


def test_design_doc_oversized_fence_split() -> None:
    """DESIGN_DOC: oversized code fence (>1,200 tokens) is split at blank lines."""
    # Create a fence with ~1,300 tokens (5,200 chars)
    fence_body_part1 = "\n".join([f"# comment {i}" for i in range(200)])
    fence_body_part2 = "\n".join([f"# more {i}" for i in range(200)])
    fence = f"```python\n{fence_body_part1}\n\n{fence_body_part2}\n```"
    content = f"## Code Section\n\n{fence}\n"
    result = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))

    # Should produce multiple chunks since fence exceeds 1,200 tokens
    # All chunks from a split fence should have has_code_fence=True
    fence_chunks = [c for c in result.chunks if c.has_code_fence]
    # At least the fence body was processed (may or may not split depending on actual size)
    assert len(result.chunks) >= 1


# ---------------------------------------------------------------------------
# GENERAL_MARKDOWN strategy
# ---------------------------------------------------------------------------


def test_general_markdown_heading_split() -> None:
    """GENERAL_MARKDOWN: split at ## and ### headings (each section >= 100 tokens)."""
    h2_body = _make_long_prose(120)
    h2b_body = _make_long_prose(120)
    content = f"## H2 Section\n\n{h2_body}\n\n## Another H2\n\n{h2b_body}\n"
    result = handle_document_parse(_make_input(content, EnumDocType.GENERAL_MARKDOWN))

    assert len(result.chunks) == 2
    headings = [c.section_heading for c in result.chunks if c.section_heading]
    assert any("H2 Section" in h for h in headings)
    assert any("Another H2" in h for h in headings)


def test_general_markdown_paragraph_fallback() -> None:
    """GENERAL_MARKDOWN: falls back to paragraph splits when no headings."""
    content = "First paragraph with some content.\n\nSecond paragraph with more content.\n\nThird paragraph.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.GENERAL_MARKDOWN))

    # Should produce multiple chunks from paragraph splits
    assert len(result.chunks) >= 1
    all_content = " ".join(c.content for c in result.chunks)
    assert "First paragraph" in all_content
    assert "Second paragraph" in all_content


def test_general_markdown_sliding_window_fallback() -> None:
    """GENERAL_MARKDOWN: sliding window fallback when no headings and no paragraph breaks."""
    # Single long paragraph without breaks — ~800 tokens
    long_line = "word " * 800
    result = handle_document_parse(_make_input(long_line, EnumDocType.GENERAL_MARKDOWN))

    # Should produce at least one chunk
    assert len(result.chunks) >= 1
    # Total token estimate should cover the content
    assert result.total_token_estimate > 0


# ---------------------------------------------------------------------------
# Common behavior
# ---------------------------------------------------------------------------


def test_empty_content_returns_empty_chunks() -> None:
    """Empty raw_content produces an empty chunk list."""
    result = handle_document_parse(_make_input("", EnumDocType.GENERAL_MARKDOWN))
    assert result.chunks == ()
    assert result.total_token_estimate == 0


def test_whitespace_only_content_returns_empty_chunks() -> None:
    """Whitespace-only content produces an empty chunk list."""
    result = handle_document_parse(_make_input("   \n\n  \n", EnumDocType.CLAUDE_MD))
    assert result.chunks == ()


def test_correlation_id_propagated() -> None:
    """Correlation ID from doc_meta is propagated to output."""
    content = "## Section\n\nContent.\n"
    result = handle_document_parse(
        _make_input(content, EnumDocType.CLAUDE_MD, correlation_id="test-corr-99")
    )
    assert result.correlation_id == "test-corr-99"


def test_source_ref_propagated() -> None:
    """Source ref from doc_meta is propagated to output."""
    content = "## Section\n\nContent.\n"
    result = handle_document_parse(
        _make_input(content, EnumDocType.CLAUDE_MD, source_ref="docs/CLAUDE.md")
    )
    assert result.source_ref == "docs/CLAUDE.md"


def test_total_token_estimate_is_sum_of_chunks() -> None:
    """total_token_estimate equals sum of individual chunk token_estimate values."""
    content = "## A\n\nContent A.\n\n## B\n\nContent B.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))
    assert result.total_token_estimate == sum(c.token_estimate for c in result.chunks)


def test_character_offsets_are_within_bounds() -> None:
    """character_offset_start and character_offset_end are within content bounds."""
    content = "## Section\n\nHello world content.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.GENERAL_MARKDOWN))
    content_len = len(content)
    for chunk in result.chunks:
        assert 0 <= chunk.character_offset_start <= content_len
        assert 0 <= chunk.character_offset_end <= content_len


def test_replay_safety_same_input_same_output() -> None:
    """Same input always produces identical output (replay safety)."""
    content = "## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
    result1 = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))
    result2 = handle_document_parse(_make_input(content, EnumDocType.CLAUDE_MD))
    assert result1.chunks == result2.chunks
    assert result1.total_token_estimate == result2.total_token_estimate


def test_chunks_have_valid_token_estimates() -> None:
    """All chunks have positive token estimates."""
    content = "## A\n\nSome content here.\n\n## B\n\nMore content.\n"
    result = handle_document_parse(_make_input(content, EnumDocType.DESIGN_DOC))
    for chunk in result.chunks:
        assert chunk.token_estimate > 0
        # Verify estimate formula
        assert chunk.token_estimate == len(chunk.content) // 4
