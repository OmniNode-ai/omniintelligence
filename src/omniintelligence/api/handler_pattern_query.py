"""Handler for pattern query API endpoint.

Contains all business logic for querying patterns from the pattern store.
The router delegates to this handler, following the ONEX pattern of
keeping endpoint definitions thin and logic in handlers.

Ticket: OMN-2253
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import ValidationError

from omniintelligence.api.models_pattern_query import (
    ModelPatternQueryPage,
    ModelPatternQueryResponse,
)

if TYPE_CHECKING:
    from omniintelligence.repositories.adapter_pattern_store import (
        AdapterPatternStore,
    )

logger = logging.getLogger(__name__)


async def handle_query_patterns(
    *,
    adapter: AdapterPatternStore,
    domain: str | None = None,
    language: str | None = None,
    min_confidence: float = 0.7,
    limit: int = 50,
    offset: int = 0,
) -> ModelPatternQueryPage:
    """Query validated/provisional patterns from the pattern store.

    Delegates to AdapterPatternStore.query_patterns and transforms
    raw database rows into typed response models.

    Args:
        adapter: Pattern store adapter for database access.
        domain: Optional domain filter.
        language: Optional language filter (matched against keywords).
        min_confidence: Minimum confidence threshold (default 0.7).
        limit: Maximum results per page (1-200, default 50).
        offset: Pagination offset (default 0).

    Returns:
        Paginated response with matching patterns.
    """
    logger.debug(
        "Querying patterns: domain=%s language=%s min_confidence=%.2f "
        "limit=%d offset=%d",
        domain,
        language,
        min_confidence,
        limit,
        offset,
    )

    try:
        rows = await adapter.query_patterns(
            domain=domain,
            language=language,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
    except Exception:
        logger.exception("Database query failed in pattern store adapter")
        raise HTTPException(
            status_code=502,
            detail="Pattern query failed due to a database error.",
        )

    try:
        patterns = [ModelPatternQueryResponse.model_validate(row) for row in rows]
    except ValidationError as exc:
        logger.error(
            "Failed to validate pattern rows from database: %s",
            exc.error_count(),
            exc_info=exc,
        )
        raise HTTPException(
            status_code=502,
            detail="Pattern query returned rows with unexpected schema.",
        )

    return ModelPatternQueryPage(
        patterns=patterns,
        total_returned=len(patterns),
        limit=limit,
        offset=offset,
    )


__all__ = ["handle_query_patterns"]
