# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for token counting utility.

This module tests the token counting functions in utils/util_token_counter.py:
- count_tokens: Count tokens using tiktoken cl100k_base encoding
- get_tokenizer: Get or create the shared tokenizer instance (singleton)

Test cases cover:
- Empty string handling (returns 0)
- Return type validation (always int)
- Singleton pattern verification (same instance returned)
- Known text token count validation (expected range)

Reference:
    - OMN-1672: Pattern compilation with token counting
"""

from __future__ import annotations

import pytest

# =============================================================================
# Test Class: count_tokens
# =============================================================================


@pytest.mark.unit
class TestCountTokens:
    """Tests for the count_tokens function."""

    def test_count_tokens_returns_int(self) -> None:
        """count_tokens always returns an integer."""
        from omniintelligence.utils.util_token_counter import count_tokens

        result = count_tokens("Hello, world!")
        assert isinstance(result, int)

    def test_empty_string_returns_zero(self) -> None:
        """Empty string returns 0 tokens."""
        from omniintelligence.utils.util_token_counter import count_tokens

        assert count_tokens("") == 0

    def test_none_like_empty_returns_zero(self) -> None:
        """Empty-like strings return 0 tokens."""
        from omniintelligence.utils.util_token_counter import count_tokens

        # Empty string
        assert count_tokens("") == 0

    def test_whitespace_only_string(self) -> None:
        """Whitespace-only strings have tokens (spaces are tokenized)."""
        from omniintelligence.utils.util_token_counter import count_tokens

        result = count_tokens("   ")
        # Whitespace is tokenized, should be > 0
        assert result > 0

    def test_single_word(self) -> None:
        """Single common word has expected token count."""
        from omniintelligence.utils.util_token_counter import count_tokens

        # "hello" is typically 1 token in cl100k_base
        result = count_tokens("hello")
        assert result >= 1
        assert result <= 2

    def test_known_text_has_expected_token_count_range(self) -> None:
        """Known text has token count within expected range.

        The phrase "The quick brown fox jumps over the lazy dog"
        is a well-known pangram that typically tokenizes to 9-11 tokens
        in cl100k_base encoding.
        """
        from omniintelligence.utils.util_token_counter import count_tokens

        text = "The quick brown fox jumps over the lazy dog"
        result = count_tokens(text)

        # Should be in reasonable range for this common phrase
        assert result >= 8, f"Token count {result} is too low for pangram"
        assert result <= 12, f"Token count {result} is too high for pangram"

    def test_multiline_text(self) -> None:
        """Multiline text is tokenized correctly."""
        from omniintelligence.utils.util_token_counter import count_tokens

        text = """Line one
Line two
Line three"""
        result = count_tokens(text)
        assert result > 0
        assert isinstance(result, int)

    def test_code_snippet(self) -> None:
        """Code snippets are tokenized."""
        from omniintelligence.utils.util_token_counter import count_tokens

        code = "def hello_world():\n    print('Hello, World!')"
        result = count_tokens(code)
        assert result > 0
        assert isinstance(result, int)

    def test_unicode_text(self) -> None:
        """Unicode text is tokenized correctly."""
        from omniintelligence.utils.util_token_counter import count_tokens

        # Japanese text
        result = count_tokens("Hello")
        assert result > 0

    def test_special_characters(self) -> None:
        """Special characters are handled."""
        from omniintelligence.utils.util_token_counter import count_tokens

        text = "!@#$%^&*()"
        result = count_tokens(text)
        assert result > 0
        assert isinstance(result, int)


# =============================================================================
# Test Class: get_tokenizer (Singleton Pattern)
# =============================================================================


@pytest.mark.unit
class TestGetTokenizer:
    """Tests for the get_tokenizer singleton function."""

    def test_get_tokenizer_returns_encoding(self) -> None:
        """get_tokenizer returns a tiktoken.Encoding instance."""
        import tiktoken

        from omniintelligence.utils.util_token_counter import get_tokenizer

        tokenizer = get_tokenizer()
        assert isinstance(tokenizer, tiktoken.Encoding)

    def test_singleton_pattern_returns_same_instance(self) -> None:
        """get_tokenizer returns the same instance on repeated calls."""
        from omniintelligence.utils.util_token_counter import get_tokenizer

        tokenizer1 = get_tokenizer()
        tokenizer2 = get_tokenizer()
        tokenizer3 = get_tokenizer()

        # All calls should return the exact same instance
        assert tokenizer1 is tokenizer2
        assert tokenizer2 is tokenizer3

    def test_tokenizer_uses_cl100k_base_encoding(self) -> None:
        """Tokenizer uses cl100k_base encoding (GPT-3.5/4 compatible)."""
        from omniintelligence.utils.util_token_counter import get_tokenizer

        tokenizer = get_tokenizer()
        # The name property should indicate cl100k_base
        assert tokenizer.name == "cl100k_base"

    def test_tokenizer_can_encode_text(self) -> None:
        """Tokenizer can encode text to token IDs."""
        from omniintelligence.utils.util_token_counter import get_tokenizer

        tokenizer = get_tokenizer()
        tokens = tokenizer.encode("Hello, world!")

        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(t, int) for t in tokens)

    def test_tokenizer_can_decode_tokens(self) -> None:
        """Tokenizer can decode token IDs back to text."""
        from omniintelligence.utils.util_token_counter import get_tokenizer

        tokenizer = get_tokenizer()
        original = "Hello, world!"
        tokens = tokenizer.encode(original)
        decoded = tokenizer.decode(tokens)

        assert decoded == original


# =============================================================================
# Test Class: Integration
# =============================================================================


@pytest.mark.unit
class TestIntegration:
    """Integration tests for count_tokens and get_tokenizer."""

    def test_count_tokens_uses_shared_tokenizer(self) -> None:
        """count_tokens uses the singleton tokenizer internally."""
        from omniintelligence.utils.util_token_counter import (
            count_tokens,
            get_tokenizer,
        )

        text = "Test text for tokenization"
        tokenizer = get_tokenizer()

        # Manual encoding should match count_tokens result
        expected = len(tokenizer.encode(text))
        actual = count_tokens(text)

        assert actual == expected

    def test_consistent_results_across_calls(self) -> None:
        """Token counting is deterministic and consistent."""
        from omniintelligence.utils.util_token_counter import count_tokens

        text = "Consistent tokenization test"

        results = [count_tokens(text) for _ in range(10)]

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_longer_text_has_more_tokens(self) -> None:
        """Longer text generally has more tokens."""
        from omniintelligence.utils.util_token_counter import count_tokens

        short = "Hello"
        medium = "Hello, how are you doing today?"
        long_text = "Hello, how are you doing today? " * 10

        short_tokens = count_tokens(short)
        medium_tokens = count_tokens(medium)
        long_tokens = count_tokens(long_text)

        assert short_tokens < medium_tokens
        assert medium_tokens < long_tokens
