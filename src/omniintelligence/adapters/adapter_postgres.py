# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""PostgreSQL protocol handler.

Implements the ProtocolHandler interface for PostgreSQL database operations
using asyncpg for async connection pooling and query execution.

Supported Operations:
    - query: Execute a SELECT query and return rows
    - execute: Execute a DML statement (INSERT, UPDATE, DELETE)

Config Keys:
    - dsn (str, required): PostgreSQL connection string
    - min_size (int, optional): Minimum pool size (default: 2)
    - max_size (int, optional): Maximum pool size (default: 10)
    - command_timeout (float, optional): Query timeout in seconds (default: 30.0)

Params Keys (per operation):
    - sql (str, required): SQL query or statement
    - args (list, optional): Positional arguments for parameterized queries

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

VALID_OPERATIONS = frozenset({"query", "execute"})
DEFAULT_MIN_POOL_SIZE = 2
DEFAULT_MAX_POOL_SIZE = 10
DEFAULT_COMMAND_TIMEOUT = 30.0


# =============================================================================
# Handler Implementation
# =============================================================================


class PostgresHandler:
    """PostgreSQL protocol handler using asyncpg.

    Manages an async connection pool with configurable sizing and
    command timeouts. Supports parameterized queries and DML execution.

    Thread Safety:
        asyncpg pools are safe for concurrent use from multiple
        coroutines within the same event loop.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._dsn: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        """Create an asyncpg connection pool.

        Args:
            config: Connection configuration.
                - dsn (str, required): PostgreSQL connection string.
                - min_size (int, optional): Minimum pool size.
                - max_size (int, optional): Maximum pool size.
                - command_timeout (float, optional): Query timeout.

        Raises:
            ConnectionError: If dsn is missing or connection fails.
        """
        dsn = config.get("dsn")
        if not dsn:
            raise ConnectionError("PostgresHandler requires 'dsn' in config")

        min_size = config.get("min_size", DEFAULT_MIN_POOL_SIZE)
        max_size = config.get("max_size", DEFAULT_MAX_POOL_SIZE)
        command_timeout = config.get("command_timeout", DEFAULT_COMMAND_TIMEOUT)
        self._dsn = str(dsn)

        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
            )
        except Exception as exc:
            self._pool = None
            raise ConnectionError(f"PostgreSQL connection failed: {exc}") from exc

        logger.info(
            "PostgreSQL pool created",
            extra={"min_size": min_size, "max_size": max_size},
        )

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a PostgreSQL operation.

        Args:
            operation: "query" for SELECT or "execute" for DML.
            params: Operation parameters.
                - sql (str, required): SQL query or statement.
                - args (list, optional): Positional arguments.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            For "query": dict with "rows" (list of dicts) and "row_count".
            For "execute": dict with "status" (command tag string).

        Raises:
            RuntimeError: If handler is not connected.
            ConnectionError: If the database is unreachable.
            TimeoutError: If the query times out.
        """
        if self._pool is None:
            raise RuntimeError(
                "PostgresHandler is not connected. Call connect() first."
            )

        if operation not in VALID_OPERATIONS:
            raise ValueError(
                f"Unsupported PostgreSQL operation: {operation}. Must be one of {VALID_OPERATIONS}"
            )

        sql = params.get("sql")
        if not sql:
            raise ValueError("PostgresHandler requires 'sql' in params")

        args = params.get("args", [])

        log_extra: dict[str, Any] = {
            "operation": operation,
            "correlation_id": correlation_id,
        }

        try:
            async with self._pool.acquire() as conn:
                if operation == "query":
                    rows = await conn.fetch(sql, *args)
                    result_rows = [dict(row) for row in rows]
                    logger.debug(
                        "PostgreSQL query completed",
                        extra={**log_extra, "row_count": len(result_rows)},
                    )
                    return {
                        "rows": result_rows,
                        "row_count": len(result_rows),
                    }
                else:  # execute
                    status = await conn.execute(sql, *args)
                    logger.debug(
                        "PostgreSQL execute completed",
                        extra={**log_extra, "status": status},
                    )
                    return {
                        "status": status,
                    }
        except asyncpg.PostgresConnectionError as exc:
            raise ConnectionError(f"PostgreSQL connection error: {exc}") from exc
        except asyncpg.QueryCanceledError as exc:
            raise TimeoutError(f"PostgreSQL query timed out: {exc}") from exc

    async def disconnect(self) -> None:
        """Close the asyncpg connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL pool closed")

    async def health_check(self) -> bool:
        """Check if the PostgreSQL pool is operational.

        Returns:
            True if a connection can be acquired and a simple query succeeds.
        """
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False


__all__ = [
    "PostgresHandler",
]
