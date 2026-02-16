# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Utilities for parsing asyncpg command status strings.

asyncpg returns status strings from ``execute()`` calls that indicate the
number of rows affected by a DML statement.  The format follows the
PostgreSQL wire protocol:

    - ``"UPDATE N"``       -- N rows updated
    - ``"DELETE N"``       -- N rows deleted
    - ``"INSERT oid N"``   -- N rows inserted (oid is legacy, usually 0)

This module provides a single helper to extract the trailing row count from
these status strings, replacing the multiple private copies that previously
existed across handler modules.
"""

from __future__ import annotations


def parse_pg_status_count(status: str | None) -> int:
    """Parse the row count from a PostgreSQL / asyncpg command status string.

    Args:
        status: asyncpg command status string (e.g., ``"UPDATE 1"``,
            ``"INSERT 0 1"``), or ``None``.

    Returns:
        The row count (last integer in the status string), or 0 if *status*
        is ``None``, empty, or cannot be parsed.
    """
    if not status:
        return 0

    parts = status.split()
    if len(parts) >= 2:
        try:
            return int(parts[-1])
        except ValueError:
            return 0
    return 0
