# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Run the retrieval eval: replay scenarios, metrics, and the baseline scorecard.

The six replay scenarios are evaluated as data so the CI job's own log names
each one as it executes.  They are the gate.  The ranking metrics are computed
in the same pass and reported alongside, but they do not gate until the corpus
arms them.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from omniintelligence.code_projection.retrieval_eval.golden import (
    ModelGoldenQuerySet,
    load_golden_query_set,
)
from omniintelligence.code_projection.retrieval_eval.metrics import summarize_metrics
from omniintelligence.code_projection.retrieval_eval.replay import (
    HARNESS_EMBEDDING_MODEL,
    HARNESS_EMBEDDING_MODEL_VERSION,
    REPLAY_LANES,
    ModelReplayCorpus,
    ModelStageLatencySample,
    load_replay_corpus,
    open_replay_state,
)
from omniintelligence.code_projection.retrieval_eval.scorecard import (
    UNKNOWN,
    ModelEmbeddingCompatibilityKey,
    ModelLatencyReport,
    ModelScenarioOutcome,
    ModelScorecard,
)

SCORECARD_VERSION = "v1"
TICKET = "OMN-16522"
CORPUS_MANIFEST_ID = "omninode.code-projection-fixtures.v2"

GREETER_CHUNK_KEY = "symbol:fixtures.greeter.Greeter"
WIDGET_CHUNK_KEY = "symbol:fixtures.widget.Widget"
_SEARCH_LIMIT = 100


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


class ModelEvalResult(_FrozenModel):
    """The full harness output: the committed scorecard plus loose latency."""

    scorecard: ModelScorecard
    latency: ModelLatencyReport


def _outcome(
    scenario_id: str,
    lane_id: str,
    *,
    passed: bool,
    detail: str,
) -> ModelScenarioOutcome:
    return ModelScenarioOutcome(
        scenario_id=scenario_id,
        lane_id=lane_id,
        description=REPLAY_LANES[lane_id].description,
        passed=passed,
        detail=detail,
    )


async def _run_scenarios(
    corpus: ModelReplayCorpus,
    samples: list[ModelStageLatencySample],
) -> tuple[ModelScenarioOutcome, ...]:
    """Evaluate R1-R6, each against the wrong answer it must reject."""

    greeter_source_id = corpus.batches["python_a_seq1.json"].source.source_id
    widget_source_id = corpus.batches["typescript_seq1.json"].source.source_id
    revision_a = corpus.sole_document("python_a_seq1.json")
    revision_b = corpus.sole_document("python_b_seq2.json")
    external_nodes = [
        node
        for node in corpus.batches["python_a_seq1.json"].nodes
        if node.qualified_name == "builtins.str"
    ]
    outcomes: list[ModelScenarioOutcome] = []

    # R1 -- generation currency. Identity, never relevance: the two greeter
    # revisions differ only by a trailing "  # v2" comment.
    async with open_replay_state(corpus, REPLAY_LANES["a_to_b_to_a"]) as state:
        hits = await state.search("where is the Greeter class defined", limit=100)
        samples.extend(state.stage_samples)
    greeter = [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY]
    r1_ok = len(greeter) == 1 and greeter[0].document_id == revision_a.document_id
    outcomes.append(
        _outcome(
            "R1",
            "a_to_b_to_a",
            passed=r1_ok,
            detail=(
                f"served document_id={greeter[0].document_id if greeter else None}; "
                f"stale revision B ({revision_b.document_id}) must not appear"
            ),
        )
    )

    # R2 -- source deletion excludes the partition, and only that partition.
    async with open_replay_state(corpus, REPLAY_LANES["source_tombstone"]) as state:
        hits = await state.search("where is the Greeter class defined", limit=100)
        r2_reason = state.current_tombstone_reason(greeter_source_id)
        samples.extend(state.stage_samples)
    r2_greeter = [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY]
    r2_widget = [hit for hit in hits if hit.chunk_key == WIDGET_CHUNK_KEY]
    outcomes.append(
        _outcome(
            "R2",
            "source_tombstone",
            passed=not r2_greeter and bool(r2_widget) and r2_reason == "source_deleted",
            detail=(
                f"greeter_hits={len(r2_greeter)} widget_hits={len(r2_widget)} "
                f"reason={r2_reason}"
            ),
        )
    )

    # R3 -- policy revocation, on its own lane so it asserts beyond R2.
    policy_lane = REPLAY_LANES["policy_tombstone"]
    independent = "source_tombstone_seq4.json" not in policy_lane.batch_names
    async with open_replay_state(corpus, policy_lane) as state:
        hits = await state.search("where is the Greeter class defined", limit=100)
        r3_reason = state.current_tombstone_reason(greeter_source_id)
        samples.extend(state.stage_samples)
    r3_greeter = [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY]
    outcomes.append(
        _outcome(
            "R3",
            "policy_tombstone",
            passed=(independent and not r3_greeter and r3_reason == "policy_revoked"),
            detail=(
                f"greeter_hits={len(r3_greeter)} reason={r3_reason} "
                f"seq4_skipped={independent}"
            ),
        )
    )

    # R4 -- an empty snapshot is a state, not a deletion and not a failure.
    empty_source_id = corpus.batches["empty_python_seq1.json"].source.source_id
    async with open_replay_state(corpus, REPLAY_LANES["empty_snapshot"]) as state:
        hits = await state.search("what is defined in the empty module", limit=100)
        empty_generation = state.current_generation(empty_source_id)
        samples.extend(state.stage_samples)
    outcomes.append(
        _outcome(
            "R4",
            "empty_snapshot",
            passed=(
                not hits
                and empty_generation is not None
                and empty_generation.operation == "snapshot"
                and empty_generation.document_ids == ()
            ),
            detail=(
                f"hits={len(hits)} operation="
                f"{empty_generation.operation if empty_generation else None}"
            ),
        )
    )

    # R5 -- external symbols are graph nodes, never retrievable documents.
    external_node_id = external_nodes[0].node_id if external_nodes else None
    async with open_replay_state(corpus, REPLAY_LANES["external_symbol"]) as state:
        hits = await state.search("builtins str type", limit=100)
        samples.extend(state.stage_samples)
    materialized = [hit for hit in hits if hit.anchor_node_id == external_node_id]
    outcomes.append(
        _outcome(
            "R5",
            "external_symbol",
            passed=external_node_id is not None and not materialized,
            detail=(f"node={external_node_id} materialized_chunks={len(materialized)}"),
        )
    )

    # R6 -- partition scoping holds across every greeter mutation.
    widget_document = corpus.sole_document("typescript_seq1.json")
    survived: list[str] = []
    for lane_id in ("a_to_b", "a_to_b_to_a", "source_tombstone", "policy_tombstone"):
        async with open_replay_state(corpus, REPLAY_LANES[lane_id]) as state:
            hits = await state.search(
                "what fields does the Widget interface declare", limit=100
            )
            samples.extend(state.stage_samples)
        widget = [
            hit
            for hit in hits
            if hit.chunk_key == WIDGET_CHUNK_KEY
            and hit.document_id == widget_document.document_id
            and hit.source_id == widget_source_id
        ]
        if len(widget) == 1:
            survived.append(lane_id)
    outcomes.append(
        _outcome(
            "R6",
            "typescript_snapshot",
            passed=len(survived) == 4,
            detail=f"widget survived greeter mutations in lanes: {sorted(survived)}",
        )
    )

    return tuple(outcomes)


async def _score_golden_set(
    corpus: ModelReplayCorpus,
    golden: ModelGoldenQuerySet,
    samples: list[ModelStageLatencySample],
) -> tuple[list[tuple[Sequence[str], frozenset[str]]], list[Sequence[str]]]:
    """Evaluate every ``(query, replay-state)`` pair the golden set declares."""

    positive_rows: list[tuple[Sequence[str], frozenset[str]]] = []
    negative_rows: list[Sequence[str]] = []

    by_lane: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for query in golden.queries:
        for expectation in query.expectations:
            by_lane.setdefault(expectation.lane_id, []).append(
                (query.query_text, expectation.expected_document_ids)
            )

    for lane_id in sorted(by_lane):
        async with open_replay_state(corpus, REPLAY_LANES[lane_id]) as state:
            for query_text, expected in by_lane[lane_id]:
                hits = await state.search(query_text, limit=_SEARCH_LIMIT)
                ranked = [hit.document_id for hit in hits]
                if expected:
                    positive_rows.append((ranked, frozenset(expected)))
                else:
                    negative_rows.append(ranked)
            samples.extend(state.stage_samples)

    return (positive_rows, negative_rows)


def _embedding_key() -> ModelEmbeddingCompatibilityKey:
    """Build the five-part key, recording what the platform does not carry.

    The platform's embedding contract currently pins only a model identifier and
    a dimension.  Artifact digest, tokenizer/preprocessing version and
    normalization are not carried anywhere in code yet, so they are recorded as
    explicitly unknown rather than invented.
    """

    return ModelEmbeddingCompatibilityKey(
        model_name=HARNESS_EMBEDDING_MODEL,
        model_artifact_digest=UNKNOWN,
        model_revision=HARNESS_EMBEDDING_MODEL_VERSION,
        tokenizer_preprocessing_version=UNKNOWN,
        normalization=UNKNOWN,
        distance_metric="Dot",
        dimension=1024,
    )


async def run_eval(
    *,
    corpus: ModelReplayCorpus | None = None,
    golden: ModelGoldenQuerySet | None = None,
) -> ModelEvalResult:
    """Run the whole harness and return the scorecard plus the latency report."""

    resolved_corpus = load_replay_corpus() if corpus is None else corpus
    resolved_golden = load_golden_query_set() if golden is None else golden
    samples: list[ModelStageLatencySample] = []

    scenarios = await _run_scenarios(resolved_corpus, samples)
    positive_rows, negative_rows = await _score_golden_set(
        resolved_corpus, resolved_golden, samples
    )

    chunk_keys = tuple(sorted(resolved_corpus.distinct_chunk_keys()))
    metrics = summarize_metrics(
        positive_rows=positive_rows,
        negative_rows=negative_rows,
        distinct_documents=len(chunk_keys),
        labeled_queries=resolved_golden.labeled_query_count,
    )
    key = _embedding_key()

    scorecard = ModelScorecard(
        scorecard_version=SCORECARD_VERSION,
        ticket=TICKET,
        corpus_manifest_id=CORPUS_MANIFEST_ID,
        golden_set_version=resolved_golden.golden_set_version,
        corpus_fixture_count=len(resolved_corpus.batches),
        distinct_chunk_keys=chunk_keys,
        golden_query_ids=tuple(query.query_id for query in resolved_golden.queries),
        assertion_count=resolved_golden.assertion_count(),
        metrics=metrics,
        embedding_compatibility_key=key,
        unknown_embedding_components=key.unknown_components,
        scenarios=scenarios,
    )
    return ModelEvalResult(
        scorecard=scorecard,
        latency=ModelLatencyReport.from_samples(tuple(samples)),
    )


__all__ = [
    "CORPUS_MANIFEST_ID",
    "SCORECARD_VERSION",
    "TICKET",
    "ModelEvalResult",
    "run_eval",
]
