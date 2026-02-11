"""Shared protocol definitions for OmniIntelligence handlers.

These protocols define the interfaces for database and event bus operations
used across multiple handler modules. Centralizing them prevents definition
drift and simplifies maintenance.

Reference:
    - OMN-2133: Protocol extraction to shared module
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the interface required for database operations
    in handler functions. It supports both asyncpg connections and
    mock implementations for testing.

    The methods mirror asyncpg.Connection semantics:
        - fetch: Execute query and return list of Records
        - fetchrow: Execute query and return single Record or None
        - execute: Execute query and return status string (e.g., "UPDATE 1")

    Note:
        Parameters use asyncpg-style positional placeholders ($1, $2, etc.)
        rather than named parameters.
    """

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        """Execute a query and return all results as Records."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        """Execute a query and return first row, or None."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status string."""
        ...


__all__ = ["ProtocolPatternRepository"]
