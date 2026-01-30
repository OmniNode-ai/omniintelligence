"""Token counting utility for pattern compilation.

Uses tiktoken with cl100k_base encoding (GPT-3.5/4 compatible).
Provides consistent token counts for injection budget management.

Ticket: OMN-1672
"""

from __future__ import annotations

import tiktoken

# Singleton tokenizer (encoding is expensive to load)
_TOKENIZER: tiktoken.Encoding | None = None


def get_tokenizer() -> tiktoken.Encoding:
    """Get or create the shared tokenizer instance.

    Uses cl100k_base encoding which is compatible with GPT-3.5/4.
    The tokenizer is cached as a singleton for performance.

    Returns:
        tiktoken.Encoding: The shared tokenizer instance.
    """
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = tiktoken.get_encoding("cl100k_base")
    return _TOKENIZER


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken cl100k_base encoding.

    Args:
        text: Text to count tokens for.

    Returns:
        Number of tokens in the text.
    """
    if not text:
        return 0
    return len(get_tokenizer().encode(text))


__all__ = ["count_tokens", "get_tokenizer"]
