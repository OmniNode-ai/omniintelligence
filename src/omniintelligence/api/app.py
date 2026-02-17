"""FastAPI application factory for OmniIntelligence API.

Provides create_app() to construct a configured FastAPI application
with pattern query endpoints. Connection pool lifecycle is managed
via FastAPI lifespan events.

Usage:
    >>> app = create_app(database_url="postgresql://...")
    >>> # Run with uvicorn:
    >>> # uvicorn omniintelligence.api.app:create_app --factory

Ticket: OMN-2253
"""

from __future__ import annotations

import dataclasses
import logging
import urllib.parse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from omniintelligence.api.router_patterns import create_pattern_router
from omniintelligence.repositories.adapter_pattern_store import (
    AdapterPatternStore,
    create_pattern_store_adapter,
)

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings loaded from POSTGRES_* environment variables.

    Follows the LogSanitizerSettings pattern established in this codebase.
    Required fields (host, password) will raise ValidationError if not set.
    """

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(..., description="PostgreSQL host address")
    port: int = Field(default=5436, description="PostgreSQL port")
    database: str = Field(
        default="omninode_bridge", description="PostgreSQL database name"
    )
    user: str = Field(default="postgres", description="PostgreSQL user")
    password: str = Field(..., description="PostgreSQL password")

    def get_dsn(self) -> str:
        """Build PostgreSQL DSN from validated settings.

        URL-encodes user and password to handle special characters
        (@, /, :, %, #) that would otherwise break DSN parsing.

        Returns:
            PostgreSQL connection string.
        """
        encoded_user = urllib.parse.quote_plus(self.user)
        encoded_password = urllib.parse.quote_plus(self.password)
        return (
            f"postgresql://{encoded_user}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


async def _create_pool(database_url: str | None) -> asyncpg.Pool:  # type: ignore[type-arg]
    """Create asyncpg connection pool without keeping credentials in scope.

    When *database_url* is supplied it is used directly.  Otherwise the
    pool is created from discrete ``DatabaseSettings`` fields so that no
    assembled DSN string lingers in a local variable that could leak
    through exception tracebacks.

    Args:
        database_url: Optional pre-built PostgreSQL DSN.

    Returns:
        An initialised asyncpg connection pool.

    Raises:
        Exception: Re-raises any pool creation error after logging an
            actionable diagnostic message.
    """
    try:
        if database_url is not None:
            return await asyncpg.create_pool(
                dsn=database_url, min_size=2, max_size=10
            )

        settings = DatabaseSettings()  # type: ignore[call-arg]  # fields populated from env vars at runtime
        return await asyncpg.create_pool(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            min_size=2,
            max_size=10,
        )
    except Exception:
        logger.exception(
            "Failed to create database connection pool. "
            "Verify POSTGRES_HOST, POSTGRES_PORT, and POSTGRES_PASSWORD "
            "are correct and that the database is reachable."
        )
        raise


@dataclasses.dataclass
class _AppState:
    """Typed shared state for the FastAPI lifespan and dependency closures.

    Replaces an untyped ``dict[str, Any]`` to make the contract explicit
    and prevent key-name typos at the cost of one small class.
    """

    database_url: str | None = None
    adapter: AdapterPatternStore | None = None
    pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


def create_app(
    *,
    database_url: str | None = None,
) -> FastAPI:
    """Create a FastAPI application with pattern query endpoints.

    Args:
        database_url: PostgreSQL connection URL. If not provided,
            falls back to POSTGRES_* environment variables via
            DatabaseSettings.

    Returns:
        Configured FastAPI application.
    """
    state = _AppState(database_url=database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
        """Manage connection pool lifecycle."""
        logger.info("Connecting to database...")
        pool = await _create_pool(state.database_url)
        try:
            adapter = await create_pattern_store_adapter(pool)
        except Exception:
            await pool.close()
            raise
        state.pool = pool
        state.adapter = adapter
        logger.info("Database connection pool established")

        yield

        logger.info("Closing database connection pool...")
        await pool.close()
        state.pool = None
        state.adapter = None
        logger.info("Database connection pool closed")

    async def get_adapter() -> AdapterPatternStore:
        """FastAPI dependency that returns the pattern store adapter."""
        adapter = state.adapter
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

    @app.get("/health", tags=["infrastructure"])
    async def health_check() -> JSONResponse:
        """Liveness/readiness probe for load balancers and orchestrators."""
        pool = state.pool
        if pool is None:
            return JSONResponse(
                status_code=503,
                content={"status": "starting"},
            )
        try:
            await pool.fetchval("SELECT 1")
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError):
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "detail": "database unreachable"},
            )
        return JSONResponse(content={"status": "healthy"})

    return app


__all__ = ["DatabaseSettings", "create_app"]
