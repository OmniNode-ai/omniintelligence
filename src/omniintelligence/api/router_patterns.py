"""FastAPI router for pattern query endpoints.

Provides GET /api/v1/patterns for querying validated/provisional patterns
applicable to a given domain and language. This replaces direct DB access
that was disabled in OMN-2058.

The router is a thin shell: all business logic lives in handler_pattern_query.

Ticket: OMN-2253
"""

# NOTE: Do NOT use `from __future__ import annotations` in this module.
# FastAPI requires runtime-accessible type annotations for dependency injection
# and query parameter extraction. PEP 563 (stringified annotations) would
# prevent FastAPI from recognizing Depends() and Query() at runtime.

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from omniintelligence.api.handler_pattern_query import handle_query_patterns
from omniintelligence.api.models_pattern_query import ModelPatternQueryPage
from omniintelligence.repositories.adapter_pattern_store import AdapterPatternStore


def create_pattern_router(
    *,
    get_adapter: Any,
) -> APIRouter:
    """Create a FastAPI router for pattern query endpoints.

    Args:
        get_adapter: Dependency callable that returns an AdapterPatternStore.
            Typically a closure over a connection pool:

            >>> async def get_adapter() -> AdapterPatternStore:
            ...     return await create_pattern_store_adapter(pool)

    Returns:
        Configured APIRouter ready to be mounted on a FastAPI app.
    """
    router = APIRouter(
        prefix="/api/v1",
        tags=["patterns"],
    )

    @router.get(
        "/patterns",
        response_model=ModelPatternQueryPage,
        summary="Query patterns for enforcement",
        description=(
            "Query validated and provisional patterns applicable to a domain "
            "and language. Returns paginated results filtered by minimum "
            "confidence threshold. Used by compliance/enforcement nodes."
        ),
    )
    async def get_patterns(
        adapter: Annotated[AdapterPatternStore, Depends(get_adapter)],
        domain: Annotated[
            str | None,
            Query(
                max_length=50,
                description="Domain identifier to filter patterns by",
            ),
        ] = None,
        language: Annotated[
            str | None,
            Query(
                max_length=50,
                description="Programming language to filter by",
            ),
        ] = None,
        min_confidence: Annotated[
            float,
            Query(
                ge=0.0,
                le=1.0,
                description="Minimum confidence threshold (0.0-1.0)",
            ),
        ] = 0.7,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=200,
                description="Maximum patterns per page",
            ),
        ] = 50,
        offset: Annotated[
            int,
            Query(
                ge=0,
                description="Number of patterns to skip for pagination",
            ),
        ] = 0,
    ) -> ModelPatternQueryPage:
        """Query patterns for enforcement/compliance.

        Returns validated and provisional patterns matching the given
        domain, language, and confidence criteria.
        """
        return await handle_query_patterns(
            adapter=adapter,
            domain=domain,
            language=language,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )

    return router


__all__ = ["create_pattern_router"]
