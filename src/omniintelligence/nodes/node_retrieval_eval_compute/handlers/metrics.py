# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Ranking metrics and the automatic arming rule.

These metrics are computed from day one so the wiring and the committed
baseline exist, but they are **reported, not gated**, until the corpus is large
enough for them to mean anything.

The reason is arithmetic, not caution.  With N distinct rankable documents and
one relevant document per query, ``recall@k`` is pinned at 1.0 for every
``k >= N``.  The published corpus exposes at most two current-generation
documents at any replay state, so ``recall@5`` and ``recall@10`` cannot express
a failure at all, ``recall@1`` is a coin flip, and MRR's chance floor is
``H_2 / 2 = 0.75`` -- not 0.5.  At the post-tombstone states only one document
survives and every metric pins at 1.00.  A gate on any of them would be a gate
on nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: N: distinct current-generation chunk keys required before ranking metrics
#: can discriminate.  ``recall@10`` is pinned at 1.00 for every N <= 10, so it
#: cannot express a failure below N = 11; 20 is the first round number that puts
#: its chance floor at 0.50, recall@5's at 0.25, recall@1's at 0.05 and MRR's
#: at 0.18.
ARMING_MINIMUM_DISTINCT_DOCUMENTS = 20

#: Q: labeled golden queries required alongside N.  N fixes the chance floor;
#: Q fixes the confidence interval.  At N = 2 the 0.50 floor sits inside the
#: 95% interval of any observed score on a Q <= 12 set (half-width >= 0.28), so
#: no threshold is meaningful at that size however carefully it is picked.
ARMING_MINIMUM_LABELED_QUERIES = 30

#: The k values reported in the scorecard.
RECALL_K_VALUES = (1, 5, 10)

MetricStatus = Literal["degenerate", "armed"]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


def recall_at_k(
    ranked_document_ids: Sequence[str],
    relevant_document_ids: frozenset[str],
    k: int,
) -> float | None:
    """Return the fraction of relevant documents present in the top ``k``.

    Returns ``None`` when the query has no relevant document, which is the
    correct answer for a negative row rather than a score of zero.
    """

    if k < 1:
        message = "k must be at least 1"
        raise ValueError(message)
    if not relevant_document_ids:
        return None
    retrieved = set(ranked_document_ids[:k])
    return len(retrieved & relevant_document_ids) / len(relevant_document_ids)


def reciprocal_rank(
    ranked_document_ids: Sequence[str],
    relevant_document_ids: frozenset[str],
) -> float | None:
    """Return ``1 / rank`` of the first relevant document, or 0.0 if unranked."""

    if not relevant_document_ids:
        return None
    for index, document_id in enumerate(ranked_document_ids, start=1):
        if document_id in relevant_document_ids:
            return 1.0 / index
    return 0.0


def top_rank_hit(
    ranked_document_ids: Sequence[str],
    relevant_document_ids: frozenset[str],
) -> bool | None:
    """Return whether a relevant document occupies rank 1."""

    if not relevant_document_ids:
        return None
    if not ranked_document_ids:
        return False
    return ranked_document_ids[0] in relevant_document_ids


def negative_row_is_clean(ranked_document_ids: Sequence[str]) -> bool:
    """Return whether a no-relevant-document row returned nothing.

    Read this one carefully before treating it as a quality signal.  Vector
    search returns nearest neighbours with no absolute relevance cutoff unless a
    ``score_threshold`` is supplied, so a negative row comes back empty mainly
    when the replay state itself holds no documents.  On the current corpus this
    measures "was the state empty" far more than "did search correctly reject",
    which is why it is reported and never gated.
    """

    return not ranked_document_ids


def resolve_metric_status(
    *,
    distinct_chunk_keys: int,
    labeled_queries: int,
) -> MetricStatus:
    """Return whether ranking metrics gate at this corpus and query-set size.

    Both thresholds must hold: N alone fixes the chance floor, Q alone fixes the
    confidence interval, and either without the other leaves a threshold that
    cannot be read.  Evaluated at runtime against whatever corpus the harness is
    handed, so a larger corpus arms the metrics with no code change.
    """

    if (
        distinct_chunk_keys >= ARMING_MINIMUM_DISTINCT_DOCUMENTS
        and labeled_queries >= ARMING_MINIMUM_LABELED_QUERIES
    ):
        return "armed"
    return "degenerate"


def chance_floor_recall_at_k(distinct_chunk_keys: int, k: int) -> float:
    """Return the score a random ranker earns, for one relevant document."""

    if distinct_chunk_keys < 1:
        message = "distinct_chunk_keys must be at least 1"
        raise ValueError(message)
    return min(1.0, k / distinct_chunk_keys)


def chance_floor_mrr(distinct_chunk_keys: int) -> float:
    """Return random-ranker MRR: the harmonic number ``H_N`` divided by ``N``.

    At N = 2 this is ``(1 + 1/2) / 2 = 0.75``, which is why MRR's floor is not
    the 0.50 that ``recall@1`` shows.
    """

    if distinct_chunk_keys < 1:
        message = "distinct_chunk_keys must be at least 1"
        raise ValueError(message)
    harmonic = sum(1.0 / rank for rank in range(1, distinct_chunk_keys + 1))
    return harmonic / distinct_chunk_keys


class ModelRankingMetrics(_FrozenModel):
    """Ranking metrics over the scored rows, with their honesty label.

    Every score is carried in **basis points** (0-10000), not as a float.  The
    canonical projection encoding forbids floating point outright, and integer
    basis points remove any dependence on float repr -- which is what makes the
    committed scorecard byte-identical across runs and machines.
    """

    metric_status: MetricStatus
    status_reason: str
    observed_distinct_chunk_keys: int = Field(ge=0)
    observed_labeled_queries: int = Field(ge=0)
    scored_positive_rows: int = Field(
        ge=0,
        description=(
            "(query, replay-state) pairs whose judged set is non-empty. NOT the "
            "count of positive-polarity rows."
        ),
    )
    scored_negative_rows: int = Field(
        ge=0,
        description=(
            "(query, replay-state) pairs whose judged set is empty. NOT the "
            "count of negative-polarity rows: most are positive-polarity rows "
            "evaluated at post-tombstone states where their document is gone."
        ),
    )
    recall_at_1_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    recall_at_5_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    recall_at_10_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    mean_reciprocal_rank_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    top_rank_accuracy_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    negative_row_precision_basis_points: int | None = Field(
        default=None, ge=0, le=10_000
    )
    chance_floor_recall_at_1_basis_points: int = Field(ge=0, le=10_000)
    chance_floor_mrr_basis_points: int = Field(ge=0, le=10_000)


def _mean_basis_points(values: list[float]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values) * 10_000)


def summarize_metrics(
    *,
    positive_rows: list[tuple[Sequence[str], frozenset[str]]],
    negative_rows: list[Sequence[str]],
    distinct_chunk_keys: int,
    labeled_queries: int,
) -> ModelRankingMetrics:
    """Aggregate per-row metrics and attach the arming decision."""

    status = resolve_metric_status(
        distinct_chunk_keys=distinct_chunk_keys,
        labeled_queries=labeled_queries,
    )
    if status == "armed":
        reason = (
            f"N={distinct_chunk_keys} distinct documents and Q={labeled_queries} "
            "labeled queries both clear the arming thresholds "
            f"(N>={ARMING_MINIMUM_DISTINCT_DOCUMENTS}, "
            f"Q>={ARMING_MINIMUM_LABELED_QUERIES}); ranking metrics gate."
        )
    else:
        reason = (
            f"below {ARMING_MINIMUM_DISTINCT_DOCUMENTS} distinct rankable documents "
            f"or {ARMING_MINIMUM_LABELED_QUERIES} labeled queries "
            f"(observed N={distinct_chunk_keys}, Q={labeled_queries}), these values "
            "are pinned by construction and carry no information about retrieval "
            "quality."
        )

    recalls: dict[int, list[float]] = {k: [] for k in RECALL_K_VALUES}
    reciprocal_ranks: list[float] = []
    top_ranks: list[float] = []
    for ranked, relevant in positive_rows:
        for k in RECALL_K_VALUES:
            value = recall_at_k(ranked, relevant, k)
            if value is not None:
                recalls[k].append(value)
        rank_value = reciprocal_rank(ranked, relevant)
        if rank_value is not None:
            reciprocal_ranks.append(rank_value)
        hit = top_rank_hit(ranked, relevant)
        if hit is not None:
            top_ranks.append(1.0 if hit else 0.0)

    clean = [1.0 if negative_row_is_clean(ranked) else 0.0 for ranked in negative_rows]

    return ModelRankingMetrics(
        metric_status=status,
        status_reason=reason,
        observed_distinct_chunk_keys=distinct_chunk_keys,
        observed_labeled_queries=labeled_queries,
        scored_positive_rows=len(positive_rows),
        scored_negative_rows=len(negative_rows),
        recall_at_1_basis_points=_mean_basis_points(recalls[1]),
        recall_at_5_basis_points=_mean_basis_points(recalls[5]),
        recall_at_10_basis_points=_mean_basis_points(recalls[10]),
        mean_reciprocal_rank_basis_points=_mean_basis_points(reciprocal_ranks),
        top_rank_accuracy_basis_points=_mean_basis_points(top_ranks),
        negative_row_precision_basis_points=_mean_basis_points(clean),
        chance_floor_recall_at_1_basis_points=round(
            chance_floor_recall_at_k(max(distinct_chunk_keys, 1), 1) * 10_000
        ),
        chance_floor_mrr_basis_points=round(
            chance_floor_mrr(max(distinct_chunk_keys, 1)) * 10_000
        ),
    )


__all__ = [
    "ARMING_MINIMUM_DISTINCT_DOCUMENTS",
    "ARMING_MINIMUM_LABELED_QUERIES",
    "RECALL_K_VALUES",
    "MetricStatus",
    "ModelRankingMetrics",
    "chance_floor_mrr",
    "chance_floor_recall_at_k",
    "negative_row_is_clean",
    "recall_at_k",
    "reciprocal_rank",
    "resolve_metric_status",
    "summarize_metrics",
    "top_rank_hit",
]
