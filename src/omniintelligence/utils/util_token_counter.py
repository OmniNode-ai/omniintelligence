# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Token counting utility for pattern compilation.

Uses tiktoken with cl100k_base encoding (GPT-3.5/4 compatible).
Provides consistent token counts for injection budget management.

Ticket: OMN-1672
"""

from __future__ import annotations

from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def get_tokenizer() -> tiktoken.Encoding:
    """Get or create the shared tokenizer instance.

    Uses cl100k_base encoding which is compatible with GPT-3.5/4.
    The tokenizer is cached using lru_cache for thread-safe singleton behavior.

    Returns:
        tiktoken.Encoding: The shared tokenizer instance.
    """
    return tiktoken.get_encoding("cl100k_base")


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
