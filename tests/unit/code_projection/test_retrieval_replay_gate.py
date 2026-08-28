# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16522 retrieval-layer replay gate.

The reducer-level replay semantics are already proven in
``test_fixture_contract.py`` and ``test_codec_and_replay.py``.  What those
suites never assert is what a *search over the index* returns at each replay
state.  That is what this module gates.

R1 (generation currency) is an identity assertion on ``document_id`` and
``sanitized_content_hash_sha256``, never a relevance or ranking assertion: the
two greeter revisions differ only by a trailing six-character ``  # v2``
comment, so no query can separate them on content.
"""

from __future__ import annotations

import pytest

from omniintelligence.code_projection.retrieval_eval import (
    REPLAY_LANES,
    load_replay_corpus,
    open_replay_state,
)

pytestmark = pytest.mark.unit

GREETER_CHUNK_KEY = "symbol:fixtures.greeter.Greeter"
WIDGET_CHUNK_KEY = "symbol:fixtures.widget.Widget"
GREETER_QUERY = "where is the Greeter class defined"


async def test_r1_generation_currency_serves_revision_a_after_a_to_b_to_a() -> None:
    """R1: after 1->2->3 the greeter hit is revision A, not the stale revision B."""

    corpus = load_replay_corpus()
    revision_a = corpus.sole_document("python_a_seq1.json")
    revision_b = corpus.sole_document("python_b_seq2.json")

    # Guard the premise: the two revisions are genuinely distinct documents that
    # differ only by content hash, so "returned the stale one" is observable.
    assert revision_a.document_id != revision_b.document_id
    assert (
        revision_a.sanitized_content_hash_sha256
        != revision_b.sanitized_content_hash_sha256
    )
    # a->b->a restores the exact prior document rather than minting a third.
    assert corpus.sole_document("python_a_seq3.json").document_id == (
        revision_a.document_id
    )

    async with open_replay_state(corpus, REPLAY_LANES["a_to_b_to_a"]) as state:
        hits = await state.search("where is the Greeter class defined")

    greeter_hits = [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY]
    assert len(greeter_hits) == 1

    served = greeter_hits[0]
    assert served.document_id == revision_a.document_id
    assert served.sanitized_content_hash_sha256 == (
        revision_a.sanitized_content_hash_sha256
    )
    # The stated wrong answer, named explicitly so the gate reads as a gate.
    assert served.document_id != revision_b.document_id


async def test_r1_gate_discriminates_and_serves_revision_b_at_the_a_to_b_state() -> (
    None
):
    """R1 has teeth: the same query returns revision B one state earlier.

    Without this, R1 passing would be consistent with a harness that always
    returns revision A regardless of replay state.  Feeding the gate the state
    that produces its stated wrong answer is what proves it discriminates.
    """

    corpus = load_replay_corpus()
    revision_a = corpus.sole_document("python_a_seq1.json")
    revision_b = corpus.sole_document("python_b_seq2.json")

    async with open_replay_state(corpus, REPLAY_LANES["a_to_b"]) as state:
        hits = await state.search("where is the Greeter class defined")

    greeter_hits = [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY]
    assert len(greeter_hits) == 1

    served = greeter_hits[0]
    assert served.document_id == revision_b.document_id
    assert served.sanitized_content_hash_sha256 == (
        revision_b.sanitized_content_hash_sha256
    )
    assert served.document_id != revision_a.document_id


async def test_r2_source_deletion_excludes_the_greeter_and_spares_the_widget() -> None:
    """R2: after ``source_deleted`` no greeter document is retrievable.

    The stated wrong answer is any greeter hit surviving the tombstone --
    including a stale one whose batch predates it.
    """

    corpus = load_replay_corpus()
    greeter_source_id = corpus.batches["python_a_seq1.json"].source.source_id

    async with open_replay_state(corpus, REPLAY_LANES["source_tombstone"]) as state:
        hits = await state.search(GREETER_QUERY, limit=100)
        generation = state.current_generation(greeter_source_id)
        reason = state.current_tombstone_reason(greeter_source_id)

    assert [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY] == []
    assert generation is not None
    assert generation.operation == "tombstone"
    assert reason == "source_deleted"
    # The tombstone is partition-scoped: the widget must be untouched by it.
    assert [hit for hit in hits if hit.chunk_key == WIDGET_CHUNK_KEY] != []


async def test_r3_policy_revocation_excludes_the_greeter_on_its_own_lane() -> None:
    """R3: ``policy_revoked`` empties the partition independently of R2.

    Both tombstones sit on the greeter partition at sequences 4 and 5, so a
    monotone 1->2->3->4->5 replay would leave the partition already empty when
    seq5 lands and this scenario would assert nothing beyond R2 -- five real
    scenarios, not six.  Planning seq5 against the same prior state as seq4 is
    what makes it independently gating.
    """

    corpus = load_replay_corpus()
    lane = REPLAY_LANES["policy_tombstone"]
    greeter_source_id = corpus.batches["python_a_seq1.json"].source.source_id

    # The independence premise, asserted rather than assumed: this lane reaches
    # its empty state without ever applying the source tombstone.
    assert "source_tombstone_seq4.json" not in lane.batch_names
    assert "policy_tombstone_seq5.json" in lane.batch_names

    async with open_replay_state(corpus, lane) as state:
        hits = await state.search(GREETER_QUERY, limit=100)
        generation = state.current_generation(greeter_source_id)
        reason = state.current_tombstone_reason(greeter_source_id)

    assert [hit for hit in hits if hit.chunk_key == GREETER_CHUNK_KEY] == []
    assert generation is not None
    assert generation.operation == "tombstone"
    # Distinct from R2's reason -- surfacing the same exclusion for a different
    # cause is the whole point of the scenario being separate.
    assert reason == "policy_revoked"
    assert reason != "source_deleted"
    assert [hit for hit in hits if hit.chunk_key == WIDGET_CHUNK_KEY] != []


async def test_r4_empty_snapshot_is_a_state_not_a_deletion_or_a_failure() -> None:
    """R4: a zero-document snapshot applies cleanly and yields nothing.

    The stated wrong answers are raising, or treating the empty snapshot as a
    deletion or a no-op.
    """

    corpus = load_replay_corpus()
    empty_source_id = corpus.batches["empty_python_seq1.json"].source.source_id

    async with open_replay_state(corpus, REPLAY_LANES["empty_snapshot"]) as state:
        hits = await state.search("what is defined in the empty module", limit=100)
        generation = state.current_generation(empty_source_id)
        reason = state.current_tombstone_reason(empty_source_id)

    assert hits == ()
    assert generation is not None
    # Applied, and applied as a snapshot -- not a tombstone, not absent.
    assert generation.operation == "snapshot"
    assert generation.document_ids == ()
    assert reason is None


async def test_r5_external_symbols_are_graph_nodes_but_never_retrievable() -> None:
    """R5: ``builtins.str`` is a real node and edge target with no document.

    The stated wrong answer is a graph-walk expansion materializing a chunk for
    it.  The premise is asserted first: if the node stopped being a real edge
    target this test would silently stop proving anything.
    """

    corpus = load_replay_corpus()
    batch = corpus.batches["python_a_seq1.json"]

    external = [node for node in batch.nodes if node.qualified_name == "builtins.str"]
    assert len(external) == 1
    external_node_id = external[0].node_id
    # It is genuinely part of the graph: a node, and the target of a real edge.
    assert external[0].source_span is None
    assert [edge for edge in batch.edges if edge.target_node_id == external_node_id]
    # ...and it anchors no semantic document anywhere in the corpus.
    assert [
        document
        for document in batch.semantic_documents
        if document.anchor_node_id == external_node_id
    ] == []

    async with open_replay_state(corpus, REPLAY_LANES["external_symbol"]) as state:
        hits = await state.search("builtins str type", limit=100)

    assert [hit for hit in hits if hit.anchor_node_id == external_node_id] == []


async def test_r6_partition_scoping_holds_across_every_greeter_mutation() -> None:
    """R6: the widget survives every greeter-partition mutation.

    R6 names two wrong answers and only one is assertable here.  This asserts
    the greeter tombstones not removing the widget document -- a partition-scoped
    mutation leaking across partitions.

    The other conjunct, "a python-scoped query returns the widget", is *not*
    asserted and cannot be through this surface: ``search()`` filters on tenant,
    repository and record_kind, there is no language parameter, and a replay
    lane must sit inside one repository so both fixture partitions share a
    ``repository_id``.  It is unassertable rather than unasserted, recorded so
    half a gate does not read as a whole one.
    """

    corpus = load_replay_corpus()
    greeter_source_id = corpus.batches["python_a_seq1.json"].source.source_id
    widget_source_id = corpus.batches["typescript_seq1.json"].source.source_id
    widget_document = corpus.sole_document("typescript_seq1.json")
    assert greeter_source_id != widget_source_id

    # Every lane that mutates the greeter partition, including both tombstones.
    for lane_id in ("a_to_b", "a_to_b_to_a", "source_tombstone", "policy_tombstone"):
        async with open_replay_state(corpus, REPLAY_LANES[lane_id]) as state:
            hits = await state.search(
                "what does the Widget interface declare", limit=100
            )
            widget_generation = state.current_generation(widget_source_id)

        widget_hits = [hit for hit in hits if hit.chunk_key == WIDGET_CHUNK_KEY]
        assert len(widget_hits) == 1, lane_id
        assert widget_hits[0].document_id == widget_document.document_id, lane_id
        assert widget_hits[0].source_id == widget_source_id, lane_id
        # The widget's own generation is untouched by greeter mutations.
        assert widget_generation is not None, lane_id
        assert widget_generation.operation == "snapshot", lane_id


async def test_r7_identical_content_at_a_higher_cursor_changes_nothing() -> None:
    """R7 (optional): seq3 re-applies seq1's exact document at a later cursor.

    Different ``batch_id``, ``cursor.sequence`` and ``source_version``; identical
    ``document_id`` and ``content_ref``.  Advancing the pointer must not change
    what is retrievable.
    """

    corpus = load_replay_corpus()
    first = corpus.batches["python_a_seq1.json"]
    third = corpus.batches["python_a_seq3.json"]

    assert first.batch_id != third.batch_id
    assert first.cursor.sequence < third.cursor.sequence
    assert first.source.source_version != third.source.source_version
    assert corpus.sole_document("python_a_seq1.json").document_id == (
        corpus.sole_document("python_a_seq3.json").document_id
    )

    async with open_replay_state(corpus, REPLAY_LANES["external_symbol"]) as early:
        early_hits = await early.search(GREETER_QUERY, limit=100)
    async with open_replay_state(corpus, REPLAY_LANES["a_to_b_to_a"]) as late:
        late_hits = await late.search(GREETER_QUERY, limit=100)
        late_generation = late.current_generation(first.source.source_id)

    early_documents = sorted(hit.document_id for hit in early_hits)
    late_documents = sorted(
        hit.document_id for hit in late_hits if hit.source_id == first.source.source_id
    )
    assert early_documents == late_documents
    # The pointer did advance, even though the retrievable set did not.
    assert late_generation is not None
    assert late_generation.batch_id == third.batch_id


async def test_current_chunk_keys_excludes_tombstoned_and_superseded_keys() -> None:
    """N must come from the current generation, not from the whole corpus.

    Corpus-wide counting is wrong in the unsafe direction: it counts superseded
    revisions and tombstoned partitions as rankable, so a corpus whose keys are
    mostly tombstoned in the scored lanes would arm the ranking metrics against
    a corpus that cannot actually rank. Inert on this fixture set -- which is
    exactly why it needs a test rather than a reader's trust.
    """

    corpus = load_replay_corpus()
    assert corpus.distinct_chunk_keys() == {GREETER_CHUNK_KEY, WIDGET_CHUNK_KEY}

    async with open_replay_state(corpus, REPLAY_LANES["a_to_b_to_a"]) as state:
        both_live = state.current_chunk_keys()
    async with open_replay_state(corpus, REPLAY_LANES["source_tombstone"]) as state:
        after_source_tombstone = state.current_chunk_keys()
    async with open_replay_state(corpus, REPLAY_LANES["policy_tombstone"]) as state:
        after_policy_tombstone = state.current_chunk_keys()
    async with open_replay_state(corpus, REPLAY_LANES["empty_snapshot"]) as state:
        empty_only = state.current_chunk_keys()

    assert both_live == {GREETER_CHUNK_KEY, WIDGET_CHUNK_KEY}
    # Both tombstones drop the greeter key while the corpus-wide count stays 2.
    assert after_source_tombstone == {WIDGET_CHUNK_KEY}
    assert after_policy_tombstone == {WIDGET_CHUNK_KEY}
    assert empty_only == frozenset()
