# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tenant-closed Qdrant materialization for semantic code documents.

The canonical projection batch owns document identity and content digests.  This
module owns only the derived embedding index: it resolves the addressed bytes,
verifies them, obtains real model embeddings, and proves the exact Qdrant state
for one tenant and source.  Credentials and endpoint construction remain with
the operator; callers inject an already-configured ``AsyncQdrantClient``.
"""

from __future__ import annotations

import math
import struct
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Final, Literal, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    normalize_repository_id,
    normalize_tenant_id,
    sha256_hex,
)
from omniintelligence.code_projection.codec import (
    derive_code_source_id,
    make_code_chunk,
    parse_code_projection_batch,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection.models import (
    ModelChunkKind,
    ModelCodeProjectionBatch,
    ModelCodeProjectionDocument,
    ModelCodeProjectionSpan,
)

_STORAGE_SCHEMA_ID: Final = "com.omninode.code-projection-qdrant"
_STORAGE_SCHEMA_VERSION: Final = "2.0.0"
_PAYLOAD_DIGEST_FIELD: Final = "payload_sha256"
_VECTOR_DIGEST_FIELD: Final = "embedding_vector_sha256"
_DOCUMENT_RECORD_KIND: Final = "semantic_document"
_MANIFEST_RECORD_KIND: Final = "source_manifest"
MAX_CODE_PROJECTION_SEARCH_DOCUMENT_BYTES: Final = 131_072
_FILTERED_KEYWORD_FIELDS: Final = (
    "tenant_id",
    "source_id",
    "repository_id",
    "record_kind",
)

type _QdrantCondition = (
    qmodels.FieldCondition
    | qmodels.IsEmptyCondition
    | qmodels.IsNullCondition
    | qmodels.HasIdCondition
    | qmodels.HasVectorCondition
    | qmodels.NestedCondition
    | qmodels.Filter
)

BoundedConfigText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, strip_whitespace=False),
]
Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]


class CodeProjectionQdrantIntegrityError(RuntimeError):
    """Qdrant cannot prove the configured projection state exactly."""


@runtime_checkable
class ProtocolCodeProjectionEmbeddingClient(Protocol):
    """Minimum real-model embedding surface required by this materializer."""

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one dense embedding for each input, preserving input order."""


class ProtocolCodeProjectionContentResolver(Protocol):
    """Resolve one immutable ``artifact://sha256`` reference to exact bytes."""

    def __call__(self, content_ref: str) -> bytes:
        """Return the bytes addressed by ``content_ref`` or raise."""


class ProtocolCodeProjectionCurrentGenerationResolver(Protocol):
    """Resolve the globally applied source generation outside Qdrant."""

    def __call__(
        self,
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        """Return the promoted generation or ``None`` when it is not applied."""


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ModelCodeProjectionQdrantConfig(_FrozenModel):
    """Pinned storage and model contract for one shared Qdrant collection.

    URL and API-key fields are intentionally absent.  A local or cloud client
    is configured at the composition root and injected into the store.
    """

    collection_name: BoundedConfigText = "code_semantic_v2"
    vector_name: BoundedConfigText = "code_semantic_v2"
    embedding_model: BoundedConfigText
    embedding_model_version: BoundedConfigText
    embedding_dimension: Literal[1024] = 1024
    # Inputs are normalized in the adapter and stored with DOT so Qdrant does
    # not rewrite vector bytes (Cosine collections normalize on upload).
    distance: Literal["Dot"] = "Dot"
    reembedding_cosine_threshold_basis_points: Literal[9990] = 9990
    read_consistency: Literal["majority", "quorum", "all"] = "majority"
    write_ordering: Literal["weak", "medium", "strong"] = "medium"
    embedding_batch_size: int = Field(default=64, ge=1, le=512)
    mutation_batch_size: int = Field(default=128, ge=1, le=1_000)
    scroll_page_size: int = Field(default=256, ge=1, le=1_000)


class ModelCodeProjectionQdrantCollection(_FrozenModel):
    """Validated shared-collection schema receipt."""

    collection_name: str
    vector_name: str
    embedding_model: str
    embedding_model_version: str
    embedding_dimension: int = Field(ge=1)
    distance: str
    reembedding_cosine_threshold_basis_points: int = Field(ge=0, le=10_000)
    indexed_fields: tuple[str, ...]


class ModelCodeProjectionCurrentGeneration(_FrozenModel):
    """Authoritative current-pointer receipt used to gate search visibility."""

    tenant_id: str
    source_id: str
    batch_id: str
    operation: Literal["snapshot", "tombstone"]
    batch_content_hash_sha256: Sha256Digest
    document_ids: tuple[str, ...]


class ModelCodeProjectionQdrantReadback(_FrozenModel):
    """Exact source-scoped Qdrant proof."""

    tenant_id: str
    source_id: str
    batch_id: str
    operation: str
    manifest_point_id: str
    point_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    point_count: int = Field(ge=0)
    record_count: int = Field(ge=1)


class ModelCodeProjectionQdrantApplyReport(_FrozenModel):
    """Mutation and verification result for one batch."""

    tenant_id: str
    source_id: str
    batch_id: str
    operation: str
    decision: Literal["noop", "replace", "tombstone"]
    documents_embedded: int = Field(ge=0)
    points_upserted: int = Field(ge=0)
    points_deleted: int = Field(ge=0)
    readback: ModelCodeProjectionQdrantReadback


class ModelCodeProjectionSearchHit(_FrozenModel):
    """Authorized metadata-only semantic result; content remains in artifacts."""

    point_id: str
    score: float
    tenant_id: str
    repository_id: str
    relative_path: str
    source_id: str
    batch_id: str
    document_id: str
    byte_count: int = Field(ge=0, le=MAX_CODE_PROJECTION_SEARCH_DOCUMENT_BYTES)
    content_ref: str
    sanitized_content_hash_sha256: str
    chunk_key: str
    chunk_kind: str
    anchor_node_id: str | None
    source_span: ModelCodeProjectionSpan | None
    embedding_model: str
    embedding_model_version: str


class ProtocolCodeProjectionQdrantStore(Protocol):
    """Narrow injected third-store surface used by the materializer."""

    @property
    def config(self) -> ModelCodeProjectionQdrantConfig:
        """Return the immutable storage/model contract."""

    async def ensure_collection(self) -> ModelCodeProjectionQdrantCollection:
        """Create or validate the shared collection and filter indexes."""

    async def guard_replay(self, batch: ModelCodeProjectionBatch) -> None:
        """Reject a stale/conflicting cursor before any companion-store write."""

    async def apply(
        self, batch: ModelCodeProjectionBatch
    ) -> ModelCodeProjectionQdrantApplyReport:
        """Apply and verify one source-owned batch."""

    async def readback(
        self, batch: ModelCodeProjectionBatch
    ) -> ModelCodeProjectionQdrantReadback:
        """Read and verify one source-owned batch."""

    async def search(
        self,
        *,
        query_text: str,
        tenant_id: str,
        repository_id: str | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> tuple[ModelCodeProjectionSearchHit, ...]:
        """Search inside one explicit tenant boundary."""


def derive_code_projection_point_id(
    *,
    tenant_id: str,
    document_id: str,
    embedding_model: str,
    embedding_model_version: str,
) -> str:
    """Return a stable UUIDv5 separated by tenant, document, and model version."""

    canonical_tenant_id = normalize_tenant_id(tenant_id)
    if not document_id or not embedding_model or not embedding_model_version:
        raise ValueError("point identity fields must be non-empty")
    identity = canonical_json_bytes(
        {
            "document_id": document_id,
            "embedding_model": embedding_model,
            "embedding_model_version": embedding_model_version,
            "tenant_id": canonical_tenant_id,
        }
    ).decode("utf-8")
    name = f"urn:omninode:code-projection:qdrant-point:v2:{identity}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def derive_code_projection_manifest_point_id(
    *,
    tenant_id: str,
    source_id: str,
    embedding_model: str,
    embedding_model_version: str,
) -> str:
    """Return the stable source-control point ID for one embedding contract."""

    canonical_tenant_id = normalize_tenant_id(tenant_id)
    if not source_id or not embedding_model or not embedding_model_version:
        raise ValueError("manifest point identity fields must be non-empty")
    identity = canonical_json_bytes(
        {
            "embedding_model": embedding_model,
            "embedding_model_version": embedding_model_version,
            "source_id": source_id,
            "tenant_id": canonical_tenant_id,
        }
    ).decode("utf-8")
    name = f"urn:omninode:code-projection:qdrant-manifest:v2:{identity}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


@dataclass(frozen=True, slots=True)
class _ExpectedPoint:
    payload: Mapping[str, object]
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _CurrentSourceState:
    cursor_authority: str
    cursor_sequence: int
    batch_id: str
    operation: str


def _payload_digest(payload: Mapping[str, object]) -> str:
    return sha256_hex(canonical_json_bytes(payload))


def _payload_without_digest(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value for key, value in payload.items() if key != _PAYLOAD_DIGEST_FIELD
    }


def _validate_payload_digest(payload: Mapping[str, object]) -> None:
    digest = payload.get(_PAYLOAD_DIGEST_FIELD)
    if not isinstance(digest, str):
        raise CodeProjectionQdrantIntegrityError(
            "Qdrant point payload is missing its canonical digest"
        )
    try:
        expected = _payload_digest(_payload_without_digest(payload))
    except (TypeError, ValueError) as exc:
        raise CodeProjectionQdrantIntegrityError(
            "Qdrant point payload is not canonicalizable"
        ) from exc
    if digest != expected:
        raise CodeProjectionQdrantIntegrityError(
            "Qdrant point payload digest does not match its fields"
        )


def _validated_vector(
    vector: Sequence[object],
    *,
    dimension: int,
    description: str,
) -> list[float]:
    if len(vector) != dimension:
        raise CodeProjectionQdrantIntegrityError(
            f"{description} dimension is {len(vector)}, expected {dimension}"
        )
    validated: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise CodeProjectionQdrantIntegrityError(
                f"{description} contains a non-numeric value"
            )
        item = float(value)
        if not math.isfinite(item):
            raise CodeProjectionQdrantIntegrityError(
                f"{description} contains a non-finite value"
            )
        try:
            # Qdrant persists dense values as float32. Quantize before hashing
            # and writing so readback has one portable byte representation.
            item = struct.unpack("<f", struct.pack("<f", item))[0]
        except OverflowError as exc:
            raise CodeProjectionQdrantIntegrityError(
                f"{description} contains a value outside float32 range"
            ) from exc
        validated.append(item)
    return validated


def _vector_digest(vector: Sequence[float]) -> str:
    return sha256_hex(struct.pack(f"<{len(vector)}f", *vector))


def _normalized_vector(vector: Sequence[float], *, description: str) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm == 0.0:
        raise CodeProjectionQdrantIntegrityError(
            f"{description} must have a finite non-zero norm"
        )
    return _validated_vector(
        [value / norm for value in vector],
        dimension=len(vector),
        description=description,
    )


def _require_semantically_equivalent_vector(
    stored: Sequence[float],
    expected: Sequence[float],
    *,
    minimum_cosine_basis_points: int,
    description: str,
) -> None:
    """Reject material semantic drift while tolerating model runtime jitter."""

    if len(stored) != len(expected):
        raise CodeProjectionQdrantIntegrityError(
            f"{description} vector dimension does not match model output"
        )
    stored_norm = math.sqrt(sum(value * value for value in stored))
    expected_norm = math.sqrt(sum(value * value for value in expected))
    if (
        not math.isfinite(stored_norm)
        or not math.isfinite(expected_norm)
        or stored_norm == 0.0
        or expected_norm == 0.0
    ):
        raise CodeProjectionQdrantIntegrityError(
            f"{description} vector norm is not finite and non-zero"
        )
    similarity = sum(
        stored_value * expected_value
        for stored_value, expected_value in zip(stored, expected, strict=True)
    ) / (stored_norm * expected_norm)
    threshold = minimum_cosine_basis_points / 10_000
    if not math.isfinite(similarity) or similarity < threshold:
        raise CodeProjectionQdrantIntegrityError(
            f"{description} vector does not match model output"
        )


def _stored_payload(
    base_payload: Mapping[str, object],
    vector: Sequence[float],
) -> dict[str, object]:
    payload = dict(base_payload)
    payload[_VECTOR_DIGEST_FIELD] = _vector_digest(vector)
    payload[_PAYLOAD_DIGEST_FIELD] = _payload_digest(payload)
    return payload


def _qdrant_filter(
    *,
    tenant_id: str,
    source_id: str | None = None,
    repository_id: str | None = None,
    record_kind: str | None = None,
    point_ids: Sequence[str] = (),
) -> qmodels.Filter:
    conditions: list[_QdrantCondition] = [
        qmodels.FieldCondition(
            key="tenant_id",
            match=qmodels.MatchValue(value=normalize_tenant_id(tenant_id)),
        )
    ]
    if source_id is not None:
        conditions.append(
            qmodels.FieldCondition(
                key="source_id",
                match=qmodels.MatchValue(value=source_id),
            )
        )
    if repository_id is not None:
        conditions.append(
            qmodels.FieldCondition(
                key="repository_id",
                match=qmodels.MatchValue(value=normalize_repository_id(repository_id)),
            )
        )
    if record_kind is not None:
        conditions.append(
            qmodels.FieldCondition(
                key="record_kind",
                match=qmodels.MatchValue(value=record_kind),
            )
        )
    if point_ids:
        conditions.append(qmodels.HasIdCondition(has_id=list(point_ids)))
    return qmodels.Filter(must=conditions)


class CodeProjectionQdrantStore:
    """Materialize and search semantic code documents in one shared collection."""

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        embedding_client: ProtocolCodeProjectionEmbeddingClient,
        content_resolver: ProtocolCodeProjectionContentResolver,
        current_generation_resolver: ProtocolCodeProjectionCurrentGenerationResolver,
        config: ModelCodeProjectionQdrantConfig,
    ) -> None:
        self._client = client
        self._embedding_client = embedding_client
        self._content_resolver = content_resolver
        self._current_generation_resolver = current_generation_resolver
        self._config = config

    @property
    def config(self) -> ModelCodeProjectionQdrantConfig:
        """Return the immutable storage/model contract."""

        return self._config

    def _read_consistency(self) -> qmodels.ReadConsistencyType:
        return {
            "all": qmodels.ReadConsistencyType.ALL,
            "majority": qmodels.ReadConsistencyType.MAJORITY,
            "quorum": qmodels.ReadConsistencyType.QUORUM,
        }[self._config.read_consistency]

    def _write_ordering(self) -> qmodels.WriteOrdering:
        return {
            "medium": qmodels.WriteOrdering.MEDIUM,
            "strong": qmodels.WriteOrdering.STRONG,
            "weak": qmodels.WriteOrdering.WEAK,
        }[self._config.write_ordering]

    def _collection_metadata(self) -> dict[str, object]:
        return {
            "embedding_dimension": self._config.embedding_dimension,
            "embedding_model": self._config.embedding_model,
            "embedding_model_version": self._config.embedding_model_version,
            "reembedding_cosine_threshold_basis_points": (
                self._config.reembedding_cosine_threshold_basis_points
            ),
            "storage_schema_id": _STORAGE_SCHEMA_ID,
            "storage_schema_version": _STORAGE_SCHEMA_VERSION,
            "vector_distance": self._config.distance,
            "vector_name": self._config.vector_name,
        }

    @staticmethod
    def _is_create_race(exc: UnexpectedResponse) -> bool:
        return exc.status_code == 409 or (
            exc.status_code == 400 and "already exists" in str(exc).lower()
        )

    def _validate_collection_shape(self, info: qmodels.CollectionInfo) -> None:
        vectors = info.config.params.vectors
        if not isinstance(vectors, Mapping):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant collection must use named vectors"
            )
        vector = vectors.get(self._config.vector_name)
        if not isinstance(vector, qmodels.VectorParams):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant collection is missing the configured named vector"
            )
        if vector.size != self._config.embedding_dimension:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant named-vector dimension does not match embedding contract"
            )
        if vector.distance != qmodels.Distance.DOT:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant named-vector distance must be Dot"
            )
        if vector.datatype not in {None, qmodels.Datatype.FLOAT32}:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant named-vector datatype must preserve float32 values"
            )
        if vector.multivector_config is not None:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant named vector must not use a multivector configuration"
            )

        metadata = info.config.metadata
        if not isinstance(metadata, Mapping):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant collection metadata is missing"
            )
        for key, expected in self._collection_metadata().items():
            if metadata.get(key) != expected:
                raise CodeProjectionQdrantIntegrityError(
                    f"Qdrant collection metadata mismatch for {key}"
                )

    @staticmethod
    def _validate_payload_index(
        field_name: str,
        index: qmodels.PayloadIndexInfo,
    ) -> None:
        if index.data_type != qmodels.PayloadSchemaType.KEYWORD:
            raise CodeProjectionQdrantIntegrityError(
                f"Qdrant payload index {field_name} must be keyword"
            )
        if field_name == "tenant_id":
            params = index.params
            if (
                not isinstance(params, qmodels.KeywordIndexParams)
                or params.is_tenant is not True
            ):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant tenant_id index must set is_tenant=true"
                )

    async def ensure_collection(self) -> ModelCodeProjectionQdrantCollection:
        """Create or validate the shared collection and every filter index."""

        exists = await self._client.collection_exists(self._config.collection_name)
        if not exists:
            try:
                await self._client.create_collection(
                    collection_name=self._config.collection_name,
                    vectors_config={
                        self._config.vector_name: qmodels.VectorParams(
                            size=self._config.embedding_dimension,
                            distance=qmodels.Distance.DOT,
                        )
                    },
                    metadata=self._collection_metadata(),
                )
            except UnexpectedResponse as exc:
                if not self._is_create_race(exc):
                    raise

        info = await self._client.get_collection(self._config.collection_name)
        self._validate_collection_shape(info)
        for field_name in _FILTERED_KEYWORD_FIELDS:
            existing = info.payload_schema.get(field_name)
            if existing is not None:
                self._validate_payload_index(field_name, existing)
                continue
            try:
                await self._client.create_payload_index(
                    collection_name=self._config.collection_name,
                    field_name=field_name,
                    field_schema=qmodels.KeywordIndexParams(
                        type=qmodels.KeywordIndexType.KEYWORD,
                        is_tenant=field_name == "tenant_id",
                    ),
                    wait=True,
                    ordering=self._write_ordering(),
                )
            except UnexpectedResponse as exc:
                if not self._is_create_race(exc):
                    raise

        verified = await self._client.get_collection(self._config.collection_name)
        self._validate_collection_shape(verified)
        for field_name in _FILTERED_KEYWORD_FIELDS:
            index = verified.payload_schema.get(field_name)
            if index is None:
                raise CodeProjectionQdrantIntegrityError(
                    f"Qdrant payload index {field_name} was not created"
                )
            self._validate_payload_index(field_name, index)

        return ModelCodeProjectionQdrantCollection(
            collection_name=self._config.collection_name,
            vector_name=self._config.vector_name,
            embedding_model=self._config.embedding_model,
            embedding_model_version=self._config.embedding_model_version,
            embedding_dimension=self._config.embedding_dimension,
            distance=self._config.distance,
            reembedding_cosine_threshold_basis_points=(
                self._config.reembedding_cosine_threshold_basis_points
            ),
            indexed_fields=_FILTERED_KEYWORD_FIELDS,
        )

    def _document_payload(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        document: ModelCodeProjectionDocument,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "anchor_node_id": document.anchor_node_id,
            "batch_id": batch.batch_id,
            "byte_count": document.byte_count,
            "chunk_key": document.chunk_key,
            "chunk_kind": document.chunk_kind,
            "chunker_version": document.chunker_version,
            "content_ref": document.content_ref,
            "cursor_authority": batch.cursor.authority,
            "cursor_sequence": batch.cursor.sequence,
            "document_id": document.document_id,
            "embedding_dimension": self._config.embedding_dimension,
            "embedding_input_hash_sha256": (document.sanitized_content_hash_sha256),
            "embedding_model": self._config.embedding_model,
            "embedding_model_version": self._config.embedding_model_version,
            "reembedding_cosine_threshold_basis_points": (
                self._config.reembedding_cosine_threshold_basis_points
            ),
            "identity_version": batch.identity_version,
            "policy_payload_sha256": _payload_digest(
                cast(
                    dict[str, object],
                    batch.policy.model_dump(mode="json"),
                )
            ),
            "policy_access_scope": batch.policy.access_scope,
            "policy_scope_ref": batch.policy.scope_ref,
            "policy_tenant_id": batch.policy.tenant_id,
            "policy_visibility": batch.policy.visibility,
            "projection_version": batch.projection_version,
            "provenance_payload_sha256": _payload_digest(
                cast(
                    dict[str, object],
                    batch.provenance.model_dump(mode="json"),
                )
            ),
            "reducer_version": batch.reducer_version,
            "record_kind": _DOCUMENT_RECORD_KIND,
            "relative_path": batch.source.relative_path,
            "repository_id": batch.source.repository_id,
            "sanitized_content_hash_sha256": (document.sanitized_content_hash_sha256),
            "schema_id": batch.schema_id,
            "schema_version": batch.schema_version,
            "source_hash_sha256": document.source_hash_sha256,
            "source_id": batch.source.source_id,
            "source_span": (
                document.source_span.model_dump(mode="json")
                if document.source_span is not None
                else None
            ),
            "source_version": batch.source.source_version,
            "storage_schema_id": _STORAGE_SCHEMA_ID,
            "storage_schema_version": _STORAGE_SCHEMA_VERSION,
            "tenant_id": batch.source.tenant_id,
            "vector_name": self._config.vector_name,
        }
        return payload

    def _manifest_point_id(self, batch: ModelCodeProjectionBatch) -> str:
        return derive_code_projection_manifest_point_id(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            embedding_model=self._config.embedding_model,
            embedding_model_version=self._config.embedding_model_version,
        )

    def _manifest_vector(self) -> tuple[float, ...]:
        return (1.0, *(0.0 for _ in range(self._config.embedding_dimension - 1)))

    def _manifest_payload(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        document_point_ids: Sequence[str],
    ) -> dict[str, object]:
        return {
            "batch_content_hash_sha256": sha256_hex(
                serialize_code_projection_batch(batch)
            ),
            "batch_id": batch.batch_id,
            "cursor_authority": batch.cursor.authority,
            "cursor_sequence": batch.cursor.sequence,
            "document_ids": [
                document.document_id for document in batch.semantic_documents
            ],
            "document_point_ids": list(document_point_ids),
            "embedding_dimension": self._config.embedding_dimension,
            "embedding_model": self._config.embedding_model,
            "embedding_model_version": self._config.embedding_model_version,
            "reembedding_cosine_threshold_basis_points": (
                self._config.reembedding_cosine_threshold_basis_points
            ),
            "operation": batch.operation,
            "policy_access_scope": batch.policy.access_scope,
            "policy_scope_ref": batch.policy.scope_ref,
            "policy_tenant_id": batch.policy.tenant_id,
            "policy_visibility": batch.policy.visibility,
            "record_kind": _MANIFEST_RECORD_KIND,
            "relative_path": batch.source.relative_path,
            "repository_id": batch.source.repository_id,
            "source_id": batch.source.source_id,
            "storage_schema_id": _STORAGE_SCHEMA_ID,
            "storage_schema_version": _STORAGE_SCHEMA_VERSION,
            "tenant_id": batch.source.tenant_id,
            "vector_name": self._config.vector_name,
        }

    def _manifest_expected_point(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        document_point_ids: Sequence[str],
    ) -> tuple[str, _ExpectedPoint]:
        manifest_point_id = self._manifest_point_id(batch)
        return (
            manifest_point_id,
            _ExpectedPoint(
                payload=self._manifest_payload(
                    batch=batch,
                    document_point_ids=document_point_ids,
                ),
                vector=self._manifest_vector(),
            ),
        )

    @staticmethod
    def _payload_text(payload: Mapping[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise CodeProjectionQdrantIntegrityError(
                f"Qdrant source manifest {key} must be non-empty text"
            )
        return value

    @staticmethod
    def _payload_sequence(payload: Mapping[str, object]) -> int:
        value = payload.get("cursor_sequence")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant source manifest cursor_sequence must be non-negative"
            )
        return value

    def _current_source_state(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        records: Sequence[qmodels.Record],
    ) -> _CurrentSourceState | None:
        if not records:
            return None
        manifest_records: list[qmodels.Record] = []
        for record in records:
            if not isinstance(record.payload, Mapping):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant source record is missing its payload"
                )
            payload = cast(Mapping[str, object], record.payload)
            if payload.get("tenant_id") != batch.source.tenant_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant source record crossed the tenant boundary"
                )
            if payload.get("source_id") != batch.source.source_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant source record crossed the source boundary"
                )
            if payload.get("record_kind") == _MANIFEST_RECORD_KIND:
                manifest_records.append(record)
        if not manifest_records:
            # Documents are written before the manifest so the manifest remains
            # the applied-generation boundary. A first application interrupted
            # before that final write is safe to replay under the caller's
            # source lock; the subsequent exact readback closes the state.
            if all(
                isinstance(record.payload, Mapping)
                and record.payload.get("record_kind") == _DOCUMENT_RECORD_KIND
                for record in records
            ):
                return None
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant source has records but no recoverable cursor manifest"
            )
        if len(manifest_records) != 1:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant source must contain exactly one cursor manifest"
            )
        record = manifest_records[0]
        payload = cast(Mapping[str, object], record.payload)
        # The cursor fields are the minimum ordering hint. Exact point ID,
        # payload digest, and vector checks happen against the incoming batch
        # in _assert_records so an identical authoritative replay can repair a
        # malformed control point instead of becoming permanently wedged.
        return _CurrentSourceState(
            cursor_authority=self._payload_text(payload, "cursor_authority"),
            cursor_sequence=self._payload_sequence(payload),
            batch_id=self._payload_text(payload, "batch_id"),
            operation=self._payload_text(payload, "operation"),
        )

    @staticmethod
    def _guard_replay(
        *,
        batch: ModelCodeProjectionBatch,
        current: _CurrentSourceState | None,
    ) -> None:
        if current is None:
            return
        if current.cursor_authority != batch.cursor.authority:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant source cursor authority does not match the incoming batch"
            )
        if batch.cursor.sequence < current.cursor_sequence:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant refused a stale source cursor"
            )
        if (
            batch.cursor.sequence == current.cursor_sequence
            and batch.batch_id != current.batch_id
        ):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant refused a conflicting source cursor"
            )

    def _resolve_documents(
        self,
        batch: ModelCodeProjectionBatch,
    ) -> tuple[
        tuple[ModelCodeProjectionDocument, str, dict[str, object]],
        ...,
    ]:
        resolved: list[tuple[ModelCodeProjectionDocument, str, dict[str, object]]] = []
        for document in sorted(
            batch.semantic_documents,
            key=lambda item: item.document_id,
        ):
            content = self._content_resolver(document.content_ref)
            if not isinstance(content, bytes):
                raise CodeProjectionQdrantIntegrityError(
                    "semantic content resolver must return bytes"
                )
            if sha256_hex(content) != document.sanitized_content_hash_sha256:
                raise CodeProjectionQdrantIntegrityError(
                    f"semantic document {document.document_id} digest mismatch"
                )
            if len(content) != document.byte_count:
                raise CodeProjectionQdrantIntegrityError(
                    f"semantic document {document.document_id} byte-count mismatch"
                )
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CodeProjectionQdrantIntegrityError(
                    f"semantic document {document.document_id} is not UTF-8"
                ) from exc
            if not text:
                raise CodeProjectionQdrantIntegrityError(
                    f"semantic document {document.document_id} is empty"
                )
            resolved.append(
                (
                    document,
                    text,
                    self._document_payload(
                        batch=batch,
                        document=document,
                    ),
                )
            )
        return tuple(resolved)

    async def _embed(self, texts: Sequence[str]) -> tuple[list[float], ...]:
        vectors: list[list[float]] = []
        batch_size = self._config.embedding_batch_size
        for start in range(0, len(texts), batch_size):
            requested = list(texts[start : start + batch_size])
            returned = await self._embedding_client.get_embeddings_batch(requested)
            if len(returned) != len(requested):
                raise CodeProjectionQdrantIntegrityError(
                    "embedding client did not return one vector per document"
                )
            vectors.extend(
                _normalized_vector(
                    _validated_vector(
                        vector,
                        dimension=self._config.embedding_dimension,
                        description="model embedding",
                    ),
                    description="model embedding",
                )
                for vector in returned
            )
        return tuple(vectors)

    def _expected_points(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        resolved: Sequence[
            tuple[ModelCodeProjectionDocument, str, Mapping[str, object]]
        ],
        vectors: Sequence[Sequence[float]],
    ) -> dict[str, _ExpectedPoint]:
        if len(resolved) != len(vectors):
            raise CodeProjectionQdrantIntegrityError(
                "resolved semantic documents and embeddings do not align"
            )
        expected: dict[str, _ExpectedPoint] = {}
        for (document, _, payload), vector in zip(resolved, vectors, strict=True):
            point_id = derive_code_projection_point_id(
                tenant_id=batch.source.tenant_id,
                document_id=document.document_id,
                embedding_model=self._config.embedding_model,
                embedding_model_version=self._config.embedding_model_version,
            )
            expected[point_id] = _ExpectedPoint(
                payload=payload,
                vector=tuple(vector),
            )
        manifest_point_id, manifest = self._manifest_expected_point(
            batch=batch,
            document_point_ids=tuple(sorted(expected)),
        )
        expected[manifest_point_id] = manifest
        return expected

    async def _scroll_source(
        self,
        *,
        tenant_id: str,
        source_id: str,
    ) -> tuple[qmodels.Record, ...]:
        records: list[qmodels.Record] = []
        offset: int | str | uuid.UUID | None = None
        seen_offsets: set[int | str | uuid.UUID] = set()
        while True:
            page, next_offset = await self._client.scroll(
                collection_name=self._config.collection_name,
                scroll_filter=_qdrant_filter(
                    tenant_id=tenant_id,
                    source_id=source_id,
                ),
                limit=self._config.scroll_page_size,
                offset=offset,
                with_payload=True,
                with_vectors=[self._config.vector_name],
                consistency=self._read_consistency(),
            )
            records.extend(page)
            if next_offset is None:
                break
            if next_offset in seen_offsets:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant scroll returned a repeated page offset"
                )
            seen_offsets.add(next_offset)
            offset = next_offset
        return tuple(records)

    async def _count_source(self, *, tenant_id: str, source_id: str) -> int:
        result = await self._client.count(
            collection_name=self._config.collection_name,
            count_filter=_qdrant_filter(
                tenant_id=tenant_id,
                source_id=source_id,
            ),
            exact=True,
        )
        return result.count

    async def guard_replay(self, batch: ModelCodeProjectionBatch) -> None:
        """Reject sequential stale/conflicting writes using the source manifest."""

        validated = parse_code_projection_batch(serialize_code_projection_batch(batch))
        await self.ensure_collection()
        current = await self._scroll_source(
            tenant_id=validated.source.tenant_id,
            source_id=validated.source.source_id,
        )
        state = self._current_source_state(batch=validated, records=current)
        self._guard_replay(batch=validated, current=state)

    def _record_vector(
        self,
        record: qmodels.Record | qmodels.ScoredPoint,
    ) -> list[float]:
        vectors = record.vector
        if not isinstance(vectors, Mapping):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant readback is missing named vectors"
            )
        vector = vectors.get(self._config.vector_name)
        if not isinstance(vector, Sequence):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant readback is missing the configured dense vector"
            )
        return _validated_vector(
            cast(Sequence[object], vector),
            dimension=self._config.embedding_dimension,
            description="stored embedding",
        )

    def _assert_records(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        expected_points: Mapping[str, _ExpectedPoint],
        records: Sequence[qmodels.Record],
    ) -> tuple[tuple[str, ...], str]:
        actual: dict[str, qmodels.Record] = {}
        for record in records:
            point_id = str(record.id)
            if point_id in actual:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant readback contains a duplicate point ID"
                )
            actual[point_id] = record
        if set(actual) != set(expected_points):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant source point IDs do not exactly match the batch"
            )

        for point_id, expected in expected_points.items():
            record = actual[point_id]
            if not isinstance(record.payload, Mapping):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant readback is missing point payload"
                )
            payload = cast(Mapping[str, object], record.payload)
            _validate_payload_digest(payload)
            vector = self._record_vector(record)
            if payload.get(_VECTOR_DIGEST_FIELD) != _vector_digest(vector):
                raise CodeProjectionQdrantIntegrityError(
                    f"Qdrant point {point_id} vector digest does not match"
                )
            _require_semantically_equivalent_vector(
                vector,
                expected.vector,
                minimum_cosine_basis_points=(
                    self._config.reembedding_cosine_threshold_basis_points
                ),
                description=f"Qdrant point {point_id}",
            )
            comparable_payload = _payload_without_digest(payload)
            comparable_payload.pop(_VECTOR_DIGEST_FIELD, None)
            if comparable_payload != dict(expected.payload):
                raise CodeProjectionQdrantIntegrityError(
                    f"Qdrant point {point_id} payload does not match the batch"
                )
            if payload.get("tenant_id") != batch.source.tenant_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant readback crossed the tenant boundary"
                )
        manifest_point_id = self._manifest_point_id(batch)
        document_point_ids = tuple(
            sorted(point_id for point_id in actual if point_id != manifest_point_id)
        )
        return document_point_ids, manifest_point_id

    async def _readback_expected(
        self,
        *,
        batch: ModelCodeProjectionBatch,
        expected_points: Mapping[str, _ExpectedPoint],
    ) -> ModelCodeProjectionQdrantReadback:
        records = await self._scroll_source(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
        )
        count = await self._count_source(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
        )
        if count != len(records):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant exact count does not match scroll readback"
            )
        point_ids, manifest_point_id = self._assert_records(
            batch=batch,
            expected_points=expected_points,
            records=records,
        )
        return ModelCodeProjectionQdrantReadback(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            batch_id=batch.batch_id,
            operation=batch.operation,
            manifest_point_id=manifest_point_id,
            point_ids=point_ids,
            document_ids=tuple(
                document.document_id for document in batch.semantic_documents
            ),
            point_count=len(point_ids),
            record_count=count,
        )

    async def readback(
        self,
        batch: ModelCodeProjectionBatch,
    ) -> ModelCodeProjectionQdrantReadback:
        """Re-embed and prove exact source payloads, cursor, and vector bytes."""

        validated = parse_code_projection_batch(serialize_code_projection_batch(batch))
        await self.ensure_collection()
        resolved = self._resolve_documents(validated)
        vectors = await self._embed(tuple(text for _, text, _ in resolved))
        expected_points = self._expected_points(
            batch=validated,
            resolved=resolved,
            vectors=vectors,
        )
        return await self._readback_expected(
            batch=validated,
            expected_points=expected_points,
        )

    async def _delete_points(
        self,
        *,
        tenant_id: str,
        source_id: str,
        point_ids: Sequence[str],
    ) -> None:
        batch_size = self._config.mutation_batch_size
        for start in range(0, len(point_ids), batch_size):
            selected = point_ids[start : start + batch_size]
            await self._client.delete(
                collection_name=self._config.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=_qdrant_filter(
                        tenant_id=tenant_id,
                        source_id=source_id,
                        point_ids=selected,
                    )
                ),
                wait=True,
                ordering=self._write_ordering(),
            )

    async def apply(
        self,
        batch: ModelCodeProjectionBatch,
    ) -> ModelCodeProjectionQdrantApplyReport:
        """Apply one ordered source snapshot or tombstone, then prove it."""

        validated = parse_code_projection_batch(serialize_code_projection_batch(batch))
        await self.ensure_collection()
        tenant_id = validated.source.tenant_id
        source_id = validated.source.source_id
        current = await self._scroll_source(
            tenant_id=tenant_id,
            source_id=source_id,
        )
        current_ids = tuple(sorted(str(record.id) for record in current))
        state = self._current_source_state(batch=validated, records=current)
        self._guard_replay(batch=validated, current=state)
        resolved = self._resolve_documents(validated)
        vectors = await self._embed(tuple(text for _, text, _ in resolved))
        expected_points = self._expected_points(
            batch=validated,
            resolved=resolved,
            vectors=vectors,
        )
        try:
            point_ids, manifest_point_id = self._assert_records(
                batch=validated,
                expected_points=expected_points,
                records=current,
            )
        except CodeProjectionQdrantIntegrityError:
            pass
        else:
            readback = ModelCodeProjectionQdrantReadback(
                tenant_id=tenant_id,
                source_id=source_id,
                batch_id=validated.batch_id,
                operation=validated.operation,
                manifest_point_id=manifest_point_id,
                point_ids=point_ids,
                document_ids=tuple(
                    document.document_id for document in validated.semantic_documents
                ),
                point_count=len(point_ids),
                record_count=len(current),
            )
            return ModelCodeProjectionQdrantApplyReport(
                tenant_id=tenant_id,
                source_id=source_id,
                batch_id=validated.batch_id,
                operation=validated.operation,
                decision="noop",
                documents_embedded=len(resolved),
                points_upserted=0,
                points_deleted=0,
                readback=readback,
            )

        manifest_point_id = self._manifest_point_id(validated)
        document_points = [
            qmodels.PointStruct(
                id=point_id,
                vector={self._config.vector_name: list(expected.vector)},
                payload=_stored_payload(expected.payload, expected.vector),
            )
            for point_id, expected in sorted(expected_points.items())
            if point_id != manifest_point_id
        ]
        mutation_batch_size = self._config.mutation_batch_size
        for start in range(0, len(document_points), mutation_batch_size):
            await self._client.upsert(
                collection_name=self._config.collection_name,
                points=document_points[start : start + mutation_batch_size],
                wait=True,
                ordering=self._write_ordering(),
            )

        expected_ids = set(expected_points)
        stale_ids = tuple(
            point_id for point_id in current_ids if point_id not in expected_ids
        )
        await self._delete_points(
            tenant_id=tenant_id,
            source_id=source_id,
            point_ids=stale_ids,
        )
        manifest = expected_points[manifest_point_id]
        await self._client.upsert(
            collection_name=self._config.collection_name,
            points=[
                qmodels.PointStruct(
                    id=manifest_point_id,
                    vector={self._config.vector_name: list(manifest.vector)},
                    payload=_stored_payload(manifest.payload, manifest.vector),
                )
            ],
            wait=True,
            ordering=self._write_ordering(),
        )
        readback = await self._readback_expected(
            batch=validated,
            expected_points=expected_points,
        )
        return ModelCodeProjectionQdrantApplyReport(
            tenant_id=tenant_id,
            source_id=source_id,
            batch_id=validated.batch_id,
            operation=validated.operation,
            decision=("tombstone" if validated.operation == "tombstone" else "replace"),
            documents_embedded=len(resolved),
            points_upserted=len(document_points) + 1,
            points_deleted=len(stale_ids),
            readback=readback,
        )

    def _validate_search_identity(
        self,
        *,
        tenant_id: str,
        point: qmodels.ScoredPoint,
        payload: Mapping[str, object],
    ) -> None:
        try:
            repository_id = cast(str, payload["repository_id"])
            relative_path = cast(str, payload["relative_path"])
            source_id = cast(str, payload["source_id"])
            expected_source_id = derive_code_source_id(
                tenant_id=tenant_id,
                repository_id=repository_id,
                relative_path=relative_path,
            )
            if source_id != expected_source_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search source identity does not match its tenant"
                )
            source_span_value = payload["source_span"]
            source_span = (
                ModelCodeProjectionSpan.model_validate(source_span_value)
                if source_span_value is not None
                else None
            )
            document = make_code_chunk(
                source_id=source_id,
                source_hash_sha256=cast(str, payload["source_hash_sha256"]),
                chunk_key=cast(str, payload["chunk_key"]),
                chunk_kind=cast(ModelChunkKind, payload["chunk_kind"]),
                chunker_version=cast(str, payload["chunker_version"]),
                sanitized_content_hash_sha256=cast(
                    str,
                    payload["sanitized_content_hash_sha256"],
                ),
                byte_count=cast(int, payload["byte_count"]),
                anchor_node_id=cast(str | None, payload["anchor_node_id"]),
                source_span=source_span,
                content_ref=cast(str, payload["content_ref"]),
            )
            if payload["document_id"] != document.document_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search document identity does not match its source"
                )
            expected_point_id = derive_code_projection_point_id(
                tenant_id=tenant_id,
                document_id=document.document_id,
                embedding_model=self._config.embedding_model,
                embedding_model_version=self._config.embedding_model_version,
            )
            if str(point.id) != expected_point_id:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search point identity does not match its tenant"
                )
            if payload["content_ref"] != (
                f"artifact://sha256/{payload['sanitized_content_hash_sha256']}"
            ):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content reference is not content-addressed"
                )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, CodeProjectionQdrantIntegrityError):
                raise
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search identity payload is malformed"
            ) from exc

    async def _search_manifest_payload(
        self,
        *,
        tenant_id: str,
        source_id: str,
    ) -> Mapping[str, object]:
        records, next_offset = await self._client.scroll(
            collection_name=self._config.collection_name,
            scroll_filter=_qdrant_filter(
                tenant_id=tenant_id,
                source_id=source_id,
                record_kind=_MANIFEST_RECORD_KIND,
            ),
            limit=2,
            with_payload=True,
            with_vectors=[self._config.vector_name],
            consistency=self._read_consistency(),
        )
        if len(records) != 1 or next_offset is not None:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source has no unique applied manifest"
            )
        record = records[0]
        if not isinstance(record.payload, Mapping):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source manifest is missing its payload"
            )
        payload = cast(Mapping[str, object], record.payload)
        _validate_payload_digest(payload)
        expected_id = derive_code_projection_manifest_point_id(
            tenant_id=tenant_id,
            source_id=source_id,
            embedding_model=self._config.embedding_model,
            embedding_model_version=self._config.embedding_model_version,
        )
        if str(record.id) != expected_id:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source manifest has the wrong point ID"
            )
        vector = self._record_vector(record)
        if tuple(vector) != self._manifest_vector():
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source manifest vector is not canonical"
            )
        if payload.get(_VECTOR_DIGEST_FIELD) != _vector_digest(vector):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source manifest vector digest does not match"
            )
        if (
            payload.get("tenant_id") != tenant_id
            or payload.get("source_id") != source_id
            or payload.get("policy_tenant_id") != tenant_id
        ):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search source manifest crossed the tenant boundary"
            )
        return payload

    def _search_hit(
        self,
        *,
        tenant_id: str,
        repository_id: str | None,
        point: qmodels.ScoredPoint,
        expected_vector: Sequence[float],
    ) -> ModelCodeProjectionSearchHit:
        if not isinstance(point.payload, Mapping):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search hit is missing its payload"
            )
        payload = cast(Mapping[str, object], point.payload)
        _validate_payload_digest(payload)
        if payload.get("record_kind") != _DOCUMENT_RECORD_KIND:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search returned a non-document control point"
            )
        if payload.get("tenant_id") != tenant_id:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search returned a cross-tenant hit"
            )
        if repository_id is not None and payload.get("repository_id") != repository_id:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search returned a cross-repository hit"
            )
        if payload.get("policy_tenant_id") != tenant_id:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search result policy crossed the tenant boundary"
            )
        if (
            payload.get("embedding_model") != self._config.embedding_model
            or payload.get("embedding_model_version")
            != self._config.embedding_model_version
            or payload.get("embedding_dimension") != self._config.embedding_dimension
        ):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search hit does not match the embedding contract"
            )
        stored_vector = self._record_vector(point)
        if payload.get(_VECTOR_DIGEST_FIELD) != _vector_digest(stored_vector):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search hit vector digest does not match"
            )
        _require_semantically_equivalent_vector(
            stored_vector,
            expected_vector,
            minimum_cosine_basis_points=(
                self._config.reembedding_cosine_threshold_basis_points
            ),
            description="Qdrant search hit",
        )
        if not math.isfinite(point.score):
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search hit has a non-finite score"
            )

        try:
            return ModelCodeProjectionSearchHit(
                point_id=str(point.id),
                score=point.score,
                tenant_id=cast(str, payload["tenant_id"]),
                repository_id=cast(str, payload["repository_id"]),
                relative_path=cast(str, payload["relative_path"]),
                source_id=cast(str, payload["source_id"]),
                batch_id=cast(str, payload["batch_id"]),
                document_id=cast(str, payload["document_id"]),
                byte_count=cast(int, payload["byte_count"]),
                content_ref=cast(str, payload["content_ref"]),
                sanitized_content_hash_sha256=cast(
                    str,
                    payload["sanitized_content_hash_sha256"],
                ),
                chunk_key=cast(str, payload["chunk_key"]),
                chunk_kind=cast(str, payload["chunk_kind"]),
                anchor_node_id=cast(str | None, payload["anchor_node_id"]),
                source_span=(
                    ModelCodeProjectionSpan.model_validate(payload["source_span"])
                    if payload["source_span"] is not None
                    else None
                ),
                embedding_model=cast(str, payload["embedding_model"]),
                embedding_model_version=cast(
                    str,
                    payload["embedding_model_version"],
                ),
            )
        except (KeyError, ValueError) as exc:
            raise CodeProjectionQdrantIntegrityError(
                "Qdrant search hit payload is malformed"
            ) from exc

    async def search(
        self,
        *,
        query_text: str,
        tenant_id: str,
        repository_id: str | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> tuple[ModelCodeProjectionSearchHit, ...]:
        """Run real-model semantic search inside one explicit tenant boundary."""

        canonical_tenant_id = normalize_tenant_id(tenant_id)
        canonical_repository_id = (
            normalize_repository_id(repository_id)
            if repository_id is not None
            else None
        )
        if not query_text or not query_text.strip():
            raise ValueError("query_text must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("search limit must be between 1 and 100")
        if score_threshold is not None and not math.isfinite(score_threshold):
            raise ValueError("score_threshold must be finite")

        await self.ensure_collection()
        vectors = await self._embed((query_text,))
        response = await self._client.query_points(
            collection_name=self._config.collection_name,
            query=vectors[0],
            using=self._config.vector_name,
            query_filter=_qdrant_filter(
                tenant_id=canonical_tenant_id,
                repository_id=canonical_repository_id,
                record_kind=_DOCUMENT_RECORD_KIND,
            ),
            limit=limit,
            with_payload=True,
            with_vectors=[self._config.vector_name],
            score_threshold=score_threshold,
            consistency=self._read_consistency(),
        )
        texts: list[str] = []
        manifests: dict[str, Mapping[str, object]] = {}
        current_generations: dict[str, ModelCodeProjectionCurrentGeneration | None] = {}
        for point in response.points:
            if not isinstance(point.payload, Mapping):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search hit is missing its payload"
                )
            payload = cast(Mapping[str, object], point.payload)
            _validate_payload_digest(payload)
            self._validate_search_identity(
                tenant_id=canonical_tenant_id,
                point=point,
                payload=payload,
            )
            source_id = payload.get("source_id")
            if not isinstance(source_id, str):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search hit has no source identity"
                )
            manifest = manifests.get(source_id)
            if manifest is None:
                manifest = await self._search_manifest_payload(
                    tenant_id=canonical_tenant_id,
                    source_id=source_id,
                )
                manifests[source_id] = manifest
            if source_id not in current_generations:
                current_generations[source_id] = self._current_generation_resolver(
                    canonical_tenant_id,
                    source_id,
                )
            current_generation = current_generations[source_id]
            manifest_document_ids = manifest.get("document_ids")
            manifest_point_ids = manifest.get("document_point_ids")
            expected_document_ids = (
                current_generation.document_ids
                if current_generation is not None
                else ()
            )
            expected_point_ids = tuple(
                sorted(
                    derive_code_projection_point_id(
                        tenant_id=canonical_tenant_id,
                        document_id=document_id,
                        embedding_model=self._config.embedding_model,
                        embedding_model_version=self._config.embedding_model_version,
                    )
                    for document_id in expected_document_ids
                )
            )
            if (
                current_generation is None
                or current_generation.tenant_id != canonical_tenant_id
                or current_generation.source_id != source_id
                or current_generation.operation != "snapshot"
                or current_generation.batch_id != manifest.get("batch_id")
                or current_generation.batch_content_hash_sha256
                != manifest.get("batch_content_hash_sha256")
                or not isinstance(manifest_document_ids, list)
                or tuple(manifest_document_ids) != expected_document_ids
                or not isinstance(manifest_point_ids, list)
                or tuple(manifest_point_ids) != expected_point_ids
            ):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search source generation is not globally applied"
                )
            if (
                manifest.get("operation") != "snapshot"
                or manifest.get("batch_id") != payload.get("batch_id")
                or str(point.id) not in expected_point_ids
                or payload.get("document_id") not in expected_document_ids
            ):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search hit is not part of the applied source generation"
                )
            content_ref = payload.get("content_ref")
            content_hash = payload.get("sanitized_content_hash_sha256")
            byte_count = payload.get("byte_count")
            if not isinstance(content_ref, str) or not isinstance(content_hash, str):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search hit has no content-addressed source"
                )
            if (
                not isinstance(byte_count, int)
                or isinstance(byte_count, bool)
                or not 0 <= byte_count <= MAX_CODE_PROJECTION_SEARCH_DOCUMENT_BYTES
            ):
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content exceeds the serving document ceiling"
                )
            content = self._content_resolver(content_ref)
            if len(content) != byte_count:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content artifact byte count does not match"
                )
            if sha256_hex(content) != content_hash:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content artifact digest does not match"
                )
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content artifact is not UTF-8"
                ) from exc
            if not text:
                raise CodeProjectionQdrantIntegrityError(
                    "Qdrant search content artifact is empty"
                )
            texts.append(text)
        expected_vectors = await self._embed(texts)
        return tuple(
            self._search_hit(
                tenant_id=canonical_tenant_id,
                repository_id=canonical_repository_id,
                point=point,
                expected_vector=expected_vector,
            )
            for point, expected_vector in zip(
                response.points,
                expected_vectors,
                strict=True,
            )
        )


__all__ = [
    "CodeProjectionQdrantIntegrityError",
    "CodeProjectionQdrantStore",
    "ModelCodeProjectionQdrantApplyReport",
    "ModelCodeProjectionQdrantCollection",
    "ModelCodeProjectionQdrantConfig",
    "ModelCodeProjectionQdrantReadback",
    "ModelCodeProjectionCurrentGeneration",
    "ModelCodeProjectionSearchHit",
    "MAX_CODE_PROJECTION_SEARCH_DOCUMENT_BYTES",
    "ProtocolCodeProjectionContentResolver",
    "ProtocolCodeProjectionCurrentGenerationResolver",
    "ProtocolCodeProjectionEmbeddingClient",
    "ProtocolCodeProjectionQdrantStore",
    "derive_code_projection_point_id",
    "derive_code_projection_manifest_point_id",
]
