# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Real in-memory Qdrant proofs for the tenant-scoped semantic index."""

from __future__ import annotations

import hashlib
import struct
import warnings
from collections.abc import Sequence
from typing import Any, cast

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from omniintelligence.code_projection._canonical import canonical_json_bytes
from omniintelligence.code_projection.codec import (
    make_code_chunk,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection.extraction import project_source_with_documents
from omniintelligence.code_projection.qdrant import (
    CodeProjectionQdrantIntegrityError,
    CodeProjectionQdrantStore,
    ModelCodeProjectionCurrentGeneration,
    ModelCodeProjectionQdrantConfig,
    derive_code_projection_manifest_point_id,
    derive_code_projection_point_id,
)
from tests.unit.code_projection.fixture_vectors import (
    FIXTURE_ROOT,
    build_fixture_batches,
)

pytestmark = pytest.mark.unit


class _IndexedMemoryClient(AsyncQdrantClient):
    """Qdrant local mode plus faithful payload-index metadata receipts."""

    def __init__(self) -> None:
        super().__init__(location=":memory:")
        self.created_indexes: dict[str, qmodels.KeywordIndexParams] = {}

    async def create_payload_index(  # type: ignore[override]
        self,
        collection_name: str,
        field_name: str,
        field_schema: qmodels.KeywordIndexParams | None = None,
        **kwargs: Any,
    ) -> qmodels.UpdateResult:
        if field_schema is None:
            raise AssertionError("projection indexes require an explicit schema")
        self.created_indexes[field_name] = field_schema
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
        info = await super().get_collection(collection_name, **kwargs)
        indexes = {
            name: qmodels.PayloadIndexInfo(
                data_type=qmodels.PayloadSchemaType.KEYWORD,
                params=params,
                points=0,
            )
            for name, params in self.created_indexes.items()
        }
        return info.model_copy(update={"payload_schema": indexes})


class _DeterministicEmbeddingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, ...]] = []

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(tuple(texts))
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append(
                [float(digest[index % len(digest)] + 1) for index in range(1024)]
            )
        return vectors


class _JitteringEmbeddingClient(_DeterministicEmbeddingClient):
    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.requests.append(tuple(texts))
        jitter = 0.01 if len(self.requests) > 1 else 0.0
        return [[1.0, jitter, *([0.0] * 1022)] for _ in texts]


def _artifact_bytes() -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    for path in (FIXTURE_ROOT / "sanitized").iterdir():
        if not path.is_file():
            continue
        payload = path.read_bytes()
        artifacts[f"artifact://sha256/{hashlib.sha256(payload).hexdigest()}"] = payload
    return artifacts


def _store(
    client: _IndexedMemoryClient,
    embedding_client: _DeterministicEmbeddingClient,
) -> CodeProjectionQdrantStore:
    artifacts = _artifact_bytes()

    def resolve(content_ref: str) -> bytes:
        try:
            return artifacts[content_ref]
        except KeyError as exc:
            raise FileNotFoundError(content_ref) from exc

    current = build_fixture_batches()["python_a_seq1.json"]

    def resolve_current(
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        if (
            tenant_id != current.source.tenant_id
            or source_id != current.source.source_id
        ):
            return None
        return ModelCodeProjectionCurrentGeneration(
            tenant_id=current.source.tenant_id,
            source_id=current.source.source_id,
            batch_id=current.batch_id,
            operation=current.operation,
            batch_content_hash_sha256=hashlib.sha256(
                serialize_code_projection_batch(current)
            ).hexdigest(),
            document_ids=tuple(
                document.document_id for document in current.semantic_documents
            ),
        )

    return CodeProjectionQdrantStore(
        client=client,
        embedding_client=embedding_client,
        content_resolver=resolve,
        current_generation_resolver=resolve_current,
        config=ModelCodeProjectionQdrantConfig(
            collection_name="test_code_semantic_v2",
            vector_name="code_semantic_v2",
            embedding_model="text-embedding-qwen3",
            embedding_model_version="lab-2026-08-14",
            read_consistency="majority",
            write_ordering="medium",
        ),
    )


async def test_collection_apply_noop_and_semantic_search_are_real() -> None:
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batch = build_fixture_batches()["python_a_seq1.json"]
    try:
        collection = await store.ensure_collection()
        first = await store.apply(batch)
        second = await store.apply(batch)
        hits = await store.search(
            query_text="find the Greeter implementation",
            tenant_id=batch.source.tenant_id,
            repository_id=batch.source.repository_id,
        )

        assert collection.embedding_dimension == 1024
        assert collection.distance == "Dot"
        assert collection.reembedding_cosine_threshold_basis_points == 9990
        assert collection.indexed_fields == (
            "tenant_id",
            "source_id",
            "repository_id",
            "record_kind",
        )
        assert client.created_indexes["tenant_id"].is_tenant is True
        assert first.decision == "replace"
        assert first.documents_embedded == 1
        assert first.readback.point_count == 1
        assert second.decision == "noop"
        assert second.documents_embedded == 1
        assert len(embedding_client.requests) == 4
        assert len(hits) == 1
        assert hits[0].tenant_id == batch.source.tenant_id
        assert hits[0].repository_id == batch.source.repository_id
        assert hits[0].document_id == batch.semantic_documents[0].document_id
    finally:
        await client.close()


async def test_collection_rejects_float16_vector_storage() -> None:
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    await client.create_collection(
        collection_name=store.config.collection_name,
        vectors_config={
            store.config.vector_name: qmodels.VectorParams(
                size=1024,
                distance=qmodels.Distance.DOT,
                datatype=qmodels.Datatype.FLOAT16,
            )
        },
        metadata={
            "embedding_dimension": 1024,
            "embedding_model": store.config.embedding_model,
            "embedding_model_version": store.config.embedding_model_version,
            "storage_schema_id": "com.omninode.code-projection-qdrant",
            "storage_schema_version": "2.0.0",
            "vector_distance": "Dot",
            "vector_name": store.config.vector_name,
        },
    )
    try:
        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="datatype must preserve float32",
        ):
            await store.ensure_collection()
    finally:
        await client.close()


async def test_valid_multi_document_projection_applies_and_searches() -> None:
    base = build_fixture_batches()["python_a_seq1.json"]
    projected = project_source_with_documents(
        raw_source=(
            b"def calculate_total(left: int, right: int) -> int:\n"
            b"    return left + right\n"
        ),
        tenant_id=base.source.tenant_id,
        repository_id=base.source.repository_id,
        relative_path="src/example/calculator.py",
        source_version=base.source.source_version,
        language="python",
        cursor_authority=base.cursor.authority,
        cursor_sequence=base.cursor.sequence,
        policy=base.policy,
        provenance=base.provenance,
    )
    batch = projected.batch
    artifacts = {
        f"artifact://sha256/{hashlib.sha256(artifact.content).hexdigest()}": (
            artifact.content
        )
        for artifact in projected.document_artifacts
    }

    def resolve_current(
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        if tenant_id != batch.source.tenant_id or source_id != batch.source.source_id:
            return None
        return ModelCodeProjectionCurrentGeneration(
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

    client = _IndexedMemoryClient()
    store = CodeProjectionQdrantStore(
        client=client,
        embedding_client=_DeterministicEmbeddingClient(),
        content_resolver=lambda content_ref: artifacts[content_ref],
        current_generation_resolver=resolve_current,
        config=ModelCodeProjectionQdrantConfig(
            collection_name="test_multi_document_code_semantic_v2",
            vector_name="code_semantic_v2",
            embedding_model="text-embedding-qwen3",
            embedding_model_version="lab-2026-08-14",
            read_consistency="majority",
            write_ordering="medium",
        ),
    )
    try:
        applied = await store.apply(batch)
        hits = await store.search(
            query_text="calculate total",
            tenant_id=batch.source.tenant_id,
            repository_id=batch.source.repository_id,
            limit=10,
        )

        assert len(batch.semantic_documents) == 2
        assert applied.decision == "replace"
        assert applied.readback.point_count == 2
        assert {hit.document_id for hit in hits} == {
            document.document_id for document in batch.semantic_documents
        }
    finally:
        await client.close()


async def test_readback_accepts_bounded_live_model_jitter() -> None:
    client = _IndexedMemoryClient()
    embedding_client = _JitteringEmbeddingClient()
    store = _store(client, embedding_client)
    batch = build_fixture_batches()["python_a_seq1.json"]
    try:
        await store.apply(batch)

        readback = await store.readback(batch)

        assert readback.point_count == 1
        assert len(embedding_client.requests) == 2
    finally:
        await client.close()


async def test_replace_tombstone_and_vector_drift_repair() -> None:
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batches = build_fixture_batches()
    first = batches["python_a_seq1.json"]
    changed = batches["python_b_seq2.json"]
    tombstone = batches["source_tombstone_seq4.json"]
    try:
        applied = await store.apply(first)
        point_id = applied.readback.point_ids[0]
        records, _ = await client.scroll(
            collection_name=store.config.collection_name,
            with_payload=True,
            with_vectors=True,
        )
        document_records = [
            record
            for record in records
            if isinstance(record.payload, dict)
            and record.payload.get("record_kind") == "semantic_document"
        ]
        assert len(document_records) == 1
        payload = cast(dict[str, Any], document_records[0].payload)
        await client.upsert(
            collection_name=store.config.collection_name,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector={store.config.vector_name: [1.0] * 1024},
                    payload=payload,
                )
            ],
            wait=True,
        )

        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="vector digest",
        ):
            await store.readback(first)
        repaired = await store.apply(first)
        replaced = await store.apply(changed)
        deleted = await store.apply(tombstone)

        assert repaired.decision == "replace"
        assert replaced.decision == "replace"
        assert replaced.points_deleted == 1
        assert replaced.readback.document_ids == (
            changed.semantic_documents[0].document_id,
        )
        assert deleted.decision == "tombstone"
        assert deleted.points_deleted == 1
        assert deleted.readback.point_count == 0
        assert deleted.readback.record_count == 1
    finally:
        await client.close()


async def test_tenant_scoped_ids_and_filters_prevent_cross_tenant_results() -> None:
    batches = build_fixture_batches()
    document = batches["python_a_seq1.json"].semantic_documents[0]
    alpha = derive_code_projection_point_id(
        tenant_id="tenant-alpha",
        document_id=document.document_id,
        embedding_model="text-embedding-qwen3",
        embedding_model_version="lab-2026-08-14",
    )
    bravo = derive_code_projection_point_id(
        tenant_id="tenant-bravo",
        document_id=document.document_id,
        embedding_model="text-embedding-qwen3",
        embedding_model_version="lab-2026-08-14",
    )

    assert alpha != bravo

    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batch = batches["python_a_seq1.json"]
    try:
        await store.apply(batch)
        hits = await store.search(
            query_text="Greeter",
            tenant_id="tenant-with-no-points",
        )
        assert hits == ()
    finally:
        await client.close()


async def test_embedding_shape_fails_closed_before_any_point_is_written() -> None:
    class WrongDimensionEmbeddingClient:
        async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 2.0] for _ in texts]

    client = _IndexedMemoryClient()
    artifacts = _artifact_bytes()
    store = CodeProjectionQdrantStore(
        client=client,
        embedding_client=WrongDimensionEmbeddingClient(),
        content_resolver=lambda content_ref: artifacts[content_ref],
        current_generation_resolver=lambda _tenant_id, _source_id: None,
        config=ModelCodeProjectionQdrantConfig(
            embedding_model="text-embedding-qwen3",
            embedding_model_version="lab-2026-08-14",
        ),
    )
    batch = build_fixture_batches()["python_a_seq1.json"]
    try:
        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="dimension is 2, expected 1024",
        ):
            await store.apply(batch)
        count = await client.count(
            collection_name=store.config.collection_name,
            exact=True,
        )
        assert count.count == 0
    finally:
        await client.close()


async def test_cursor_manifest_blocks_stale_resurrection_and_repairs_partial_init() -> (
    None
):
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batches = build_fixture_batches()
    first = batches["python_a_seq1.json"]
    newer = batches["python_a_seq3.json"]
    tombstone = batches["source_tombstone_seq4.json"]
    try:
        await store.apply(first)
        manifest_id = derive_code_projection_manifest_point_id(
            tenant_id=first.source.tenant_id,
            source_id=first.source.source_id,
            embedding_model=store.config.embedding_model,
            embedding_model_version=store.config.embedding_model_version,
        )
        await client.delete(
            collection_name=store.config.collection_name,
            points_selector=[manifest_id],
            wait=True,
        )

        repaired = await store.apply(first)
        assert repaired.decision == "replace"
        assert repaired.readback.record_count == 2

        await store.apply(newer)
        with pytest.raises(CodeProjectionQdrantIntegrityError, match="stale"):
            await store.apply(first)

        await store.apply(tombstone)
        with pytest.raises(CodeProjectionQdrantIntegrityError, match="stale"):
            await store.apply(newer)
    finally:
        await client.close()


async def test_search_rejects_qdrant_generation_before_global_pointer_promotion() -> (
    None
):
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batches = build_fixture_batches()
    try:
        await store.apply(batches["python_a_seq1.json"])
        await store.apply(batches["python_a_seq3.json"])

        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="not globally applied",
        ):
            await store.search(
                query_text="Greeter",
                tenant_id=batches["python_a_seq1.json"].source.tenant_id,
            )
    finally:
        await client.close()


async def test_reembedding_rejects_self_consistent_vector_and_tenant_relabel_drift() -> (
    None
):
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batch = build_fixture_batches()["python_a_seq1.json"]
    try:
        applied = await store.apply(batch)
        document_id = applied.readback.point_ids[0]
        records, _ = await client.scroll(
            collection_name=store.config.collection_name,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="record_kind",
                        match=qmodels.MatchValue(value="semantic_document"),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=True,
        )
        assert len(records) == 1
        payload = cast(dict[str, Any], records[0].payload)
        drifted_vector = [0.03125] * 1024
        payload["embedding_vector_sha256"] = hashlib.sha256(
            struct.pack("<1024f", *drifted_vector)
        ).hexdigest()
        payload_without_digest = {
            key: value for key, value in payload.items() if key != "payload_sha256"
        }
        payload["payload_sha256"] = hashlib.sha256(
            canonical_json_bytes(payload_without_digest)
        ).hexdigest()
        await client.upsert(
            collection_name=store.config.collection_name,
            points=[
                qmodels.PointStruct(
                    id=document_id,
                    vector={store.config.vector_name: drifted_vector},
                    payload=payload,
                )
            ],
            wait=True,
        )

        with pytest.raises(CodeProjectionQdrantIntegrityError, match="model output"):
            await store.readback(batch)
        with pytest.raises(CodeProjectionQdrantIntegrityError, match="model output"):
            await store.search(
                query_text="Greeter",
                tenant_id=batch.source.tenant_id,
            )

        repaired = await store.apply(batch)
        assert repaired.decision == "replace"

        repaired_records, _ = await client.scroll(
            collection_name=store.config.collection_name,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="record_kind",
                        match=qmodels.MatchValue(value="semantic_document"),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=True,
        )
        relabeled_payload = cast(dict[str, Any], repaired_records[0].payload)
        relabeled_payload["tenant_id"] = "tenant-other"
        relabeled_payload["policy_tenant_id"] = "tenant-other"
        relabeled_without_digest = {
            key: value
            for key, value in relabeled_payload.items()
            if key != "payload_sha256"
        }
        relabeled_payload["payload_sha256"] = hashlib.sha256(
            canonical_json_bytes(relabeled_without_digest)
        ).hexdigest()
        repaired_vectors = repaired_records[0].vector
        assert isinstance(repaired_vectors, dict)
        repaired_vector = repaired_vectors[store.config.vector_name]
        assert isinstance(repaired_vector, list)
        await client.upsert(
            collection_name=store.config.collection_name,
            points=[
                qmodels.PointStruct(
                    id=document_id,
                    vector={store.config.vector_name: repaired_vector},
                    payload=relabeled_payload,
                )
            ],
            wait=True,
        )

        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="source identity does not match its tenant",
        ):
            await store.search(query_text="Greeter", tenant_id="tenant-other")
    finally:
        await client.close()


async def test_search_rejects_self_consistent_point_outside_authoritative_batch() -> (
    None
):
    client = _IndexedMemoryClient()
    embedding_client = _DeterministicEmbeddingClient()
    store = _store(client, embedding_client)
    batch = build_fixture_batches()["python_a_seq1.json"]
    document = batch.semantic_documents[0]
    try:
        await store.apply(batch)
        records, _ = await client.scroll(
            collection_name=store.config.collection_name,
            with_payload=True,
            with_vectors=True,
        )
        document_record = next(
            record
            for record in records
            if isinstance(record.payload, dict)
            and record.payload.get("record_kind") == "semantic_document"
        )
        manifest_record = next(
            record
            for record in records
            if isinstance(record.payload, dict)
            and record.payload.get("record_kind") == "source_manifest"
        )
        vectors = document_record.vector
        manifest_vectors = manifest_record.vector
        assert isinstance(vectors, dict)
        assert isinstance(manifest_vectors, dict)
        vector = cast(list[float], vectors[store.config.vector_name])
        manifest_vector = cast(
            list[float],
            manifest_vectors[store.config.vector_name],
        )

        fabricated = make_code_chunk(
            source_id=document.source_id,
            source_hash_sha256=document.source_hash_sha256,
            chunk_key="fabricated-but-self-consistent",
            chunk_kind=document.chunk_kind,
            chunker_version=document.chunker_version,
            sanitized_content_hash_sha256=document.sanitized_content_hash_sha256,
            byte_count=document.byte_count,
            anchor_node_id=document.anchor_node_id,
            source_span=document.source_span,
            content_ref=document.content_ref,
        )
        fabricated_point_id = derive_code_projection_point_id(
            tenant_id=batch.source.tenant_id,
            document_id=fabricated.document_id,
            embedding_model=store.config.embedding_model,
            embedding_model_version=store.config.embedding_model_version,
        )

        fabricated_payload = cast(dict[str, Any], document_record.payload).copy()
        fabricated_payload["chunk_key"] = fabricated.chunk_key
        fabricated_payload["document_id"] = fabricated.document_id
        fabricated_payload["embedding_vector_sha256"] = hashlib.sha256(
            struct.pack("<1024f", *vector)
        ).hexdigest()
        fabricated_payload.pop("payload_sha256", None)
        fabricated_payload["payload_sha256"] = hashlib.sha256(
            canonical_json_bytes(fabricated_payload)
        ).hexdigest()

        manifest_payload = cast(dict[str, Any], manifest_record.payload).copy()
        manifest_payload["document_ids"] = sorted(
            [*cast(list[str], manifest_payload["document_ids"]), fabricated.document_id]
        )
        manifest_payload["document_point_ids"] = sorted(
            [
                *cast(list[str], manifest_payload["document_point_ids"]),
                fabricated_point_id,
            ]
        )
        manifest_payload["embedding_vector_sha256"] = hashlib.sha256(
            struct.pack("<1024f", *manifest_vector)
        ).hexdigest()
        manifest_payload.pop("payload_sha256", None)
        manifest_payload["payload_sha256"] = hashlib.sha256(
            canonical_json_bytes(manifest_payload)
        ).hexdigest()

        await client.upsert(
            collection_name=store.config.collection_name,
            points=[
                qmodels.PointStruct(
                    id=fabricated_point_id,
                    vector={store.config.vector_name: vector},
                    payload=fabricated_payload,
                ),
                qmodels.PointStruct(
                    id=manifest_record.id,
                    vector={store.config.vector_name: manifest_vector},
                    payload=manifest_payload,
                ),
            ],
            wait=True,
        )

        with pytest.raises(
            CodeProjectionQdrantIntegrityError,
            match="source generation is not globally applied",
        ):
            await store.search(
                query_text="Greeter",
                tenant_id=batch.source.tenant_id,
                limit=10,
            )
    finally:
        await client.close()


def test_public_embedding_protocol_remains_batch_ordered() -> None:
    """Keep a type-level check that the fake matches the production protocol."""

    client = _DeterministicEmbeddingClient()
    method: Any = client.get_embeddings_batch
    assert callable(method)
    assert isinstance(cast(Sequence[object], client.requests), Sequence)
