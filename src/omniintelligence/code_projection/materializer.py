# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Materialize a validated code projection into the existing lab stores.

Postgres remains the durable application read model and Memgraph remains a
rebuildable derived index.  This module deliberately accepts already-created
clients; environment and credential resolution belong to the operator entry
point.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final, cast

import asyncpg
from neo4j import AsyncDriver
from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    decode_json_no_duplicates,
    sha256_hex,
)
from omniintelligence.code_projection.codec import (
    parse_code_projection_batch,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionEdge,
    ModelCodeProjectionNode,
    ModelCodeProjectionSpan,
)
from omniintelligence.code_projection.qdrant import (
    CodeProjectionQdrantIntegrityError,
    ModelCodeProjectionQdrantReadback,
    ProtocolCodeProjectionQdrantStore,
)

_PROJECTION_METADATA_KEY: Final = "code_projection"
_PROJECTION_EVIDENCE_MARKER: Final = "code_projection:v2"
_EDGE_PAYLOAD_PREFIX: Final = "code_projection:edge_payload:v2:"


class ProjectionReadbackIntegrityError(RuntimeError):
    """Stored projection data cannot prove the canonical batch exactly."""


class _FrozenReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ModelProjectionApplyReport(_FrozenReport):
    """Counts from one complete Postgres plus Memgraph application."""

    tenant_id: str
    source_id: str
    batch_id: str
    operation: str
    postgres_nodes_written: int = Field(ge=0)
    postgres_edges_written: int = Field(ge=0)
    postgres_nodes_deleted: int = Field(ge=0)
    graph_nodes_written: int = Field(ge=0)
    graph_edges_written: int = Field(ge=0)
    qdrant_decision: str
    qdrant_documents_embedded: int = Field(ge=0)
    qdrant_points_upserted: int = Field(ge=0)
    qdrant_points_deleted: int = Field(ge=0)


class ModelProjectionNodeReadback(_FrozenReport):
    """One projection-owned node recovered from the durable read model."""

    tenant_id: str
    batch_id: str
    node_id: str
    qualified_name: str
    display_name: str
    entity_kind: str
    resolution_state: str
    symbol_visibility: str
    source_span: ModelCodeProjectionSpan | None = None
    labels: tuple[str, ...] = ()
    labels_payload_sha256: str
    record_payload_sha256: str


class ModelProjectionEdgeReadback(_FrozenReport):
    """One projection-owned relationship recovered from the durable read model."""

    tenant_id: str
    batch_id: str
    edge_id: str
    source_qualified_name: str
    target_qualified_name: str
    relationship_kind: str
    trust_tier: str
    confidence_basis_points: int = Field(ge=0, le=10_000)
    evidence_refs: tuple[str, ...] = ()
    context_eligible: bool
    record_payload_sha256: str


class ModelProjectionReadback(_FrozenReport):
    """Cross-store proof that one source projection is queryable."""

    tenant_id: str
    source_id: str
    postgres_nodes: tuple[ModelProjectionNodeReadback, ...]
    postgres_edges: tuple[ModelProjectionEdgeReadback, ...]
    graph_nodes: tuple[ModelProjectionNodeReadback, ...]
    graph_edges: tuple[ModelProjectionEdgeReadback, ...]
    graph_node_count: int = Field(ge=0)
    graph_edge_count: int = Field(ge=0)
    graph_node_ids: tuple[str, ...] = ()
    graph_edge_ids: tuple[str, ...] = ()
    policy_payload_sha256: str
    provenance_payload_sha256: str
    qdrant: ModelCodeProjectionQdrantReadback


def _application_lock_key(*, tenant_id: str, source_id: str) -> int:
    """Derive one stable signed advisory-lock key for a tenant/source pair."""

    payload = canonical_json_bytes(
        {
            "domain": "omniintelligence.code-projection-apply.v2",
            "source_id": source_id,
            "tenant_id": tenant_id,
        }
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=True)


def _validated_batch(batch: ModelCodeProjectionBatch) -> ModelCodeProjectionBatch:
    """Revalidate stable IDs, manifest integrity, and canonical bytes."""

    return parse_code_projection_batch(serialize_code_projection_batch(batch))


def _storage_qualified_name(node: ModelCodeProjectionNode) -> str:
    """Adapt source-owned identity to the legacy repository-wide unique key."""

    return f"projection::{node.source_id}::{node.qualified_name}"


def _labels_payload(node: ModelCodeProjectionNode) -> list[dict[str, object]]:
    return [label.model_dump(mode="json") for label in node.labels]


def _record_payload(value: BaseModel) -> dict[str, object]:
    return cast(dict[str, object], value.model_dump(mode="json"))


def _record_payload_json(value: BaseModel) -> str:
    return canonical_json_bytes(_record_payload(value)).decode("utf-8")


def _decode_stored_json(value: str, *, field_name: str) -> object:
    try:
        return decode_json_no_duplicates(value)
    except ValueError as exc:
        msg = f"stored projection {field_name} is malformed JSON"
        raise ProjectionReadbackIntegrityError(msg) from exc


def _decoded_record_payload(value: object) -> Mapping[str, object]:
    if isinstance(value, str):
        value = _decode_stored_json(value, field_name="record payload")
    if not isinstance(value, Mapping):
        msg = "stored projection record payload must be a JSON object"
        raise ProjectionReadbackIntegrityError(msg)
    return cast(Mapping[str, object], value)


def _payload_digest(value: object) -> str:
    payload = _decoded_record_payload(value)
    try:
        return sha256_hex(canonical_json_bytes(payload)) if payload else ""
    except (TypeError, ValueError) as exc:
        msg = "stored projection record payload is not canonicalizable"
        raise ProjectionReadbackIntegrityError(msg) from exc


def _edge_evidence_refs_from_payload(value: object) -> tuple[str, ...]:
    evidence_refs = _decoded_record_payload(value).get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return ()
    if not all(isinstance(item, str) for item in evidence_refs):
        return ()
    return tuple(sorted(cast(list[str], evidence_refs)))


def _payload_text(value: object, key: str) -> str:
    item = _decoded_record_payload(value).get(key)
    return item if isinstance(item, str) else ""


def _payload_span(value: object) -> ModelCodeProjectionSpan | None:
    item = _decoded_record_payload(value).get("source_span")
    if item is None:
        return None
    try:
        return ModelCodeProjectionSpan.model_validate(item)
    except ValueError:
        return None


def _model_digest(value: BaseModel) -> str:
    return sha256_hex(canonical_json_bytes(_record_payload(value)))


def _label_value(
    node: ModelCodeProjectionNode,
    *,
    suffixes: tuple[str, ...],
) -> tuple[str | None, float | None]:
    for label in node.labels:
        if label.namespace.endswith(suffixes):
            return label.value, label.confidence_basis_points / 10_000
    return None, None


async def _upsert_postgres_node(
    connection: asyncpg.Connection,
    *,
    batch: ModelCodeProjectionBatch,
    node: ModelCodeProjectionNode,
) -> str:
    classification, classification_confidence = _label_value(
        node,
        suffixes=("classification", "purpose"),
    )
    deterministic_type, deterministic_confidence = _label_value(
        node,
        suffixes=("node_type", "archetype"),
    )
    architectural_pattern, _ = _label_value(node, suffixes=("pattern",))
    metadata = {
        _PROJECTION_METADATA_KEY: {
            "batch_id": batch.batch_id,
            "identity_version": batch.identity_version,
            "labels": _labels_payload(node),
            "node_payload": _record_payload(node),
            "node_id": node.node_id,
            "policy_payload_sha256": _model_digest(batch.policy),
            "provenance_payload_sha256": _model_digest(batch.provenance),
            "qualified_name": node.qualified_name,
            "resolution_state": node.resolution_state,
            "source_id": batch.source.source_id,
            "storage_qualified_name": _storage_qualified_name(node),
            "tenant_id": batch.source.tenant_id,
        }
    }
    row = await connection.fetchrow(
        """
        INSERT INTO code_entities (
            entity_name, entity_type, qualified_name, source_repo, source_path,
            line_number, bases, methods, fields, decorators, docstring, signature,
            file_hash, classification, architectural_pattern,
            classification_confidence, deterministic_node_type,
            deterministic_confidence, deterministic_alternatives,
            enrichment_metadata, source_language, last_extracted_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, NULL, NULL,
            $11, $12, $13, $14, $15, $16, $17::jsonb, $18::jsonb, $19, NOW(), NOW()
        )
        ON CONFLICT (qualified_name, source_repo) DO UPDATE SET
            entity_name = EXCLUDED.entity_name,
            entity_type = EXCLUDED.entity_type,
            source_path = EXCLUDED.source_path,
            line_number = EXCLUDED.line_number,
            file_hash = EXCLUDED.file_hash,
            classification = EXCLUDED.classification,
            architectural_pattern = EXCLUDED.architectural_pattern,
            classification_confidence = EXCLUDED.classification_confidence,
            deterministic_node_type = EXCLUDED.deterministic_node_type,
            deterministic_confidence = EXCLUDED.deterministic_confidence,
            deterministic_alternatives = EXCLUDED.deterministic_alternatives,
            enrichment_metadata = code_entities.enrichment_metadata || EXCLUDED.enrichment_metadata,
            source_language = EXCLUDED.source_language,
            last_extracted_at = NOW(),
            updated_at = NOW()
        RETURNING id
        """,
        node.display_name,
        node.entity_kind,
        _storage_qualified_name(node),
        batch.source.repository_id,
        batch.source.relative_path,
        node.source_span.start_line if node.source_span is not None else None,
        [],
        "[]",
        "[]",
        [],
        batch.source.raw_content_hash_sha256,
        classification,
        architectural_pattern,
        classification_confidence,
        deterministic_type,
        deterministic_confidence,
        "[]",
        json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        batch.source.language,
    )
    if row is None:
        msg = f"Postgres did not return an ID for {node.node_id}"
        raise RuntimeError(msg)
    return str(row["id"])


async def _delete_projection_relationships(
    connection: asyncpg.Connection,
    *,
    tenant_id: str,
    source_id: str,
) -> int:
    result = await connection.execute(
        """
        DELETE FROM code_relationships AS relationship
        USING code_entities AS source_entity
        WHERE relationship.source_entity_id = source_entity.id
          AND source_entity.enrichment_metadata #>> '{code_projection,source_id}' = $1
          AND source_entity.enrichment_metadata #>> '{code_projection,tenant_id}' = $2
          AND $3 = ANY(relationship.evidence)
        """,
        source_id,
        tenant_id,
        _PROJECTION_EVIDENCE_MARKER,
    )
    return int(result.rsplit(" ", maxsplit=1)[-1])


async def _delete_stale_projection_nodes(
    connection: asyncpg.Connection,
    *,
    tenant_id: str,
    source_id: str,
    current_storage_qualified_names: tuple[str, ...],
) -> int:
    result = await connection.execute(
        """
        DELETE FROM code_entities
        WHERE enrichment_metadata #>> '{code_projection,source_id}' = $1
          AND enrichment_metadata #>> '{code_projection,tenant_id}' = $2
          AND NOT (qualified_name = ANY($3::text[]))
        """,
        source_id,
        tenant_id,
        list(current_storage_qualified_names),
    )
    return int(result.rsplit(" ", maxsplit=1)[-1])


async def _delete_all_projection_nodes(
    connection: asyncpg.Connection,
    *,
    tenant_id: str,
    source_id: str,
) -> int:
    result = await connection.execute(
        """
        DELETE FROM code_entities
        WHERE enrichment_metadata #>> '{code_projection,source_id}' = $1
          AND enrichment_metadata #>> '{code_projection,tenant_id}' = $2
        """,
        source_id,
        tenant_id,
    )
    return int(result.rsplit(" ", maxsplit=1)[-1])


async def _upsert_postgres_edge(
    connection: asyncpg.Connection,
    *,
    batch: ModelCodeProjectionBatch,
    edge: ModelCodeProjectionEdge,
    entity_ids: Mapping[str, str],
) -> str:
    source_entity_id = entity_ids[edge.source_node_id]
    target_entity_id = entity_ids[edge.target_node_id]
    evidence = [
        _PROJECTION_EVIDENCE_MARKER,
        f"projection_batch_id:{batch.batch_id}",
        f"projection_edge_id:{edge.edge_id}",
        f"{_EDGE_PAYLOAD_PREFIX}{_record_payload_json(edge)}",
        *edge.evidence_refs,
    ]
    row = await connection.fetchrow(
        """
        INSERT INTO code_relationships (
            source_entity_id, target_entity_id, relationship_type,
            trust_tier, confidence, evidence, inject_into_context,
            source_repo, updated_at
        ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, NOW())
        ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO UPDATE SET
            trust_tier = EXCLUDED.trust_tier,
            confidence = EXCLUDED.confidence,
            evidence = EXCLUDED.evidence,
            inject_into_context = EXCLUDED.inject_into_context,
            source_repo = EXCLUDED.source_repo,
            updated_at = NOW()
        RETURNING id
        """,
        source_entity_id,
        target_entity_id,
        edge.relationship_kind,
        edge.trust_tier,
        edge.confidence_basis_points / 10_000,
        evidence,
        edge.context_eligible,
        batch.source.repository_id,
    )
    if row is None:
        msg = f"Postgres did not return an ID for {edge.edge_id}"
        raise RuntimeError(msg)
    return str(row["id"])


async def _materialize_postgres(
    batch: ModelCodeProjectionBatch,
    connection: asyncpg.Connection,
) -> tuple[int, int, int]:
    async with connection.transaction():
        await _delete_projection_relationships(
            connection,
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
        )
        if batch.operation == "tombstone":
            deleted = await _delete_all_projection_nodes(
                connection,
                tenant_id=batch.source.tenant_id,
                source_id=batch.source.source_id,
            )
            return 0, 0, deleted

        entity_ids: dict[str, str] = {}
        for node in batch.nodes:
            entity_ids[node.node_id] = await _upsert_postgres_node(
                connection,
                batch=batch,
                node=node,
            )

        deleted = await _delete_stale_projection_nodes(
            connection,
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            current_storage_qualified_names=tuple(
                _storage_qualified_name(node) for node in batch.nodes
            ),
        )
        for edge in batch.edges:
            await _upsert_postgres_edge(
                connection,
                batch=batch,
                edge=edge,
                entity_ids=entity_ids,
            )
        return len(entity_ids), len(batch.edges), deleted


async def _run_graph_query(
    driver: AsyncDriver,
    query: str,
    **parameters: Any,
) -> None:
    async with driver.session() as session:
        result = await session.run(query, **parameters)
        await result.consume()


async def _materialize_graph(
    batch: ModelCodeProjectionBatch,
    driver: AsyncDriver,
) -> tuple[int, int]:
    source_id = batch.source.source_id
    tenant_id = batch.source.tenant_id
    await _run_graph_query(
        driver,
        """
        MATCH ()-[relationship:CODE_PROJECTION_RELATIONSHIP]->()
        WHERE relationship.tenant_id = $tenant_id
          AND relationship.projection_source_id = $source_id
        DELETE relationship
        """,
        tenant_id=tenant_id,
        source_id=source_id,
    )
    if batch.operation == "tombstone":
        await _run_graph_query(
            driver,
            """
            MATCH (node:CodeProjectionNode)
            WHERE node.tenant_id = $tenant_id
              AND node.projection_source_id = $source_id
            DETACH DELETE node
            """,
            tenant_id=tenant_id,
            source_id=source_id,
        )
        return 0, 0

    await _run_graph_query(
        driver,
        """
        MATCH (node:CodeProjectionNode)
        WHERE node.tenant_id = $tenant_id
          AND node.projection_source_id = $source_id
          AND NOT node.node_id IN $node_ids
        DETACH DELETE node
        """,
        tenant_id=tenant_id,
        source_id=source_id,
        node_ids=[node.node_id for node in batch.nodes],
    )
    for node in batch.nodes:
        await _run_graph_query(
            driver,
            """
            MERGE (node:CodeProjectionNode {node_id: $node_id})
            SET node.tenant_id = $tenant_id,
                node.projection_source_id = $source_id,
                node.batch_id = $batch_id,
                node.repository_id = $repository_id,
                node.relative_path = $relative_path,
                node.qualified_name = $qualified_name,
                node.display_name = $display_name,
                node.entity_kind = $entity_kind,
                node.resolution_state = $resolution_state,
                node.labels_json = $labels_json,
                node.record_payload_json = $record_payload_json,
                node.policy_payload_sha256 = $policy_payload_sha256,
                node.provenance_payload_sha256 = $provenance_payload_sha256
            """,
            node_id=node.node_id,
            tenant_id=tenant_id,
            source_id=source_id,
            batch_id=batch.batch_id,
            repository_id=batch.source.repository_id,
            relative_path=batch.source.relative_path,
            qualified_name=node.qualified_name,
            display_name=node.display_name,
            entity_kind=node.entity_kind,
            resolution_state=node.resolution_state,
            labels_json=json.dumps(
                _labels_payload(node),
                sort_keys=True,
                separators=(",", ":"),
            ),
            record_payload_json=_record_payload_json(node),
            policy_payload_sha256=_model_digest(batch.policy),
            provenance_payload_sha256=_model_digest(batch.provenance),
        )
    for edge in batch.edges:
        await _run_graph_query(
            driver,
            """
            MATCH (source:CodeProjectionNode {node_id: $source_node_id})
            MATCH (target:CodeProjectionNode {node_id: $target_node_id})
            MERGE (source)-[relationship:CODE_PROJECTION_RELATIONSHIP {edge_id: $edge_id}]->(target)
            SET relationship.projection_source_id = $projection_source_id,
                relationship.tenant_id = $tenant_id,
                relationship.batch_id = $batch_id,
                relationship.relationship_kind = $relationship_kind,
                relationship.trust_tier = $trust_tier,
                relationship.confidence_basis_points = $confidence_basis_points,
                relationship.context_eligible = $context_eligible,
                relationship.record_payload_json = $record_payload_json
            """,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            edge_id=edge.edge_id,
            tenant_id=tenant_id,
            projection_source_id=source_id,
            batch_id=batch.batch_id,
            relationship_kind=edge.relationship_kind,
            trust_tier=edge.trust_tier,
            confidence_basis_points=edge.confidence_basis_points,
            context_eligible=edge.context_eligible,
            record_payload_json=_record_payload_json(edge),
        )
    return len(batch.nodes), len(batch.edges)


async def apply_code_projection(
    batch: ModelCodeProjectionBatch,
    *,
    postgres_pool: asyncpg.Pool,
    graph_driver: AsyncDriver,
    qdrant_store: ProtocolCodeProjectionQdrantStore,
) -> ModelProjectionApplyReport:
    """Apply one canonical source snapshot or tombstone to all three stores."""

    canonical_batch = _validated_batch(batch)
    lock_key = _application_lock_key(
        tenant_id=canonical_batch.source.tenant_id,
        source_id=canonical_batch.source.source_id,
    )
    async with postgres_pool.acquire() as connection:
        await connection.execute("SELECT pg_advisory_lock($1::bigint)", lock_key)
        try:
            await qdrant_store.guard_replay(canonical_batch)
            pg_nodes, pg_edges, pg_deleted = await _materialize_postgres(
                canonical_batch,
                connection,
            )
            graph_nodes, graph_edges = await _materialize_graph(
                canonical_batch,
                graph_driver,
            )
            qdrant = await qdrant_store.apply(canonical_batch)
        finally:
            unlocked = await connection.fetchval(
                "SELECT pg_advisory_unlock($1::bigint)",
                lock_key,
            )
            if unlocked is not True:
                raise RuntimeError(
                    "Postgres did not release the projection source lock"
                )
    return ModelProjectionApplyReport(
        tenant_id=canonical_batch.source.tenant_id,
        source_id=canonical_batch.source.source_id,
        batch_id=canonical_batch.batch_id,
        operation=canonical_batch.operation,
        postgres_nodes_written=pg_nodes,
        postgres_edges_written=pg_edges,
        postgres_nodes_deleted=pg_deleted,
        graph_nodes_written=graph_nodes,
        graph_edges_written=graph_edges,
        qdrant_decision=qdrant.decision,
        qdrant_documents_embedded=qdrant.documents_embedded,
        qdrant_points_upserted=qdrant.points_upserted,
        qdrant_points_deleted=qdrant.points_deleted,
    )


def _metadata_mapping(
    value: object,
    *,
    field_name: str = "metadata",
) -> Mapping[str, object]:
    if isinstance(value, str):
        value = _decode_stored_json(value, field_name=field_name)
    if not isinstance(value, Mapping):
        msg = f"stored projection {field_name} must be a JSON object"
        raise ProjectionReadbackIntegrityError(msg)
    return cast(Mapping[str, object], value)


def _metadata_text(metadata: Mapping[str, object], key: str) -> str:
    projection = _metadata_mapping(
        metadata.get(_PROJECTION_METADATA_KEY),
        field_name="metadata.code_projection",
    )
    value = projection.get(key)
    return value if isinstance(value, str) else ""


def _decoded_labels(raw_labels: object) -> list[object]:
    if isinstance(raw_labels, str):
        raw_labels = _decode_stored_json(raw_labels, field_name="labels payload")
    if not isinstance(raw_labels, list):
        msg = "stored projection labels payload must be a JSON array"
        raise ProjectionReadbackIntegrityError(msg)
    return cast(list[object], raw_labels)


def _label_strings(raw_labels: object) -> tuple[str, ...]:
    decoded_labels = _decoded_labels(raw_labels)
    values: list[str] = []
    for index, raw_label in enumerate(decoded_labels):
        label = _metadata_mapping(
            raw_label,
            field_name=f"labels payload item {index}",
        )
        namespace = label.get("namespace")
        value = label.get("value")
        if not isinstance(namespace, str) or not isinstance(value, str):
            msg = (
                "stored projection labels payload items require string "
                "namespace and value fields"
            )
            raise ProjectionReadbackIntegrityError(msg)
        values.append(f"{namespace}={value}")
    return tuple(sorted(values))


def _label_payload_digest(raw_labels: object) -> str:
    try:
        return sha256_hex(canonical_json_bytes(_decoded_labels(raw_labels)))
    except (TypeError, ValueError) as exc:
        msg = "stored projection labels payload is not canonicalizable"
        raise ProjectionReadbackIntegrityError(msg) from exc


async def read_code_projection(
    batch: ModelCodeProjectionBatch,
    *,
    postgres_pool: asyncpg.Pool,
    graph_driver: AsyncDriver,
    qdrant_store: ProtocolCodeProjectionQdrantStore,
) -> ModelProjectionReadback:
    """Read the exact source-owned projection back from all live stores."""

    canonical_batch = _validated_batch(batch)
    tenant_id = canonical_batch.source.tenant_id
    source_id = canonical_batch.source.source_id
    node_rows = await postgres_pool.fetch(
        """
        SELECT entity_type, enrichment_metadata
        FROM code_entities
        WHERE enrichment_metadata #>> '{code_projection,source_id}' = $1
          AND enrichment_metadata #>> '{code_projection,tenant_id}' = $2
        ORDER BY enrichment_metadata #>> '{code_projection,node_id}'
        """,
        source_id,
        tenant_id,
    )
    nodes: list[ModelProjectionNodeReadback] = []
    postgres_policy_digests: list[str] = []
    postgres_provenance_digests: list[str] = []
    for row in node_rows:
        metadata = _metadata_mapping(row["enrichment_metadata"])
        projection_metadata = _metadata_mapping(metadata.get(_PROJECTION_METADATA_KEY))
        raw_labels = projection_metadata.get("labels")
        node_payload = projection_metadata.get("node_payload")
        postgres_policy_digests.append(
            _metadata_text(metadata, "policy_payload_sha256")
        )
        postgres_provenance_digests.append(
            _metadata_text(metadata, "provenance_payload_sha256")
        )
        nodes.append(
            ModelProjectionNodeReadback(
                tenant_id=_metadata_text(metadata, "tenant_id"),
                batch_id=_metadata_text(metadata, "batch_id"),
                node_id=_metadata_text(metadata, "node_id"),
                qualified_name=_metadata_text(metadata, "qualified_name"),
                display_name=_payload_text(node_payload, "display_name"),
                entity_kind=str(row["entity_type"]),
                resolution_state=_payload_text(node_payload, "resolution_state"),
                symbol_visibility=_payload_text(node_payload, "symbol_visibility"),
                source_span=_payload_span(node_payload),
                labels=_label_strings(raw_labels),
                labels_payload_sha256=_label_payload_digest(raw_labels),
                record_payload_sha256=_payload_digest(node_payload),
            )
        )

    edge_rows = await postgres_pool.fetch(
        """
        SELECT relationship.relationship_type, relationship.trust_tier,
               relationship.confidence, relationship.evidence,
               relationship.inject_into_context,
               source_entity.enrichment_metadata AS source_metadata,
               target_entity.enrichment_metadata AS target_metadata
        FROM code_relationships AS relationship
        JOIN code_entities AS source_entity ON source_entity.id = relationship.source_entity_id
        JOIN code_entities AS target_entity ON target_entity.id = relationship.target_entity_id
        WHERE source_entity.enrichment_metadata #>> '{code_projection,source_id}' = $1
          AND source_entity.enrichment_metadata #>> '{code_projection,tenant_id}' = $2
          AND $3 = ANY(relationship.evidence)
        ORDER BY relationship.evidence
        """,
        source_id,
        tenant_id,
        _PROJECTION_EVIDENCE_MARKER,
    )
    edges: list[ModelProjectionEdgeReadback] = []
    for row in edge_rows:
        raw_evidence = row["evidence"]
        evidence = (
            [str(value) for value in raw_evidence]
            if isinstance(raw_evidence, list)
            else []
        )
        edge_id = next(
            (
                value.removeprefix("projection_edge_id:")
                for value in evidence
                if value.startswith("projection_edge_id:")
            ),
            "",
        )
        edge_batch_id = next(
            (
                value.removeprefix("projection_batch_id:")
                for value in evidence
                if value.startswith("projection_batch_id:")
            ),
            "",
        )
        edge_payload = next(
            (
                value.removeprefix(_EDGE_PAYLOAD_PREFIX)
                for value in evidence
                if value.startswith(_EDGE_PAYLOAD_PREFIX)
            ),
            "",
        )
        evidence_refs = tuple(
            sorted(
                value
                for value in evidence
                if value != _PROJECTION_EVIDENCE_MARKER
                and not value.startswith("projection_batch_id:")
                and not value.startswith("projection_edge_id:")
                and not value.startswith(_EDGE_PAYLOAD_PREFIX)
            )
        )
        source_metadata = _metadata_mapping(row["source_metadata"])
        target_metadata = _metadata_mapping(row["target_metadata"])
        edges.append(
            ModelProjectionEdgeReadback(
                tenant_id=_metadata_text(source_metadata, "tenant_id"),
                batch_id=edge_batch_id,
                edge_id=edge_id,
                source_qualified_name=_metadata_text(
                    source_metadata,
                    "qualified_name",
                ),
                target_qualified_name=_metadata_text(
                    target_metadata,
                    "qualified_name",
                ),
                relationship_kind=str(row["relationship_type"]),
                trust_tier=str(row["trust_tier"]),
                confidence_basis_points=round(float(row["confidence"]) * 10_000),
                evidence_refs=evidence_refs,
                context_eligible=bool(row["inject_into_context"]),
                record_payload_sha256=_payload_digest(edge_payload),
            )
        )

    async with graph_driver.session() as session:
        graph_node_rows = await (
            await session.run(
                """
                MATCH (node:CodeProjectionNode)
                WHERE node.tenant_id = $tenant_id
                  AND node.projection_source_id = $source_id
                RETURN node.tenant_id AS tenant_id,
                       node.batch_id AS batch_id,
                       node.node_id AS node_id,
                       node.qualified_name AS qualified_name,
                       node.entity_kind AS entity_kind,
                       node.labels_json AS labels_json,
                       node.record_payload_json AS record_payload_json,
                       node.policy_payload_sha256 AS policy_payload_sha256,
                       node.provenance_payload_sha256 AS provenance_payload_sha256
                ORDER BY node.node_id
                """,
                tenant_id=tenant_id,
                source_id=source_id,
            )
        ).data()
        graph_edge_rows = await (
            await session.run(
                """
                MATCH (source:CodeProjectionNode)-[relationship:CODE_PROJECTION_RELATIONSHIP]->(target:CodeProjectionNode)
                WHERE relationship.tenant_id = $tenant_id
                  AND relationship.projection_source_id = $source_id
                RETURN relationship.tenant_id AS tenant_id,
                       relationship.batch_id AS batch_id,
                       relationship.edge_id AS edge_id,
                       source.qualified_name AS source_qualified_name,
                       target.qualified_name AS target_qualified_name,
                       relationship.relationship_kind AS relationship_kind,
                       relationship.trust_tier AS trust_tier,
                       relationship.confidence_basis_points AS confidence_basis_points,
                       relationship.context_eligible AS context_eligible,
                       relationship.record_payload_json AS record_payload_json
                ORDER BY relationship.edge_id
                """,
                tenant_id=tenant_id,
                source_id=source_id,
            )
        ).data()
    graph_nodes = tuple(
        ModelProjectionNodeReadback(
            tenant_id=str(row["tenant_id"]),
            batch_id=str(row["batch_id"]),
            node_id=str(row["node_id"]),
            qualified_name=str(row["qualified_name"]),
            display_name=_payload_text(row["record_payload_json"], "display_name"),
            entity_kind=str(row["entity_kind"]),
            resolution_state=_payload_text(
                row["record_payload_json"],
                "resolution_state",
            ),
            symbol_visibility=_payload_text(
                row["record_payload_json"],
                "symbol_visibility",
            ),
            source_span=_payload_span(row["record_payload_json"]),
            labels=_label_strings(row["labels_json"]),
            labels_payload_sha256=_label_payload_digest(row["labels_json"]),
            record_payload_sha256=_payload_digest(row["record_payload_json"]),
        )
        for row in graph_node_rows
    )
    graph_edges = tuple(
        ModelProjectionEdgeReadback(
            tenant_id=str(row["tenant_id"]),
            batch_id=str(row["batch_id"]),
            edge_id=str(row["edge_id"]),
            source_qualified_name=str(row["source_qualified_name"]),
            target_qualified_name=str(row["target_qualified_name"]),
            relationship_kind=str(row["relationship_kind"]),
            trust_tier=str(row["trust_tier"]),
            confidence_basis_points=int(row["confidence_basis_points"]),
            evidence_refs=_edge_evidence_refs_from_payload(row["record_payload_json"]),
            context_eligible=bool(row["context_eligible"]),
            record_payload_sha256=_payload_digest(row["record_payload_json"]),
        )
        for row in graph_edge_rows
    )
    expected_policy_digest = _model_digest(canonical_batch.policy)
    expected_provenance_digest = _model_digest(canonical_batch.provenance)
    graph_policy_digests = [
        str(row["policy_payload_sha256"]) for row in graph_node_rows
    ]
    graph_provenance_digests = [
        str(row["provenance_payload_sha256"]) for row in graph_node_rows
    ]

    def common_digest(
        postgres_values: list[str],
        graph_values: list[str],
        *,
        empty_value: str,
    ) -> str:
        if not canonical_batch.nodes:
            return empty_value
        values = {*postgres_values, *graph_values}
        if (
            len(postgres_values) != len(canonical_batch.nodes)
            or len(graph_values) != len(canonical_batch.nodes)
            or len(values) != 1
        ):
            return ""
        return values.pop()

    try:
        qdrant_readback = await qdrant_store.readback(canonical_batch)
    except CodeProjectionQdrantIntegrityError as exc:
        raise ProjectionReadbackIntegrityError(
            "Qdrant readback does not match the canonical batch"
        ) from exc

    return ModelProjectionReadback(
        tenant_id=tenant_id,
        source_id=source_id,
        postgres_nodes=tuple(nodes),
        postgres_edges=tuple(edges),
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        graph_node_count=len(graph_nodes),
        graph_edge_count=len(graph_edges),
        graph_node_ids=tuple(node.node_id for node in graph_nodes),
        graph_edge_ids=tuple(edge.edge_id for edge in graph_edges),
        policy_payload_sha256=common_digest(
            postgres_policy_digests,
            graph_policy_digests,
            empty_value=expected_policy_digest,
        ),
        provenance_payload_sha256=common_digest(
            postgres_provenance_digests,
            graph_provenance_digests,
            empty_value=expected_provenance_digest,
        ),
        qdrant=qdrant_readback,
    )


def assert_projection_readback(
    batch: ModelCodeProjectionBatch,
    readback: ModelProjectionReadback,
) -> None:
    """Fail closed unless both stores exactly contain the incoming graph."""

    expected_node_ids = {node.node_id for node in batch.nodes}
    expected_edge_ids = {edge.edge_id for edge in batch.edges}
    expected_document_ids = tuple(
        document.document_id for document in batch.semantic_documents
    )
    if readback.tenant_id != batch.source.tenant_id:
        msg = "readback tenant does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if readback.source_id != batch.source.source_id:
        msg = "readback source does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    qdrant = readback.qdrant
    if (
        qdrant.tenant_id != batch.source.tenant_id
        or qdrant.source_id != batch.source.source_id
        or qdrant.batch_id != batch.batch_id
        or qdrant.operation != batch.operation
        or qdrant.document_ids != expected_document_ids
        or qdrant.point_count != len(expected_document_ids)
        or not qdrant.manifest_point_id
        or qdrant.record_count != qdrant.point_count + 1
        or len(qdrant.point_ids) != len(expected_document_ids)
        or len(set(qdrant.point_ids)) != len(qdrant.point_ids)
    ):
        raise ProjectionReadbackIntegrityError(
            "Qdrant readback does not match the canonical batch"
        )
    expected_nodes = {
        node.node_id: (
            batch.source.tenant_id,
            batch.batch_id,
            node.qualified_name,
            node.display_name,
            node.entity_kind,
            node.resolution_state,
            node.symbol_visibility,
            node.source_span,
            tuple(sorted(f"{label.namespace}={label.value}" for label in node.labels)),
            sha256_hex(canonical_json_bytes(_labels_payload(node))),
            sha256_hex(canonical_json_bytes(_record_payload(node))),
        )
        for node in batch.nodes
    }
    postgres_nodes = {
        node.node_id: (
            node.tenant_id,
            node.batch_id,
            node.qualified_name,
            node.display_name,
            node.entity_kind,
            node.resolution_state,
            node.symbol_visibility,
            node.source_span,
            node.labels,
            node.labels_payload_sha256,
            node.record_payload_sha256,
        )
        for node in readback.postgres_nodes
    }
    graph_nodes = {
        node.node_id: (
            node.tenant_id,
            node.batch_id,
            node.qualified_name,
            node.display_name,
            node.entity_kind,
            node.resolution_state,
            node.symbol_visibility,
            node.source_span,
            node.labels,
            node.labels_payload_sha256,
            node.record_payload_sha256,
        )
        for node in readback.graph_nodes
    }
    node_names = {node.node_id: node.qualified_name for node in batch.nodes}
    expected_edges = {
        edge.edge_id: (
            batch.source.tenant_id,
            batch.batch_id,
            node_names[edge.source_node_id],
            node_names[edge.target_node_id],
            edge.relationship_kind,
            edge.trust_tier,
            edge.confidence_basis_points,
            tuple(sorted(edge.evidence_refs)),
            edge.context_eligible,
            sha256_hex(canonical_json_bytes(_record_payload(edge))),
        )
        for edge in batch.edges
    }
    postgres_edges = {
        edge.edge_id: (
            edge.tenant_id,
            edge.batch_id,
            edge.source_qualified_name,
            edge.target_qualified_name,
            edge.relationship_kind,
            edge.trust_tier,
            edge.confidence_basis_points,
            edge.evidence_refs,
            edge.context_eligible,
            edge.record_payload_sha256,
        )
        for edge in readback.postgres_edges
    }
    graph_edges = {
        edge.edge_id: (
            edge.tenant_id,
            edge.batch_id,
            edge.source_qualified_name,
            edge.target_qualified_name,
            edge.relationship_kind,
            edge.trust_tier,
            edge.confidence_basis_points,
            edge.evidence_refs,
            edge.context_eligible,
            edge.record_payload_sha256,
        )
        for edge in readback.graph_edges
    }
    if readback.policy_payload_sha256 != _model_digest(batch.policy):
        raise ProjectionReadbackIntegrityError(
            "projection policy readback does not match the batch"
        )
    if readback.provenance_payload_sha256 != _model_digest(batch.provenance):
        raise ProjectionReadbackIntegrityError(
            "projection provenance readback does not match the batch"
        )
    if len(readback.postgres_nodes) != len(expected_nodes):
        msg = "Postgres node readback contains missing or duplicate rows"
        raise ProjectionReadbackIntegrityError(msg)
    if len(readback.postgres_edges) != len(expected_edges):
        msg = "Postgres edge readback contains missing or duplicate rows"
        raise ProjectionReadbackIntegrityError(msg)
    if postgres_nodes != expected_nodes:
        msg = "Postgres node readback does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if postgres_edges != expected_edges:
        msg = "Postgres edge readback does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if readback.graph_node_count != len(expected_node_ids):
        msg = "Memgraph node readback does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if readback.graph_edge_count != len(expected_edge_ids):
        msg = "Memgraph edge readback does not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if len(readback.graph_nodes) != len(expected_nodes):
        msg = "Memgraph node readback contains missing or duplicate rows"
        raise ProjectionReadbackIntegrityError(msg)
    if len(readback.graph_edges) != len(expected_edges):
        msg = "Memgraph edge readback contains missing or duplicate rows"
        raise ProjectionReadbackIntegrityError(msg)
    if set(readback.graph_node_ids) != expected_node_ids:
        msg = "Memgraph node IDs do not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if set(readback.graph_edge_ids) != expected_edge_ids:
        msg = "Memgraph edge IDs do not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if graph_nodes != expected_nodes:
        msg = "Memgraph node properties do not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)
    if graph_edges != expected_edges:
        msg = "Memgraph edge properties do not match the canonical batch"
        raise ProjectionReadbackIntegrityError(msg)


__all__ = [
    "ModelProjectionApplyReport",
    "ModelProjectionEdgeReadback",
    "ModelProjectionNodeReadback",
    "ModelProjectionReadback",
    "ProjectionReadbackIntegrityError",
    "apply_code_projection",
    "assert_projection_readback",
    "read_code_projection",
]
