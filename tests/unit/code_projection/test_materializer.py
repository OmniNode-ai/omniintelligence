# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit checks for live projection readback enforcement."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel

from omniintelligence.code_projection import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionNode,
    make_code_node,
)
from omniintelligence.code_projection._canonical import canonical_json_bytes
from omniintelligence.code_projection.materializer import (
    ModelProjectionEdgeReadback,
    ModelProjectionNodeReadback,
    ModelProjectionReadback,
    ProjectionReadbackIntegrityError,
    _decoded_labels,
    _decoded_record_payload,
    _metadata_mapping,
    _storage_qualified_name,
    assert_projection_readback,
)
from tests.unit.code_projection.fixture_vectors import build_fixture_batches

pytestmark = pytest.mark.unit


def _labels_digest(node: ModelCodeProjectionNode) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            [label.model_dump(mode="json") for label in node.labels],
        )
    ).hexdigest()


def _record_digest(value: BaseModel) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value.model_dump(mode="json"))
    ).hexdigest()


def _matching_readback() -> tuple[
    ModelCodeProjectionBatch,
    ModelProjectionReadback,
]:
    batch = build_fixture_batches()["python_a_seq1.json"]
    node_names = {node.node_id: node.qualified_name for node in batch.nodes}
    readback = ModelProjectionReadback(
        source_id=batch.source.source_id,
        postgres_nodes=tuple(
            ModelProjectionNodeReadback(
                batch_id=batch.batch_id,
                node_id=node.node_id,
                qualified_name=node.qualified_name,
                display_name=node.display_name,
                entity_kind=node.entity_kind,
                resolution_state=node.resolution_state,
                symbol_visibility=node.symbol_visibility,
                source_span=node.source_span,
                labels=tuple(
                    f"{label.namespace}={label.value}" for label in node.labels
                ),
                labels_payload_sha256=_labels_digest(node),
                record_payload_sha256=_record_digest(node),
            )
            for node in batch.nodes
        ),
        postgres_edges=tuple(
            ModelProjectionEdgeReadback(
                batch_id=batch.batch_id,
                edge_id=edge.edge_id,
                source_qualified_name=node_names[edge.source_node_id],
                target_qualified_name=node_names[edge.target_node_id],
                relationship_kind=edge.relationship_kind,
                trust_tier=edge.trust_tier,
                confidence_basis_points=edge.confidence_basis_points,
                evidence_refs=edge.evidence_refs,
                context_eligible=edge.context_eligible,
                record_payload_sha256=_record_digest(edge),
            )
            for edge in batch.edges
        ),
        graph_nodes=tuple(
            ModelProjectionNodeReadback(
                batch_id=batch.batch_id,
                node_id=node.node_id,
                qualified_name=node.qualified_name,
                display_name=node.display_name,
                entity_kind=node.entity_kind,
                resolution_state=node.resolution_state,
                symbol_visibility=node.symbol_visibility,
                source_span=node.source_span,
                labels=tuple(
                    f"{label.namespace}={label.value}" for label in node.labels
                ),
                labels_payload_sha256=_labels_digest(node),
                record_payload_sha256=_record_digest(node),
            )
            for node in batch.nodes
        ),
        graph_edges=tuple(
            ModelProjectionEdgeReadback(
                batch_id=batch.batch_id,
                edge_id=edge.edge_id,
                source_qualified_name=node_names[edge.source_node_id],
                target_qualified_name=node_names[edge.target_node_id],
                relationship_kind=edge.relationship_kind,
                trust_tier=edge.trust_tier,
                confidence_basis_points=edge.confidence_basis_points,
                evidence_refs=edge.evidence_refs,
                context_eligible=edge.context_eligible,
                record_payload_sha256=_record_digest(edge),
            )
            for edge in batch.edges
        ),
        graph_node_count=len(batch.nodes),
        graph_edge_count=len(batch.edges),
        graph_node_ids=tuple(node.node_id for node in batch.nodes),
        graph_edge_ids=tuple(edge.edge_id for edge in batch.edges),
        policy_payload_sha256=_record_digest(batch.policy),
        provenance_payload_sha256=_record_digest(batch.provenance),
    )
    return batch, readback


def test_readback_accepts_exact_cross_store_projection() -> None:
    batch, readback = _matching_readback()

    assert_projection_readback(batch, readback)


@pytest.mark.parametrize(
    ("payload_kind", "malformed_payload", "message"),
    [
        ("metadata", '{"code_projection":', "metadata is malformed JSON"),
        ("labels", '[{"namespace":', "labels payload is malformed JSON"),
        (
            "record",
            '{"display_name":',
            "record payload is malformed JSON",
        ),
        (
            "evidence",
            '{"evidence_refs":[',
            "record payload is malformed JSON",
        ),
    ],
)
def test_malformed_stored_json_raises_typed_readback_integrity_error(
    payload_kind: str,
    malformed_payload: str,
    message: str,
) -> None:
    with pytest.raises(ProjectionReadbackIntegrityError, match=message):
        if payload_kind == "metadata":
            _metadata_mapping(malformed_payload)
        elif payload_kind == "labels":
            _decoded_labels(malformed_payload)
        else:
            _decoded_record_payload(malformed_payload)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("postgres_nodes", "Postgres node"),
        ("postgres_edges", "Postgres edge"),
        ("graph_nodes", "Memgraph node"),
        ("graph_edges", "Memgraph edge"),
        ("graph_node_count", "Memgraph node"),
        ("graph_edge_count", "Memgraph edge"),
        ("graph_node_ids", "Memgraph node IDs"),
        ("graph_edge_ids", "Memgraph edge IDs"),
    ],
)
def test_readback_fails_closed_on_any_cross_store_drift(
    field: str,
    message: str,
) -> None:
    batch, readback = _matching_readback()
    if field in {
        "postgres_nodes",
        "postgres_edges",
        "graph_nodes",
        "graph_edges",
        "graph_node_ids",
        "graph_edge_ids",
    }:
        replacement: object = ()
    else:
        replacement = 0
    drifted = readback.model_copy(update={field: replacement})

    with pytest.raises(RuntimeError, match=message):
        assert_projection_readback(batch, drifted)


def test_readback_rejects_a_receipt_for_the_wrong_source() -> None:
    batch, readback = _matching_readback()
    wrong_source = readback.model_copy(
        update={"source_id": f"csrc_v1_{'0' * 64}"},
    )

    with pytest.raises(RuntimeError, match="readback source"):
        assert_projection_readback(batch, wrong_source)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("postgres_nodes", "Postgres node readback contains"),
        ("postgres_edges", "Postgres edge readback contains"),
    ],
)
def test_readback_rejects_duplicate_postgres_projection_ids(
    field: str,
    message: str,
) -> None:
    batch, readback = _matching_readback()
    values = getattr(readback, field)
    duplicated = readback.model_copy(update={field: (*values, values[0])})

    with pytest.raises(RuntimeError, match=message):
        assert_projection_readback(batch, duplicated)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("postgres_nodes", "Postgres node readback does not match"),
        ("postgres_edges", "Postgres edge readback does not match"),
        ("graph_nodes", "Memgraph node properties do not match"),
        ("graph_edges", "Memgraph edge properties do not match"),
    ],
)
def test_readback_rejects_stale_batch_identity_in_each_store(
    field: str,
    message: str,
) -> None:
    batch, readback = _matching_readback()
    values = getattr(readback, field)
    stale = values[0].model_copy(update={"batch_id": f"cbatch_v1_{'0' * 64}"})
    drifted = readback.model_copy(update={field: (stale, *values[1:])})

    with pytest.raises(RuntimeError, match=message):
        assert_projection_readback(batch, drifted)


def test_readback_rejects_stale_memgraph_labels_and_relationship_kind() -> None:
    batch, readback = _matching_readback()
    stale_node = readback.graph_nodes[0].model_copy(
        update={"labels": ("onex.code-quality=stale",)},
    )
    stale_nodes = readback.model_copy(
        update={"graph_nodes": (stale_node, *readback.graph_nodes[1:])},
    )
    with pytest.raises(RuntimeError, match="Memgraph node properties"):
        assert_projection_readback(batch, stale_nodes)

    stale_edge = readback.graph_edges[0].model_copy(
        update={"relationship_kind": "references"},
    )
    stale_edges = readback.model_copy(
        update={"graph_edges": (stale_edge, *readback.graph_edges[1:])},
    )
    with pytest.raises(RuntimeError, match="Memgraph edge properties"):
        assert_projection_readback(batch, stale_edges)


@pytest.mark.parametrize("field", ["postgres_nodes", "graph_nodes"])
def test_readback_rejects_stale_label_payload_with_same_visible_labels(
    field: str,
) -> None:
    batch, readback = _matching_readback()
    values = getattr(readback, field)
    stale = values[0].model_copy(update={"labels_payload_sha256": "0" * 64})
    drifted = readback.model_copy(update={field: (stale, *values[1:])})

    with pytest.raises(RuntimeError, match=r"node .*does not match|node properties"):
        assert_projection_readback(batch, drifted)


@pytest.mark.parametrize("field", ["postgres_nodes", "graph_nodes"])
@pytest.mark.parametrize(
    ("property_name", "drifted_value"),
    [
        ("source_span", None),
        ("symbol_visibility", "private"),
        ("resolution_state", "external_symbol"),
    ],
)
def test_readback_rejects_unmaterialized_node_semantics(
    field: str,
    property_name: str,
    drifted_value: object,
) -> None:
    batch, readback = _matching_readback()
    values = getattr(readback, field)
    stale = values[0].model_copy(
        update={property_name: drifted_value},
    )
    drifted = readback.model_copy(update={field: (stale, *values[1:])})

    with pytest.raises(RuntimeError, match=r"node .*does not match|node properties"):
        assert_projection_readback(batch, drifted)


@pytest.mark.parametrize("field", ["postgres_edges", "graph_edges"])
@pytest.mark.parametrize(
    ("property_name", "drifted_value"),
    [
        ("trust_tier", "weak"),
        ("confidence_basis_points", 1),
        ("context_eligible", False),
        ("evidence_refs", ()),
    ],
)
def test_readback_rejects_unmaterialized_edge_semantics(
    field: str,
    property_name: str,
    drifted_value: object,
) -> None:
    batch, readback = _matching_readback()
    values = getattr(readback, field)
    stale = values[0].model_copy(
        update={property_name: drifted_value},
    )
    drifted = readback.model_copy(update={field: (stale, *values[1:])})

    with pytest.raises(RuntimeError, match=r"edge .*does not match|edge properties"):
        assert_projection_readback(batch, drifted)


@pytest.mark.parametrize(
    "digest_field",
    ["policy_payload_sha256", "provenance_payload_sha256"],
)
def test_readback_rejects_stale_policy_or_provenance_digest(
    digest_field: str,
) -> None:
    batch, readback = _matching_readback()
    drifted = readback.model_copy(update={digest_field: "0" * 64})

    with pytest.raises(RuntimeError, match=r"policy|provenance"):
        assert_projection_readback(batch, drifted)


def test_projection_storage_key_is_source_scoped() -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    external = next(
        node for node in batch.nodes if node.entity_kind == "external_symbol"
    )

    assert _storage_qualified_name(external) == (
        f"projection::{batch.source.source_id}::{external.qualified_name}"
    )


def test_same_qualified_name_from_two_sources_has_distinct_storage_keys() -> None:
    batches = build_fixture_batches()
    python_source = batches["python_a_seq1.json"].source
    typescript_source = batches["typescript_seq1.json"].source
    python_import = make_code_node(
        source_id=python_source.source_id,
        entity_kind="import",
        qualified_name="shared.Widget",
    )
    typescript_import = make_code_node(
        source_id=typescript_source.source_id,
        entity_kind="import",
        qualified_name="shared.Widget",
    )

    assert python_import.qualified_name == typescript_import.qualified_name
    assert _storage_qualified_name(python_import) != _storage_qualified_name(
        typescript_import
    )
    assert _storage_qualified_name(python_import) == (
        f"projection::{python_source.source_id}::shared.Widget"
    )
    assert _storage_qualified_name(typescript_import) == (
        f"projection::{typescript_source.source_id}::shared.Widget"
    )
