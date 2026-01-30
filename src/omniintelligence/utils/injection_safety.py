"""Injection safety validators for compiled patterns.

Validates that compiled snippets are safe for manifest injection.
Prevents control character injection, format string attacks, and prompt injection.

Ticket: OMN-1672
"""

from __future__ import annotations

import re

# Control characters (excluding tab and newline only)
# Note: Carriage return (0x0d) is rejected as it enables terminal injection attacks
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# ANSI escape sequences
_ANSI_ESCAPE = re.compile(r"\x1b\[[\d;]*[A-Za-z]|\x1b.")

# Dangerous format string patterns (f-string injection)
_DANGEROUS_BRACES = re.compile(r"\{[^}]*(__|\[|\.)")

# Prompt injection markers
_PROMPT_INJECTION = re.compile(
    r"(?i)"
    r"\[?(SYSTEM|ADMIN|OVERRIDE|IGNORE\s+PREVIOUS)\]?\s*:|"
    # Triple-dash only when followed by non-whitespace content (mid-text separator)
    # This allows horizontal rules at end of snippets (no content after)
    r"\n---\s*\n(?=\S)|"
    r"```\s*(system|admin)"
)

# Maximum snippet size in characters
MAX_SNIPPET_SIZE = 4096

# Maximum line length
MAX_LINE_LENGTH = 500


def check_injection_safety(snippet: str) -> bool:
    """Check if a compiled snippet is safe for injection.

    Validates against:
    - Control characters (log/prompt injection)
    - ANSI escape codes (terminal hijacking)
    - Null bytes (truncation attacks)
    - Format string injection (code execution via f-strings)
    - Prompt injection markers (context manipulation)

    Args:
        snippet: The compiled pattern snippet to validate.

    Returns:
        True if safe for injection, False if unsafe.
    """
    if not snippet:
        return False

    # Null byte check (truncation attacks)
    if "\x00" in snippet:
        return False

    # Control character detection
    if _CONTROL_CHARS.search(snippet):
        return False

    # ANSI escape code detection
    if _ANSI_ESCAPE.search(snippet):
        return False

    # Format string injection prevention
    if _DANGEROUS_BRACES.search(snippet):
        return False

    # Prompt injection markers
    if _PROMPT_INJECTION.search(snippet):
        return False

    return True


def validate_format(snippet: str) -> bool:
    """Validate the format of a compiled snippet.

    Checks structural validity:
    - Non-empty after stripping
    - Size within limits
    - Valid UTF-8
    - Balanced code blocks
    - Reasonable line lengths

    Args:
        snippet: The compiled pattern snippet to validate.

    Returns:
        True if format is valid, False otherwise.
    """
    # Non-empty
    if not snippet or not snippet.strip():
        return False

    # Size limit
    if len(snippet) > MAX_SNIPPET_SIZE:
        return False

    # UTF-8 validity
    try:
        snippet.encode("utf-8")
    except UnicodeEncodeError:
        return False

    # Balanced code blocks
    if snippet.count("```") % 2 != 0:
        return False

    # Line length check
    return all(len(line) <= MAX_LINE_LENGTH for line in snippet.split("\n"))


__all__ = [
    "MAX_LINE_LENGTH",
    "MAX_SNIPPET_SIZE",
    "check_injection_safety",
    "validate_format",
]
