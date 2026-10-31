# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Debug retrieval handler — time-decayed fix record retrieval.

Effect node handler: logging allowed; all I/O via injected ProtocolDebugStore.

Ticket: OMN-3556
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from omniintelligence.debug_intel.protocols import ProtocolDebugStore
from omniintelligence.nodes.node_debug_retrieval_compute.models import (
    ModelDebugRetrievalRequest,
    ModelDebugRetrievalResponse,
)

logger = logging.getLogger(__name__)

# Time decay constant: half-life of 30 days
_HALF_LIFE_SECONDS = 30 * 24 * 3600.0


def _time_decay_weight(created_at_utc: datetime, now: datetime | None = None) -> float:
    """Compute exponential time-decay weight for a fix record.

    Weight = exp(-lambda * age_seconds) where lambda = ln(2) / half_life.
    Newer fixes have weight closer to 1.0; older fixes decay toward 0.

    Args:
        created_at_utc: When the fix record was created.
        now: Reference time (defaults to UTC now). Pass explicitly for testing.

    Returns:
        Float in (0, 1].
    """
    if now is None:
        now = datetime.now(UTC)
    # Ensure timezone-aware comparison
    if created_at_utc.tzinfo is None:
        created_at_utc = created_at_utc.replace(tzinfo=UTC)
    age_seconds = max(0.0, (now - created_at_utc).total_seconds())
    decay_lambda = math.log(2) / _HALF_LIFE_SECONDS
    return math.exp(-decay_lambda * age_seconds)


class HandlerDebugRetrieval:
    """Retrieve time-decayed fix records using an injected debug store."""

    def __init__(self, *, store: ProtocolDebugStore) -> None:
        """Initialise with a debug store protocol implementation."""
        self._store = store

    async def handle(
        self, request: ModelDebugRetrievalRequest
    ) -> ModelDebugRetrievalResponse:
        """Retrieve past fix records for a fingerprint with time-decay weights.

        Fetches confirmed fix records (join-verified, no orphans) and annotates
        each with a time_decay_weight field for caller scoring.

        Args:
            request: Fingerprint, maximum record count, and optional reference
                time for decay calculation (defaults to UTC now).

        Returns:
            Response containing fix record dicts, each with an additional
            'time_decay_weight' field. Ordered by recency (newest first, from
            DB query).
        """
        records = await self._store.query_fix_records(
            failure_fingerprint=request.failure_fingerprint,
            limit=request.limit,
        )

        if not records:
            logger.debug(
                "No fix records found for fingerprint=%s",
                request.failure_fingerprint[:16],  # truncate for log safety
            )
            return ModelDebugRetrievalResponse(records=[])

        # Annotate each record with time-decay weight
        annotated = []
        for record in records:
            created_at = record.get("created_at_utc")
            if created_at is not None and isinstance(created_at, datetime):
                weight = _time_decay_weight(created_at, now=request.now)
            else:
                # Fallback: treat as maximum age (no decay info)
                weight = 0.0

            annotated.append({**record, "time_decay_weight": weight})

        return ModelDebugRetrievalResponse(records=annotated)


__all__ = ["HandlerDebugRetrieval", "_time_decay_weight"]
