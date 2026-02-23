# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for DocumentParserCompute — pure markdown chunking.

Chunking strategies (from OMN-2390 design doc §8):

  CLAUDE_MD — Section boundary split:
    - Primary split at ## boundaries
    - ### subsections stay with parent ## unless alone they exceed 800 tokens
    - Minimum chunk: 100 tokens. Merge upward if below threshold.
    - Code fences kept whole (subject to 1,200-token fence cap)

  DESIGN_DOC / ARCHITECTURE_DOC — Heading with fence preservation:
    - Primary split at ## boundaries
    - Code fences are atomic (subject to 1,200-token fence cap)
    - Prose sections >800 tokens with no code fences: sliding window
      (600-token target, 100-token overlap), split at nearest paragraph break

  GENERAL_MARKDOWN — Graceful fallback:
    - Split at ## then ### heading boundaries
    - If no headings: split at paragraph breaks
    - If no paragraph breaks: 500-token sliding window, 100-token overlap,
      split at nearest sentence boundary

  Code Fence Atomicity Cap (All Strategies):
    - Fences are atomic up to 1,200 tokens
    - If a fence exceeds 1,200 tokens:
        Split at logical blank lines inside the fence.
        Each sub-chunk retains the fence language tag.
        No sub-chunk exceeds 1,200 tokens.

Token estimation: len(content) // 4 — no model call required.
Token target: 200-700 tokens (prose), up to 1,200 (code).
Minimum chunk: 100 tokens (merge upward if below).

Ticket: OMN-2390
"""

from __future__ import annotations

import re
from typing import NamedTuple

from omniintelligence.nodes.node_document_parser_compute.models.enum_doc_type import (
    EnumDocType,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_meta import (
    ModelDocumentMeta,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_input import (
    ModelDocumentParseInput,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_document_parse_output import (
    ModelDocumentParseOutput,
)
from omniintelligence.nodes.node_document_parser_compute.models.model_raw_chunk import (
    ModelRawChunk,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOKEN_ESTIMATE_DIVISOR = 4
_MIN_CHUNK_TOKENS = 100
_MAX_PROSE_TOKENS = 700
_MAX_CODE_TOKENS = 1200
_PROSE_SLIDING_WINDOW_TARGET = 600
_PROSE_SLIDING_WINDOW_OVERLAP = 100
_GENERAL_SLIDING_WINDOW_TARGET = 500
_GENERAL_SLIDING_WINDOW_OVERLAP = 100

# Patterns
_H2_PATTERN = re.compile(r"^## .+", re.MULTILINE)
_H3_PATTERN = re.compile(r"^### .+", re.MULTILINE)
_HEADING_PATTERN = re.compile(r"^#{1,6} .+", re.MULTILINE)
_FENCE_OPEN_PATTERN = re.compile(r"^```(\w*)", re.MULTILINE)
_FENCE_CLOSE_PATTERN = re.compile(r"^```\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _Segment(NamedTuple):
    """A raw text segment with its offset in the original document."""

    text: str
    offset: int
    heading: str | None = None


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Estimate token count as len(text) // 4."""
    return len(text) // _TOKEN_ESTIMATE_DIVISOR


# ---------------------------------------------------------------------------
# Code fence detection helpers
# ---------------------------------------------------------------------------


def _extract_fence_language(fence_open_line: str) -> str | None:
    """Extract language tag from opening fence line (e.g., '```python' -> 'python')."""
    m = _FENCE_OPEN_PATTERN.match(fence_open_line)
    if m:
        lang = m.group(1).strip()
        return lang if lang else None
    return None


def _detect_code_fence(text: str) -> tuple[bool, str | None]:
    """Return (has_code_fence, code_fence_language) for a chunk of text."""
    for line in text.splitlines():
        lang = _extract_fence_language(line)
        if lang is not None or line.startswith("```"):
            return True, lang
    return False, None


# ---------------------------------------------------------------------------
# Segment splitting: split raw content at heading boundaries
# ---------------------------------------------------------------------------


def _split_at_h2(content: str) -> list[_Segment]:
    """Split content at ## heading boundaries. Returns list of _Segment."""
    positions = [m.start() for m in _H2_PATTERN.finditer(content)]
    if not positions:
        return [_Segment(text=content, offset=0, heading=None)]

    segments: list[_Segment] = []

    # Content before first ## heading (preamble)
    if positions[0] > 0:
        preamble = content[: positions[0]]
        if preamble.strip():
            segments.append(_Segment(text=preamble, offset=0, heading=None))

    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(content)
        seg_text = content[pos:end]
        # Extract heading from first line
        first_line = seg_text.splitlines()[0] if seg_text.splitlines() else ""
        heading = first_line.lstrip("#").strip() or None
        segments.append(_Segment(text=seg_text, offset=pos, heading=heading))

    return segments


def _split_at_any_heading(content: str) -> list[_Segment]:
    """Split at ## and ### heading boundaries."""
    positions = [m.start() for m in re.finditer(r"^#{2,3} .+", content, re.MULTILINE)]
    if not positions:
        return [_Segment(text=content, offset=0, heading=None)]

    segments: list[_Segment] = []

    if positions[0] > 0:
        preamble = content[: positions[0]]
        if preamble.strip():
            segments.append(_Segment(text=preamble, offset=0, heading=None))

    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(content)
        seg_text = content[pos:end]
        first_line = seg_text.splitlines()[0] if seg_text.splitlines() else ""
        heading = first_line.lstrip("#").strip() or None
        segments.append(_Segment(text=seg_text, offset=pos, heading=heading))

    return segments


def _split_at_paragraphs(content: str, offset: int = 0) -> list[_Segment]:
    """Split at paragraph boundaries (blank lines)."""
    paragraphs = re.split(r"\n\n+", content)
    segments: list[_Segment] = []
    current_offset = offset
    for para in paragraphs:
        if para.strip():
            segments.append(_Segment(text=para, offset=current_offset, heading=None))
        current_offset += len(para) + 2  # +2 for the \n\n separator
    return segments


# ---------------------------------------------------------------------------
# Code fence splitting (atomicity cap)
# ---------------------------------------------------------------------------


def _split_fence_at_blank_lines(
    fence_text: str,
    fence_offset: int,
    lang_tag: str | None,
    heading: str | None,
) -> list[_Segment]:
    """Split an oversized fence at blank lines inside, each sub-chunk ≤ 1,200 tokens.

    Each sub-chunk retains the fence language tag.
    """
    open_tag = f"```{lang_tag}" if lang_tag else "```"
    close_tag = "```"

    # Extract content between first ``` open and last ``` close
    lines = fence_text.splitlines()
    inner_lines: list[str] = []
    in_fence = False
    for line in lines:
        if not in_fence and line.startswith("```"):
            in_fence = True
            continue
        if in_fence and line.strip() == "```":
            break
        if in_fence:
            inner_lines.append(line)

    # Split inner content at blank lines
    inner_content = "\n".join(inner_lines)
    parts = re.split(r"\n\n+", inner_content)

    result: list[_Segment] = []
    current_lines: list[str] = []
    current_tokens = 0
    rel_offset = fence_offset

    def _flush(chunk_lines: list[str]) -> None:
        chunk_text = f"{open_tag}\n" + "\n".join(chunk_lines) + f"\n{close_tag}"
        chunk_tokens = _estimate_tokens(chunk_text)
        result.append(
            _Segment(
                text=chunk_text,
                offset=rel_offset,
                heading=heading,
            )
        )
        # offset tracking is approximate for sub-fence splits
        _ = chunk_tokens  # tokens recorded in ModelRawChunk.token_estimate

    for part in parts:
        part_tokens = _estimate_tokens(part)
        if current_tokens + part_tokens > _MAX_CODE_TOKENS and current_lines:
            _flush(current_lines)
            current_lines = []
            current_tokens = 0
        current_lines.extend(part.splitlines())
        current_tokens += part_tokens

    if current_lines:
        _flush(current_lines)

    return result


# ---------------------------------------------------------------------------
# Sliding window splitting (prose overflow)
# ---------------------------------------------------------------------------


def _sliding_window_split(
    text: str,
    offset: int,
    heading: str | None,
    target_tokens: int,
    overlap_tokens: int,
) -> list[_Segment]:
    """Split text using a sliding window, breaking at paragraph or sentence boundaries."""
    if not text.strip():
        return []

    segments: list[_Segment] = []
    # Work in approximate character units (target_tokens * 4 chars)
    target_chars = target_tokens * _TOKEN_ESTIMATE_DIVISOR
    overlap_chars = overlap_tokens * _TOKEN_ESTIMATE_DIVISOR

    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + target_chars, text_len)

        if end < text_len:
            # Try to break at nearest paragraph boundary before end
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + overlap_chars:
                end = para_break + 2
            else:
                # Try sentence boundary (. ! ?)
                for boundary_char in (".", "!", "?"):
                    sent_break = text.rfind(boundary_char, start, end)
                    if sent_break > start + overlap_chars:
                        end = sent_break + 1
                        break

        chunk = text[start:end]
        if chunk.strip():
            segments.append(
                _Segment(text=chunk, offset=offset + start, heading=heading)
            )

        if end >= text_len:
            break

        # Next window starts with overlap
        start = max(start + 1, end - overlap_chars)

    return segments


# ---------------------------------------------------------------------------
# Chunk finalization: apply min-token merge and build ModelRawChunk list
# ---------------------------------------------------------------------------


def _segments_to_chunks(
    segments: list[_Segment], original_content: str
) -> list[ModelRawChunk]:
    """Convert _Segment list to ModelRawChunk list, merging undersized chunks upward."""
    if not segments:
        return []

    # Merge upward: if a segment is < MIN_CHUNK_TOKENS, merge with previous
    merged: list[_Segment] = []
    for seg in segments:
        if not seg.text.strip():
            continue
        tokens = _estimate_tokens(seg.text)
        if tokens < _MIN_CHUNK_TOKENS and merged:
            prev = merged[-1]
            combined_text = prev.text + "\n\n" + seg.text
            merged[-1] = _Segment(
                text=combined_text,
                offset=prev.offset,
                heading=prev.heading,
            )
        else:
            merged.append(seg)

    chunks: list[ModelRawChunk] = []
    for seg in merged:
        content = seg.text.strip()
        if not content:
            continue
        token_estimate = _estimate_tokens(content)
        has_fence, fence_lang = _detect_code_fence(content)
        # Compute character offsets in the original content
        char_start = seg.offset
        char_end = seg.offset + len(seg.text)
        chunks.append(
            ModelRawChunk(
                content=content,
                section_heading=seg.heading,
                character_offset_start=char_start,
                character_offset_end=min(char_end, len(original_content)),
                token_estimate=token_estimate,
                has_code_fence=has_fence,
                code_fence_language=fence_lang,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Fence extraction and capping
# ---------------------------------------------------------------------------


def _process_segments_with_fence_cap(
    segments: list[_Segment],
) -> list[_Segment]:
    """Apply 1,200-token fence cap to each segment.

    Segments containing oversized code fences are split at blank lines inside
    the fence. Non-fence segments and small-fence segments are passed through.
    """
    result: list[_Segment] = []
    for seg in segments:
        tokens = _estimate_tokens(seg.text)
        has_fence, lang_tag = _detect_code_fence(seg.text)

        if has_fence and tokens > _MAX_CODE_TOKENS:
            # Split oversized fence at blank lines
            sub_segs = _split_fence_at_blank_lines(
                seg.text, seg.offset, lang_tag, seg.heading
            )
            result.extend(sub_segs)
        else:
            result.append(seg)

    return result


# ---------------------------------------------------------------------------
# Strategy: CLAUDE_MD
# ---------------------------------------------------------------------------


def _parse_claude_md(content: str, _meta: ModelDocumentMeta) -> list[ModelRawChunk]:
    """CLAUDE_MD strategy: section-boundary split.

    - Primary split at ## boundaries
    - ### subsections stay with parent ## unless alone they exceed 800 tokens
    - Minimum chunk: 100 tokens (merge upward)
    - Code fences kept whole (subject to 1,200-token fence cap)
    """
    h2_segments = _split_at_h2(content)
    processed: list[_Segment] = []

    for seg in h2_segments:
        # Check for ### subsections within this ## section
        h3_positions = [m.start() for m in _H3_PATTERN.finditer(seg.text)]

        if not h3_positions:
            # No subsections — apply fence cap and add directly
            capped = _process_segments_with_fence_cap([seg])
            processed.extend(capped)
            continue

        # Try keeping ### subsections with parent ## section
        total_tokens = _estimate_tokens(seg.text)
        if total_tokens <= _MAX_PROSE_TOKENS:
            # Section fits as a whole — keep it together
            capped = _process_segments_with_fence_cap([seg])
            processed.extend(capped)
        else:
            # Split at ### boundaries
            sub_segs = _split_at_any_heading(seg.text)
            # Re-offset sub_segs relative to their position in the full content
            reoffset = [
                _Segment(
                    text=s.text,
                    offset=seg.offset + s.offset,
                    heading=s.heading or seg.heading,
                )
                for s in sub_segs
            ]
            capped = _process_segments_with_fence_cap(reoffset)
            processed.extend(capped)

    return _segments_to_chunks(processed, content)


# ---------------------------------------------------------------------------
# Strategy: DESIGN_DOC / ARCHITECTURE_DOC
# ---------------------------------------------------------------------------


def _parse_design_doc(content: str, _meta: ModelDocumentMeta) -> list[ModelRawChunk]:
    """DESIGN_DOC / ARCHITECTURE_DOC strategy: heading + fence preservation.

    - Primary split at ## boundaries
    - Code fences are atomic (subject to 1,200-token fence cap)
    - Prose sections >800 tokens with no code fences: sliding window
      (600-token target, 100-token overlap), split at nearest paragraph break
    """
    h2_segments = _split_at_h2(content)
    processed: list[_Segment] = []

    for seg in h2_segments:
        # Apply fence cap first
        capped = _process_segments_with_fence_cap([seg])

        for capped_seg in capped:
            capped_tokens = _estimate_tokens(capped_seg.text)
            capped_has_fence, _ = _detect_code_fence(capped_seg.text)

            if capped_tokens > _MAX_PROSE_TOKENS and not capped_has_fence:
                # Oversized prose section — apply sliding window
                sub_segs = _sliding_window_split(
                    capped_seg.text,
                    capped_seg.offset,
                    capped_seg.heading,
                    _PROSE_SLIDING_WINDOW_TARGET,
                    _PROSE_SLIDING_WINDOW_OVERLAP,
                )
                processed.extend(sub_segs)
            else:
                processed.append(capped_seg)

    return _segments_to_chunks(processed, content)


# ---------------------------------------------------------------------------
# Strategy: GENERAL_MARKDOWN
# ---------------------------------------------------------------------------


def _parse_general_markdown(
    content: str, _meta: ModelDocumentMeta
) -> list[ModelRawChunk]:
    """GENERAL_MARKDOWN strategy: graceful fallback.

    - Split at ## then ### heading boundaries
    - If no headings: split at paragraph breaks
    - If no paragraph breaks: 500-token sliding window, 100-token overlap,
      split at nearest sentence boundary
    """
    # Try heading split first
    heading_positions = [
        m.start() for m in re.finditer(r"^#{2,3} .+", content, re.MULTILINE)
    ]

    if heading_positions:
        segments = _split_at_any_heading(content)
    else:
        # Try paragraph split
        para_segments = _split_at_paragraphs(content)
        if len(para_segments) > 1:
            segments = para_segments
        else:
            # Fall back to sliding window
            segments = _sliding_window_split(
                content,
                0,
                None,
                _GENERAL_SLIDING_WINDOW_TARGET,
                _GENERAL_SLIDING_WINDOW_OVERLAP,
            )
            return _segments_to_chunks(segments, content)

    # Apply fence cap to heading/paragraph segments
    processed: list[_Segment] = []
    for seg in segments:
        capped = _process_segments_with_fence_cap([seg])
        for capped_seg in capped:
            capped_tokens = _estimate_tokens(capped_seg.text)
            capped_has_fence, _ = _detect_code_fence(capped_seg.text)

            if capped_tokens > _MAX_PROSE_TOKENS and not capped_has_fence:
                # Oversized prose — sliding window
                sub_segs = _sliding_window_split(
                    capped_seg.text,
                    capped_seg.offset,
                    capped_seg.heading,
                    _GENERAL_SLIDING_WINDOW_TARGET,
                    _GENERAL_SLIDING_WINDOW_OVERLAP,
                )
                processed.extend(sub_segs)
            else:
                processed.append(capped_seg)

    return _segments_to_chunks(processed, content)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


def handle_document_parse(
    input_data: ModelDocumentParseInput,
) -> ModelDocumentParseOutput:
    """Parse raw document content into chunks using the appropriate strategy.

    Pure function — no I/O, fully deterministic. Same input always produces
    the same chunk list.

    Args:
        input_data: Parse request with doc_meta (type, source) and raw_content.

    Returns:
        ModelDocumentParseOutput with ordered list of raw chunks.
    """
    doc_type = input_data.doc_meta.doc_type
    content = input_data.raw_content
    meta = input_data.doc_meta

    if doc_type == EnumDocType.CLAUDE_MD:
        chunks = _parse_claude_md(content, meta)
    elif doc_type in (EnumDocType.DESIGN_DOC, EnumDocType.ARCHITECTURE_DOC):
        chunks = _parse_design_doc(content, meta)
    else:
        # GENERAL_MARKDOWN (default)
        chunks = _parse_general_markdown(content, meta)

    total_tokens = sum(c.token_estimate for c in chunks)

    return ModelDocumentParseOutput(
        chunks=tuple(chunks),
        source_ref=meta.source_ref,
        total_token_estimate=total_tokens,
        correlation_id=meta.correlation_id,
    )


__all__ = ["handle_document_parse"]
