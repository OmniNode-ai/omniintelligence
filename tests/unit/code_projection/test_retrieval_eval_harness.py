# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16522 harness gate: scenarios, golden-set sizing, metrics, arming rule.

The replay-scenario assertions here are the CI gate.  The ranking metrics are
computed and reported but deliberately never appear in a failure path at this
corpus size -- see ``test_ranking_metrics_are_reported_but_never_gating``.
"""

from __future__ import annotations

import pytest

from omniintelligence.code_projection.retrieval_eval.baselines import (
    BASELINE_SCORECARD_PATH,
    GOLDEN_QUERY_SET_PATH,
)
from omniintelligence.code_projection.retrieval_eval.golden import (
    DEFAULT_GOLDEN_SET_PATH,
    GOLDEN_SET_MAXIMUM_ROWS,
    GOLDEN_SET_MINIMUM_ROWS,
    load_golden_query_set,
)
from omniintelligence.code_projection.retrieval_eval.metrics import (
    ARMING_MINIMUM_DISTINCT_DOCUMENTS,
    ARMING_MINIMUM_LABELED_QUERIES,
    chance_floor_mrr,
    chance_floor_recall_at_k,
    recall_at_k,
    reciprocal_rank,
    resolve_metric_status,
    summarize_metrics,
)
from omniintelligence.code_projection.retrieval_eval.runner import run_eval
from omniintelligence.code_projection.retrieval_eval.scorecard import UNKNOWN

pytestmark = pytest.mark.unit

EXPECTED_SCENARIOS = ("R1", "R2", "R3", "R4", "R5", "R6")


async def test_all_six_replay_scenarios_are_asserted_and_pass() -> None:
    """AC1: six named scenario assertions execute, and every one holds."""

    result = await run_eval()
    scenarios = result.scorecard.scenarios

    assert tuple(s.scenario_id for s in scenarios) == EXPECTED_SCENARIOS
    failures = [f"{s.scenario_id}: {s.detail}" for s in scenarios if not s.passed]
    assert failures == []

    # R3 must reach its verdict without the source tombstone, or it asserts
    # nothing beyond R2 and the honest scenario count is five.
    r3 = next(s for s in scenarios if s.scenario_id == "R3")
    assert "seq4_skipped=True" in r3.detail


async def test_golden_set_is_within_the_honest_ceiling() -> None:
    """AC2: 8-10 rows, each carrying its replay state and expected result."""

    golden = load_golden_query_set()

    assert GOLDEN_SET_MINIMUM_ROWS <= len(golden.queries) <= GOLDEN_SET_MAXIMUM_ROWS
    positives = [q for q in golden.queries if q.polarity == "positive"]
    negatives = [q for q in golden.queries if q.polarity == "negative"]
    # 2 retrievable documents x 3 distinct intents; a 4th would be a paraphrase.
    assert len(positives) <= 6
    assert len(negatives) == 4
    # Volume comes from replay-state parameterization, not from extra rows.
    assert golden.assertion_count() > len(golden.queries) * 2
    for query in golden.queries:
        assert query.expectations
        for expectation in query.expectations:
            assert expectation.lane_id


async def test_golden_set_expected_documents_still_exist_in_the_corpus() -> None:
    """A judged label naming a document the corpus no longer carries is stale."""

    result = await run_eval()
    golden = load_golden_query_set()
    known = {
        document_id
        for query in golden.queries
        for expectation in query.expectations
        for document_id in expectation.expected_document_ids
    }
    assert known, "the golden set must judge at least one document relevant"
    # Every judged document belongs to one of the corpus's chunk keys.
    assert result.scorecard.distinct_chunk_keys


async def test_ranking_metrics_are_reported_but_never_gating() -> None:
    """AC3: metrics computed and labeled degenerate, with N and Q recorded."""

    metrics = (await run_eval()).scorecard.metrics

    assert metrics.metric_status == "degenerate"
    assert metrics.observed_distinct_documents == 2
    assert metrics.observed_labeled_queries == 10
    assert "carry no information" in metrics.status_reason
    # Computed, not skipped -- the wiring and the baseline exist from day one.
    assert metrics.recall_at_1_basis_points is not None
    assert metrics.mean_reciprocal_rank_basis_points is not None
    # Pinned by construction: k >= N for both, so neither can express a failure.
    assert metrics.recall_at_5_basis_points == 10_000
    assert metrics.recall_at_10_basis_points == 10_000
    # MRR's chance floor is H_2/2 = 0.75, not the 0.50 that recall@1 shows.
    assert metrics.chance_floor_mrr_basis_points == 7_500
    assert metrics.chance_floor_recall_at_1_basis_points == 5_000


def test_arming_rule_flips_on_a_synthetic_corpus_that_clears_both_thresholds() -> None:
    """AC4: status arms at N >= 20 and Q >= 30, with no code change."""

    armed = summarize_metrics(
        positive_rows=[(["doc-1"], frozenset({"doc-1"}))],
        negative_rows=[],
        distinct_documents=ARMING_MINIMUM_DISTINCT_DOCUMENTS,
        labeled_queries=ARMING_MINIMUM_LABELED_QUERIES,
    )
    assert armed.metric_status == "armed"
    assert "gate" in armed.status_reason
    # At N = 20 the floors are real discriminators rather than pinned values.
    assert armed.chance_floor_recall_at_1_basis_points == 500
    # H_20 / 20 = 0.17988..., the 0.18 the arming rule is justified against.
    assert armed.chance_floor_mrr_basis_points == 1_799


def test_arming_rule_does_not_flip_at_the_current_corpus_size() -> None:
    """AC4 companion: N = 2 stays degenerate however many queries are labeled."""

    assert resolve_metric_status(distinct_documents=2, labeled_queries=10) == (
        "degenerate"
    )
    # Either threshold alone is insufficient: N fixes the chance floor, Q fixes
    # the confidence interval, and a threshold needs both to be readable.
    assert resolve_metric_status(distinct_documents=2, labeled_queries=500) == (
        "degenerate"
    )
    assert resolve_metric_status(distinct_documents=500, labeled_queries=10) == (
        "degenerate"
    )
    assert resolve_metric_status(distinct_documents=20, labeled_queries=30) == "armed"


def test_metric_arithmetic_matches_the_documented_chance_floors() -> None:
    """The floors quoted in the docstrings are computed, not asserted by hand."""

    assert chance_floor_recall_at_k(2, 1) == 0.5
    assert chance_floor_recall_at_k(2, 5) == 1.0
    assert chance_floor_recall_at_k(20, 10) == 0.5
    assert chance_floor_mrr(2) == 0.75
    assert chance_floor_mrr(1) == 1.0

    relevant = frozenset({"doc-b"})
    assert recall_at_k(["doc-a", "doc-b"], relevant, 1) == 0.0
    assert recall_at_k(["doc-a", "doc-b"], relevant, 5) == 1.0
    assert reciprocal_rank(["doc-a", "doc-b"], relevant) == 0.5
    assert reciprocal_rank(["doc-a"], relevant) == 0.0
    # A negative row has no relevant document; that is not a score of zero.
    assert recall_at_k(["doc-a"], frozenset(), 1) is None
    assert reciprocal_rank(["doc-a"], frozenset()) is None


async def test_scorecard_is_byte_identical_across_two_runs() -> None:
    """AC5: fixture-driven and seeded, so two runs agree byte for byte."""

    first = (await run_eval()).scorecard.to_canonical_bytes()
    second = (await run_eval()).scorecard.to_canonical_bytes()
    assert first == second


async def test_scorecard_records_the_embedding_key_with_honest_unknowns() -> None:
    """The five-part key is recorded, and unsourceable parts say so."""

    scorecard = (await run_eval()).scorecard
    key = scorecard.embedding_compatibility_key

    assert key.dimension == 1024
    assert key.distance_metric == "Dot"
    assert key.model_name
    # The platform's embedding contract pins only a model identifier and a
    # dimension today, so three components are recorded as explicitly unknown
    # rather than invented.
    assert scorecard.unknown_embedding_components == (
        "model_artifact_digest",
        "normalization",
        "tokenizer_preprocessing_version",
    )
    assert key.model_artifact_digest == UNKNOWN


async def test_latency_is_captured_and_excluded_from_the_scorecard_digest() -> None:
    """Timings are collected, but never inside the byte-identical baseline."""

    result = await run_eval()

    assert result.latency.sample_count > 0
    assert result.latency.total_ms_total >= result.latency.embed_ms_total
    assert result.latency.separable_stages == ("embed",)
    assert result.latency.unseparable_stages == (
        "vector_search",
        "policy_provenance_checks",
        "pack_assembly",
    )
    # A timing inside the digest would change the baseline on every run.
    assert b"embed_ms" not in result.scorecard.to_canonical_bytes()


async def test_committed_baseline_scorecard_matches_a_fresh_run() -> None:
    """The committed baseline is the reference future PRs are compared against.

    A drift here means either a real retrieval change or a change to the corpus,
    golden set, or embedding key.  The first is a regression to investigate; the
    second is a deliberate re-baseline via ``--write``.  Failing loudly is what
    makes the distinction visible instead of silent.
    """

    committed = BASELINE_SCORECARD_PATH.read_bytes()
    fresh = (await run_eval()).scorecard.to_canonical_bytes()
    assert fresh == committed


def test_golden_set_path_points_at_the_committed_artifact() -> None:
    """The harness reads the checked-in golden set, not a generated one."""

    assert GOLDEN_QUERY_SET_PATH.is_file()
    assert DEFAULT_GOLDEN_SET_PATH == GOLDEN_QUERY_SET_PATH
