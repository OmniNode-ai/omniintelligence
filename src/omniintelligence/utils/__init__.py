# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Utility modules for omniintelligence."""

import contextlib

from omniintelligence.utils.db_url import safe_db_url_display
from omniintelligence.utils.injection_safety import (
    MAX_LINE_LENGTH,
    MAX_SNIPPET_SIZE,
    check_injection_safety,
    validate_format,
)
from omniintelligence.utils.log_sanitizer import (
    LogSanitizer,
    LogSanitizerSettings,
    get_log_sanitizer,
    get_sanitizer_settings,
    sanitize_logs,
)
from omniintelligence.utils.pg_status import parse_pg_status_count

# tiktoken is an optional dependency for token counting; guard against
# environments where it is not installed (e.g. pre-commit isolated venvs).
with contextlib.suppress(ImportError):  # pragma: no cover
    from omniintelligence.utils.util_token_counter import (
        count_tokens,
        get_tokenizer,
    )

__all__ = [
    # Database URL display
    "safe_db_url_display",
    # Injection safety
    "MAX_LINE_LENGTH",
    "MAX_SNIPPET_SIZE",
    # Log sanitization
    "LogSanitizer",
    "LogSanitizerSettings",
    "check_injection_safety",
    # PostgreSQL status parsing
    "parse_pg_status_count",
    # Token counting
    "count_tokens",
    "get_log_sanitizer",
    "get_sanitizer_settings",
    "get_tokenizer",
    "sanitize_logs",
    "validate_format",
]
