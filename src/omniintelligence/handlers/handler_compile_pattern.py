"""Pattern compilation handler.

Compiles raw LearnedPattern records into injectable markdown snippets
with safety validation and token counting.

Invariants:
- If safety check fails, returns None (pattern not injectable)
- compiled_snippet IS NOT NULL means safe + injectable
- No fallback rendering - if not compiled, not eligible

Ticket: OMN-1672
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import NamedTuple

from omniintelligence.utils.injection_safety import (
    check_injection_safety,
    validate_format,
)
from omniintelligence.utils.util_token_counter import count_tokens

logger = logging.getLogger(__name__)

# Compiler version for tracking format changes
COMPILER_VERSION = "1.0.0"


class CompilationResult(NamedTuple):
    """Result of pattern compilation."""

    snippet: str
    token_count: int
    compiled_at: datetime
    compiler_version: str


def format_pattern_snippet(
    pattern_name: str,
    domain_name: str,
    domain_id: str,
    confidence: float,
    quality_score: float,
    keywords: list[str] | tuple[str, ...],
) -> str:
    """Format a pattern into an injectable markdown snippet.

    Args:
        pattern_name: Human-readable pattern name.
        domain_name: Human-readable domain name.
        domain_id: Domain identifier.
        confidence: Pattern confidence score (0.0-1.0).
        quality_score: Pattern quality score (0.0-1.0).
        keywords: List of pattern keywords.

    Returns:
        Formatted markdown snippet with compiler version stamp.
    """
    # Truncate long names with ellipsis indicator
    display_name = (
        pattern_name[:100] + "..." if len(pattern_name) > 100 else pattern_name
    )

    # Limit keywords to first 10, add ellipsis if truncated
    if not keywords:
        keyword_str = "none"
    elif len(keywords) > 10:
        keyword_str = ", ".join(keywords[:10]) + ", ..."
    else:
        keyword_str = ", ".join(keywords)

    return f"""<!-- compiler:v{COMPILER_VERSION} -->
### {display_name}

- **Domain**: {domain_name} (`{domain_id}`)
- **Confidence**: {confidence:.0%}
- **Quality**: {quality_score:.0%}

**Keywords**: {keyword_str}

---"""


def compile_pattern(
    pattern_id: str,
    pattern_name: str,
    domain_name: str,
    domain_id: str,
    confidence: float,
    quality_score: float,
    keywords: list[str] | tuple[str, ...],
) -> CompilationResult | None:
    """Compile a pattern into an injectable snippet.

    Performs safety validation and token counting. Returns None if
    the pattern fails safety checks (should not be stored/injected).

    Args:
        pattern_id: Unique pattern identifier (for logging).
        pattern_name: Human-readable pattern name.
        domain_name: Human-readable domain name.
        domain_id: Domain identifier.
        confidence: Pattern confidence score (0.0-1.0).
        quality_score: Pattern quality score (0.0-1.0).
        keywords: List of pattern keywords.

    Returns:
        CompilationResult if successful, None if safety check fails.
    """
    # Format the snippet
    snippet = format_pattern_snippet(
        pattern_name=pattern_name,
        domain_name=domain_name,
        domain_id=domain_id,
        confidence=confidence,
        quality_score=quality_score,
        keywords=keywords,
    )

    # Safety validation
    if not check_injection_safety(snippet):
        logger.warning(
            "compilation_rejected",
            extra={
                "pattern_id": pattern_id,
                "reason": "injection_unsafe",
                "pattern_name": pattern_name[:50],
            },
        )
        return None

    # Format validation
    if not validate_format(snippet):
        logger.warning(
            "compilation_rejected",
            extra={
                "pattern_id": pattern_id,
                "reason": "format_invalid",
                "pattern_name": pattern_name[:50],
            },
        )
        return None

    # Count tokens
    token_count = count_tokens(snippet)

    return CompilationResult(
        snippet=snippet,
        token_count=token_count,
        compiled_at=datetime.now(UTC),
        compiler_version=COMPILER_VERSION,
    )


__all__ = [
    "COMPILER_VERSION",
    "CompilationResult",
    "compile_pattern",
    "format_pattern_snippet",
]
