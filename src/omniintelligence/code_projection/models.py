# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Immutable wire models for deterministic offline code projections."""

from __future__ import annotations

from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from omniintelligence.code_projection._canonical import (
    normalize_relative_path,
    normalize_repository_id,
    normalize_text,
)

CODE_PROJECTION_SCHEMA_ID: Final[Literal["com.omninode.code-projection-batch"]] = (
    "com.omninode.code-projection-batch"
)
CODE_PROJECTION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CODE_PROJECTION_NAME: Final[Literal["code-intelligence"]] = "code-intelligence"
CODE_PROJECTION_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CODE_PROJECTION_REDUCER_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CODE_PROJECTION_IDENTITY_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CODE_PROJECTION_MANIFEST_VERSION: Final[Literal["1.0.0"]] = "1.0.0"

type ModelOperation = Literal["snapshot", "tombstone"]
type ModelTombstoneReason = Literal["source_deleted", "policy_revoked"]
type ModelSourceLanguage = Literal["python", "typescript", "javascript"]
type ModelAccessScope = Literal["repository", "project", "team", "organization"]
type ModelAccessVisibility = Literal["repository", "organization", "public"]
type ModelRedactionState = Literal["sanitized", "not_required"]
type ModelSourceTrustTier = Literal[
    "verified_source", "declared_source", "untrusted_source"
]
type ModelRetentionClass = Literal["source_controlled", "policy_managed", "ephemeral"]
type ModelResolutionState = Literal["declared", "external_symbol"]
type ModelSymbolVisibility = Literal["public", "protected", "private", "module"]
type ModelEntityKind = Literal[
    "module",
    "class",
    "protocol",
    "model",
    "function",
    "method",
    "import",
    "constant",
    "interface",
    "type_alias",
    "enum",
    "external_symbol",
]
type ModelRelationshipKind = Literal[
    "inherits",
    "imports",
    "defines",
    "implements",
    "calls",
    "references",
    "contains",
]
type ModelRelationshipTrustTier = Literal["strong", "conservative", "weak"]
type ModelChunkKind = Literal["symbol", "module", "source"]
type ModelReplayDecision = Literal["noop", "replace", "stale", "conflict"]

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
SourceId = Annotated[str, StringConstraints(pattern=r"^csrc_v1_[0-9a-f]{64}$")]
NodeId = Annotated[str, StringConstraints(pattern=r"^cnode_v1_[0-9a-f]{64}$")]
EdgeId = Annotated[str, StringConstraints(pattern=r"^cedge_v1_[0-9a-f]{64}$")]
DocumentId = Annotated[str, StringConstraints(pattern=r"^cdoc_v1_[0-9a-f]{64}$")]
BatchId = Annotated[str, StringConstraints(pattern=r"^cbatch_v1_[0-9a-f]{64}$")]
ArtifactRef = Annotated[
    str, StringConstraints(pattern=r"^artifact://sha256/[0-9a-f]{64}$")
]
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=512)]
BoundedVersion = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class _FrozenWireModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        from_attributes=True,
    )


def _require_canonical_text(value: str) -> str:
    if value != normalize_text(value) or not value or value != value.strip():
        msg = "text must be non-empty NFC with no surrounding whitespace"
        raise ValueError(msg)
    return value


class ModelCodeProjectionCursor(_FrozenWireModel):
    """Monotonic progress boundary comparable within one source partition."""

    authority: BoundedText
    partition: SourceId
    sequence: int = Field(ge=1)

    @field_validator("authority")
    @classmethod
    def _require_canonical_authority(cls, value: str) -> str:
        return _require_canonical_text(value)


class ModelCodeProjectionSource(_FrozenWireModel):
    """Logical, content-addressed source identity independent of checkout root."""

    source_id: SourceId
    repository_id: BoundedText
    relative_path: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    source_version: BoundedVersion
    raw_content_hash_sha256: Sha256Hex
    artifact_ref: ArtifactRef
    byte_count: int = Field(ge=0)
    media_type: Literal["text/x-python", "text/typescript", "text/javascript"]
    language: ModelSourceLanguage

    @field_validator("repository_id", "source_version")
    @classmethod
    def _require_canonical_text(cls, value: str) -> str:
        return _require_canonical_text(value)

    @field_validator("repository_id")
    @classmethod
    def _require_logical_repository_id(cls, value: str) -> str:
        if value != normalize_repository_id(value):
            msg = "repository_id must already be canonical"
            raise ValueError(msg)
        return value

    @field_validator("relative_path")
    @classmethod
    def _require_canonical_path(cls, value: str) -> str:
        normalized = normalize_relative_path(value)
        if normalized != value:
            msg = "relative_path must already be canonical POSIX form"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _require_content_addressed_source(self) -> Self:
        expected = f"artifact://sha256/{self.raw_content_hash_sha256}"
        if self.artifact_ref != expected:
            msg = "source artifact_ref must address raw_content_hash_sha256"
            raise ValueError(msg)
        language_media_types = {
            "python": "text/x-python",
            "typescript": "text/typescript",
            "javascript": "text/javascript",
        }
        if language_media_types[self.language] != self.media_type:
            msg = "source media_type must match language"
            raise ValueError(msg)
        return self


class ModelCodeProjectionPolicy(_FrozenWireModel):
    """Closed privacy and access envelope inherited by every record."""

    scope_ref: BoundedText
    access_scope: ModelAccessScope
    visibility: ModelAccessVisibility
    redaction_state: ModelRedactionState
    trust_tier: ModelSourceTrustTier
    retention_class: ModelRetentionClass
    policy_version: BoundedVersion
    metadata_allowlist_version: BoundedVersion

    @field_validator("scope_ref", "policy_version", "metadata_allowlist_version")
    @classmethod
    def _require_canonical_policy_text(cls, value: str) -> str:
        return _require_canonical_text(value)


class ModelCodeProjectionProvenance(_FrozenWireModel):
    """Versioned transforms used to create the projection artifact."""

    producer: BoundedText
    producer_version: BoundedVersion
    projection_builder_version: BoundedVersion
    extractor_name: BoundedText
    extractor_version: BoundedVersion
    extractor_config_hash_sha256: Sha256Hex
    transform_manifest_ref: ArtifactRef
    transform_manifest_hash_sha256: Sha256Hex
    labeler_version: BoundedVersion | None = None
    chunker_version: BoundedVersion | None = None

    @field_validator(
        "producer",
        "producer_version",
        "projection_builder_version",
        "extractor_name",
        "extractor_version",
        "labeler_version",
        "chunker_version",
    )
    @classmethod
    def _require_canonical_provenance_text(cls, value: str | None) -> str | None:
        return _require_canonical_text(value) if value is not None else None

    @model_validator(mode="after")
    def _require_content_addressed_manifest(self) -> Self:
        expected = f"artifact://sha256/{self.transform_manifest_hash_sha256}"
        if self.transform_manifest_ref != expected:
            msg = "transform_manifest_ref must address transform_manifest_hash_sha256"
            raise ValueError(msg)
        return self


class ModelCodeProjectionSpan(_FrozenWireModel):
    """One-based inclusive source span."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _require_ordered_span(self) -> Self:
        if self.end_line < self.start_line:
            msg = "source span end_line must be at or after start_line"
            raise ValueError(msg)
        return self


class ModelCodeProjectionLabel(_FrozenWireModel):
    """Bounded deterministic label shape reserved for A1."""

    namespace: BoundedText
    value: BoundedText
    confidence_basis_points: int = Field(ge=0, le=10_000)
    producer: BoundedText
    producer_version: BoundedVersion

    @field_validator("namespace", "value", "producer", "producer_version")
    @classmethod
    def _require_canonical_label_text(cls, value: str) -> str:
        return _require_canonical_text(value)


class ModelCodeProjectionNode(_FrozenWireModel):
    """Source-owned declared or explicit external-symbol graph node."""

    node_id: NodeId
    source_id: SourceId
    entity_kind: ModelEntityKind
    resolution_state: ModelResolutionState
    qualified_name: BoundedText
    display_name: BoundedText
    symbol_visibility: ModelSymbolVisibility
    source_span: ModelCodeProjectionSpan | None = None
    labels: tuple[ModelCodeProjectionLabel, ...] = Field(default=(), max_length=32)

    @field_validator("qualified_name", "display_name")
    @classmethod
    def _require_canonical_names(cls, value: str) -> str:
        return _require_canonical_text(value)

    @model_validator(mode="after")
    def _require_resolution_shape(self) -> Self:
        is_external_kind = self.entity_kind == "external_symbol"
        is_external_resolution = self.resolution_state == "external_symbol"
        if is_external_kind != is_external_resolution:
            msg = "external_symbol kind and resolution_state must agree"
            raise ValueError(msg)
        label_keys = tuple(
            (
                label.namespace,
                label.value,
                label.producer,
                label.producer_version,
                label.confidence_basis_points,
            )
            for label in self.labels
        )
        if label_keys != tuple(sorted(label_keys)) or len(set(label_keys)) != len(
            label_keys
        ):
            msg = "node labels must be uniquely sorted by their canonical key"
            raise ValueError(msg)
        return self


class ModelCodeProjectionEdge(_FrozenWireModel):
    """Closed relationship between nodes owned by the same source snapshot."""

    edge_id: EdgeId
    source_id: SourceId
    source_node_id: NodeId
    target_node_id: NodeId
    relationship_kind: ModelRelationshipKind
    confidence_basis_points: int = Field(ge=0, le=10_000)
    trust_tier: ModelRelationshipTrustTier
    evidence_refs: tuple[ArtifactRef, ...] = Field(default=(), max_length=32)
    context_eligible: bool

    @model_validator(mode="after")
    def _require_sorted_evidence(self) -> Self:
        if self.evidence_refs != tuple(sorted(self.evidence_refs)) or len(
            set(self.evidence_refs)
        ) != len(self.evidence_refs):
            msg = "edge evidence_refs must be uniquely sorted"
            raise ValueError(msg)
        return self


class ModelCodeProjectionDocument(_FrozenWireModel):
    """Content-addressed semantic document with no inline source text."""

    document_id: DocumentId
    source_id: SourceId
    source_hash_sha256: Sha256Hex
    chunk_key: BoundedText
    chunk_kind: ModelChunkKind
    anchor_node_id: NodeId | None = None
    source_span: ModelCodeProjectionSpan | None = None
    chunker_version: BoundedVersion
    content_ref: ArtifactRef
    sanitized_content_hash_sha256: Sha256Hex
    byte_count: int = Field(ge=0)

    @field_validator("chunk_key", "chunker_version")
    @classmethod
    def _require_canonical_document_text(cls, value: str) -> str:
        return _require_canonical_text(value)

    @model_validator(mode="after")
    def _require_content_addressed_document(self) -> Self:
        expected = f"artifact://sha256/{self.sanitized_content_hash_sha256}"
        if self.content_ref != expected:
            msg = "document content_ref must address sanitized_content_hash_sha256"
            raise ValueError(msg)
        return self


class ModelCodeProjectionReplayManifest(_FrozenWireModel):
    """Exact source-owned identifiers and checksums needed for replay planning."""

    manifest_version: Literal["1.0.0"] = CODE_PROJECTION_MANIFEST_VERSION
    projection_version: Literal["1.0.0"] = CODE_PROJECTION_VERSION
    reducer_version: Literal["1.0.0"] = CODE_PROJECTION_REDUCER_VERSION
    identity_version: Literal["1.0.0"] = CODE_PROJECTION_IDENTITY_VERSION
    source_id: SourceId
    cursor: ModelCodeProjectionCursor
    operation: ModelOperation
    source_hash_sha256: Sha256Hex
    batch_id: BatchId
    record_checksum_sha256: Sha256Hex
    node_ids: tuple[NodeId, ...] = ()
    edge_ids: tuple[EdgeId, ...] = ()
    document_ids: tuple[DocumentId, ...] = ()

    @model_validator(mode="after")
    def _require_sorted_owned_ids(self) -> Self:
        for name, values in (
            ("node_ids", self.node_ids),
            ("edge_ids", self.edge_ids),
            ("document_ids", self.document_ids),
        ):
            if values != tuple(sorted(values)) or len(set(values)) != len(values):
                msg = f"manifest {name} must be uniquely sorted"
                raise ValueError(msg)
        if self.cursor.partition != self.source_id:
            msg = "manifest cursor partition must equal source_id"
            raise ValueError(msg)
        return self


class ModelCodeProjectionBatch(_FrozenWireModel):
    """One source-scoped authoritative projection snapshot or tombstone."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        from_attributes=True,
        json_schema_extra={"$id": "urn:omninode:code-projection:batch:v1"},
    )

    kind: Literal["code_projection_batch"] = "code_projection_batch"
    schema_id: Literal["com.omninode.code-projection-batch"] = CODE_PROJECTION_SCHEMA_ID
    schema_version: Literal["1.0.0"] = CODE_PROJECTION_SCHEMA_VERSION
    projection_name: Literal["code-intelligence"] = CODE_PROJECTION_NAME
    projection_version: Literal["1.0.0"] = CODE_PROJECTION_VERSION
    reducer_version: Literal["1.0.0"] = CODE_PROJECTION_REDUCER_VERSION
    identity_version: Literal["1.0.0"] = CODE_PROJECTION_IDENTITY_VERSION
    batch_id: BatchId
    operation: ModelOperation
    tombstone_reason: ModelTombstoneReason | None = None
    cursor: ModelCodeProjectionCursor
    source: ModelCodeProjectionSource
    policy: ModelCodeProjectionPolicy
    provenance: ModelCodeProjectionProvenance
    nodes: tuple[ModelCodeProjectionNode, ...] = ()
    edges: tuple[ModelCodeProjectionEdge, ...] = ()
    semantic_documents: tuple[ModelCodeProjectionDocument, ...] = ()
    manifest: ModelCodeProjectionReplayManifest

    @model_validator(mode="after")
    def _require_closed_source_snapshot(self) -> Self:
        if self.cursor.partition != self.source.source_id:
            msg = "batch cursor partition must equal source.source_id"
            raise ValueError(msg)
        if self.operation == "snapshot" and self.tombstone_reason is not None:
            msg = "snapshot must not carry tombstone_reason"
            raise ValueError(msg)
        if self.operation == "tombstone" and self.tombstone_reason is None:
            msg = "tombstone must carry tombstone_reason"
            raise ValueError(msg)
        if self.operation == "tombstone" and (
            self.nodes or self.edges or self.semantic_documents
        ):
            msg = "tombstone must not carry active projection records"
            raise ValueError(msg)

        node_ids = tuple(node.node_id for node in self.nodes)
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        document_ids = tuple(
            document.document_id for document in self.semantic_documents
        )
        for name, values in (
            ("nodes", node_ids),
            ("edges", edge_ids),
            ("semantic_documents", document_ids),
        ):
            if values != tuple(sorted(values)) or len(set(values)) != len(values):
                msg = f"batch {name} must be uniquely sorted by stable ID"
                raise ValueError(msg)

        node_id_set = set(node_ids)
        for node in self.nodes:
            if node.source_id != self.source.source_id:
                msg = "every node must be owned by batch source_id"
                raise ValueError(msg)
        for edge in self.edges:
            if edge.source_id != self.source.source_id:
                msg = "every edge must be owned by batch source_id"
                raise ValueError(msg)
            if (
                edge.source_node_id not in node_id_set
                or edge.target_node_id not in node_id_set
            ):
                msg = "every edge endpoint must resolve inside the batch"
                raise ValueError(msg)
        for document in self.semantic_documents:
            if document.source_id != self.source.source_id:
                msg = "every semantic document must be owned by batch source_id"
                raise ValueError(msg)
            if document.source_hash_sha256 != self.source.raw_content_hash_sha256:
                msg = "document source hash must equal batch source hash"
                raise ValueError(msg)
            if (
                document.anchor_node_id is not None
                and document.anchor_node_id not in node_id_set
            ):
                msg = "semantic document anchor must resolve inside the batch"
                raise ValueError(msg)

        if self.manifest.source_id != self.source.source_id:
            msg = "manifest source_id must equal batch source_id"
            raise ValueError(msg)
        if self.manifest.cursor != self.cursor:
            msg = "manifest cursor must equal batch cursor"
            raise ValueError(msg)
        if self.manifest.operation != self.operation:
            msg = "manifest operation must equal batch operation"
            raise ValueError(msg)
        if self.manifest.source_hash_sha256 != self.source.raw_content_hash_sha256:
            msg = "manifest source hash must equal batch source hash"
            raise ValueError(msg)
        if self.manifest.batch_id != self.batch_id:
            msg = "manifest batch_id must equal batch batch_id"
            raise ValueError(msg)
        if self.manifest.node_ids != node_ids:
            msg = "manifest node_ids must exactly describe the batch"
            raise ValueError(msg)
        if self.manifest.edge_ids != edge_ids:
            msg = "manifest edge_ids must exactly describe the batch"
            raise ValueError(msg)
        if self.manifest.document_ids != document_ids:
            msg = "manifest document_ids must exactly describe the batch"
            raise ValueError(msg)
        return self


class ModelCodeProjectionReplayPlan(_FrozenWireModel):
    """Pure deterministic change plan for the later stateful A2 reducer."""

    decision: ModelReplayDecision
    source_id: SourceId
    previous_batch_id: BatchId | None = None
    current_batch_id: BatchId
    previous_sequence: int | None = Field(default=None, ge=1)
    current_sequence: int = Field(ge=1)
    delete_node_ids: tuple[NodeId, ...] = ()
    upsert_node_ids: tuple[NodeId, ...] = ()
    delete_edge_ids: tuple[EdgeId, ...] = ()
    upsert_edge_ids: tuple[EdgeId, ...] = ()
    delete_document_ids: tuple[DocumentId, ...] = ()
    upsert_document_ids: tuple[DocumentId, ...] = ()

    @model_validator(mode="after")
    def _require_canonical_change_sets(self) -> Self:
        collections = (
            self.delete_node_ids,
            self.upsert_node_ids,
            self.delete_edge_ids,
            self.upsert_edge_ids,
            self.delete_document_ids,
            self.upsert_document_ids,
        )
        for values in collections:
            if values != tuple(sorted(values)) or len(set(values)) != len(values):
                msg = "replay change sets must be uniquely sorted"
                raise ValueError(msg)
        if self.decision != "replace" and any(collections):
            msg = "only replace replay plans may mutate records"
            raise ValueError(msg)
        return self
