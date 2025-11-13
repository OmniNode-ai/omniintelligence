"""
Security Utilities for Intelligence Service

Provides input validation and sanitization functions to prevent security
vulnerabilities including log injection attacks.

Created: 2025-10-15
Purpose: Security-focused utility functions for intelligence service

Security Rationale:
-----------------
Correlation IDs are used extensively throughout the codebase in:
1. Logging statements - directly interpolated into log messages
2. Kafka message keys - used for routing and partitioning
3. Event tracking - stored in databases and distributed systems

Without proper sanitization, malicious correlation IDs could:
- Inject newlines and control characters into logs
- Forge log entries by inserting crafted content
- Bypass log aggregation and monitoring systems
- Inject ANSI escape codes to hide malicious activity
- Cause parsing errors in downstream log processing systems

The sanitize_correlation_id function prevents these attacks by:
1. Allowing only alphanumeric characters, hyphens, and underscores
2. Enforcing maximum length to prevent buffer issues
3. Stripping control characters and escape sequences
4. Providing a safe "unknown" fallback for invalid IDs
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum allowed length for correlation IDs
# UUIDs are 36 chars (32 hex + 4 hyphens), allow some buffer
MAX_CORRELATION_ID_LENGTH = 128

# Allowed characters: alphanumeric, hyphens, underscores
# This pattern matches valid UUID format and other safe identifiers
ALLOWED_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Pattern to detect control characters and escape sequences
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_correlation_id(
    correlation_id: Optional[str],
    allow_unknown: bool = True,
    max_length: int = MAX_CORRELATION_ID_LENGTH,
) -> str:
    """
    Sanitize correlation ID to prevent log injection attacks.

    This function validates and sanitizes correlation IDs before they are used in:
    - Log statements (prevents log injection)
    - Kafka message keys (prevents routing issues)
    - Database storage (prevents injection attacks)

    Args:
        correlation_id: The correlation ID to sanitize (can be None)
        allow_unknown: If True, return "unknown" for invalid IDs; if False, raise ValueError
        max_length: Maximum allowed length for correlation ID

    Returns:
        Sanitized correlation ID string (safe for logging and use as keys)

    Raises:
        ValueError: If correlation_id is invalid and allow_unknown is False

    Examples:
        >>> sanitize_correlation_id("abc123-def456")
        'abc123-def456'

        >>> sanitize_correlation_id("abc\\ndef")  # Contains newline
        'unknown'

        >>> sanitize_correlation_id("abc\\x1b[31mRED\\x1b[0m")  # Contains ANSI codes
        'unknown'

        >>> sanitize_correlation_id("a" * 200)  # Too long
        'unknown'

        >>> sanitize_correlation_id(None)
        'unknown'

        >>> sanitize_correlation_id("invalid\\nid", allow_unknown=False)
        ValueError: Invalid correlation_id: contains control characters

    Security Notes:
        - Blocks newlines (\\n, \\r) that could split log entries
        - Blocks control characters (0x00-0x1f, 0x7f-0x9f) including ANSI escape codes
        - Enforces length limit to prevent buffer issues
        - Only allows alphanumeric, hyphens, and underscores
        - Safe for use in log statements, SQL queries, and Kafka keys
    """
    # Handle None or empty
    if not correlation_id:
        if allow_unknown:
            return "unknown"
        raise ValueError("correlation_id cannot be None or empty")

    # Convert to string if needed
    correlation_id_str = str(correlation_id)

    # Check length
    if len(correlation_id_str) > max_length:
        logger.warning(
            f"Correlation ID exceeds maximum length ({len(correlation_id_str)} > {max_length}): "
            f"truncated to 'unknown'"
        )
        if allow_unknown:
            return "unknown"
        raise ValueError(
            f"correlation_id exceeds maximum length: {len(correlation_id_str)} > {max_length}"
        )

    # Check for control characters and escape sequences
    if CONTROL_CHARS_PATTERN.search(correlation_id_str):
        logger.warning(
            f"Correlation ID contains control characters, sanitized to 'unknown': "
            f"original='{correlation_id_str[:50]}...'"
        )
        if allow_unknown:
            return "unknown"
        raise ValueError("correlation_id contains control characters")

    # Check against allowed pattern
    if not ALLOWED_PATTERN.match(correlation_id_str):
        logger.warning(
            f"Correlation ID contains invalid characters, sanitized to 'unknown': "
            f"original='{correlation_id_str[:50]}...'"
        )
        if allow_unknown:
            return "unknown"
        raise ValueError(
            "correlation_id contains invalid characters (only alphanumeric, hyphens, underscores allowed)"
        )

    # All checks passed - return sanitized ID
    return correlation_id_str


def validate_correlation_id_format(correlation_id: str) -> bool:
    """
    Validate correlation ID format without raising exceptions.

    Useful for pre-validation before processing events.

    Args:
        correlation_id: The correlation ID to validate

    Returns:
        True if correlation ID is valid, False otherwise

    Examples:
        >>> validate_correlation_id_format("abc123-def456")
        True

        >>> validate_correlation_id_format("abc\\ndef")
        False

        >>> validate_correlation_id_format(None)
        False
    """
    try:
        sanitized = sanitize_correlation_id(correlation_id, allow_unknown=False)
        return sanitized == correlation_id
    except (ValueError, TypeError):
        return False
