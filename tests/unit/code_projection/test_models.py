# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Hostile validation tests for the code-projection wire models."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from omniintelligence.code_projection._canonical import canonical_json_bytes
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionDocument,
    ModelCodeProjectionEdge,
    ModelCodeProjectionLabel,
    ModelCodeProjectionNode,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionReplayManifest,
    ModelCodeProjectionSource,
    ModelCodeProjectionSpan,
)

pytestmark = pytest.mark.unit

_SOURCE_ID = f"csrc_v1_{'1' * 64}"
_NODE_ID_A = f"cnode_v1_{'1' * 64}"
_NODE_ID_B = f"cnode_v1_{'2' * 64}"
_EDGE_ID = f"cedge_v1_{'3' * 64}"
_DOCUMENT_ID = f"cdoc_v1_{'4' * 64}"
_BATCH_ID = f"cbatch_v1_{'5' * 64}"
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_ref(digest: str) -> str:
    return f"artifact://sha256/{digest}"


def _source(*, raw_hash: str, byte_count: int) -> ModelCodeProjectionSource:
    return ModelCodeProjectionSource(
        source_id=_SOURCE_ID,
        repository_id="omninode/omniintelligence",
        relative_path="src/pkg/café.py",
        source_version="commit:0123456789abcdef",
        raw_content_hash_sha256=raw_hash,
        artifact_ref=_artifact_ref(raw_hash),
        byte_count=byte_count,
        media_type="text/x-python",
        language="python",
    )


def _cursor(*, sequence: int = 7) -> ModelCodeProjectionCursor:
    return ModelCodeProjectionCursor(
        authority="git:omninode/omniintelligence",
        partition=_SOURCE_ID,
        sequence=sequence,
    )


@pytest.mark.parametrize(
    "authority",
    [" ", " git:omninode/omniintelligence", "git:cafe\N{COMBINING ACUTE ACCENT}"],
)
def test_cursor_authority_must_be_nonempty_canonical_text(authority: str) -> None:
    with pytest.raises(ValidationError, match="authority"):
        ModelCodeProjectionCursor(
            authority=authority,
            partition=_SOURCE_ID,
            sequence=1,
        )


def _policy() -> ModelCodeProjectionPolicy:
    return ModelCodeProjectionPolicy(
        scope_ref="repository:omninode/omniintelligence",
        access_scope="repository",
        visibility="repository",
        redaction_state="sanitized",
        trust_tier="verified_source",
        retention_class="source_controlled",
        policy_version="policy-v1",
        metadata_allowlist_version="allowlist-v1",
    )


def _provenance() -> ModelCodeProjectionProvenance:
    config_hash = _sha256(b"extractor-config-v1")
    manifest_hash = _sha256(b"transform-manifest-v1")
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection",
        producer_version="1.0.0",
        projection_builder_version="1.0.0",
        extractor_name="python-ast",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=config_hash,
        transform_manifest_ref=_artifact_ref(manifest_hash),
        transform_manifest_hash_sha256=manifest_hash,
        labeler_version="deterministic-labeler-v1",
        chunker_version="ast-span-v1",
    )


def _nodes() -> tuple[ModelCodeProjectionNode, ModelCodeProjectionNode]:
    label = ModelCodeProjectionLabel(
        namespace="onex.entity-kind",
        value="class",
        confidence_basis_points=10_000,
        producer="python-ast",
        producer_version="1.0.0",
    )
    declared = ModelCodeProjectionNode(
        node_id=_NODE_ID_A,
        source_id=_SOURCE_ID,
        entity_kind="class",
        resolution_state="declared",
        qualified_name="pkg.café.Example",
        display_name="Example",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=1, end_line=3),
        labels=(label,),
    )
    external = ModelCodeProjectionNode(
        node_id=_NODE_ID_B,
        source_id=_SOURCE_ID,
        entity_kind="external_symbol",
        resolution_state="external_symbol",
        qualified_name="typing.Protocol",
        display_name="Protocol",
        symbol_visibility="public",
    )
    return declared, external


def _edge() -> ModelCodeProjectionEdge:
    evidence_hash = _sha256(b"sanitized-edge-evidence")
    return ModelCodeProjectionEdge(
        edge_id=_EDGE_ID,
        source_id=_SOURCE_ID,
        source_node_id=_NODE_ID_A,
        target_node_id=_NODE_ID_B,
        relationship_kind="implements",
        confidence_basis_points=10_000,
        trust_tier="strong",
        evidence_refs=(_artifact_ref(evidence_hash),),
        context_eligible=True,
    )


def _document(*, source_hash: str) -> ModelCodeProjectionDocument:
    sanitized_hash = _sha256(b"sanitized semantic projection")
    return ModelCodeProjectionDocument(
        document_id=_DOCUMENT_ID,
        source_id=_SOURCE_ID,
        source_hash_sha256=source_hash,
        chunk_key="symbol:pkg.café.Example",
        chunk_kind="symbol",
        anchor_node_id=_NODE_ID_A,
        source_span=ModelCodeProjectionSpan(start_line=1, end_line=3),
        chunker_version="ast-span-v1",
        content_ref=_artifact_ref(sanitized_hash),
        sanitized_content_hash_sha256=sanitized_hash,
        byte_count=len(b"sanitized semantic projection"),
    )


def _batch_with_secret_source() -> tuple[ModelCodeProjectionBatch, bytes]:
    raw_source = b'class Example:\n    """DOCSTRING_SECRET_SENTINEL"""\n    pass\n'
    raw_hash = _sha256(raw_source)
    nodes = _nodes()
    edge = _edge()
    document = _document(source_hash=raw_hash)
    cursor = _cursor()
    manifest = ModelCodeProjectionReplayManifest(
        source_id=_SOURCE_ID,
        cursor=cursor,
        operation="snapshot",
        source_hash_sha256=raw_hash,
        batch_id=_BATCH_ID,
        record_checksum_sha256=_sha256(b"record-set-v1"),
        node_ids=tuple(node.node_id for node in nodes),
        edge_ids=(edge.edge_id,),
        document_ids=(document.document_id,),
    )
    batch = ModelCodeProjectionBatch(
        batch_id=_BATCH_ID,
        operation="snapshot",
        cursor=cursor,
        source=_source(raw_hash=raw_hash, byte_count=len(raw_source)),
        policy=_policy(),
        provenance=_provenance(),
        nodes=nodes,
        edges=(edge,),
        semantic_documents=(document,),
        manifest=manifest,
    )
    return batch, raw_source


def test_models_are_deeply_frozen_and_extra_forbidden() -> None:
    batch, _ = _batch_with_secret_source()

    with pytest.raises(ValidationError, match="frozen"):
        batch.source.relative_path = "src/pkg/changed.py"
    with pytest.raises(ValidationError, match="frozen"):
        batch.nodes[0].labels[0].value = "mutated"
    with pytest.raises(ValidationError, match="extra"):
        ModelCodeProjectionPolicy.model_validate(
            {**batch.policy.model_dump(mode="json"), "ambient_authority": True}
        )

    assert isinstance(batch.nodes, tuple)
    assert isinstance(batch.nodes[0].labels, tuple)
    assert isinstance(batch.edges[0].evidence_refs, tuple)


def _label_payload(confidence: object) -> dict[str, object]:
    return {
        "namespace": "onex.entity-kind",
        "value": "class",
        "confidence_basis_points": confidence,
        "producer": "python-ast",
        "producer_version": "1.0.0",
    }


def _edge_payload(confidence: object) -> dict[str, object]:
    return {
        **_edge().model_dump(),
        "confidence_basis_points": confidence,
    }


@pytest.mark.parametrize("confidence", [0, 7_000, 9_999, 10_000])
@pytest.mark.parametrize(
    ("model", "payload_factory"),
    [
        (ModelCodeProjectionLabel, _label_payload),
        (ModelCodeProjectionEdge, _edge_payload),
    ],
)
def test_confidence_uses_bounded_integer_basis_points(
    model: type[ModelCodeProjectionLabel] | type[ModelCodeProjectionEdge],
    payload_factory: Callable[[object], dict[str, object]],
    confidence: int,
) -> None:
    payload = payload_factory(confidence)
    assert model.model_validate(payload).confidence_basis_points == confidence


@pytest.mark.parametrize("confidence", [-1, 10_001, 7_000.0, True, "7000"])
@pytest.mark.parametrize(
    ("model", "payload_factory"),
    [
        (ModelCodeProjectionLabel, _label_payload),
        (ModelCodeProjectionEdge, _edge_payload),
    ],
)
def test_confidence_rejects_out_of_range_or_coerced_values(
    model: type[ModelCodeProjectionLabel] | type[ModelCodeProjectionEdge],
    payload_factory: Callable[[object], dict[str, object]],
    confidence: object,
) -> None:
    with pytest.raises(ValidationError, match="confidence_basis_points"):
        model.model_validate(payload_factory(confidence))


def test_empty_source_has_explicit_content_addressed_snapshot() -> None:
    cursor = _cursor(sequence=1)
    manifest = ModelCodeProjectionReplayManifest(
        source_id=_SOURCE_ID,
        cursor=cursor,
        operation="snapshot",
        source_hash_sha256=_EMPTY_SHA256,
        batch_id=_BATCH_ID,
        record_checksum_sha256=_sha256(b"empty-record-set"),
    )
    batch = ModelCodeProjectionBatch(
        batch_id=_BATCH_ID,
        operation="snapshot",
        cursor=cursor,
        source=_source(raw_hash=_EMPTY_SHA256, byte_count=0),
        policy=_policy(),
        provenance=_provenance(),
        manifest=manifest,
    )

    assert batch.operation == "snapshot"
    assert batch.source.raw_content_hash_sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert batch.source.artifact_ref == _artifact_ref(_EMPTY_SHA256)
    assert batch.source.byte_count == 0
    assert batch.nodes == batch.edges == batch.semantic_documents == ()


def test_authoritative_batch_contains_references_not_inline_sensitive_text() -> None:
    batch, raw_source = _batch_with_secret_source()
    encoded = canonical_json_bytes(batch.model_dump(mode="json"))

    assert raw_source not in encoded
    assert b"DOCSTRING_SECRET_SENTINEL" not in encoded
    assert b"docstring" not in encoded.lower()
    assert b"source_content" not in encoded
    assert b"chunk_text" not in encoded
    assert b"sanitized semantic projection" not in encoded

    document = batch.semantic_documents[0]
    assert document.content_ref == _artifact_ref(document.sanitized_content_hash_sha256)
    assert set(document.model_fields_set) >= {
        "content_ref",
        "sanitized_content_hash_sha256",
    }
    assert not {"content", "text", "source", "docstring"}.intersection(
        type(document).model_fields
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        r"src\pkg\module.py",
        "/absolute/module.py",
        "src/../module.py",
        "src/module.py\x00hidden",
    ],
)
def test_source_model_requires_precanonicalized_relative_path(
    relative_path: str,
) -> None:
    payload = _source(raw_hash=_EMPTY_SHA256, byte_count=0).model_dump(mode="json")
    payload["relative_path"] = relative_path

    with pytest.raises(ValidationError, match="relative_path"):
        ModelCodeProjectionSource.model_validate(payload)


@pytest.mark.parametrize("collection_name", ["nodes", "edges", "semantic_documents"])
def test_batch_rejects_duplicate_stable_ids(collection_name: str) -> None:
    batch, _ = _batch_with_secret_source()
    payload = batch.model_dump()
    records = payload[collection_name]
    assert isinstance(records, tuple)
    payload[collection_name] = (records[0], records[0])

    with pytest.raises(ValidationError, match="uniquely sorted"):
        ModelCodeProjectionBatch.model_validate(payload)


def test_batch_rejects_dangling_edge_endpoint() -> None:
    batch, _ = _batch_with_secret_source()
    payload = batch.model_dump()
    edge = batch.edges[0].model_dump()
    edge["target_node_id"] = f"cnode_v1_{'9' * 64}"
    payload["edges"] = (ModelCodeProjectionEdge.model_validate(edge),)

    with pytest.raises(ValidationError, match="edge endpoint"):
        ModelCodeProjectionBatch.model_validate(payload)


def test_batch_rejects_dangling_document_anchor() -> None:
    batch, _ = _batch_with_secret_source()
    payload = batch.model_dump()
    document = batch.semantic_documents[0].model_dump()
    document["anchor_node_id"] = f"cnode_v1_{'9' * 64}"
    payload["semantic_documents"] = (
        ModelCodeProjectionDocument.model_validate(document),
    )

    with pytest.raises(ValidationError, match="document anchor"):
        ModelCodeProjectionBatch.model_validate(payload)


@pytest.mark.parametrize(
    ("manifest_update", "expected_error"),
    [
        ({"node_ids": (_NODE_ID_A,)}, "manifest node_ids"),
        ({"edge_ids": ()}, "manifest edge_ids"),
        ({"document_ids": ()}, "manifest document_ids"),
        ({"source_hash_sha256": "9" * 64}, "manifest source hash"),
        ({"batch_id": f"cbatch_v1_{'9' * 64}"}, "manifest batch_id"),
    ],
)
def test_batch_rejects_manifest_drift(
    manifest_update: dict[str, object],
    expected_error: str,
) -> None:
    batch, _ = _batch_with_secret_source()
    payload = batch.model_dump()
    manifest = batch.manifest.model_dump()
    manifest.update(manifest_update)
    payload["manifest"] = ModelCodeProjectionReplayManifest.model_validate(manifest)

    with pytest.raises(ValidationError, match=expected_error):
        ModelCodeProjectionBatch.model_validate(payload)
