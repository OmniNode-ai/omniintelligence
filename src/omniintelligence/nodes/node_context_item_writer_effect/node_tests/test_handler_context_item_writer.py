# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_context_item_writer — ContextItemWriterEffect.

All tests use mock store implementations. No live PostgreSQL, Qdrant, or
Memgraph connections required.

Test coverage:
    - Idempotency: CREATED / UPDATED / SKIPPED cases
    - Empty input: returns zero-count output
    - Bootstrap tier assignment: VALIDATED vs QUARANTINE by source_ref
    - Partial failure: one chunk fails, rest succeed
    - Event emission: success and failure cases
    - Counter accuracy: items_created / items_updated / items_skipped / items_failed
    - Correlation ID propagation

Ticket: OMN-2393
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_context_item_writer_effect.handlers.handler_context_item_writer import (
    ProtocolContextStore,
    ProtocolEventEmitter,
    ProtocolGraphStore,
    ProtocolVectorStore,
    handle_context_item_write,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.enum_bootstrap_tier import (
    EnumBootstrapTier,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_context_item_write_input import (
    ModelContextItemWriteInput,
)
from omniintelligence.nodes.node_context_item_writer_effect.models.model_tier_policy import (
    ModelTierPolicy,
    assign_bootstrap_tier,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedded_chunk import (
    ModelEmbeddedChunk,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING: tuple[float, ...] = tuple([0.1] * 1024)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_embedded_chunk(
    content: str = "Sample embedded text.",
    source_ref: str = "docs/CLAUDE.md",
    content_fingerprint: str = "fp-abc",
    version_hash: str = "vh-def",
    offset_start: int = 0,
    offset_end: int = 21,
    crawl_scope: str = "omninode/omniintelligence",
    correlation_id: str | None = "test-corr-01",
) -> ModelEmbeddedChunk:
    return ModelEmbeddedChunk(
        content=content,
        section_heading="Overview",
        item_type=EnumContextItemType.DOC_EXCERPT,
        rule_version="v1",
        tags=("source:docs/CLAUDE.md",),
        content_fingerprint=content_fingerprint,
        version_hash=version_hash,
        character_offset_start=offset_start,
        character_offset_end=offset_end,
        token_estimate=len(content) // 4,
        has_code_fence=False,
        code_fence_language=None,
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        source_version="sha-abc123",
        correlation_id=correlation_id,
        embedding=_FAKE_EMBEDDING,
    )


def _make_input(
    chunks: list[ModelEmbeddedChunk],
    source_ref: str = "docs/CLAUDE.md",
    emit_event: bool = False,
    correlation_id: str | None = "test-corr-01",
) -> ModelContextItemWriteInput:
    return ModelContextItemWriteInput(
        embedded_chunks=tuple(chunks),
        source_ref=source_ref,
        crawl_scope="omninode/omniintelligence",
        emit_event=emit_event,
        correlation_id=correlation_id,
    )


def _make_context_store(
    lookup_result: tuple[UUID, str] | None = None,
    lookup_side_effect: Exception | None = None,
) -> ProtocolContextStore:
    """Create a mock ProtocolContextStore."""
    mock = MagicMock(spec=ProtocolContextStore)
    if lookup_side_effect is not None:
        mock.lookup_by_position = AsyncMock(side_effect=lookup_side_effect)
    else:
        mock.lookup_by_position = AsyncMock(return_value=lookup_result)
    mock.insert_item = AsyncMock()
    mock.update_item_fingerprint = AsyncMock()
    return mock


def _make_vector_store() -> ProtocolVectorStore:
    mock = MagicMock(spec=ProtocolVectorStore)
    mock.upsert_vector = AsyncMock()
    return mock


def _make_graph_store() -> ProtocolGraphStore:
    mock = MagicMock(spec=ProtocolGraphStore)
    mock.upsert_context_item_edge = AsyncMock()
    return mock


def _make_event_emitter(return_value: bool = True) -> ProtocolEventEmitter:
    mock = MagicMock(spec=ProtocolEventEmitter)
    mock.emit_document_indexed = AsyncMock(return_value=return_value)
    return mock


# ---------------------------------------------------------------------------
# Idempotency: CREATED case
# ---------------------------------------------------------------------------


class TestCreatedCase:
    """Fresh insert — no existing record."""

    @pytest.mark.asyncio
    async def test_single_chunk_created(self) -> None:
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_created == 1
        assert result.items_updated == 0
        assert result.items_skipped == 0
        assert result.items_failed == 0

    @pytest.mark.asyncio
    async def test_created_calls_insert_item(self) -> None:
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        ctx_store.insert_item.assert_called_once()  # type: ignore[attr-defined]
        vec_store.upsert_vector.assert_called_once()  # type: ignore[attr-defined]
        gph_store.upsert_context_item_edge.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_multiple_chunks_all_created(self) -> None:
        chunks = [
            _make_embedded_chunk(
                content=f"Chunk {i}.", offset_start=i * 20, offset_end=(i + 1) * 20
            )
            for i in range(5)
        ]
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input(chunks),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_created == 5
        assert result.total_chunks == 5


# ---------------------------------------------------------------------------
# Idempotency: SKIPPED case
# ---------------------------------------------------------------------------


class TestSkippedCase:
    """No-op — fingerprint unchanged."""

    @pytest.mark.asyncio
    async def test_chunk_skipped_same_fingerprint(self) -> None:
        chunk = _make_embedded_chunk(content_fingerprint="fp-same")
        existing_id = uuid4()
        # Same fingerprint → no-op
        ctx_store = _make_context_store(lookup_result=(existing_id, "fp-same"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_skipped == 1
        assert result.items_created == 0
        assert result.items_updated == 0

    @pytest.mark.asyncio
    async def test_skipped_does_not_call_insert_or_update(self) -> None:
        chunk = _make_embedded_chunk(content_fingerprint="fp-same")
        existing_id = uuid4()
        ctx_store = _make_context_store(lookup_result=(existing_id, "fp-same"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        ctx_store.insert_item.assert_not_called()  # type: ignore[attr-defined]
        ctx_store.update_item_fingerprint.assert_not_called()  # type: ignore[attr-defined]
        vec_store.upsert_vector.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Idempotency: UPDATED case
# ---------------------------------------------------------------------------


class TestUpdatedCase:
    """Soft update — same position, different fingerprint."""

    @pytest.mark.asyncio
    async def test_chunk_updated_different_fingerprint(self) -> None:
        chunk = _make_embedded_chunk(content_fingerprint="fp-new")
        existing_id = uuid4()
        # Different fingerprint → update
        ctx_store = _make_context_store(lookup_result=(existing_id, "fp-old"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_updated == 1
        assert result.items_created == 0
        assert result.items_skipped == 0

    @pytest.mark.asyncio
    async def test_updated_calls_update_not_insert(self) -> None:
        chunk = _make_embedded_chunk(content_fingerprint="fp-new")
        existing_id = uuid4()
        ctx_store = _make_context_store(lookup_result=(existing_id, "fp-old"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        ctx_store.update_item_fingerprint.assert_called_once()  # type: ignore[attr-defined]
        ctx_store.insert_item.assert_not_called()  # type: ignore[attr-defined]
        vec_store.upsert_vector.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_updated_uses_existing_id_for_qdrant(self) -> None:
        chunk = _make_embedded_chunk(content_fingerprint="fp-new")
        existing_id = uuid4()
        ctx_store = _make_context_store(lookup_result=(existing_id, "fp-old"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        call_kwargs = vec_store.upsert_vector.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["point_id"] == existing_id


# ---------------------------------------------------------------------------
# Mixed outcomes
# ---------------------------------------------------------------------------


class TestMixedOutcomes:
    """Multiple chunks with different outcomes."""

    @pytest.mark.asyncio
    async def test_mixed_created_updated_skipped(self) -> None:
        """3 chunks: 1 new, 1 updated, 1 skipped."""
        chunks = [
            _make_embedded_chunk(
                content="New chunk.",
                offset_start=0,
                offset_end=10,
                content_fingerprint="fp-new",
            ),
            _make_embedded_chunk(
                content="Updated chunk.",
                offset_start=10,
                offset_end=24,
                content_fingerprint="fp-new2",
            ),
            _make_embedded_chunk(
                content="Skipped chunk.",
                offset_start=24,
                offset_end=38,
                content_fingerprint="fp-same",
            ),
        ]

        existing_id_1 = uuid4()
        existing_id_2 = uuid4()

        lookup_results: list[tuple[UUID, str] | None] = [
            None,  # chunk 0 → CREATED
            (existing_id_1, "fp-old"),  # chunk 1 → UPDATED
            (existing_id_2, "fp-same"),  # chunk 2 → SKIPPED
        ]

        ctx_store = MagicMock(spec=ProtocolContextStore)
        ctx_store.lookup_by_position = AsyncMock(side_effect=lookup_results)
        ctx_store.insert_item = AsyncMock()
        ctx_store.update_item_fingerprint = AsyncMock()

        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input(chunks),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_created == 1
        assert result.items_updated == 1
        assert result.items_skipped == 1
        assert result.items_failed == 0
        assert result.total_chunks == 3


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero_counts(self) -> None:
        ctx_store = _make_context_store()
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_created == 0
        assert result.items_updated == 0
        assert result.items_skipped == 0
        assert result.items_failed == 0
        assert result.total_chunks == 0

    @pytest.mark.asyncio
    async def test_empty_chunks_does_not_call_stores(self) -> None:
        ctx_store = _make_context_store()
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        await handle_context_item_write(
            _make_input([]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        ctx_store.lookup_by_position.assert_not_called()  # type: ignore[attr-defined]
        vec_store.upsert_vector.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_store_error_counted_as_failed(self) -> None:
        """When lookup raises, chunk is counted as failed, not raised."""
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(
            lookup_side_effect=RuntimeError("DB connection lost")
        )
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_failed == 1
        assert result.items_created == 0

    @pytest.mark.asyncio
    async def test_partial_failure_other_chunks_succeed(self) -> None:
        """One chunk fails, two others succeed."""
        chunks = [
            _make_embedded_chunk(content="Good 1.", offset_start=0, offset_end=7),
            _make_embedded_chunk(content="Bad.", offset_start=7, offset_end=11),
            _make_embedded_chunk(content="Good 2.", offset_start=11, offset_end=18),
        ]

        ctx_store = MagicMock(spec=ProtocolContextStore)
        ctx_store.lookup_by_position = AsyncMock(
            side_effect=[
                None,  # Good 1 → CREATED
                RuntimeError("DB error"),  # Bad → FAILED
                None,  # Good 2 → CREATED
            ]
        )
        ctx_store.insert_item = AsyncMock()
        ctx_store.update_item_fingerprint = AsyncMock()

        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input(chunks),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_created == 2
        assert result.items_failed == 1

    @pytest.mark.asyncio
    async def test_all_chunks_fail(self) -> None:
        chunks = [
            _make_embedded_chunk(offset_start=i * 10, offset_end=(i + 1) * 10)
            for i in range(3)
        ]
        ctx_store = _make_context_store(lookup_side_effect=RuntimeError("DB down"))
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input(chunks),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.items_failed == 3
        assert result.items_created == 0
        assert result.total_chunks == 3


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    @pytest.mark.asyncio
    async def test_event_emitted_on_success(self) -> None:
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()
        emitter = _make_event_emitter(return_value=True)

        result = await handle_context_item_write(
            _make_input([chunk], emit_event=True),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
            event_emitter=emitter,
        )

        assert result.event_emitted is True
        emitter.emit_document_indexed.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_no_emitter_event_not_emitted(self) -> None:
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk], emit_event=True),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
            event_emitter=None,
        )

        assert result.event_emitted is False

    @pytest.mark.asyncio
    async def test_emit_disabled(self) -> None:
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()
        emitter = _make_event_emitter()

        result = await handle_context_item_write(
            _make_input([chunk], emit_event=False),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
            event_emitter=emitter,
        )

        assert result.event_emitted is False
        emitter.emit_document_indexed.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_emit_failure_non_blocking(self) -> None:
        """Event emission failure should not raise — event_emitted=False."""
        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        emitter = MagicMock(spec=ProtocolEventEmitter)
        emitter.emit_document_indexed = AsyncMock(
            side_effect=RuntimeError("Kafka down")
        )

        result = await handle_context_item_write(
            _make_input([chunk], emit_event=True),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
            event_emitter=emitter,
        )

        assert result.event_emitted is False
        assert result.items_created == 1  # Write succeeded despite event failure


# ---------------------------------------------------------------------------
# Bootstrap tier assignment
# ---------------------------------------------------------------------------


class TestBootstrapTierAssignment:
    def test_claude_md_gets_validated(self) -> None:
        policy = assign_bootstrap_tier("docs/CLAUDE.md")
        assert policy.tier == EnumBootstrapTier.VALIDATED
        assert policy.bootstrap_confidence == 0.85

    def test_home_claude_md_gets_validated(self) -> None:
        policy = assign_bootstrap_tier("/Users/jonah/.claude/CLAUDE.md")
        assert policy.tier == EnumBootstrapTier.VALIDATED

    def test_design_doc_gets_validated(self) -> None:
        policy = assign_bootstrap_tier("omni_save/design/DESIGN_OMNIMEMORY.md")
        assert policy.tier == EnumBootstrapTier.VALIDATED
        assert policy.bootstrap_confidence == 0.75

    def test_plans_doc_gets_quarantine(self) -> None:
        policy = assign_bootstrap_tier("omni_save/plans/SPRINT_PLAN.md")
        assert policy.tier == EnumBootstrapTier.QUARANTINE
        assert policy.bootstrap_confidence == 0.65

    def test_generic_md_gets_quarantine(self) -> None:
        policy = assign_bootstrap_tier("random/file.md")
        assert policy.tier == EnumBootstrapTier.QUARANTINE
        assert policy.bootstrap_confidence == 0.0

    def test_non_md_gets_quarantine(self) -> None:
        policy = assign_bootstrap_tier("src/some_module.py")
        assert policy.tier == EnumBootstrapTier.QUARANTINE

    def test_first_match_wins(self) -> None:
        """Custom policies: more specific pattern before generic."""
        custom_policies = (
            ModelTierPolicy(
                pattern="special/*.md",
                tier=EnumBootstrapTier.VALIDATED,
                bootstrap_confidence=0.9,
            ),
            ModelTierPolicy(
                pattern="*.md",
                tier=EnumBootstrapTier.QUARANTINE,
                bootstrap_confidence=0.0,
            ),
        )
        policy = assign_bootstrap_tier("special/doc.md", custom_policies)
        assert policy.tier == EnumBootstrapTier.VALIDATED
        assert policy.bootstrap_confidence == 0.9


# ---------------------------------------------------------------------------
# Correlation ID propagation
# ---------------------------------------------------------------------------


class TestCorrelationId:
    @pytest.mark.asyncio
    async def test_correlation_id_propagated_to_output(self) -> None:
        chunk = _make_embedded_chunk(correlation_id="corr-test")
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk], correlation_id="corr-test"),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.correlation_id == "corr-test"

    @pytest.mark.asyncio
    async def test_none_correlation_id_preserved(self) -> None:
        chunk = _make_embedded_chunk(correlation_id=None)
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk], correlation_id=None),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        assert result.correlation_id is None


# ---------------------------------------------------------------------------
# Output model immutability
# ---------------------------------------------------------------------------


class TestOutputImmutability:
    @pytest.mark.asyncio
    async def test_output_is_frozen(self) -> None:
        from pydantic import ValidationError

        chunk = _make_embedded_chunk()
        ctx_store = _make_context_store(lookup_result=None)
        vec_store = _make_vector_store()
        gph_store = _make_graph_store()

        result = await handle_context_item_write(
            _make_input([chunk]),
            context_store=ctx_store,
            vector_store=vec_store,
            graph_store=gph_store,
        )

        with pytest.raises(ValidationError):
            result.items_created = 999
