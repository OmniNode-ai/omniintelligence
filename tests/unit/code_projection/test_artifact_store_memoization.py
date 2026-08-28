# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-16764: request-scoped memoization of `load_current`.

Serving one context pack calls `load_current` 24 times -- once per candidate in
the resolver, plus once per source inside `search()`'s current-generation check.
Each call re-reads and SHA-256-verifies *every* semantic document in the whole
batch, so candidates from the same source pay the full cost again each time.
Measured on the dev lane: 616 ms of an 857 ms warm request, producing 2704
content-artifact reads.

The memo is deliberately **opt-in and explicitly scoped** rather than always-on.
`mark_applied` calls `load_current` immediately after atomically replacing the
current-state file, and a blanket cache would hand it back the stale
pre-promotion projection -- a data-integrity bug introduced by a latency
optimization. `test_promotion_is_not_memoized` pins that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from tests.unit.code_projection.fixture_vectors import (
    build_fixture_batches,
    fixture_bytes,
)

pytestmark = pytest.mark.unit


def _raw_greeter() -> bytes:
    return fixture_bytes("sources/greeter.py.fixture")


def _stage_fixture_contract_artifacts(
    store: CodeProjectionArtifactStore,
    batch: object,
) -> None:
    """Stage every artifact the batch's contract references."""

    from tests.unit.code_projection.test_artifacts import (
        _stage_fixture_contract_artifacts as _stage,
    )

    _stage(store, batch)


def _promoted_store(tmp_path: Path) -> tuple[CodeProjectionArtifactStore, str]:
    """Return a store with one promoted source, and that source's id."""

    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)
    _stage_fixture_contract_artifacts(store, batch)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    with store.source_lock(batch.source.source_id):
        store.mark_applied(staged)
    return store, batch.source.source_id


class _ReadCounter:
    """Count store-file reads without changing what they return."""

    def __init__(self, store: CodeProjectionArtifactStore) -> None:
        self._original = store._read_store_file  # noqa: SLF001
        self.count = 0
        store._read_store_file = self._counted  # type: ignore[method-assign] # noqa: SLF001

    def _counted(self, *args: object, **kwargs: object) -> bytes:
        self.count += 1
        return self._original(*args, **kwargs)  # type: ignore[arg-type]


def test_repeated_loads_are_uncached_by_default(tmp_path: Path) -> None:
    """Without an explicit scope, every call does the full read-and-verify."""

    store, source_id = _promoted_store(tmp_path)
    counter = _ReadCounter(store)

    store.load_current(source_id)
    first = counter.count
    store.load_current(source_id)

    assert first > 0, "the first load should read from the store"
    assert counter.count == first * 2, (
        "an unscoped second load must repeat the work, not silently cache"
    )


def test_memoized_scope_collapses_repeated_loads(tmp_path: Path) -> None:
    """Inside the scope, the same source_id is read and verified once."""

    store, source_id = _promoted_store(tmp_path)
    counter = _ReadCounter(store)

    with store.memoized_current():
        first = store.load_current(source_id)
        reads_after_first = counter.count
        second = store.load_current(source_id)
        third = store.load_current(source_id)

    assert reads_after_first > 0
    assert counter.count == reads_after_first, (
        "second and third loads inside the scope must not touch the store"
    )
    assert first is second is third, "the memo must return the same object"


def test_memo_is_discarded_when_the_scope_exits(tmp_path: Path) -> None:
    """The memo is request-scoped; it must not survive the scope."""

    store, source_id = _promoted_store(tmp_path)

    with store.memoized_current():
        store.load_current(source_id)

    counter = _ReadCounter(store)
    store.load_current(source_id)

    assert counter.count > 0, "leaving the scope must discard the memo"


def test_absent_source_is_memoized_too(tmp_path: Path) -> None:
    """A miss is as cacheable as a hit, and must not be re-probed."""

    store, _ = _promoted_store(tmp_path)
    absent = "csrc_v2_" + "0" * 64
    counter = _ReadCounter(store)

    with store.memoized_current():
        assert store.load_current(absent) is None
        reads_after_first = counter.count
        assert store.load_current(absent) is None

    assert counter.count == reads_after_first


def test_promotion_is_not_memoized(tmp_path: Path) -> None:
    """The read-after-write in `mark_applied` must never see a stale memo.

    `mark_applied` loads current state, replaces it atomically, then loads again
    to return the promoted projection. If that second load were served from a
    memo populated by the first, it would return the *pre-promotion* projection
    and the caller would silently receive the wrong batch.
    """

    batches = build_fixture_batches()
    first_batch = batches["python_a_seq1.json"]
    second_batch = batches["python_b_seq2.json"]

    store = CodeProjectionArtifactStore(tmp_path)
    _stage_fixture_contract_artifacts(store, first_batch)
    _stage_fixture_contract_artifacts(store, second_batch)

    staged_first = store.stage(raw_source=_raw_greeter(), batch=first_batch)
    with store.source_lock(first_batch.source.source_id):
        store.mark_applied(staged_first)

    staged_second = store.stage(
        raw_source=fixture_bytes("sources/greeter_v2.py.fixture"),
        batch=second_batch,
    )

    # Promote inside a memo scope that already holds the *old* projection.
    with store.memoized_current():
        stale = store.load_current(first_batch.source.source_id)
        assert stale is not None
        assert stale.batch == first_batch

        with store.source_lock(second_batch.source.source_id):
            promoted = store.mark_applied(staged_second)

        assert promoted.batch == second_batch, (
            "mark_applied returned the pre-promotion projection; the memo "
            "leaked into the write path"
        )


def test_nested_scopes_do_not_clobber_the_outer_memo(tmp_path: Path) -> None:
    """A nested scope reuses the active memo rather than resetting it."""

    store, source_id = _promoted_store(tmp_path)
    counter = _ReadCounter(store)

    with store.memoized_current():
        store.load_current(source_id)
        reads_after_first = counter.count
        with store.memoized_current():
            store.load_current(source_id)
        store.load_current(source_id)

    assert counter.count == reads_after_first
