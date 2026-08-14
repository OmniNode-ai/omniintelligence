# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adversarial canonical-codec and source-scoped replay tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

import pytest

from omniintelligence.code_projection import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionReplayPlan,
    ModelCodeProjectionSpan,
    build_code_projection_batch,
    decode_canonical_batch,
    encode_canonical_batch,
    make_code_chunk,
    make_code_edge,
    make_code_node,
    make_code_source,
    plan_code_projection_replay,
)
from omniintelligence.code_projection._canonical import (
    DuplicateJsonKeyError,
    canonical_json_bytes,
)

pytestmark = pytest.mark.unit

_RAW_A = b'class Example:\n    """RAW_SECRET_SENTINEL"""\n    pass\n'
_RAW_B = b"class Replacement:\n    pass\n"
_SANITIZED_SENTINEL = b"SANITIZED_TEXT_MUST_NOT_BE_INLINE"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_ref(value: bytes) -> str:
    return f"artifact://sha256/{_sha256(value)}"


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
    manifest_bytes = b"code-projection-transform-manifest-v1"
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection",
        producer_version="1.0.0",
        projection_builder_version="1.0.0",
        extractor_name="python-ast",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=_sha256(b"extractor-config-v1"),
        transform_manifest_ref=_artifact_ref(manifest_bytes),
        transform_manifest_hash_sha256=_sha256(manifest_bytes),
        labeler_version="deterministic-labeler-v1",
        chunker_version="ast-span-v1",
    )


def _build_batch(
    *,
    sequence: int = 7,
    raw_source: bytes = _RAW_A,
    source_version: str = "commit:a",
    repository_id: str = "omninode/omniintelligence",
    relative_path: str = "src/pkg/café.py",
    qualified_names: tuple[str, ...] = ("pkg.Shared", "pkg.café.Example"),
    reverse_inputs: bool = False,
    tombstone: bool = False,
) -> ModelCodeProjectionBatch:
    raw_hash = _sha256(raw_source)
    source = make_code_source(
        repository_id=repository_id,
        relative_path=relative_path,
        source_version=source_version,
        raw_content_hash_sha256=raw_hash,
        byte_count=len(raw_source),
        language="python",
    )
    cursor = ModelCodeProjectionCursor(
        authority=f"git:{repository_id}",
        partition=source.source_id,
        sequence=sequence,
    )
    if tombstone:
        return build_code_projection_batch(
            source=source,
            cursor=cursor,
            policy=_policy(),
            provenance=_provenance(),
            operation="tombstone",
            tombstone_reason="source_deleted",
        )

    nodes = [
        make_code_node(
            source_id=source.source_id,
            entity_kind="class",
            qualified_name=name,
            display_name=name.rsplit(".", maxsplit=1)[-1],
            symbol_visibility="public",
            source_span=ModelCodeProjectionSpan(start_line=index, end_line=index + 1),
        )
        for index, name in enumerate(qualified_names, start=1)
    ]
    external = make_code_node(
        source_id=source.source_id,
        entity_kind="external_symbol",
        qualified_name="typing.Protocol",
        symbol_visibility="public",
    )
    nodes.append(external)
    edges = [
        make_code_edge(
            source_id=source.source_id,
            source_node_id=node.node_id,
            target_node_id=external.node_id,
            relationship_kind="implements",
            confidence_basis_points=7_000,
            trust_tier="conservative",
            evidence_refs=(_artifact_ref(f"edge:{node.node_id}".encode()),),
        )
        for node in nodes
        if node is not external
    ]
    documents = [
        make_code_chunk(
            source_id=source.source_id,
            source_hash_sha256=raw_hash,
            chunk_key=f"symbol:{node.qualified_name}",
            chunk_kind="symbol",
            chunker_version="ast-span-v1",
            sanitized_content_hash_sha256=_sha256(
                _SANITIZED_SENTINEL + node.node_id.encode()
            ),
            byte_count=len(_SANITIZED_SENTINEL),
            anchor_node_id=node.node_id,
            source_span=node.source_span,
        )
        for node in nodes
        if node is not external
    ]
    if reverse_inputs:
        nodes.reverse()
        edges.reverse()
        documents.reverse()
    return build_code_projection_batch(
        source=source,
        cursor=cursor,
        policy=_policy(),
        provenance=_provenance(),
        nodes=nodes,
        edges=edges,
        semantic_documents=documents,
    )


def _mutate_canonical_payload(
    batch: ModelCodeProjectionBatch,
    mutate: Callable[[dict[str, object]], None],
) -> bytes:
    decoded = json.loads(encode_canonical_batch(batch))
    assert isinstance(decoded, dict)
    mutate(decoded)
    return canonical_json_bytes(decoded)


def _all_change_sets(
    plan: ModelCodeProjectionReplayPlan,
) -> tuple[tuple[str, ...], ...]:
    return (
        plan.delete_node_ids,
        plan.upsert_node_ids,
        plan.delete_edge_ids,
        plan.upsert_edge_ids,
        plan.delete_document_ids,
        plan.upsert_document_ids,
    )


def test_reordered_collections_produce_byte_identical_batches() -> None:
    forward = _build_batch()
    reversed_inputs = _build_batch(reverse_inputs=True)

    assert reversed_inputs == forward
    assert reversed_inputs.batch_id == forward.batch_id
    assert encode_canonical_batch(reversed_inputs) == encode_canonical_batch(forward)


def test_exact_roundtrip_preserves_unicode_and_privacy_boundary() -> None:
    batch = _build_batch()
    encoded = encode_canonical_batch(batch)
    decoded = decode_canonical_batch(encoded)

    assert decoded == batch
    assert encode_canonical_batch(decoded) == encoded
    assert "café".encode() in encoded
    assert _RAW_A not in encoded
    assert b"RAW_SECRET_SENTINEL" not in encoded
    assert _SANITIZED_SENTINEL not in encoded
    assert b"docstring" not in encoded.lower()
    assert b"source_content" not in encoded
    assert b"chunk_text" not in encoded

    document_payload = decoded.semantic_documents[0].model_dump(mode="json")
    assert document_payload["content_ref"] == (
        f"artifact://sha256/{document_payload['sanitized_content_hash_sha256']}"
    )
    assert not {"content", "text", "source_content", "chunk_text"}.intersection(
        document_payload
    )


def test_duplicate_json_key_is_rejected_before_model_validation() -> None:
    batch = _build_batch()
    encoded = encode_canonical_batch(batch)
    duplicate = f'{{"batch_id":"{batch.batch_id}",'.encode("ascii") + encoded[1:]

    with pytest.raises(DuplicateJsonKeyError, match=r"duplicate .*JSON object key"):
        decode_canonical_batch(duplicate)


def test_semantically_valid_noncanonical_encodings_are_rejected() -> None:
    batch = _build_batch()
    encoded = encode_canonical_batch(batch)
    decoded = json.loads(encoded)
    assert isinstance(decoded, dict)
    reversed_object = dict(reversed(tuple(decoded.items())))
    reordered = json.dumps(
        reversed_object,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    escaped_unicode = encoded.replace("é".encode(), b"\\u00e9")

    for noncanonical in (
        b" " + encoded,
        encoded + b"\n",
        reordered,
        escaped_unicode,
    ):
        assert noncanonical != encoded
        with pytest.raises(ValueError, match="not exact canonical bytes"):
            decode_canonical_batch(noncanonical)


@pytest.mark.parametrize("forbidden_key", ["source_content", "docstring", "chunk_text"])
def test_inline_content_fields_are_rejected_explicitly(forbidden_key: str) -> None:
    batch = _build_batch()

    def inject(payload: dict[str, object]) -> None:
        if forbidden_key == "source_content":
            target = payload["source"]
        elif forbidden_key == "docstring":
            target = payload["nodes"][0]
        else:
            target = payload["semantic_documents"][0]
        assert isinstance(target, dict)
        target[forbidden_key] = "RAW_SECRET_SENTINEL"

    tampered = _mutate_canonical_payload(batch, inject)
    with pytest.raises(ValueError, match="inline content field is forbidden"):
        decode_canonical_batch(tampered)


@pytest.mark.parametrize("collection_name", ["nodes", "edges", "semantic_documents"])
def test_decoder_rejects_duplicate_record_ids(collection_name: str) -> None:
    batch = _build_batch()

    def duplicate(payload: dict[str, object]) -> None:
        records = payload[collection_name]
        assert isinstance(records, list)
        records.append(records[0])

    tampered = _mutate_canonical_payload(batch, duplicate)
    with pytest.raises(ValueError, match="uniquely sorted"):
        decode_canonical_batch(tampered)


def test_decoder_rejects_dangling_edge_endpoint() -> None:
    batch = _build_batch()

    def dangle(payload: dict[str, object]) -> None:
        edges = payload["edges"]
        assert isinstance(edges, list)
        edge = edges[0]
        assert isinstance(edge, dict)
        edge["target_node_id"] = f"cnode_v1_{'9' * 64}"

    with pytest.raises(ValueError, match="edge endpoint"):
        decode_canonical_batch(_mutate_canonical_payload(batch, dangle))


def test_decoder_rejects_dangling_document_anchor() -> None:
    batch = _build_batch()

    def dangle(payload: dict[str, object]) -> None:
        documents = payload["semantic_documents"]
        assert isinstance(documents, list)
        document = documents[0]
        assert isinstance(document, dict)
        document["anchor_node_id"] = f"cnode_v1_{'9' * 64}"

    with pytest.raises(ValueError, match="document anchor"):
        decode_canonical_batch(_mutate_canonical_payload(batch, dangle))


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda payload: payload["manifest"].update(
                {"record_checksum_sha256": "9" * 64}
            ),
            "record checksum",
        ),
        (
            lambda payload: payload.update({"batch_id": f"cbatch_v1_{'9' * 64}"}),
            "batch_id",
        ),
        (
            lambda payload: payload["manifest"].update({"node_ids": ()}),
            "manifest node_ids",
        ),
        (
            lambda payload: payload["provenance"].update(
                {"projection_builder_version": "9.0.0"}
            ),
            "projection_builder_version",
        ),
        (
            lambda payload: payload["manifest"].update({"manifest_version": "9.0.0"}),
            "manifest_version",
        ),
    ],
)
def test_decoder_rejects_tamper_and_manifest_drift(
    mutate: Callable[[dict[str, object]], None],
    expected_error: str,
) -> None:
    batch = _build_batch()
    with pytest.raises(ValueError, match=expected_error):
        decode_canonical_batch(_mutate_canonical_payload(batch, mutate))


def test_first_replay_is_replace_with_exact_incoming_sets() -> None:
    incoming = _build_batch(sequence=1)
    plan = plan_code_projection_replay(incoming)

    assert plan.decision == "replace"
    assert plan.previous_batch_id is None
    assert plan.previous_sequence is None
    assert plan.current_sequence == 1
    assert (
        plan.delete_node_ids == plan.delete_edge_ids == plan.delete_document_ids == ()
    )
    assert plan.upsert_node_ids == incoming.manifest.node_ids
    assert plan.upsert_edge_ids == incoming.manifest.edge_ids
    assert plan.upsert_document_ids == incoming.manifest.document_ids


def test_same_batch_replay_is_noop_with_no_change_sets() -> None:
    incoming = _build_batch(sequence=1)
    plan = plan_code_projection_replay(incoming, incoming.manifest)

    assert plan.decision == "noop"
    assert not any(_all_change_sets(plan))


def test_same_sequence_different_batch_is_conflict_with_no_change_sets() -> None:
    current = _build_batch(sequence=1)
    conflicting = _build_batch(
        sequence=1,
        raw_source=_RAW_B,
        source_version="commit:b",
        qualified_names=("pkg.Replacement",),
    )
    plan = plan_code_projection_replay(conflicting, current.manifest)

    assert plan.decision == "conflict"
    assert plan.previous_batch_id == current.batch_id
    assert plan.current_batch_id == conflicting.batch_id
    assert not any(_all_change_sets(plan))


def test_older_input_is_stale_with_no_change_sets() -> None:
    older = _build_batch(sequence=1)
    current = _build_batch(
        sequence=2,
        raw_source=_RAW_B,
        source_version="commit:b",
        qualified_names=("pkg.Replacement",),
    )
    plan = plan_code_projection_replay(older, current.manifest)

    assert plan.decision == "stale"
    assert plan.previous_sequence == 2
    assert plan.current_sequence == 1
    assert not any(_all_change_sets(plan))


def test_replace_reports_exact_previous_deletes_and_all_incoming_upserts() -> None:
    current = _build_batch(sequence=1, qualified_names=("pkg.AOnly", "pkg.Shared"))
    incoming = _build_batch(
        sequence=2,
        raw_source=_RAW_B,
        source_version="commit:b",
        qualified_names=("pkg.BOnly", "pkg.Shared"),
    )
    plan = plan_code_projection_replay(incoming, current.manifest)

    assert plan.decision == "replace"
    assert set(plan.delete_node_ids) == (
        set(current.manifest.node_ids) - set(incoming.manifest.node_ids)
    )
    assert set(plan.delete_edge_ids) == (
        set(current.manifest.edge_ids) - set(incoming.manifest.edge_ids)
    )
    assert set(plan.delete_document_ids) == (
        set(current.manifest.document_ids) - set(incoming.manifest.document_ids)
    )
    assert plan.upsert_node_ids == incoming.manifest.node_ids
    assert plan.upsert_edge_ids == incoming.manifest.edge_ids
    assert plan.upsert_document_ids == incoming.manifest.document_ids


def test_tombstone_replaces_source_with_exact_full_deletes() -> None:
    current = _build_batch(sequence=1)
    tombstone = _build_batch(
        sequence=2,
        source_version="deleted:2",
        tombstone=True,
    )
    plan = plan_code_projection_replay(tombstone, current.manifest)

    assert plan.decision == "replace"
    assert plan.delete_node_ids == current.manifest.node_ids
    assert plan.delete_edge_ids == current.manifest.edge_ids
    assert plan.delete_document_ids == current.manifest.document_ids
    assert (
        plan.upsert_node_ids == plan.upsert_edge_ids == plan.upsert_document_ids == ()
    )


def test_a_to_b_to_a_reversion_is_deterministic() -> None:
    first_a = _build_batch(
        sequence=1,
        raw_source=_RAW_A,
        source_version="commit:a1",
        qualified_names=("pkg.AOnly", "pkg.Shared"),
    )
    middle_b = _build_batch(
        sequence=2,
        raw_source=_RAW_B,
        source_version="commit:b",
        qualified_names=("pkg.BOnly", "pkg.Shared"),
    )
    reverted_a = _build_batch(
        sequence=3,
        raw_source=_RAW_A,
        source_version="commit:a3",
        qualified_names=("pkg.AOnly", "pkg.Shared"),
    )

    to_b = plan_code_projection_replay(middle_b, first_a.manifest)
    to_a = plan_code_projection_replay(reverted_a, middle_b.manifest)

    assert to_b.decision == to_a.decision == "replace"
    assert set(to_a.delete_node_ids) == (
        set(middle_b.manifest.node_ids) - set(reverted_a.manifest.node_ids)
    )
    assert to_a.upsert_node_ids == reverted_a.manifest.node_ids
    assert plan_code_projection_replay(reverted_a, middle_b.manifest) == to_a


def test_replay_never_compares_or_deletes_records_from_another_source() -> None:
    incoming = _build_batch(sequence=2)
    unrelated = _build_batch(
        sequence=1,
        repository_id="omninode/other-repository",
        relative_path="src/pkg/café.py",
    )

    with pytest.raises(ValueError, match="different sources"):
        plan_code_projection_replay(incoming, unrelated.manifest)


def test_replay_is_identical_before_and_after_canonical_roundtrip() -> None:
    current = _build_batch(sequence=1)
    incoming = _build_batch(
        sequence=2,
        raw_source=_RAW_B,
        source_version="commit:b",
        qualified_names=("pkg.Replacement",),
    )

    in_memory = plan_code_projection_replay(incoming, current.manifest)
    roundtripped = plan_code_projection_replay(
        decode_canonical_batch(encode_canonical_batch(incoming)),
        decode_canonical_batch(encode_canonical_batch(current)).manifest,
    )

    assert in_memory == roundtripped
