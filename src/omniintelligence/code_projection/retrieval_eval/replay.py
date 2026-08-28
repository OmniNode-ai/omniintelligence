# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Corpus-parameterized replay states for the OMN-16522 retrieval eval harness.

The reducer proves what a *batch* does to projection state.  This module builds
the retrieval-layer equivalent: apply an ordered lane of batches into a real
in-memory index, then ask what a search actually returns at that state.

Everything here is offline by construction -- an in-memory Qdrant, a
deterministic hash-derived embedding client, and content resolved from the
frozen sanitized artifacts.  No network, no live services, no model calls.

Nothing in this module is fixture-specific: it is handed a corpus and a lane
and works over whatever it is given, so a larger published corpus drops in
without a rewrite.
"""

from __future__ import annotations

import hashlib
import warnings
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from omniintelligence.code_projection.codec import (
    parse_code_projection_batch,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionDocument,
    ModelTombstoneReason,
)
from omniintelligence.code_projection.qdrant import (
    CodeProjectionQdrantStore,
    ModelCodeProjectionCurrentGeneration,
    ModelCodeProjectionQdrantConfig,
    ModelCodeProjectionSearchHit,
)

#: Repository-relative location of the frozen OMN-16061 v2 replay vectors.
#: Resolved from this file rather than an absolute path so the harness works in
#: a worktree, a clone, or CI without configuration.
DEFAULT_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[4] / "tests/fixtures/code_projection/v2"
)

#: Embedding dimension pinned by the shared projection collection contract.
_EMBEDDING_DIMENSION = 1024

#: Identity of the harness embedding function.  This is deliberately not a real
#: model: it is a deterministic hash projection so two runs agree byte for byte.
#: It is recorded in the scorecard's embedding-compatibility key as such.
HARNESS_EMBEDDING_MODEL = "omn16522-deterministic-hash-projection"
HARNESS_EMBEDDING_MODEL_VERSION = "1"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


class ModelReplayLane(_FrozenModel):
    """One ordered application of batches, producing a single replay state."""

    lane_id: str
    batch_names: tuple[str, ...] = Field(min_length=1)
    description: str


#: The lanes the replay gate asserts against.
#:
#: ``policy_tombstone`` deliberately skips ``source_tombstone_seq4``.  Both
#: tombstones sit on the same greeter partition at sequences 4 and 5, so a naive
#: monotone 1->2->3->4->5 replay leaves the partition already empty when seq5
#: lands -- the policy scenario would then assert nothing beyond the source one
#: and the honest scenario count would be five, not six.  Planning seq5 against
#: the same prior state as seq4 is what makes it independently gating.
REPLAY_LANES: Mapping[str, ModelReplayLane] = {
    "a_to_b_to_a": ModelReplayLane(
        lane_id="a_to_b_to_a",
        batch_names=(
            "typescript_seq1.json",
            "python_a_seq1.json",
            "python_b_seq2.json",
            "python_a_seq3.json",
        ),
        description="Greeter reverts to revision A while the widget is untouched.",
    ),
    "a_to_b": ModelReplayLane(
        lane_id="a_to_b",
        batch_names=(
            "typescript_seq1.json",
            "python_a_seq1.json",
            "python_b_seq2.json",
        ),
        description="The state R1 must NOT return: greeter still at revision B.",
    ),
    "source_tombstone": ModelReplayLane(
        lane_id="source_tombstone",
        batch_names=(
            "typescript_seq1.json",
            "python_a_seq1.json",
            "python_b_seq2.json",
            "python_a_seq3.json",
            "source_tombstone_seq4.json",
        ),
        description="Greeter partition is deleted at sequence 4.",
    ),
    "policy_tombstone": ModelReplayLane(
        lane_id="policy_tombstone",
        batch_names=(
            "typescript_seq1.json",
            "python_a_seq1.json",
            "python_b_seq2.json",
            "python_a_seq3.json",
            "policy_tombstone_seq5.json",
        ),
        description="Greeter policy is revoked at sequence 5, seq4 skipped.",
    ),
    "empty_snapshot": ModelReplayLane(
        lane_id="empty_snapshot",
        batch_names=("empty_python_seq1.json",),
        description="A zero-document snapshot is a state, not a deletion.",
    ),
    "external_symbol": ModelReplayLane(
        lane_id="external_symbol",
        batch_names=("python_a_seq1.json",),
        description="builtins.str is a graph node with no retrievable document.",
    ),
    "typescript_snapshot": ModelReplayLane(
        lane_id="typescript_snapshot",
        batch_names=("typescript_seq1.json",),
        description="The widget partition alone, for language/partition scoping.",
    ),
}


class ModelReplayCorpus(_FrozenModel):
    """A loaded fixture corpus: its batches, and the artifacts they reference."""

    fixture_root: Path
    batches: Mapping[str, ModelCodeProjectionBatch]
    artifacts: Mapping[str, bytes]

    def sole_document(self, batch_name: str) -> ModelCodeProjectionDocument:
        """Return the one semantic document carried by ``batch_name``."""

        documents = self.batches[batch_name].semantic_documents
        if len(documents) != 1:
            message = (
                f"{batch_name} carries {len(documents)} semantic documents, "
                "expected exactly one"
            )
            raise ValueError(message)
        return documents[0]

    def distinct_chunk_keys(self) -> frozenset[str]:
        """Return every chunk key appearing anywhere in the corpus."""

        return frozenset(
            document.chunk_key
            for batch in self.batches.values()
            for document in batch.semantic_documents
        )


class IndexedMemoryQdrant(AsyncQdrantClient):
    """Local-mode Qdrant that still reports payload-index receipts.

    Local Qdrant accepts ``create_payload_index`` but silently drops it, so the
    store's own index verification fails closed against an in-memory instance.
    Recording the created indexes and replaying them on ``get_collection``
    keeps the real verification path exercised while staying entirely offline.
    """

    def __init__(self) -> None:
        super().__init__(location=":memory:")
        self._created_indexes: dict[str, qmodels.KeywordIndexParams] = {}

    async def create_payload_index(  # type: ignore[override]
        self,
        collection_name: str,
        field_name: str,
        field_schema: qmodels.KeywordIndexParams | None = None,
        **kwargs: Any,
    ) -> qmodels.UpdateResult:
        """Record the index schema, then delegate to local Qdrant."""

        if field_schema is None:
            message = "projection indexes require an explicit schema"
            raise ValueError(message)
        self._created_indexes[field_name] = field_schema
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return await super().create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
                **kwargs,
            )

    async def get_collection(
        self,
        collection_name: str,
        **kwargs: Any,
    ) -> qmodels.CollectionInfo:
        """Return collection info carrying the recorded payload indexes."""

        info = await super().get_collection(collection_name, **kwargs)
        indexes = {
            name: qmodels.PayloadIndexInfo(
                data_type=qmodels.PayloadSchemaType.KEYWORD,
                params=params,
                points=0,
            )
            for name, params in self._created_indexes.items()
        }
        return info.model_copy(update={"payload_schema": indexes})


class DeterministicEmbedder:
    """Offline stand-in embedding function: a stable hash projection.

    Deterministic by construction, so two harness runs produce byte-identical
    output.  It carries no semantic signal, which is exactly why the ranking
    metrics computed on top of it are reported as degenerate rather than gated.
    """

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one stable pseudo-embedding per input, preserving order."""

        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append(
                [
                    float(digest[index % len(digest)] + 1)
                    for index in range(_EMBEDDING_DIMENSION)
                ]
            )
        return vectors


class ReplayGenerationResolver:
    """Current-generation pointer driven by what a lane has actually applied.

    The store drops any hit whose source generation does not match the promoted
    pointer.  Recording the pointer as each batch lands is what makes R1/R2/R3
    assertable at the retrieval layer instead of only at the reducer.
    """

    def __init__(self) -> None:
        self._generations: dict[
            tuple[str, str], ModelCodeProjectionCurrentGeneration
        ] = {}
        self._tombstone_reasons: dict[tuple[str, str], ModelTombstoneReason] = {}

    def tombstone_reason(
        self, tenant_id: str, source_id: str
    ) -> ModelTombstoneReason | None:
        """Return why the source was tombstoned, or ``None`` if it is live.

        Tracked by this harness rather than read back from the index.
        ``ModelCodeProjectionCurrentGeneration`` carries ``operation`` but no
        reason, so ``policy_revoked`` and ``source_deleted`` are
        indistinguishable at the retrieval layer today.  R3 therefore earns its
        independence from its own replay lane, not from reason propagation.
        """

        return self._tombstone_reasons.get((tenant_id, source_id))

    def promote(self, batch: ModelCodeProjectionBatch) -> None:
        """Record ``batch`` as the current generation for its source."""

        key = (batch.source.tenant_id, batch.source.source_id)
        if batch.tombstone_reason is None:
            self._tombstone_reasons.pop(key, None)
        else:
            self._tombstone_reasons[key] = batch.tombstone_reason
        self._generations[key] = ModelCodeProjectionCurrentGeneration(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            batch_id=batch.batch_id,
            operation=batch.operation,
            batch_content_hash_sha256=hashlib.sha256(
                serialize_code_projection_batch(batch)
            ).hexdigest(),
            document_ids=tuple(
                document.document_id for document in batch.semantic_documents
            ),
        )

    def __call__(
        self,
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        """Return the promoted generation, or ``None`` when none is applied."""

        return self._generations.get((tenant_id, source_id))


class ReplayState:
    """A materialized replay state, ready to be searched."""

    def __init__(
        self,
        *,
        store: CodeProjectionQdrantStore,
        resolver: ReplayGenerationResolver,
        tenant_id: str,
        repository_id: str,
    ) -> None:
        self._store = store
        self._resolver = resolver
        self._tenant_id = tenant_id
        self._repository_id = repository_id

    @property
    def tenant_id(self) -> str:
        """Return the tenant every query in this state is scoped to."""

        return self._tenant_id

    @property
    def repository_id(self) -> str:
        """Return the repository every query in this state is scoped to."""

        return self._repository_id

    def current_generation(
        self, source_id: str
    ) -> ModelCodeProjectionCurrentGeneration | None:
        """Return the promoted generation for ``source_id`` at this state."""

        return self._resolver(self._tenant_id, source_id)

    def current_tombstone_reason(self, source_id: str) -> ModelTombstoneReason | None:
        """Return why ``source_id`` was tombstoned at this state, if it was."""

        return self._resolver.tombstone_reason(self._tenant_id, source_id)

    async def search(
        self,
        query_text: str,
        *,
        limit: int = 10,
        repository_id: str | None = None,
    ) -> tuple[ModelCodeProjectionSearchHit, ...]:
        """Run a tenant-scoped search against this replay state."""

        return await self._store.search(
            query_text=query_text,
            tenant_id=self._tenant_id,
            repository_id=(
                self._repository_id if repository_id is None else repository_id
            ),
            limit=limit,
        )


def load_replay_corpus(fixture_root: Path | None = None) -> ModelReplayCorpus:
    """Load every batch and sanitized artifact under ``fixture_root``."""

    root = DEFAULT_FIXTURE_ROOT if fixture_root is None else fixture_root
    batches = {
        path.name: parse_code_projection_batch(path.read_bytes())
        for path in sorted((root / "batches").glob("*.json"))
    }
    artifacts: dict[str, bytes] = {}
    for path in sorted((root / "sanitized").iterdir()):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        artifacts[f"artifact://sha256/{hashlib.sha256(payload).hexdigest()}"] = payload
    return ModelReplayCorpus(
        fixture_root=root,
        batches=batches,
        artifacts=artifacts,
    )


def _identity(batches: Sequence[ModelCodeProjectionBatch]) -> tuple[str, str]:
    tenants = {batch.source.tenant_id for batch in batches}
    repositories = {batch.source.repository_id for batch in batches}
    if len(tenants) != 1 or len(repositories) != 1:
        message = "a replay lane must stay inside one tenant and one repository"
        raise ValueError(message)
    return (tenants.pop(), repositories.pop())


@asynccontextmanager
async def open_replay_state(
    corpus: ModelReplayCorpus,
    lane: ModelReplayLane,
) -> AsyncIterator[ReplayState]:
    """Apply ``lane`` into a fresh in-memory index and yield the searchable state."""

    batches = [corpus.batches[name] for name in lane.batch_names]
    tenant_id, repository_id = _identity(batches)
    resolver = ReplayGenerationResolver()

    def resolve_content(content_ref: str) -> bytes:
        try:
            return corpus.artifacts[content_ref]
        except KeyError as exc:
            raise FileNotFoundError(content_ref) from exc

    client = IndexedMemoryQdrant()
    try:
        store = CodeProjectionQdrantStore(
            client=client,
            embedding_client=DeterministicEmbedder(),
            content_resolver=resolve_content,
            current_generation_resolver=resolver,
            config=ModelCodeProjectionQdrantConfig(
                collection_name=f"omn16522_{lane.lane_id}",
                vector_name="code_semantic_v2",
                embedding_model=HARNESS_EMBEDDING_MODEL,
                embedding_model_version=HARNESS_EMBEDDING_MODEL_VERSION,
            ),
        )
        await store.ensure_collection()
        for batch in batches:
            await store.apply(batch)
            resolver.promote(batch)
        yield ReplayState(
            store=store,
            resolver=resolver,
            tenant_id=tenant_id,
            repository_id=repository_id,
        )
    finally:
        await client.close()


__all__ = [
    "DEFAULT_FIXTURE_ROOT",
    "HARNESS_EMBEDDING_MODEL",
    "HARNESS_EMBEDDING_MODEL_VERSION",
    "REPLAY_LANES",
    "DeterministicEmbedder",
    "IndexedMemoryQdrant",
    "ModelReplayCorpus",
    "ModelReplayLane",
    "ReplayGenerationResolver",
    "ReplayState",
    "load_replay_corpus",
    "open_replay_state",
]
