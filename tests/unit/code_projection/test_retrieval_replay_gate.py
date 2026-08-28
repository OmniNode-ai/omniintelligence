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
