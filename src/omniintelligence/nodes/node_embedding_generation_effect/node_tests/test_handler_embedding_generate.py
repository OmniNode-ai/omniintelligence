# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_embedding_generate — EmbeddingGenerationEffect.

All tests use a mocked EmbeddingClient. No live embedding server required.

Test coverage:
    - Happy path: all chunks embedded successfully
    - Empty content: chunk skipped, counted in skipped_chunks
    - Batch failure: falls back to individual retry
    - Persistent individual failure: dead-lettered, counted in failed_chunks
    - Empty input: returns empty output
    - Ordering: embedded_chunks order matches input order
    - Correlation ID propagation
    - Embedding dimension: tuple length matches client return

Ticket: OMN-2392
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)
from omniintelligence.nodes.node_embedding_generation_effect.handlers.handler_embedding_generate import (
    handle_embedding_generate,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_generate_input import (
    ModelEmbeddingGenerateInput,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

_EMBEDDING_URL = "http://localhost:8100"
_FAKE_EMBEDDING = [0.1] * 1024  # 1024-dim fake embedding


def _make_classified_chunk(
    content: str = "Sample text for embedding.",
    section_heading: str | None = "Overview",
    content_fingerprint: str = "abc123",
    version_hash: str = "def456",
    source_ref: str = "docs/CLAUDE.md",
    crawl_scope: str = "omninode/omniintelligence",
    correlation_id: str | None = "test-corr-01",
) -> ModelClassifiedChunk:
    """Create a minimal classified chunk for testing."""
    return ModelClassifiedChunk(
        content=content,
        section_heading=section_heading,
        item_type=EnumContextItemType.DOC_EXCERPT,
        rule_version="v1",
        tags=("source:docs/CLAUDE.md", "doctype:general_markdown"),
        content_fingerprint=content_fingerprint,
        version_hash=version_hash,
        character_offset_start=0,
        character_offset_end=len(content),
        token_estimate=len(content) // 4,
        has_code_fence=False,
        code_fence_language=None,
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        source_version="sha-abc123",
        correlation_id=correlation_id,
    )


def _make_input(
    chunks: list[ModelClassifiedChunk],
    source_ref: str = "docs/CLAUDE.md",
    correlation_id: str | None = "test-corr-01",
) -> ModelEmbeddingGenerateInput:
    return ModelEmbeddingGenerateInput(
        classified_chunks=tuple(chunks),
        embedding_url=_EMBEDDING_URL,
        source_ref=source_ref,
        correlation_id=correlation_id,
    )


def _make_mock_client(
    batch_result: list[list[float]] | None = None,
    batch_side_effect: Exception | None = None,
    individual_side_effects: list[Exception | list[float]] | None = None,
) -> EmbeddingClient:
    """Create a mock EmbeddingClient with configurable behavior."""
    mock = MagicMock(spec=EmbeddingClient)
    mock.connect = AsyncMock()
    mock.close = AsyncMock()

    if batch_side_effect is not None:
        mock.get_embeddings_batch = AsyncMock(side_effect=batch_side_effect)
    elif batch_result is not None:
        mock.get_embeddings_batch = AsyncMock(return_value=batch_result)
    else:
        mock.get_embeddings_batch = AsyncMock(return_value=[_FAKE_EMBEDDING])

    if individual_side_effects is not None:
        mock.get_embedding = AsyncMock(side_effect=individual_side_effects)
    else:
        mock.get_embedding = AsyncMock(return_value=_FAKE_EMBEDDING)

    return mock


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    """All chunks embed successfully."""

    @pytest.mark.asyncio
    async def test_single_chunk_embedded(self) -> None:
        chunk = _make_classified_chunk()
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk]), client=mock_client
        )

        assert result.total_chunks == 1
        assert result.skipped_chunks == 0
        assert result.failed_chunks == 0
        assert len(result.embedded_chunks) == 1
        assert result.embedded_chunks[0].embedding == tuple(_FAKE_EMBEDDING)

    @pytest.mark.asyncio
    async def test_multiple_chunks_embedded(self) -> None:
        chunks = [_make_classified_chunk(content=f"Chunk {i}.") for i in range(5)]
        embeddings = [[float(i)] * 1024 for i in range(5)]
        mock_client = _make_mock_client(batch_result=embeddings)

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        assert result.total_chunks == 5
        assert result.skipped_chunks == 0
        assert result.failed_chunks == 0
        assert len(result.embedded_chunks) == 5

    @pytest.mark.asyncio
    async def test_embedding_dimension_preserved(self) -> None:
        chunk = _make_classified_chunk()
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk]), client=mock_client
        )

        assert len(result.embedded_chunks[0].embedding) == 1024

    @pytest.mark.asyncio
    async def test_chunk_fields_propagated(self) -> None:
        chunk = _make_classified_chunk(
            content="Hello world.",
            section_heading="Intro",
            content_fingerprint="fp-abc",
            version_hash="vh-def",
        )
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk]), client=mock_client
        )

        embedded = result.embedded_chunks[0]
        assert embedded.content == "Hello world."
        assert embedded.section_heading == "Intro"
        assert embedded.content_fingerprint == "fp-abc"
        assert embedded.version_hash == "vh-def"
        assert embedded.item_type == EnumContextItemType.DOC_EXCERPT

    @pytest.mark.asyncio
    async def test_ordering_preserved(self) -> None:
        chunks = [_make_classified_chunk(content=f"Chunk {i}.") for i in range(10)]
        embeddings = [[float(i)] * 1024 for i in range(10)]
        mock_client = _make_mock_client(batch_result=embeddings)

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        for i, embedded in enumerate(result.embedded_chunks):
            assert embedded.content == f"Chunk {i}."
            assert embedded.embedding[0] == float(i)

    @pytest.mark.asyncio
    async def test_source_ref_propagated(self) -> None:
        chunk = _make_classified_chunk(source_ref="custom/path.md")
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk], source_ref="custom/path.md"), client=mock_client
        )

        assert result.source_ref == "custom/path.md"

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self) -> None:
        chunk = _make_classified_chunk(correlation_id="corr-xyz")
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk], correlation_id="corr-xyz"), client=mock_client
        )

        assert result.correlation_id == "corr-xyz"
        assert result.embedded_chunks[0].correlation_id == "corr-xyz"


# ---------------------------------------------------------------------------
# Empty input tests
# ---------------------------------------------------------------------------


class TestEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_output(self) -> None:
        mock_client = _make_mock_client()

        result = await handle_embedding_generate(_make_input([]), client=mock_client)

        assert result.total_chunks == 0
        assert result.embedded_chunks == ()
        assert result.skipped_chunks == 0
        assert result.failed_chunks == 0

    @pytest.mark.asyncio
    async def test_empty_chunks_does_not_call_client(self) -> None:
        mock_client = _make_mock_client()

        await handle_embedding_generate(_make_input([]), client=mock_client)

        mock_client.get_embeddings_batch.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Skip tests (empty content)
# ---------------------------------------------------------------------------


class TestEmptyContentSkip:
    @pytest.mark.asyncio
    async def test_empty_content_skipped(self) -> None:
        empty_chunk = _make_classified_chunk(content="")
        mock_client = _make_mock_client(batch_result=[])

        result = await handle_embedding_generate(
            _make_input([empty_chunk]), client=mock_client
        )

        assert result.skipped_chunks == 1
        assert result.total_chunks == 0
        assert result.embedded_chunks == ()

    @pytest.mark.asyncio
    async def test_whitespace_only_content_skipped(self) -> None:
        whitespace_chunk = _make_classified_chunk(content="   \n\t  ")
        mock_client = _make_mock_client(batch_result=[])

        result = await handle_embedding_generate(
            _make_input([whitespace_chunk]), client=mock_client
        )

        assert result.skipped_chunks == 1

    @pytest.mark.asyncio
    async def test_mixed_empty_and_valid_chunks(self) -> None:
        chunks = [
            _make_classified_chunk(
                content="Valid chunk one.", content_fingerprint="fp1"
            ),
            _make_classified_chunk(content="", content_fingerprint="fp2"),
            _make_classified_chunk(
                content="Valid chunk two.", content_fingerprint="fp3"
            ),
        ]
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING, _FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        assert result.total_chunks == 2
        assert result.skipped_chunks == 1
        assert result.failed_chunks == 0


# ---------------------------------------------------------------------------
# Fallback to individual retry on batch failure
# ---------------------------------------------------------------------------


class TestBatchFallback:
    @pytest.mark.asyncio
    async def test_batch_failure_retries_individually(self) -> None:
        chunks = [
            _make_classified_chunk(content="Chunk A.", content_fingerprint="fp-a"),
            _make_classified_chunk(content="Chunk B.", content_fingerprint="fp-b"),
        ]
        mock_client = _make_mock_client(
            batch_side_effect=EmbeddingClientError("batch failed"),
            individual_side_effects=[_FAKE_EMBEDDING, _FAKE_EMBEDDING],
        )

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        assert result.total_chunks == 2
        assert result.failed_chunks == 0
        assert mock_client.get_embedding.call_count == 2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_batch_failure_partial_individual_success(self) -> None:
        """One chunk succeeds individually, one fails — failed one is dead-lettered."""
        chunks = [
            _make_classified_chunk(
                content="Good chunk.", content_fingerprint="fp-good"
            ),
            _make_classified_chunk(content="Bad chunk.", content_fingerprint="fp-bad"),
        ]
        mock_client = _make_mock_client(
            batch_side_effect=EmbeddingClientError("batch failed"),
            individual_side_effects=[
                _FAKE_EMBEDDING,  # Good chunk succeeds
                EmbeddingClientError("individual failed"),  # Bad chunk fails
            ],
        )

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        assert result.total_chunks == 1
        assert result.failed_chunks == 1
        assert len(result.embedded_chunks) == 1
        assert result.embedded_chunks[0].content_fingerprint == "fp-good"

    @pytest.mark.asyncio
    async def test_all_individual_retries_fail(self) -> None:
        chunks = [
            _make_classified_chunk(content=f"Chunk {i}.", content_fingerprint=f"fp-{i}")
            for i in range(3)
        ]
        mock_client = _make_mock_client(
            batch_side_effect=EmbeddingClientError("batch failed"),
            individual_side_effects=[
                EmbeddingClientError("fail 1"),
                EmbeddingClientError("fail 2"),
                EmbeddingClientError("fail 3"),
            ],
        )

        result = await handle_embedding_generate(
            _make_input(chunks), client=mock_client
        )

        assert result.total_chunks == 0
        assert result.failed_chunks == 3
        assert result.embedded_chunks == ()


# ---------------------------------------------------------------------------
# Embedding is stored as tuple (immutable)
# ---------------------------------------------------------------------------


class TestEmbeddingImmutability:
    @pytest.mark.asyncio
    async def test_embedding_stored_as_tuple(self) -> None:
        chunk = _make_classified_chunk()
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk]), client=mock_client
        )

        assert isinstance(result.embedded_chunks[0].embedding, tuple)
        assert len(result.embedded_chunks[0].embedding) == 1024

    @pytest.mark.asyncio
    async def test_output_model_is_frozen(self) -> None:
        from pydantic import ValidationError

        chunk = _make_classified_chunk()
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        result = await handle_embedding_generate(
            _make_input([chunk]), client=mock_client
        )

        with pytest.raises(ValidationError):
            result.total_chunks = 999


# ---------------------------------------------------------------------------
# Client lifecycle tests
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_injected_client_not_managed_by_handler(self) -> None:
        """When client is injected, handler must NOT call connect/close."""
        chunk = _make_classified_chunk()
        mock_client = _make_mock_client(batch_result=[_FAKE_EMBEDDING])

        await handle_embedding_generate(_make_input([chunk]), client=mock_client)

        mock_client.connect.assert_not_called()  # type: ignore[attr-defined]
        mock_client.close.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_owned_client_connect_close_called(self) -> None:
        """When no client is injected, handler creates and manages its own client."""
        chunk = _make_classified_chunk()

        with patch(
            "omniintelligence.nodes.node_embedding_generation_effect."
            "handlers.handler_embedding_generate.EmbeddingClient"
        ) as MockClientClass:
            mock_instance = _make_mock_client(batch_result=[_FAKE_EMBEDDING])
            MockClientClass.return_value = mock_instance

            await handle_embedding_generate(_make_input([chunk]))

            mock_instance.connect.assert_called_once()  # type: ignore[attr-defined]
            mock_instance.close.assert_called_once()  # type: ignore[attr-defined]
