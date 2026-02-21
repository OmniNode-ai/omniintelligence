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
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError
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
        default="omniintelligence", description="PostgreSQL database name"
    )
    user: str = Field(default="postgres", description="PostgreSQL user")
    password: str = Field(..., description="PostgreSQL password")


async def _create_pool(database_url: str | None) -> asyncpg.Pool:
    """Create asyncpg connection pool without keeping credentials in scope.

    When *database_url* is supplied it is used directly.  Otherwise the
    pool is created by reading ``OMNIINTELLIGENCE_DB_URL`` first (consistent
    with how ``PluginIntelligence`` connects), and falling back to discrete
    ``DatabaseSettings`` fields only when that var is absent.  This prevents
    the shared ``POSTGRES_DATABASE`` env var from routing the API to the
    wrong database when the service-specific URL is not set.

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
            return await asyncpg.create_pool(dsn=database_url, min_size=2, max_size=10)

        # Prefer the service-specific URL (same var used by PluginIntelligence)
        # so that POSTGRES_DATABASE from the shared bridge env does not override
        # the omniintelligence database target.
        omni_db_url = os.getenv("OMNIINTELLIGENCE_DB_URL")
        if omni_db_url:
            return await asyncpg.create_pool(dsn=omni_db_url, min_size=2, max_size=10)

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
    except ValidationError:
        logger.exception(
            "Missing required database configuration. "
            "Set OMNIINTELLIGENCE_DB_URL, or set POSTGRES_HOST, POSTGRES_PORT, "
            "POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DATABASE environment variables."
        )
        raise
    except Exception:
        logger.exception(
            "Failed to create database connection pool. "
            "Verify OMNIINTELLIGENCE_DB_URL (or POSTGRES_HOST, POSTGRES_PORT, "
            "and POSTGRES_PASSWORD) are correct and that the database is reachable."
        )
        raise


@dataclasses.dataclass
class _AppState:
    """Typed shared state for the FastAPI lifespan and dependency closures.

    Replaces an untyped ``dict[str, Any]`` to make the contract explicit
    and prevent key-name typos at the cost of one small class.

    Thread-Safety Invariants
    ------------------------
    This mutable dataclass is safe under normal FastAPI operation because:

    1. **Startup ordering**: FastAPI's lifespan context manager runs to
       completion (up to ``yield``) *before* the server begins accepting
       requests. Therefore ``adapter`` and ``pool`` are always set before
       any request handler reads them.

    2. **Shutdown ordering**: After the lifespan ``yield`` returns, FastAPI
       drains in-flight requests before resuming the lifespan teardown.
       The pool is closed and ``adapter``/``pool`` are set to ``None``
       only after all request handlers have returned.

    3. **Single-process model**: Uvicorn workers each get their own
       ``_AppState`` instance. There is no cross-process sharing.

    If these invariants are violated (e.g. a request arrives during
    shutdown due to a server bug), ``get_adapter()`` returns HTTP 503
    rather than crashing with an unhandled ``RuntimeError``.
    """

    database_url: str | None = None
    adapter: AdapterPatternStore | None = None
    pool: asyncpg.Pool | None = None


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
        """FastAPI dependency that returns the pattern store adapter.

        Returns HTTP 503 if the adapter is unavailable (during startup
        before lifespan completes, or during shutdown after the pool
        has been closed). See ``_AppState`` docstring for invariants.
        """
        adapter = state.adapter
        if not isinstance(adapter, AdapterPatternStore):
            raise HTTPException(
                status_code=503,
                detail="Service unavailable: pattern store not initialized.",
            )
        return adapter

    app = FastAPI(
        title="OmniIntelligence Pattern API",
        description="REST API for querying learned patterns",
        version="0.1.0",
        lifespan=lifespan,
    )

    pattern_router = create_pattern_router(get_adapter=get_adapter)
    app.include_router(pattern_router)

    # Health endpoint is intentionally mounted at root path (not under /api/v1)
    # so that load balancers and orchestrators can reach it without versioned paths.
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
            logger.warning("Health check failed: database unreachable", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "detail": "database unreachable"},
            )
        return JSONResponse(content={"status": "healthy"})

    return app


__all__ = ["DatabaseSettings", "create_app"]
