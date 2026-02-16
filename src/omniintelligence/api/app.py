"""FastAPI application factory for OmniIntelligence API.

Provides create_app() to construct a configured FastAPI application
with pattern query endpoints. Connection pool lifecycle is managed
via FastAPI lifespan events.

Usage:
    >>> import asyncpg
    >>> app = create_app(database_url="postgresql://...")
    >>> # Run with uvicorn:
    >>> # uvicorn omniintelligence.api.app:create_app --factory

Ticket: OMN-2253
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from omniintelligence.api.router_patterns import create_pattern_router
from omniintelligence.repositories.adapter_pattern_store import (
    AdapterPatternStore,
    create_pattern_store_adapter,
)

logger = logging.getLogger(__name__)


def create_app(
    *,
    database_url: str | None = None,
) -> FastAPI:
    """Create a FastAPI application with pattern query endpoints.

    Args:
        database_url: PostgreSQL connection URL. If not provided,
            falls back to environment variables (POSTGRES_HOST, etc.).

    Returns:
        Configured FastAPI application.
    """
    # Store shared state for the lifespan and dependency
    state: dict[str, Any] = {
        "database_url": database_url,
        "adapter": None,
        "pool": None,
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
        """Manage connection pool lifecycle."""
        import asyncpg

        dsn = state["database_url"] or _build_dsn_from_env()
        logger.info("Connecting to database...")
        pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
        adapter = await create_pattern_store_adapter(pool)
        state["pool"] = pool
        state["adapter"] = adapter
        logger.info("Database connection pool established")

        yield

        logger.info("Closing database connection pool...")
        await pool.close()
        state["pool"] = None
        state["adapter"] = None
        logger.info("Database connection pool closed")

    async def get_adapter() -> AdapterPatternStore:
        """FastAPI dependency that returns the pattern store adapter."""
        adapter = state["adapter"]
        if not isinstance(adapter, AdapterPatternStore):
            msg = "Pattern store adapter not initialized. Is the app running?"
            raise RuntimeError(msg)
        return adapter

    app = FastAPI(
        title="OmniIntelligence Pattern API",
        description="REST API for querying learned patterns",
        version="0.1.0",
        lifespan=lifespan,
    )

    pattern_router = create_pattern_router(get_adapter=get_adapter)
    app.include_router(pattern_router)

    return app


def _build_dsn_from_env() -> str:
    """Build PostgreSQL DSN from environment variables.

    Returns:
        PostgreSQL connection string.

    Raises:
        ValueError: If required environment variables are missing.
    """
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5436")
    database = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD")

    if not host:
        msg = "POSTGRES_HOST environment variable is required"
        raise ValueError(msg)
    if not password:
        msg = "POSTGRES_PASSWORD environment variable is required"
        raise ValueError(msg)

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


__all__ = ["create_app"]
