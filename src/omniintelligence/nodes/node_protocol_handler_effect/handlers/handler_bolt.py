# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Bolt protocol handler for Neo4j/Memgraph.

Implements the ProtocolHandler interface for graph database operations
via the Neo4j Bolt protocol driver.

Supported Operations:
    - query: Execute a read query (Cypher)
    - write: Execute a write transaction (Cypher)

Config Keys:
    - uri (str, required): Bolt URI (e.g., "bolt://localhost:7687")
    - auth (list[str], optional): [username, password] for authentication
    - database (str, optional): Target database name (default: "neo4j")
    - max_connection_pool_size (int, optional): Connection pool size (default: 50)

Params Keys (per operation):
    - cypher (str, required): Cypher query string
    - parameters (dict, optional): Query parameters

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

VALID_OPERATIONS = frozenset({"query", "write"})
DEFAULT_DATABASE = "neo4j"
DEFAULT_POOL_SIZE = 50


# =============================================================================
# Handler Implementation
# =============================================================================


class BoltHandler:
    """Neo4j/Memgraph Bolt protocol handler.

    Manages an async Neo4j driver with connection pooling. Supports
    read queries and write transactions via Cypher.

    Thread Safety:
        The Neo4j async driver is safe for concurrent use from multiple
        coroutines within the same event loop.
    """

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._database: str = DEFAULT_DATABASE
        self._uri: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        """Create a Neo4j async driver with the given configuration.

        Args:
            config: Connection configuration.
                - uri (str, required): Bolt URI.
                - auth (list[str], optional): [username, password].
                - database (str, optional): Target database.
                - max_connection_pool_size (int, optional): Pool size.

        Raises:
            ConnectionError: If uri is missing or connection fails.
        """
        uri = config.get("uri")
        if not uri:
            raise ConnectionError("BoltHandler requires 'uri' in config")

        auth_list = config.get("auth")
        auth = tuple(auth_list) if auth_list else None
        self._database = config.get("database", DEFAULT_DATABASE)
        pool_size = config.get("max_connection_pool_size", DEFAULT_POOL_SIZE)
        self._uri = str(uri)

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=auth,
                max_connection_pool_size=pool_size,
            )
            # Verify connectivity
            await self._driver.verify_connectivity()
        except Exception as exc:
            self._driver = None
            raise ConnectionError(
                f"Bolt connection failed to {self._uri}: {exc}"
            ) from exc

        logger.info(
            "Bolt driver connected",
            extra={"uri": self._uri, "database": self._database},
        )

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a Bolt protocol operation.

        Args:
            operation: "query" for read or "write" for write transaction.
            params: Operation parameters.
                - cypher (str, required): Cypher query string.
                - parameters (dict, optional): Query parameters.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            dict with keys: records (list of dicts), summary.

        Raises:
            RuntimeError: If handler is not connected.
            ConnectionError: If the database is unreachable.
        """
        if self._driver is None:
            raise RuntimeError("BoltHandler is not connected. Call connect() first.")

        if operation not in VALID_OPERATIONS:
            raise ValueError(
                f"Unsupported Bolt operation: {operation}. Must be one of {VALID_OPERATIONS}"
            )

        cypher = params.get("cypher")
        if not cypher:
            raise ValueError("BoltHandler requires 'cypher' in params")

        query_params = params.get("parameters", {})

        log_extra: dict[str, Any] = {
            "operation": operation,
            "database": self._database,
            "correlation_id": correlation_id,
        }

        try:
            async with self._driver.session(database=self._database) as session:
                if operation == "query":
                    result = await session.run(cypher, query_params)
                    records = [dict(record) for record in await result.data()]
                    summary = await result.consume()
                else:  # write
                    result = await session.run(cypher, query_params)
                    records = [dict(record) for record in await result.data()]
                    summary = await result.consume()
        except Exception as exc:
            error_str = str(exc)
            if "connection" in error_str.lower() or "refused" in error_str.lower():
                raise ConnectionError(f"Bolt connection error: {exc}") from exc
            raise

        logger.debug(
            "Bolt operation completed",
            extra={**log_extra, "record_count": len(records)},
        )

        return {
            "records": records,
            "summary": {
                "counters": {
                    "nodes_created": summary.counters.nodes_created,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_created": summary.counters.relationships_created,
                    "relationships_deleted": summary.counters.relationships_deleted,
                    "properties_set": summary.counters.properties_set,
                },
                "result_available_after": summary.result_available_after,
            },
        }

    async def disconnect(self) -> None:
        """Close the Neo4j driver and release connections."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info(
                "Bolt driver disconnected",
                extra={"uri": self._uri},
            )

    async def health_check(self) -> bool:
        """Check if the Bolt driver is connected and operational.

        Returns:
            True if the driver can verify connectivity.
        """
        if self._driver is None:
            return False
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False


__all__ = [
    "BoltHandler",
]
