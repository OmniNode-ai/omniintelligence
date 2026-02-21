# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CRUD and query operations for DecisionRecord storage.

Provides the DecisionRecordRepository — an in-memory repository (backed by a
dict) for storing, querying, and retrieving DecisionRecords.

Design Decision:
    Migration freeze is active (`.migration_freeze`). No new SQL migrations
    are created. The repository interface is defined here so it can be wired
    to a real database backend once the freeze is lifted. For now, an
    in-memory implementation is provided for testing and local operation.

Query Support:
    - By decision_id (exact lookup)
    - By decision_type + time range (paginated)
    - By selected_candidate + time range (paginated)

Layer Separation:
    - get_record(decision_id, include_rationale=False) → Layer 1 only
    - get_record(decision_id, include_rationale=True) → Full record

Ticket: OMN-2467
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from omniintelligence.decision_store.models import (
    DecisionRecordCursor,
    DecisionRecordRow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default pagination page size
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# DecisionRecordRepository
# ---------------------------------------------------------------------------


class DecisionRecordRepository:
    """Repository for DecisionRecord persistence and querying.

    This implementation uses an in-memory dict store (keyed by decision_id)
    to hold records. It is designed so that the interface can be backed by
    a real database (asyncpg pool) once the migration freeze is lifted.

    Idempotency:
        ``store`` is idempotent — a duplicate ``decision_id`` is a no-op.

    Thread Safety:
        Not thread-safe. Use external locking or asyncio-safe access patterns
        for concurrent workloads.

    Layer Separation:
        ``get_record`` enforces Layer 1/Layer 2 separation via the
        ``include_rationale`` flag.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory decision record store."""
        # decision_id → DecisionRecordRow
        self._records: dict[str, DecisionRecordRow] = {}

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    def store(self, record: DecisionRecordRow) -> bool:
        """Persist a DecisionRecord.

        Idempotent: if a record with the same ``decision_id`` already exists,
        this method is a no-op and returns False.

        Args:
            record: The DecisionRecordRow to persist.

        Returns:
            True if stored successfully, False if duplicate (no-op).
        """
        if record.decision_id in self._records:
            logger.debug(
                "DecisionRecord already exists, skipping (idempotent). decision_id=%s",
                record.decision_id,
            )
            return False

        self._records[record.decision_id] = record
        logger.debug("Stored DecisionRecord. decision_id=%s", record.decision_id)
        return True

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    def get_record(
        self,
        decision_id: str,
        *,
        include_rationale: bool = False,
    ) -> dict[str, Any] | None:
        """Retrieve a DecisionRecord by its unique ID.

        Enforces layer separation:
        - ``include_rationale=False`` (default): Returns Layer 1 fields only
          (excludes ``agent_rationale``).
        - ``include_rationale=True``: Returns full record including
          ``agent_rationale`` (Layer 2).

        Args:
            decision_id: The unique decision identifier.
            include_rationale: If True, include ``agent_rationale`` in
                the returned dict.

        Returns:
            Dict of record fields, or None if not found.
        """
        record = self._records.get(decision_id)
        if record is None:
            return None

        if include_rationale:
            return record.to_full_dict()
        return record.to_layer1_dict()

    def query_by_type(
        self,
        decision_type: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: DecisionRecordCursor | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionRecordCursor | None]:
        """Query records by decision_type with optional time range filter.

        Results are sorted by ``stored_at`` ascending (oldest first).

        Args:
            decision_type: Filter records with this decision_type value.
            since: Include only records stored at or after this timestamp.
            until: Include only records stored before or at this timestamp.
            limit: Maximum number of records per page.
            cursor: Pagination cursor from a previous call.

        Returns:
            Tuple of (records_list, next_cursor). ``next_cursor`` is None
            when there are no more pages.
        """
        return self._paginate(
            filter_fn=lambda r: r.decision_type == decision_type,
            since=since,
            until=until,
            limit=limit,
            cursor=cursor,
        )

    def query_by_candidate(
        self,
        selected_candidate: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: DecisionRecordCursor | None = None,
    ) -> tuple[list[dict[str, Any]], DecisionRecordCursor | None]:
        """Query records by selected_candidate with optional time range filter.

        Results are sorted by ``stored_at`` ascending (oldest first).

        Args:
            selected_candidate: Filter records where this candidate was chosen.
            since: Include only records stored at or after this timestamp.
            until: Include only records stored before or at this timestamp.
            limit: Maximum number of records per page.
            cursor: Pagination cursor from a previous call.

        Returns:
            Tuple of (records_list, next_cursor). ``next_cursor`` is None
            when there are no more pages.
        """
        return self._paginate(
            filter_fn=lambda r: r.selected_candidate == selected_candidate,
            since=since,
            until=until,
            limit=limit,
            cursor=cursor,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of records stored."""
        return len(self._records)

    def clear(self) -> None:
        """Remove all records. For test use only."""
        self._records.clear()

    # ------------------------------------------------------------------
    # Internal pagination helper
    # ------------------------------------------------------------------

    def _paginate(
        self,
        filter_fn: Any,
        *,
        since: datetime | None,
        until: datetime | None,
        limit: int,
        cursor: DecisionRecordCursor | None,
    ) -> tuple[list[dict[str, Any]], DecisionRecordCursor | None]:
        """Apply filter and time range, then paginate.

        Args:
            filter_fn: Callable(DecisionRecordRow) → bool.
            since: Lower bound on stored_at.
            until: Upper bound on stored_at.
            limit: Max results per page.
            cursor: Pagination cursor from a previous call.

        Returns:
            (page_records, next_cursor) tuple. Layer 1 fields only.
        """
        # Collect matching records
        matching = []
        for record in self._records.values():
            if not filter_fn(record):
                continue
            if since is not None and record.stored_at < since:
                continue
            if until is not None and record.stored_at > until:
                continue
            matching.append(record)

        # Sort by stored_at ascending for deterministic pagination
        matching.sort(key=lambda r: (r.stored_at, r.decision_id))

        # Apply cursor (skip records at or before cursor position)
        if cursor is not None:
            start_idx = 0
            for idx, record in enumerate(matching):
                if record.stored_at > cursor.last_stored_at or (
                    record.stored_at == cursor.last_stored_at
                    and record.decision_id > cursor.last_decision_id
                ):
                    start_idx = idx
                    break
            else:
                # All records are at or before cursor → empty page
                start_idx = len(matching)
            matching = matching[start_idx:]

        # Take one extra to check for next page
        page = matching[: limit + 1]
        has_next = len(page) > limit
        page = page[:limit]

        records_out = [r.to_layer1_dict() for r in page]

        next_cursor: DecisionRecordCursor | None = None
        if has_next and page:
            last = page[-1]
            next_cursor = DecisionRecordCursor(
                last_decision_id=last.decision_id,
                last_stored_at=last.stored_at,
            )

        return records_out, next_cursor


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "DecisionRecordRepository",
]
