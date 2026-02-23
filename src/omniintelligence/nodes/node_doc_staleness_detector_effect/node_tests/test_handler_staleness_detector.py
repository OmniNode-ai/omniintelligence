# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_staleness_detector — DocStalenessDetectorEffect.

All tests use mock store and trigger implementations. No live connections.

Test coverage:
    - Staleness case classification (FILE_DELETED, CONTENT_CHANGED_*, FILE_MOVED)
    - FILE_DELETED: immediate blacklist
    - FILE_MOVED: in-place source_ref update
    - CONTENT_CHANGED_STATIC: 3-step atomic sequence
    - CONTENT_CHANGED_REPO: 3-step with stat carry
    - CONTENT_CHANGED_REPO: no stat carry when similarity below threshold
    - Crash recovery: resume from existing transition at INDEX_NEW step
    - Crash recovery: resume from VERIFY_NEW step (blacklist only)
    - Already-complete transition: skip without re-processing
    - Empty candidates: returns zero counts
    - Partial failure: one candidate fails, others succeed
    - Dry run: no writes performed
    - Cosine similarity computation
    - Correlation ID propagation

Ticket: OMN-2394
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_doc_staleness_detector_effect.handlers.handler_staleness_detector import (
    ProtocolReingestionTrigger,
    ProtocolStalenessStore,
    _classify_staleness,
    _compute_similarity,
    handle_staleness_detection,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_case import (
    EnumStalenessCase,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.enum_staleness_transition_step import (
    EnumStalenessTransitionStep,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_detect_input import (
    ModelStalenessCandidate,
    ModelStalenessDetectInput,
)
from omniintelligence.nodes.node_doc_staleness_detector_effect.models.model_staleness_transition import (
    ModelStalenessTransition,
)

# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _make_staleness_store(
    load_result: ModelStalenessTransition | None = None,
    verify_pg: bool = True,
    verify_qdrant: bool = True,
) -> ProtocolStalenessStore:
    mock = MagicMock(spec=ProtocolStalenessStore)
    mock.blacklist_item = AsyncMock()
    mock.update_source_ref = AsyncMock()
    mock.verify_item_in_pg = AsyncMock(return_value=verify_pg)
    mock.verify_item_in_qdrant = AsyncMock(return_value=verify_qdrant)
    mock.apply_stat_carry = AsyncMock()
    mock.save_transition = AsyncMock()
    mock.load_transition = AsyncMock(return_value=load_result)
    return mock


def _make_reingestion_trigger(
    new_item_id: UUID | None = None,
) -> ProtocolReingestionTrigger:
    mock = MagicMock(spec=ProtocolReingestionTrigger)
    mock.trigger_reingestion = AsyncMock(return_value=new_item_id)
    return mock


def _make_candidate(
    *,
    file_exists: bool = True,
    new_version_hash: str | None = "hash-new",
    new_source_ref: str | None = None,
    is_static_standards: bool = False,
    current_embedding: tuple[float, ...] | None = None,
    new_embedding: tuple[float, ...] | None = None,
    item_id: UUID | None = None,
) -> ModelStalenessCandidate:
    return ModelStalenessCandidate(
        item_id=item_id or uuid4(),
        source_ref="docs/README.md",
        current_version_hash="hash-old",
        new_version_hash=new_version_hash,
        new_source_ref=new_source_ref,
        file_exists=file_exists,
        current_embedding=current_embedding,
        new_embedding=new_embedding,
        is_static_standards=is_static_standards,
    )


# ---------------------------------------------------------------------------
# Staleness classification tests
# ---------------------------------------------------------------------------


class TestClassifyStaleness:
    def test_file_deleted(self) -> None:
        candidate = _make_candidate(file_exists=False)
        assert _classify_staleness(candidate) == EnumStalenessCase.FILE_DELETED

    def test_file_moved(self) -> None:
        candidate = _make_candidate(new_source_ref="docs/NEW_README.md")
        assert _classify_staleness(candidate) == EnumStalenessCase.FILE_MOVED

    def test_content_changed_static(self) -> None:
        candidate = _make_candidate(
            is_static_standards=True, new_version_hash="hash-new"
        )
        assert (
            _classify_staleness(candidate) == EnumStalenessCase.CONTENT_CHANGED_STATIC
        )

    def test_content_changed_repo(self) -> None:
        candidate = _make_candidate(
            is_static_standards=False, new_version_hash="hash-new"
        )
        assert _classify_staleness(candidate) == EnumStalenessCase.CONTENT_CHANGED_REPO

    def test_file_deleted_takes_priority_over_moved(self) -> None:
        # file_exists=False takes priority
        candidate = _make_candidate(file_exists=False, new_source_ref="docs/MOVED.md")
        assert _classify_staleness(candidate) == EnumStalenessCase.FILE_DELETED


# ---------------------------------------------------------------------------
# Cosine similarity tests
# ---------------------------------------------------------------------------


class TestComputeSimilarity:
    def test_identical_vectors(self) -> None:
        v = (1.0, 0.0, 0.0)
        result = _compute_similarity(v, v)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_orthogonal_vectors(self) -> None:
        result = _compute_similarity((1.0, 0.0), (0.0, 1.0))
        assert result is not None
        assert abs(result - 0.0) < 1e-9

    def test_none_when_missing_old(self) -> None:
        assert _compute_similarity(None, (1.0, 0.0)) is None

    def test_none_when_missing_new(self) -> None:
        assert _compute_similarity((1.0, 0.0), None) is None

    def test_none_when_both_none(self) -> None:
        assert _compute_similarity(None, None) is None

    def test_none_when_mismatched_length(self) -> None:
        assert _compute_similarity((1.0, 0.0), (1.0, 0.0, 0.0)) is None

    def test_none_when_zero_vector(self) -> None:
        assert _compute_similarity((0.0, 0.0), (1.0, 0.0)) is None


# ---------------------------------------------------------------------------
# FILE_DELETED case
# ---------------------------------------------------------------------------


class TestFileDeleted:
    @pytest.mark.asyncio
    async def test_blacklists_immediately(self) -> None:
        candidate = _make_candidate(file_exists=False)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.items_blacklisted == 1
        assert result.items_moved == 0
        assert result.items_reingested == 0
        store.blacklist_item.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_transition_saved_as_complete(self) -> None:
        candidate = _make_candidate(file_exists=False)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert len(result.transitions) == 1
        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.COMPLETE
        )
        assert result.transitions[0].staleness_case == EnumStalenessCase.FILE_DELETED


# ---------------------------------------------------------------------------
# FILE_MOVED case
# ---------------------------------------------------------------------------


class TestFileMoved:
    @pytest.mark.asyncio
    async def test_updates_source_ref_in_place(self) -> None:
        item_id = uuid4()
        candidate = _make_candidate(
            item_id=item_id,
            new_source_ref="docs/MOVED_README.md",
            new_version_hash=None,
        )
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.items_moved == 1
        assert result.items_blacklisted == 0
        store.update_source_ref.assert_called_once()  # type: ignore[attr-defined]
        call_kwargs = store.update_source_ref.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["item_id"] == item_id
        assert call_kwargs["new_source_ref"] == "docs/MOVED_README.md"

    @pytest.mark.asyncio
    async def test_does_not_trigger_reingestion(self) -> None:
        candidate = _make_candidate(new_source_ref="docs/NEW.md", new_version_hash=None)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        trigger.trigger_reingestion.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# CONTENT_CHANGED_STATIC case
# ---------------------------------------------------------------------------


class TestContentChangedStatic:
    @pytest.mark.asyncio
    async def test_full_3_step_sequence(self) -> None:
        item_id = uuid4()
        new_item_id = uuid4()
        candidate = _make_candidate(
            item_id=item_id,
            is_static_standards=True,
            new_version_hash="hash-new",
        )
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=new_item_id)

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.items_reingested == 1
        assert result.items_blacklisted == 1
        assert len(result.transitions) == 1
        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.COMPLETE
        )
        assert result.transitions[0].new_item_id == new_item_id

    @pytest.mark.asyncio
    async def test_blacklist_called_after_verify(self) -> None:
        candidate = _make_candidate(is_static_standards=True)
        new_id = uuid4()
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=new_id)

        await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.blacklist_item.assert_called_once()  # type: ignore[attr-defined]
        store.verify_item_in_pg.assert_called_once()  # type: ignore[attr-defined]
        store.verify_item_in_qdrant.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_no_blacklist_when_verify_fails(self) -> None:
        candidate = _make_candidate(is_static_standards=True)
        new_id = uuid4()
        store = _make_staleness_store(verify_pg=False)  # PG verify fails
        trigger = _make_reingestion_trigger(new_item_id=new_id)

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.blacklist_item.assert_not_called()  # type: ignore[attr-defined]
        assert result.items_blacklisted == 0
        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.INDEX_NEW
        )

    @pytest.mark.asyncio
    async def test_no_stat_carry_for_static(self) -> None:
        # Stat carry only applies to CONTENT_CHANGED_REPO
        candidate = _make_candidate(
            is_static_standards=True,
            current_embedding=(1.0, 0.0),
            new_embedding=(1.0, 0.0),  # similarity = 1.0 (above threshold)
        )
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=uuid4())

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.apply_stat_carry.assert_not_called()  # type: ignore[attr-defined]
        assert result.stat_carries_applied == 0


# ---------------------------------------------------------------------------
# CONTENT_CHANGED_REPO case
# ---------------------------------------------------------------------------


class TestContentChangedRepo:
    @pytest.mark.asyncio
    async def test_stat_carry_when_high_similarity(self) -> None:
        old_embed = (1.0, 0.0, 0.0)
        new_embed = (0.99, 0.1, 0.0)  # high similarity
        candidate = _make_candidate(
            is_static_standards=False,
            current_embedding=old_embed,
            new_embedding=new_embed,
        )
        new_id = uuid4()
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=new_id)

        result = await handle_staleness_detection(
            _make_input([candidate], similarity_threshold=0.85),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.apply_stat_carry.assert_called_once()  # type: ignore[attr-defined]
        assert result.stat_carries_applied == 1

    @pytest.mark.asyncio
    async def test_no_stat_carry_when_low_similarity(self) -> None:
        old_embed = (1.0, 0.0)
        new_embed = (0.0, 1.0)  # orthogonal = 0.0 similarity
        candidate = _make_candidate(
            is_static_standards=False,
            current_embedding=old_embed,
            new_embedding=new_embed,
        )
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=uuid4())

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.apply_stat_carry.assert_not_called()  # type: ignore[attr-defined]
        assert result.stat_carries_applied == 0

    @pytest.mark.asyncio
    async def test_no_stat_carry_when_embeddings_missing(self) -> None:
        candidate = _make_candidate(is_static_standards=False)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=uuid4())

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.apply_stat_carry.assert_not_called()  # type: ignore[attr-defined]
        assert result.stat_carries_applied == 0


# ---------------------------------------------------------------------------
# Crash recovery tests
# ---------------------------------------------------------------------------


class TestCrashRecovery:
    @pytest.mark.asyncio
    async def test_resume_from_index_new_step(self) -> None:
        """After crash at INDEX_NEW, re-verification and blacklist proceed."""
        item_id = uuid4()
        new_id = uuid4()

        # Simulate existing transition at INDEX_NEW step
        existing_transition = ModelStalenessTransition(
            transition_id=item_id,
            old_item_id=item_id,
            source_ref="docs/README.md",
            new_item_id=new_id,
            staleness_case=EnumStalenessCase.CONTENT_CHANGED_REPO,
            current_step=EnumStalenessTransitionStep.INDEX_NEW,
            stat_carry_applied=False,
            embedding_similarity=0.9,
            correlation_id="test-corr",
        )

        candidate = _make_candidate(item_id=item_id)
        store = _make_staleness_store(load_result=existing_transition)
        trigger = _make_reingestion_trigger(new_item_id=new_id)

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        # Should complete the sequence
        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.COMPLETE
        )
        # Stat carry applied since similarity=0.9 >= 0.85
        assert result.stat_carries_applied == 1

    @pytest.mark.asyncio
    async def test_resume_from_verify_new_step_blacklists_only(self) -> None:
        """After crash at VERIFY_NEW (verify succeeded), only blacklist remains."""
        item_id = uuid4()
        new_id = uuid4()

        existing_transition = ModelStalenessTransition(
            transition_id=item_id,
            old_item_id=item_id,
            source_ref="docs/README.md",
            new_item_id=new_id,
            staleness_case=EnumStalenessCase.CONTENT_CHANGED_STATIC,
            current_step=EnumStalenessTransitionStep.VERIFY_NEW,
            stat_carry_applied=False,
            embedding_similarity=None,
            correlation_id="test-corr",
        )

        candidate = _make_candidate(item_id=item_id, is_static_standards=True)
        store = _make_staleness_store(load_result=existing_transition)
        trigger = _make_reingestion_trigger(new_item_id=new_id)

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.COMPLETE
        )
        # trigger_reingestion NOT called (already passed INDEX_NEW)
        trigger.trigger_reingestion.assert_not_called()  # type: ignore[attr-defined]
        # Only blacklist is called
        store.blacklist_item.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_already_complete_skipped(self) -> None:
        """Transition already COMPLETE is skipped without re-processing."""
        item_id = uuid4()
        complete_transition = ModelStalenessTransition(
            transition_id=item_id,
            old_item_id=item_id,
            source_ref="docs/README.md",
            staleness_case=EnumStalenessCase.FILE_DELETED,
            current_step=EnumStalenessTransitionStep.COMPLETE,
            correlation_id=None,
        )

        candidate = _make_candidate(item_id=item_id, file_exists=False)
        store = _make_staleness_store(load_result=complete_transition)
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.blacklist_item.assert_not_called()  # type: ignore[attr-defined]
        assert (
            result.transitions[0].current_step == EnumStalenessTransitionStep.COMPLETE
        )


# ---------------------------------------------------------------------------
# Empty input and partial failure
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_candidates(self) -> None:
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.items_blacklisted == 0
        assert result.items_moved == 0
        assert result.items_reingested == 0
        assert result.items_failed == 0
        assert len(result.transitions) == 0

    @pytest.mark.asyncio
    async def test_partial_failure_other_candidates_succeed(self) -> None:
        good1 = _make_candidate(file_exists=False, item_id=uuid4())
        bad = _make_candidate(file_exists=False, item_id=uuid4())
        good2 = _make_candidate(file_exists=False, item_id=uuid4())

        call_count = 0

        async def flaky_blacklist(**_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("DB error")

        store = _make_staleness_store()
        store.blacklist_item.side_effect = flaky_blacklist  # type: ignore[attr-defined]
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([good1, bad, good2]),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.items_blacklisted == 2
        assert result.items_failed == 1

    @pytest.mark.asyncio
    async def test_dry_run_no_writes(self) -> None:
        candidate = _make_candidate(file_exists=False)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate], dry_run=True),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.blacklist_item.assert_not_called()  # type: ignore[attr-defined]
        store.save_transition.assert_not_called()  # type: ignore[attr-defined]
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self) -> None:
        candidate = _make_candidate(file_exists=False)
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger()

        result = await handle_staleness_detection(
            _make_input([candidate], correlation_id="my-corr-id"),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        assert result.correlation_id == "my-corr-id"
        assert result.transitions[0].correlation_id == "my-corr-id"


# ---------------------------------------------------------------------------
# ModelStalenessDetectInput custom threshold
# ---------------------------------------------------------------------------


class TestCustomThreshold:
    @pytest.mark.asyncio
    async def test_custom_similarity_threshold(self) -> None:
        """With threshold=0.5, lower similarity still triggers carry."""
        old_embed = (1.0, 0.0)
        new_embed = (0.8, 0.6)  # similarity ~0.8
        candidate = _make_candidate(
            is_static_standards=False,
            current_embedding=old_embed,
            new_embedding=new_embed,
        )
        store = _make_staleness_store()
        trigger = _make_reingestion_trigger(new_item_id=uuid4())

        result = await handle_staleness_detection(
            ModelStalenessDetectInput(
                candidates=(candidate,),
                similarity_threshold=0.5,  # lower threshold
                correlation_id="test",
            ),
            staleness_store=store,
            reingestion_trigger=trigger,
        )

        store.apply_stat_carry.assert_called_once()  # type: ignore[attr-defined]
        assert result.stat_carries_applied == 1


def _make_input(
    candidates: list[ModelStalenessCandidate],
    dry_run: bool = False,
    correlation_id: str | None = "test-corr",
    similarity_threshold: float = 0.85,
) -> ModelStalenessDetectInput:
    return ModelStalenessDetectInput(
        candidates=tuple(candidates),
        dry_run=dry_run,
        correlation_id=correlation_id,
        similarity_threshold=similarity_threshold,
    )
