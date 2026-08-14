# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical builders, codec, and replay planner for code projections.

This module is deliberately storage- and runtime-free.  It turns explicit,
content-addressed projection metadata into deterministic wire bytes and proves
the integrity of those bytes before a later consumer is allowed to plan state
changes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, cast

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    decode_json_no_duplicates,
    normalize_relative_path,
    normalize_text,
    sha256_hex,
    stable_id,
)
from omniintelligence.code_projection.models import (
    CODE_PROJECTION_IDENTITY_VERSION,
    CODE_PROJECTION_MANIFEST_VERSION,
    CODE_PROJECTION_VERSION,
    ModelChunkKind,
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionDocument,
    ModelCodeProjectionEdge,
    ModelCodeProjectionLabel,
    ModelCodeProjectionNode,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionReplayManifest,
    ModelCodeProjectionReplayPlan,
    ModelCodeProjectionSource,
    ModelCodeProjectionSpan,
    ModelEntityKind,
    ModelOperation,
    ModelRelationshipKind,
    ModelRelationshipTrustTier,
    ModelReplayDecision,
    ModelResolutionState,
    ModelSourceLanguage,
    ModelSymbolVisibility,
    ModelTombstoneReason,
)

_SOURCE_ID_DOMAIN = "omninode.code-projection.source.v1"
_NODE_ID_DOMAIN = "omninode.code-projection.node.v1"
_EDGE_ID_DOMAIN = "omninode.code-projection.edge.v1"
_DOCUMENT_ID_DOMAIN = "omninode.code-projection.document.v1"
_BATCH_ID_DOMAIN = "omninode.code-projection.batch.v1"

_SOURCE_ID_PREFIX = "csrc_v1_"
_NODE_ID_PREFIX = "cnode_v1_"
_EDGE_ID_PREFIX = "cedge_v1_"
_DOCUMENT_ID_PREFIX = "cdoc_v1_"
_BATCH_ID_PREFIX = "cbatch_v1_"

type _SourceMediaType = Literal["text/x-python", "text/typescript", "text/javascript"]

_LANGUAGE_MEDIA_TYPES: dict[ModelSourceLanguage, _SourceMediaType] = {
    "python": "text/x-python",
    "typescript": "text/typescript",
    "javascript": "text/javascript",
}

# V1 has no field capable of carrying these values.  Checking the decoded key
# names before Pydantic validation makes the privacy failure explicit instead
# of relying only on ``extra="forbid"`` diagnostics.
_FORBIDDEN_INLINE_CONTENT_KEYS = frozenset(
    {
        "chunk_text",
        "content",
        "docstring",
        "evidence",
        "raw_content",
        "source_code",
        "source_content",
        "source_text",
        "text",
    }
)


def _artifact_ref(digest: str) -> str:
    return f"artifact://sha256/{digest}"


def _source_id(*, repository_id: str, relative_path: str) -> str:
    return stable_id(
        prefix=_SOURCE_ID_PREFIX,
        domain=_SOURCE_ID_DOMAIN,
        payload={
            "identity_version": CODE_PROJECTION_IDENTITY_VERSION,
            "relative_path": relative_path,
            "repository_id": repository_id,
        },
    )


def _node_id(
    *,
    source_id: str,
    entity_kind: ModelEntityKind,
    qualified_name: str,
) -> str:
    return stable_id(
        prefix=_NODE_ID_PREFIX,
        domain=_NODE_ID_DOMAIN,
        payload={
            "entity_kind": entity_kind,
            "identity_version": CODE_PROJECTION_IDENTITY_VERSION,
            "qualified_name": qualified_name,
            "source_id": source_id,
        },
    )


def _edge_id(
    *,
    source_id: str,
    source_node_id: str,
    target_node_id: str,
    relationship_kind: ModelRelationshipKind,
) -> str:
    return stable_id(
        prefix=_EDGE_ID_PREFIX,
        domain=_EDGE_ID_DOMAIN,
        payload={
            "identity_version": CODE_PROJECTION_IDENTITY_VERSION,
            "relationship_kind": relationship_kind,
            "source_id": source_id,
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
        },
    )


def _document_id(
    *,
    source_id: str,
    source_hash_sha256: str,
    chunk_key: str,
    chunk_kind: ModelChunkKind,
    anchor_node_id: str | None,
    source_span: ModelCodeProjectionSpan | None,
    chunker_version: str,
    sanitized_content_hash_sha256: str,
) -> str:
    return stable_id(
        prefix=_DOCUMENT_ID_PREFIX,
        domain=_DOCUMENT_ID_DOMAIN,
        payload={
            "anchor_node_id": anchor_node_id,
            "chunk_key": chunk_key,
            "chunk_kind": chunk_kind,
            "chunker_version": chunker_version,
            "identity_version": CODE_PROJECTION_IDENTITY_VERSION,
            "sanitized_content_hash_sha256": sanitized_content_hash_sha256,
            "source_id": source_id,
            "source_hash_sha256": source_hash_sha256,
            "source_span": (
                source_span.model_dump(mode="json") if source_span is not None else None
            ),
        },
    )


def _label_sort_key(
    label: ModelCodeProjectionLabel,
) -> tuple[str, str, str, str, int]:
    return (
        label.namespace,
        label.value,
        label.producer,
        label.producer_version,
        label.confidence_basis_points,
    )


def make_code_source(
    *,
    repository_id: str,
    relative_path: str,
    source_version: str,
    raw_content_hash_sha256: str,
    byte_count: int,
    language: ModelSourceLanguage,
    artifact_ref: str | None = None,
    media_type: _SourceMediaType | None = None,
) -> ModelCodeProjectionSource:
    """Build one canonical logical source without accepting inline source bytes."""

    canonical_repository_id = normalize_text(repository_id)
    canonical_relative_path = normalize_relative_path(relative_path)
    canonical_source_version = normalize_text(source_version)
    resolved_artifact_ref = artifact_ref or _artifact_ref(raw_content_hash_sha256)
    resolved_media_type = media_type or _LANGUAGE_MEDIA_TYPES[language]
    return ModelCodeProjectionSource(
        source_id=_source_id(
            repository_id=canonical_repository_id,
            relative_path=canonical_relative_path,
        ),
        repository_id=canonical_repository_id,
        relative_path=canonical_relative_path,
        source_version=canonical_source_version,
        raw_content_hash_sha256=raw_content_hash_sha256,
        artifact_ref=resolved_artifact_ref,
        byte_count=byte_count,
        media_type=resolved_media_type,
        language=language,
    )


def make_code_node(
    *,
    source_id: str,
    entity_kind: ModelEntityKind,
    qualified_name: str,
    display_name: str | None = None,
    resolution_state: ModelResolutionState | None = None,
    symbol_visibility: ModelSymbolVisibility = "module",
    source_span: ModelCodeProjectionSpan | None = None,
    labels: Sequence[ModelCodeProjectionLabel] = (),
) -> ModelCodeProjectionNode:
    """Build a stable source-owned graph node."""

    canonical_qualified_name = normalize_text(qualified_name)
    canonical_display_name = normalize_text(
        display_name
        if display_name is not None
        else canonical_qualified_name.rsplit(".", maxsplit=1)[-1]
    )
    resolved_state: ModelResolutionState = (
        "external_symbol" if entity_kind == "external_symbol" else "declared"
    )
    if resolution_state is not None:
        resolved_state = resolution_state
    canonical_labels = tuple(sorted(labels, key=_label_sort_key))
    return ModelCodeProjectionNode(
        node_id=_node_id(
            source_id=source_id,
            entity_kind=entity_kind,
            qualified_name=canonical_qualified_name,
        ),
        source_id=source_id,
        entity_kind=entity_kind,
        resolution_state=resolved_state,
        qualified_name=canonical_qualified_name,
        display_name=canonical_display_name,
        symbol_visibility=symbol_visibility,
        source_span=source_span,
        labels=canonical_labels,
    )


def make_code_edge(
    *,
    source_id: str,
    source_node_id: str,
    target_node_id: str,
    relationship_kind: ModelRelationshipKind,
    confidence_basis_points: int = 10_000,
    trust_tier: ModelRelationshipTrustTier = "strong",
    evidence_refs: Sequence[str] = (),
    context_eligible: bool = True,
) -> ModelCodeProjectionEdge:
    """Build a stable graph edge whose endpoints are validated at batch time."""

    return ModelCodeProjectionEdge(
        edge_id=_edge_id(
            source_id=source_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_kind=relationship_kind,
        ),
        source_id=source_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relationship_kind=relationship_kind,
        confidence_basis_points=confidence_basis_points,
        trust_tier=trust_tier,
        evidence_refs=tuple(sorted(evidence_refs)),
        context_eligible=context_eligible,
    )


def make_code_chunk(
    *,
    source_id: str,
    source_hash_sha256: str,
    chunk_key: str,
    chunk_kind: ModelChunkKind,
    chunker_version: str,
    sanitized_content_hash_sha256: str,
    byte_count: int,
    anchor_node_id: str | None = None,
    source_span: ModelCodeProjectionSpan | None = None,
    content_ref: str | None = None,
) -> ModelCodeProjectionDocument:
    """Build content-addressed semantic metadata without accepting chunk text."""

    canonical_chunk_key = normalize_text(chunk_key)
    canonical_chunker_version = normalize_text(chunker_version)
    return ModelCodeProjectionDocument(
        document_id=_document_id(
            source_id=source_id,
            source_hash_sha256=source_hash_sha256,
            chunk_key=canonical_chunk_key,
            chunk_kind=chunk_kind,
            anchor_node_id=anchor_node_id,
            source_span=source_span,
            chunker_version=canonical_chunker_version,
            sanitized_content_hash_sha256=sanitized_content_hash_sha256,
        ),
        source_id=source_id,
        source_hash_sha256=source_hash_sha256,
        chunk_key=canonical_chunk_key,
        chunk_kind=chunk_kind,
        anchor_node_id=anchor_node_id,
        source_span=source_span,
        chunker_version=canonical_chunker_version,
        content_ref=content_ref or _artifact_ref(sanitized_content_hash_sha256),
        sanitized_content_hash_sha256=sanitized_content_hash_sha256,
        byte_count=byte_count,
    )


def _record_payload(
    *,
    nodes: Sequence[ModelCodeProjectionNode],
    edges: Sequence[ModelCodeProjectionEdge],
    semantic_documents: Sequence[ModelCodeProjectionDocument],
) -> dict[str, object]:
    return {
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "semantic_documents": [
            document.model_dump(mode="json") for document in semantic_documents
        ],
    }


def _record_checksum(
    *,
    nodes: Sequence[ModelCodeProjectionNode],
    edges: Sequence[ModelCodeProjectionEdge],
    semantic_documents: Sequence[ModelCodeProjectionDocument],
) -> str:
    return sha256_hex(
        canonical_json_bytes(
            _record_payload(
                nodes=nodes,
                edges=edges,
                semantic_documents=semantic_documents,
            )
        )
    )


def _batch_identity_payload(batch: ModelCodeProjectionBatch) -> dict[str, object]:
    payload = cast(dict[str, object], batch.model_dump(mode="json"))
    payload = dict(payload)
    payload.pop("batch_id")
    manifest_value = payload.get("manifest")
    if not isinstance(manifest_value, Mapping):
        msg = "batch manifest must serialize as an object"
        raise ValueError(msg)
    manifest = dict(cast(Mapping[str, object], manifest_value))
    manifest.pop("batch_id", None)
    payload["manifest"] = manifest
    return payload


def _expected_batch_id(batch: ModelCodeProjectionBatch) -> str:
    return stable_id(
        prefix=_BATCH_ID_PREFIX,
        domain=_BATCH_ID_DOMAIN,
        payload=_batch_identity_payload(batch),
    )


def build_code_projection_batch(
    *,
    source: ModelCodeProjectionSource,
    cursor: ModelCodeProjectionCursor,
    policy: ModelCodeProjectionPolicy,
    provenance: ModelCodeProjectionProvenance,
    nodes: Sequence[ModelCodeProjectionNode] = (),
    edges: Sequence[ModelCodeProjectionEdge] = (),
    semantic_documents: Sequence[ModelCodeProjectionDocument] = (),
    operation: ModelOperation = "snapshot",
    tombstone_reason: ModelTombstoneReason | None = None,
) -> ModelCodeProjectionBatch:
    """Build a canonical batch and its replay manifest from immutable records."""

    canonical_nodes = tuple(sorted(nodes, key=lambda item: item.node_id))
    canonical_edges = tuple(sorted(edges, key=lambda item: item.edge_id))
    canonical_documents = tuple(
        sorted(semantic_documents, key=lambda item: item.document_id)
    )
    placeholder_batch_id = f"{_BATCH_ID_PREFIX}{'0' * 64}"
    checksum = _record_checksum(
        nodes=canonical_nodes,
        edges=canonical_edges,
        semantic_documents=canonical_documents,
    )
    placeholder_manifest = ModelCodeProjectionReplayManifest(
        manifest_version=CODE_PROJECTION_MANIFEST_VERSION,
        source_id=source.source_id,
        cursor=cursor,
        operation=operation,
        source_hash_sha256=source.raw_content_hash_sha256,
        batch_id=placeholder_batch_id,
        record_checksum_sha256=checksum,
        node_ids=tuple(node.node_id for node in canonical_nodes),
        edge_ids=tuple(edge.edge_id for edge in canonical_edges),
        document_ids=tuple(document.document_id for document in canonical_documents),
    )
    placeholder_batch = ModelCodeProjectionBatch(
        batch_id=placeholder_batch_id,
        operation=operation,
        tombstone_reason=tombstone_reason,
        cursor=cursor,
        source=source,
        policy=policy,
        provenance=provenance,
        nodes=canonical_nodes,
        edges=canonical_edges,
        semantic_documents=canonical_documents,
        manifest=placeholder_manifest,
    )
    batch_id = _expected_batch_id(placeholder_batch)
    manifest = placeholder_manifest.model_copy(update={"batch_id": batch_id})
    batch = placeholder_batch.model_copy(
        update={"batch_id": batch_id, "manifest": manifest}
    )
    return _validate_batch_integrity(batch)


def _validate_stable_ids(batch: ModelCodeProjectionBatch) -> None:
    expected_source_id = _source_id(
        repository_id=batch.source.repository_id,
        relative_path=batch.source.relative_path,
    )
    if batch.source.source_id != expected_source_id:
        msg = "source_id does not match canonical repository identity"
        raise ValueError(msg)

    for node in batch.nodes:
        expected_node_id = _node_id(
            source_id=batch.source.source_id,
            entity_kind=node.entity_kind,
            qualified_name=node.qualified_name,
        )
        if node.node_id != expected_node_id:
            msg = f"node_id is not canonical for {node.qualified_name!r}"
            raise ValueError(msg)

    for edge in batch.edges:
        expected_edge_id = _edge_id(
            source_id=batch.source.source_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relationship_kind=edge.relationship_kind,
        )
        if edge.edge_id != expected_edge_id:
            msg = f"edge_id is not canonical: {edge.edge_id}"
            raise ValueError(msg)

    for document in batch.semantic_documents:
        expected_document_id = _document_id(
            source_id=batch.source.source_id,
            source_hash_sha256=document.source_hash_sha256,
            chunk_key=document.chunk_key,
            chunk_kind=document.chunk_kind,
            anchor_node_id=document.anchor_node_id,
            source_span=document.source_span,
            chunker_version=document.chunker_version,
            sanitized_content_hash_sha256=document.sanitized_content_hash_sha256,
        )
        if document.document_id != expected_document_id:
            msg = f"document_id is not canonical: {document.document_id}"
            raise ValueError(msg)


def _revalidate_batch(batch: ModelCodeProjectionBatch) -> ModelCodeProjectionBatch:
    # Re-validation prevents ``model_copy(update=...)`` from bypassing the closed
    # snapshot invariants before serialization or replay planning.
    payload = canonical_json_bytes(batch.model_dump(mode="json"))
    return ModelCodeProjectionBatch.model_validate_json(payload)


def _validate_batch_integrity(
    batch: ModelCodeProjectionBatch,
) -> ModelCodeProjectionBatch:
    validated = _revalidate_batch(batch)
    if validated.provenance.projection_builder_version != CODE_PROJECTION_VERSION:
        msg = "projection_builder_version is not supported by this codec"
        raise ValueError(msg)
    _validate_stable_ids(validated)

    expected_record_checksum = _record_checksum(
        nodes=validated.nodes,
        edges=validated.edges,
        semantic_documents=validated.semantic_documents,
    )
    if validated.manifest.record_checksum_sha256 != expected_record_checksum:
        msg = "manifest record checksum does not match batch records"
        raise ValueError(msg)

    expected_batch_id = _expected_batch_id(validated)
    if validated.batch_id != expected_batch_id:
        msg = "batch_id does not match canonical batch payload"
        raise ValueError(msg)
    return validated


def serialize_code_projection_batch(batch: ModelCodeProjectionBatch) -> bytes:
    """Return canonical JSON framed by exactly one repository-safe LF byte."""

    validated = _validate_batch_integrity(batch)
    return canonical_json_bytes(validated.model_dump(mode="json")) + b"\n"


def _reject_inline_content_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in cast(Mapping[object, object], value).items():
            if not isinstance(raw_key, str):
                msg = f"projection JSON key at {path} must be a string"
                raise ValueError(msg)
            if raw_key in _FORBIDDEN_INLINE_CONTENT_KEYS:
                msg = f"inline content field is forbidden at {path}.{raw_key}"
                raise ValueError(msg)
            _reject_inline_content_keys(child, path=f"{path}.{raw_key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_inline_content_keys(child, path=f"{path}[{index}]")


def parse_code_projection_batch(payload: bytes | str) -> ModelCodeProjectionBatch:
    """Parse only exact canonical v1 bytes and reject all integrity drift."""

    decoded = decode_json_no_duplicates(payload)
    _reject_inline_content_keys(decoded)
    try:
        wire_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
    except UnicodeEncodeError as exc:
        msg = "projection payload must be valid UTF-8"
        raise ValueError(msg) from exc
    batch = _validate_batch_integrity(
        ModelCodeProjectionBatch.model_validate_json(wire_bytes)
    )
    canonical = serialize_code_projection_batch(batch)
    if wire_bytes != canonical:
        msg = "projection payload is valid JSON but not exact canonical bytes"
        raise ValueError(msg)
    return batch


def _revalidate_manifest(
    manifest: ModelCodeProjectionReplayManifest,
) -> ModelCodeProjectionReplayManifest:
    return ModelCodeProjectionReplayManifest.model_validate_json(
        canonical_json_bytes(manifest.model_dump(mode="json"))
    )


def plan_code_projection_replay(
    incoming: ModelCodeProjectionBatch,
    current: ModelCodeProjectionReplayManifest | None = None,
) -> ModelCodeProjectionReplayPlan:
    """Plan source-scoped replay using only the contracted monotonic cursor."""

    incoming = _validate_batch_integrity(incoming)
    current_manifest = _revalidate_manifest(current) if current is not None else None
    if current_manifest is not None:
        if current_manifest.source_id != incoming.source.source_id:
            msg = "replay manifests from different sources are not comparable"
            raise ValueError(msg)
        if current_manifest.cursor.authority != incoming.cursor.authority:
            msg = "replay cursors from different authorities are not comparable"
            raise ValueError(msg)

    incoming_sequence = incoming.cursor.sequence
    empty: tuple[str, ...] = ()

    if current_manifest is not None:
        applied_sequence = current_manifest.cursor.sequence
        if incoming_sequence < applied_sequence:
            return ModelCodeProjectionReplayPlan(
                decision="stale",
                source_id=incoming.source.source_id,
                previous_batch_id=current_manifest.batch_id,
                current_batch_id=incoming.batch_id,
                previous_sequence=applied_sequence,
                current_sequence=incoming_sequence,
            )

        if incoming_sequence == applied_sequence:
            decision: ModelReplayDecision = (
                "noop" if incoming.batch_id == current_manifest.batch_id else "conflict"
            )
            return ModelCodeProjectionReplayPlan(
                decision=decision,
                source_id=incoming.source.source_id,
                previous_batch_id=current_manifest.batch_id,
                current_batch_id=incoming.batch_id,
                previous_sequence=applied_sequence,
                current_sequence=incoming_sequence,
            )

    previous_sequence = (
        current_manifest.cursor.sequence if current_manifest is not None else None
    )

    previous_node_ids = (
        current_manifest.node_ids if current_manifest is not None else empty
    )
    previous_edge_ids = (
        current_manifest.edge_ids if current_manifest is not None else empty
    )
    previous_document_ids = (
        current_manifest.document_ids if current_manifest is not None else empty
    )
    incoming_node_ids = incoming.manifest.node_ids
    incoming_edge_ids = incoming.manifest.edge_ids
    incoming_document_ids = incoming.manifest.document_ids
    return ModelCodeProjectionReplayPlan(
        decision="replace",
        source_id=incoming.source.source_id,
        previous_batch_id=(
            current_manifest.batch_id if current_manifest is not None else None
        ),
        current_batch_id=incoming.batch_id,
        previous_sequence=previous_sequence,
        current_sequence=incoming_sequence,
        delete_node_ids=tuple(sorted(set(previous_node_ids) - set(incoming_node_ids))),
        upsert_node_ids=incoming_node_ids,
        delete_edge_ids=tuple(sorted(set(previous_edge_ids) - set(incoming_edge_ids))),
        upsert_edge_ids=incoming_edge_ids,
        delete_document_ids=tuple(
            sorted(set(previous_document_ids) - set(incoming_document_ids))
        ),
        upsert_document_ids=incoming_document_ids,
    )


def encode_canonical_batch(batch: ModelCodeProjectionBatch) -> bytes:
    """Alias spelling for consumers that treat this module as a codec."""

    return serialize_code_projection_batch(batch)


def decode_canonical_batch(payload: bytes | str) -> ModelCodeProjectionBatch:
    """Alias spelling for consumers that treat this module as a codec."""

    return parse_code_projection_batch(payload)


__all__ = [
    "build_code_projection_batch",
    "decode_canonical_batch",
    "encode_canonical_batch",
    "make_code_chunk",
    "make_code_edge",
    "make_code_node",
    "make_code_source",
    "parse_code_projection_batch",
    "plan_code_projection_replay",
    "serialize_code_projection_batch",
]
