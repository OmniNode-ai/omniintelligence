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
