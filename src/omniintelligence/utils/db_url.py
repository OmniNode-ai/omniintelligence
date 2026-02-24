# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Database URL display utilities.

Provides safe display formatting for database connection URLs by stripping
credentials while preserving host, port, and database information for
logging and error messages.
"""

from __future__ import annotations

import urllib.parse


def safe_db_url_display(url: str) -> str:
    """Extract hostname:port/database from a database URL, stripping credentials.

    Uses urllib.parse.urlparse for safe parsing instead of fragile string
    splitting.  Validates that the URL scheme starts with ``postgres`` to
    avoid misleading output for non-database URLs (e.g. ``https://``).

    Args:
        url: A postgresql:// connection URL, possibly containing credentials.

    Returns:
        A display-safe string in the form ``host:port/database`` (or as much
        as can be extracted).  Falls back to ``"(unparseable URL)"`` if parsing
        fails or the URL is not a PostgreSQL URL.
    """
    try:
        parsed = urllib.parse.urlparse(url)

        # Reject non-PostgreSQL URLs to avoid misleading display output.
        # A valid database URL must have a scheme starting with "postgres"
        # (covers both "postgresql" and "postgres").
        if not parsed.scheme.startswith("postgres"):
            return "(unparseable URL)"

        host = parsed.hostname or "unknown"
        port = parsed.port
        database = (parsed.path or "").lstrip("/")
        if port and database:
            return f"{host}:{port}/{database}"
        if port:
            return f"{host}:{port}"
        if database:
            return f"{host}/{database}"
        return host
    except Exception:
        return "(unparseable URL)"


__all__ = ["safe_db_url_display"]
