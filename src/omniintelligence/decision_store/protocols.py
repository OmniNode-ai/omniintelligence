# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Protocol definitions for decision_store dependency injection.

Defines ``ProtocolDecisionRecordRepository`` so consumers depend on the
protocol (not the concrete implementation) — consistent with
``ProtocolPatternRepository`` and ``ProtocolIdempotencyStore`` in the
shared protocols module.

Ticket: OMN-2467
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from omniintelligence.decision_store.models import (
    DecisionRecordCursor,
    DecisionRecordRow,
)


@runtime_checkable
class ProtocolDecisionRecordRepository(Protocol):
    """Protocol for DecisionRecord persistence and querying.

    Implementations must provide:
    - ``store``: Idempotent write.
    - ``get_record``: Exact lookup with Layer 1/2 separation.
    - ``query_by_type``: Filter by decision_type + time range (paginated).
    - ``query_by_candidate``: Filter by selected_candidate + time range (paginated).
    - ``count``: Total number of stored records.
    """

    def store(
        self,
        record: DecisionRecordRow,
        *,
        correlation_id: str | None = None,
    ) -> bool:
        """Persist a DecisionRecord idempotently.

        Args:
            record: The record to store.
            correlation_id: Optional tracing ID.

        Returns:
            True if stored, False if duplicate.
        """
        ...

    def get_record(
        self,
        decision_id: str,
        *,
        include_rationale: bool = False,
        correlation_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a record by decision_id.

        Args:
            decision_id: Unique decision identifier.
            include_rationale: If True, return Layer 2 (agent_rationale).
            correlation_id: Optional tracing ID.

        Returns:
            Dict of record fields or None.
        """
        ...

    def query_by_type(
        self,
        decision_type: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor: DecisionRecordCursor | None = None,
        correlation_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionRecordCursor | None]:
        """Query records by decision_type.

        Returns:
            (records, next_cursor) tuple.
        """
        ...

    def query_by_candidate(
        self,
        selected_candidate: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor: DecisionRecordCursor | None = None,
        correlation_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionRecordCursor | None]:
        """Query records by selected_candidate.

        Returns:
            (records, next_cursor) tuple.
        """
        ...

    def count(self) -> int:
        """Return total number of stored records."""
        ...


__all__ = [
    "ProtocolDecisionRecordRepository",
]
