# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Confidence scorer handler for NodePlanReviewerMultiCompute.

Fetches per-model accuracy weights from the ``plan_reviewer_model_accuracy``
table and exposes them for use by strategy handlers.  If a model row is
missing, a neutral weight of 0.5 is seeded in-memory (no DB INSERT — the
seed INSERT is done by migration 020).

Architecture note:
    This module interacts with the database via an injected asyncpg-protocol
    connection.  No ``httpx`` or ``os.getenv`` usage is allowed here
    (ARCH-002).

Ticket: OMN-3290
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)

logger = logging.getLogger(__name__)

# Default weight when a model row is absent or the DB is unavailable.
_DEFAULT_WEIGHT: float = 0.5

# SQL to fetch all model accuracy rows.
_SQL_FETCH_ACCURACY = """
SELECT model_id, score_correctness
FROM plan_reviewer_model_accuracy
"""


class ProtocolDBConnection(Protocol):
    """Minimal asyncpg-compatible connection protocol.

    Only the ``fetch`` method is required for confidence scoring.
    """

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...


async def fetch_accuracy_weights(
    db_conn: ProtocolDBConnection | None,
) -> dict[EnumReviewModel, float]:
    """Fetch per-model accuracy weights from ``plan_reviewer_model_accuracy``.

    Returns a mapping of ``EnumReviewModel`` → ``score_correctness``.
    Missing or unreachable models default to ``0.5``.

    When ``db_conn`` is ``None`` or the query fails, all weights fall back
    to the default value of 0.5 — callers receive a valid dict, not an
    exception.

    Args:
        db_conn: Optional asyncpg-compatible connection.  When ``None``
            the function returns uniform default weights without querying.

    Returns:
        Dict mapping each ``EnumReviewModel`` to its accuracy weight in
        ``[0.0, 1.0]``.  Every ``EnumReviewModel`` member is present.

    Example::

        weights = await fetch_accuracy_weights(db_conn)
        # {"qwen3-coder": 0.7, "deepseek-r1": 0.6, ...}
    """
    # Start with uniform defaults so every model always has a weight.
    weights: dict[EnumReviewModel, float] = dict.fromkeys(
        EnumReviewModel, _DEFAULT_WEIGHT
    )

    if db_conn is None:
        logger.debug("confidence_scorer: no db_conn — using default weights (0.5)")
        return weights

    try:
        rows = await db_conn.fetch(_SQL_FETCH_ACCURACY)
        for row in rows:
            raw_model_id: str = row["model_id"]
            raw_score: float = float(row["score_correctness"])
            try:
                model = EnumReviewModel(raw_model_id)
                weights[model] = raw_score
            except ValueError:
                logger.warning(
                    "confidence_scorer: unknown model_id %r in plan_reviewer_model_accuracy — skipped",
                    raw_model_id,
                )
    except Exception:
        logger.exception(
            "confidence_scorer: failed to fetch accuracy weights — using default (0.5)"
        )

    return weights


def build_equal_weights() -> dict[EnumReviewModel, float]:
    """Return uniform weights of 0.5 for all models.

    Useful in tests and in contexts where the DB is deliberately excluded.

    Returns:
        Dict with every ``EnumReviewModel`` mapped to ``0.5``.

    Example::

        weights = build_equal_weights()
        assert all(w == 0.5 for w in weights.values())
    """
    return dict.fromkeys(EnumReviewModel, _DEFAULT_WEIGHT)


__all__ = [
    "ProtocolDBConnection",
    "build_equal_weights",
    "fetch_accuracy_weights",
]
