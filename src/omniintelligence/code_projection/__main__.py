# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Operator entry point for executable dev-lab code ingestion."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import asyncpg
import yaml
from neo4j import AsyncDriver, AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

import omniintelligence.nodes.node_ast_extraction_compute as ast_extraction_package
from omniintelligence.adapters.embedding_client_local_openai import (
    EmbeddingClientLocalOpenAI,
)
from omniintelligence.code_projection._canonical import (
    normalize_relative_path,
    normalize_repository_id,
    normalize_tenant_id,
    sha256_hex,
)
from omniintelligence.code_projection.artifacts import (
    CodeProjectionArtifactStore,
    CurrentCodeProjection,
    StagedCodeProjection,
)
from omniintelligence.code_projection.codec import (
    build_code_projection_batch,
    derive_code_source_id,
    plan_code_projection_replay,
)
from omniintelligence.code_projection.context_serving import (
    derive_projection_repository_id,
    derive_repository_policy_scope_ref,
)
from omniintelligence.code_projection.extraction import (
    ProjectedCodeSource,
    project_source_with_documents,
)
from omniintelligence.code_projection.materializer import (
    ModelProjectionApplyReport,
    ModelProjectionReadback,
    ProjectionReadbackIntegrityError,
    apply_code_projection,
    assert_projection_readback,
    read_code_projection,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelSourceLanguage,
)
from omniintelligence.code_projection.qdrant import (
    CodeProjectionQdrantStore,
    ModelCodeProjectionCurrentGeneration,
    ModelCodeProjectionQdrantConfig,
    ProtocolCodeProjectionContentResolver,
    ProtocolCodeProjectionCurrentGenerationResolver,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
    ModelEmbeddingClientConfig,
)

_CURSOR_AUTHORITY = "omniintelligence.code-projection.dev-lab.v2"
_PRODUCER_VERSION = "2.0.0"
_LAB_REPOSITORY_PREFIX = "lab/"
_DEFAULT_REPOSITORY_INSTANCE_ID = "canonical"
_DEFAULT_QDRANT_COLLECTION = "code_semantic_v2"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-qwen3"
_DEFAULT_EMBEDDING_MODEL_VERSION = "qwen3-embedding-0.6b-lab-2026-08-14"


@dataclass(frozen=True, slots=True)
class _ExtractionConfiguration:
    classification: Mapping[str, Any]
    quality: Mapping[str, Any]
    languages: Mapping[str, Any]
    contract_hash_sha256: str
    contract_bytes: bytes


@dataclass(frozen=True, slots=True)
class _LiveClientConfiguration:
    postgres_url: str
    graph_uri: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    embedding_url: str
    embedding_model: str
    embedding_model_version: str


def _require_mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        msg = f"AST extraction contract {name} must be a mapping"
        raise ValueError(msg)
    return cast(Mapping[str, Any], value)


def _load_extraction_configuration() -> _ExtractionConfiguration:
    package_file = ast_extraction_package.__file__
    contract_path = Path(package_file).with_name("contract.yaml")
    contract_bytes = contract_path.read_bytes()
    payload = yaml.safe_load(contract_bytes)
    root = _require_mapping(payload, name="root")
    configuration = _require_mapping(
        root.get("configuration"),
        name="configuration",
    )
    return _ExtractionConfiguration(
        classification=_require_mapping(
            configuration.get("deterministic_classification"),
            name="deterministic_classification",
        ),
        quality=_require_mapping(
            configuration.get("quality_scoring"),
            name="quality_scoring",
        ),
        languages=_require_mapping(
            configuration.get("language_extractors"),
            name="language_extractors",
        ),
        contract_hash_sha256=sha256_hex(contract_bytes),
        contract_bytes=contract_bytes,
    )


def _policy(
    tenant_id: str,
    repository_id: str,
    repository_instance_id: str,
) -> ModelCodeProjectionPolicy:
    """Build the policy envelope the shipped serving grant admits verbatim.

    The scope must come from the shared deriver rather than a local format
    string: ``ModelCodeContextAuthorizationGrant`` rejects any scope that does
    not end in ``:instance:{repository_instance_id}`` (OMN-16898).
    """

    return ModelCodeProjectionPolicy(
        tenant_id=tenant_id,
        scope_ref=derive_repository_policy_scope_ref(
            tenant_id=tenant_id,
            repository_id=repository_id,
            repository_instance_id=repository_instance_id,
        ),
        access_scope="repository",
        visibility="repository",
        redaction_state="not_required",
        trust_tier="verified_source",
        retention_class="source_controlled",
        policy_version="dev-lab-code-ingestion-v2",
        metadata_allowlist_version="code-projection-metadata-v2",
    )


def _provenance(
    configuration: _ExtractionConfiguration,
) -> ModelCodeProjectionProvenance:
    contract_hash = configuration.contract_hash_sha256
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection",
        producer_version=_PRODUCER_VERSION,
        projection_builder_version="2.0.0",
        extractor_name="python-ast-and-multilang-regex",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=contract_hash,
        transform_manifest_ref=f"artifact://sha256/{contract_hash}",
        transform_manifest_hash_sha256=contract_hash,
        labeler_version="deterministic-classifier-quality-semantic-v1",
        chunker_version="syntax-aware-v2",
    )


def _live_client_configuration() -> _LiveClientConfiguration:
    # The effects runtime injects these two endpoint bindings from its active
    # lane overlay. This operator consumes those exact bindings with no default.
    postgres_url = os.environ[
        "OMNIINTELLIGENCE_DB_URL"
    ]  # url-authority-ok: injected runtime-overlay binding; no fallback
    graph_uri = os.environ[
        "ARCH_GRAPH_BOLT_URI"
    ]  # url-authority-ok: injected runtime-overlay binding; no fallback
    qdrant_url = os.environ.get(
        "QDRANT_URL", ""
    ).strip()  # url-authority-ok: injected operator binding
    if not qdrant_url:
        qdrant_host = os.environ.get("QDRANT_HOST", "").strip()
        qdrant_port = os.environ.get("QDRANT_PORT", "6333").strip()
        if not qdrant_host:
            raise ValueError(
                "QDRANT_URL or QDRANT_HOST must be bound by the active runtime overlay"
            )
        if not qdrant_port.isdigit():
            raise ValueError("QDRANT_PORT must be a decimal TCP port")
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    raw_qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    if raw_qdrant_api_key is not None and (
        raw_qdrant_api_key != raw_qdrant_api_key.strip()
    ):
        raise ValueError("QDRANT_API_KEY must have no surrounding whitespace")
    qdrant_api_key = raw_qdrant_api_key or None
    qdrant_endpoint = urlsplit(qdrant_url)
    if qdrant_endpoint.scheme not in {"http", "https"} or not qdrant_endpoint.netloc:
        raise ValueError("QDRANT_URL must be an absolute http(s) endpoint")
    if qdrant_api_key is not None and qdrant_endpoint.scheme != "https":
        raise ValueError("QDRANT_API_KEY requires an https QDRANT_URL")
    qdrant_collection = os.environ.get(
        "CODE_PROJECTION_QDRANT_COLLECTION",
        _DEFAULT_QDRANT_COLLECTION,
    )
    embedding_url = os.environ.get(
        "LLM_EMBEDDING_URL", ""
    ).strip()  # url-authority-ok: injected runtime-overlay binding
    embedding_model = os.environ.get(
        "CODE_PROJECTION_EMBEDDING_MODEL",
        _DEFAULT_EMBEDDING_MODEL,
    )
    embedding_model_version = os.environ.get(
        "CODE_PROJECTION_EMBEDDING_MODEL_VERSION",
        _DEFAULT_EMBEDDING_MODEL_VERSION,
    )
    if not postgres_url:
        raise ValueError(
            "OMNIINTELLIGENCE_DB_URL is not bound by the active runtime overlay"
        )
    if not graph_uri:
        raise ValueError(
            "ARCH_GRAPH_BOLT_URI is not bound by the active runtime overlay"
        )
    if not embedding_url:
        raise ValueError("LLM_EMBEDDING_URL is not bound by the active runtime overlay")
    for name, value in (
        ("CODE_PROJECTION_QDRANT_COLLECTION", qdrant_collection),
        ("CODE_PROJECTION_EMBEDDING_MODEL", embedding_model),
        ("CODE_PROJECTION_EMBEDDING_MODEL_VERSION", embedding_model_version),
    ):
        if not value or value != value.strip():
            raise ValueError(f"{name} must be non-empty with no surrounding whitespace")
    return _LiveClientConfiguration(
        postgres_url=postgres_url,
        graph_uri=graph_uri,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        qdrant_collection=qdrant_collection,
        embedding_url=embedding_url,
        embedding_model=embedding_model,
        embedding_model_version=embedding_model_version,
    )


def _language(relative_path: str) -> ModelSourceLanguage:
    suffix = Path(relative_path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".js", ".jsx"}:
        return "javascript"
    msg = f"unsupported source extension: {suffix or '<none>'}"
    raise ValueError(msg)


def _resolve_source_path(root: Path, relative_path: str) -> tuple[Path, str]:
    canonical_path = normalize_relative_path(relative_path)
    resolved_root = root.resolve(strict=True)
    source_path = (resolved_root / canonical_path).resolve(strict=True)
    if not source_path.is_relative_to(resolved_root):
        msg = "source path resolves outside the declared repository root"
        raise ValueError(msg)
    if not source_path.is_file():
        msg = "source path must resolve to a regular file"
        raise ValueError(msg)
    return source_path, canonical_path


def _require_lab_repository_id(repository_id: str) -> str:
    canonical = normalize_repository_id(repository_id)
    lab_suffix = canonical.removeprefix(_LAB_REPOSITORY_PREFIX)
    if (
        not canonical.startswith(_LAB_REPOSITORY_PREFIX)
        or not lab_suffix
        or canonical.endswith("/")
        or "//" in canonical
    ):
        msg = (
            "live materialization requires a namespaced repository_id beginning "
            f"with {_LAB_REPOSITORY_PREFIX!r}"
        )
        raise ValueError(msg)
    return canonical


def _require_tenant_id(tenant_id: str) -> str:
    """Validate the explicit tenant boundary shared by every projection store.

    The serving contract types every tenant as a canonical UUID, so a slug
    tenant that ``normalize_tenant_id`` alone would accept can never be served.
    Reject it here rather than materialize an unservable projection
    (OMN-16898).
    """

    normalized = normalize_tenant_id(tenant_id)
    try:
        parsed = uuid.UUID(normalized)
    except ValueError as exc:
        msg = (
            "tenant_id must be a canonical lowercase UUID so the projection is "
            "servable by the code-context serving path"
        )
        raise ValueError(msg) from exc
    if str(parsed) != normalized:
        msg = "tenant_id must be a canonical lowercase UUID"
        raise ValueError(msg)
    return normalized


def _require_projection_repository_id(
    repository_id: str,
    repository_instance_id: str,
) -> str:
    """Resolve the storage identity the serving resolver matches candidates on.

    ``resolver.py`` compares both the search hit and the stored source against
    ``request.projection_repository_id``, so the checkout instance has to be
    folded into the stored ``source.repository_id`` — not just the policy scope.
    """

    return derive_projection_repository_id(
        repository_id=repository_id,
        repository_instance_id=repository_instance_id,
    )


def _next_sequence(
    current: ModelCodeProjectionBatch | None,
    *,
    incoming_hash: str,
) -> int:
    if current is None:
        return 1
    if (
        current.operation == "snapshot"
        and current.source.raw_content_hash_sha256 == incoming_hash
    ):
        return current.cursor.sequence
    return current.cursor.sequence + 1


def _build_snapshot(
    *,
    raw_source: bytes,
    tenant_id: str,
    repository_id: str,
    repository_instance_id: str,
    projection_repository_id: str,
    relative_path: str,
    current: ModelCodeProjectionBatch | None,
    configuration: _ExtractionConfiguration,
) -> ProjectedCodeSource:
    source_hash = sha256_hex(raw_source)
    sequence = _next_sequence(current, incoming_hash=source_hash)

    def build(cursor_sequence: int) -> ProjectedCodeSource:
        return project_source_with_documents(
            raw_source=raw_source,
            tenant_id=tenant_id,
            repository_id=projection_repository_id,
            relative_path=relative_path,
            source_version=f"sha256:{source_hash}",
            language=_language(relative_path),
            cursor_authority=_CURSOR_AUTHORITY,
            cursor_sequence=cursor_sequence,
            policy=_policy(tenant_id, repository_id, repository_instance_id),
            provenance=_provenance(configuration),
            classification_config=configuration.classification,
            quality_config=configuration.quality,
            language_extractor_config=configuration.languages,
        )

    projected = build(sequence)
    if (
        current is not None
        and sequence == current.cursor.sequence
        and projected.batch.batch_id != current.batch_id
    ):
        return build(sequence + 1)
    return projected


def _build_tombstone(current: ModelCodeProjectionBatch) -> ModelCodeProjectionBatch:
    if current.operation == "tombstone":
        return current
    return build_code_projection_batch(
        source=current.source,
        cursor=ModelCodeProjectionCursor(
            authority=current.cursor.authority,
            partition=current.cursor.partition,
            sequence=current.cursor.sequence + 1,
        ),
        policy=current.policy,
        provenance=current.provenance,
        operation="tombstone",
        tombstone_reason="source_deleted",
    )


def _content_resolver(
    store: CodeProjectionArtifactStore,
) -> Callable[[str], bytes]:
    def resolve(content_ref: str) -> bytes:
        prefix = "artifact://sha256/"
        if not content_ref.startswith(prefix):
            raise ValueError("semantic content_ref is not a SHA-256 artifact URI")
        return store.read_content_artifact(content_ref.removeprefix(prefix))

    return resolve


def _current_generation_resolver(
    store: CodeProjectionArtifactStore,
) -> Callable[[str, str], ModelCodeProjectionCurrentGeneration | None]:
    def resolve(
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        current = store.load_current(source_id)
        if current is None:
            return None
        batch = current.batch
        if batch.source.tenant_id != tenant_id:
            raise RuntimeError(
                "current projection tenant does not match source identity"
            )
        return ModelCodeProjectionCurrentGeneration(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            batch_id=batch.batch_id,
            operation=batch.operation,
            batch_content_hash_sha256=current.batch_content_hash_sha256,
            document_ids=tuple(
                document.document_id for document in batch.semantic_documents
            ),
        )

    return resolve


@asynccontextmanager
async def _live_qdrant_store(
    artifact_store: CodeProjectionArtifactStore,
) -> AsyncIterator[CodeProjectionQdrantStore]:
    configuration = _live_client_configuration()
    qdrant_client = AsyncQdrantClient(
        url=configuration.qdrant_url,
        api_key=configuration.qdrant_api_key,
        timeout=30,
        prefer_grpc=False,
        cloud_inference=False,
    )
    embedding_client = EmbeddingClientLocalOpenAI(
        ModelEmbeddingClientConfig(
            base_url=configuration.embedding_url,
            embedding_dimension=1024,
            timeout_seconds=60.0,
            max_retries=2,
            retry_base_delay=0.5,
            max_concurrency=4,
        ),
        model_name=configuration.embedding_model,
    )
    await embedding_client.connect()
    try:
        yield CodeProjectionQdrantStore(
            client=qdrant_client,
            embedding_client=embedding_client,
            content_resolver=cast(
                ProtocolCodeProjectionContentResolver,
                _content_resolver(artifact_store),
            ),
            current_generation_resolver=cast(
                ProtocolCodeProjectionCurrentGenerationResolver,
                _current_generation_resolver(artifact_store),
            ),
            config=ModelCodeProjectionQdrantConfig(
                collection_name=configuration.qdrant_collection,
                vector_name="code_semantic_v2",
                embedding_model=configuration.embedding_model,
                embedding_model_version=configuration.embedding_model_version,
                embedding_dimension=1024,
                read_consistency="majority",
                write_ordering="medium",
            ),
        )
    finally:
        await embedding_client.close()
        await qdrant_client.close()


@asynccontextmanager
async def _live_clients(
    artifact_store: CodeProjectionArtifactStore,
) -> AsyncIterator[tuple[asyncpg.Pool, AsyncDriver, CodeProjectionQdrantStore]]:
    configuration = _live_client_configuration()
    pool = await asyncpg.create_pool(
        configuration.postgres_url,
        min_size=1,
        max_size=2,
        command_timeout=30,
    )
    graph_driver = AsyncGraphDatabase.driver(configuration.graph_uri)
    try:
        await graph_driver.verify_connectivity()
        async with _live_qdrant_store(artifact_store) as qdrant_store:
            yield pool, graph_driver, qdrant_store
    finally:
        await graph_driver.close()
        await pool.close()


async def _apply_and_verify(
    batch: ModelCodeProjectionBatch,
    *,
    current: ModelCodeProjectionBatch | None,
    artifact_store: CodeProjectionArtifactStore,
) -> tuple[str, ModelProjectionApplyReport | None, ModelProjectionReadback]:
    replay = plan_code_projection_replay(
        batch,
        current.manifest if current is not None else None,
    )
    if replay.decision in {"stale", "conflict"}:
        msg = f"refusing {replay.decision} live projection"
        raise RuntimeError(msg)
    decision: str = replay.decision
    async with _live_clients(artifact_store) as (
        postgres_pool,
        graph_driver,
        qdrant_store,
    ):
        apply_report: ModelProjectionApplyReport | None = None
        if decision == "replace":
            apply_report = await apply_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
                qdrant_store=qdrant_store,
            )
        try:
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
                qdrant_store=qdrant_store,
            )
            assert_projection_readback(batch, readback)
        except ProjectionReadbackIntegrityError:
            if decision != "noop":
                raise
            apply_report = await apply_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
                qdrant_store=qdrant_store,
            )
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
                qdrant_store=qdrant_store,
            )
            assert_projection_readback(batch, readback)
            decision = "repair"
    return decision, apply_report, readback


def _staged_payload(
    staged: StagedCodeProjection,
    *,
    batch: ModelCodeProjectionBatch,
) -> dict[str, str]:
    return {
        "batch_content_hash_sha256": staged.batch_content_hash_sha256,
        "batch_id": staged.batch_id,
        "raw_content_hash_sha256": staged.raw_content_hash_sha256,
        "transform_manifest_hash_sha256": (
            batch.provenance.transform_manifest_hash_sha256
        ),
    }


def _id_set_digest(values: Sequence[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readback_payload(
    readback: ModelProjectionReadback,
    *,
    symbol: str | None = None,
) -> dict[str, object]:
    nodes = list(readback.postgres_nodes)
    edges = list(readback.postgres_edges)
    if symbol is not None:
        selected_nodes = [node for node in nodes if node.qualified_name == symbol]
        if not selected_nodes:
            msg = f"projection symbol not found: {symbol}"
            raise LookupError(msg)
        selected_names = {node.qualified_name for node in selected_nodes}
        selected_edges = [
            edge
            for edge in edges
            if edge.source_qualified_name in selected_names
            or edge.target_qualified_name in selected_names
        ]
    else:
        selected_nodes = nodes[:10]
        selected_edges = edges[:10]
    return {
        "graph_edge_count": readback.graph_edge_count,
        "graph_edge_id_set_sha256": _id_set_digest(readback.graph_edge_ids),
        "graph_node_count": readback.graph_node_count,
        "graph_node_id_set_sha256": _id_set_digest(readback.graph_node_ids),
        "postgres_edge_count": len(edges),
        "postgres_node_count": len(nodes),
        "qdrant_document_id_set_sha256": _id_set_digest(readback.qdrant.document_ids),
        "qdrant_point_count": readback.qdrant.point_count,
        "qdrant_point_id_set_sha256": _id_set_digest(readback.qdrant.point_ids),
        "selected_edges": [edge.model_dump(mode="json") for edge in selected_edges],
        "selected_nodes": [node.model_dump(mode="json") for node in selected_nodes],
    }


def _result_payload(
    *,
    command: str,
    decision: str,
    batch: ModelCodeProjectionBatch,
    staged: StagedCodeProjection | None,
    applied: ModelProjectionApplyReport | None,
    readback: ModelProjectionReadback,
    symbol: str | None = None,
) -> dict[str, object]:
    return {
        "apply": applied.model_dump(mode="json") if applied is not None else None,
        "artifacts": (
            _staged_payload(staged, batch=batch) if staged is not None else None
        ),
        "batch_id": batch.batch_id,
        "command": command,
        "decision": decision,
        "projection": {
            "edges": len(batch.edges),
            "nodes": len(batch.nodes),
            "semantic_documents": len(batch.semantic_documents),
        },
        "readback": _readback_payload(readback, symbol=symbol),
        "source": {
            "cursor_sequence": batch.cursor.sequence,
            "raw_content_hash_sha256": batch.source.raw_content_hash_sha256,
            "relative_path": batch.source.relative_path,
            "repository_id": batch.source.repository_id,
            "source_id": batch.source.source_id,
            "tenant_id": batch.source.tenant_id,
        },
    }


async def _ingest(args: argparse.Namespace) -> dict[str, object]:
    tenant_id = _require_tenant_id(str(args.tenant_id))
    repository_id = _require_lab_repository_id(str(args.repository_id))
    repository_instance_id = str(args.repository_instance_id)
    projection_repository_id = _require_projection_repository_id(
        repository_id,
        repository_instance_id,
    )
    source_path, relative_path = _resolve_source_path(
        Path(str(args.root)),
        str(args.path),
    )
    store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    source_id = derive_code_source_id(
        tenant_id=tenant_id,
        repository_id=projection_repository_id,
        relative_path=relative_path,
    )
    with store.source_lock(source_id):
        # Capture every projection-defining input while holding the source lock.
        # A caller that started earlier must not promote stale bytes at a newer
        # cursor after another caller wins the lock and applies a newer source.
        raw_source = source_path.read_bytes()
        configuration = _load_extraction_configuration()
        current_record = store.load_current(source_id)
        current = current_record.batch if current_record is not None else None
        manifest_artifact = store.stage_content_artifact(configuration.contract_bytes)
        if manifest_artifact.content_hash_sha256 != configuration.contract_hash_sha256:
            raise RuntimeError("staged transform manifest digest does not match")
        if (
            store.read_content_artifact(configuration.contract_hash_sha256)
            != configuration.contract_bytes
        ):
            raise RuntimeError("staged transform manifest does not resolve exactly")
        projected = _build_snapshot(
            raw_source=raw_source,
            tenant_id=tenant_id,
            repository_id=repository_id,
            repository_instance_id=repository_instance_id,
            projection_repository_id=projection_repository_id,
            relative_path=relative_path,
            current=current,
            configuration=configuration,
        )
        batch = projected.batch
        documents_by_id = {
            document.document_id: document for document in batch.semantic_documents
        }
        artifacts_by_id = {
            artifact.document_id: artifact for artifact in projected.document_artifacts
        }
        if set(documents_by_id) != set(artifacts_by_id):
            raise RuntimeError(
                "semantic document records and generated artifacts do not match"
            )
        for document_id in sorted(documents_by_id):
            document = documents_by_id[document_id]
            artifact = artifacts_by_id[document_id]
            staged_document = store.stage_content_artifact(artifact.content)
            if (
                staged_document.content_hash_sha256
                != document.sanitized_content_hash_sha256
            ):
                raise RuntimeError("staged semantic document digest does not match")
        staged = store.stage(raw_source=raw_source, batch=batch)
        decision, applied, readback = await _apply_and_verify(
            batch,
            current=current,
            artifact_store=store,
        )
        store.mark_applied(staged)
    return _result_payload(
        command="ingest",
        decision=decision,
        batch=batch,
        staged=staged,
        applied=applied,
        readback=readback,
    )


def _store_and_identity(
    args: argparse.Namespace,
) -> tuple[
    CodeProjectionArtifactStore,
    str,
    str,
    str,
    str,
]:
    tenant_id = _require_tenant_id(str(args.tenant_id))
    repository_id = _require_lab_repository_id(str(args.repository_id))
    projection_repository_id = _require_projection_repository_id(
        repository_id,
        str(args.repository_instance_id),
    )
    relative_path = normalize_relative_path(str(args.path))
    store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    source_id = derive_code_source_id(
        tenant_id=tenant_id,
        repository_id=projection_repository_id,
        relative_path=relative_path,
    )
    return store, tenant_id, projection_repository_id, relative_path, source_id


def _load_current(
    store: CodeProjectionArtifactStore,
    *,
    tenant_id: str,
    repository_id: str,
    relative_path: str,
    source_id: str,
) -> CurrentCodeProjection:
    current = store.load_current(source_id)
    if current is None:
        msg = (
            "no applied projection exists for "
            f"{tenant_id}:{repository_id}:{relative_path}"
        )
        raise FileNotFoundError(msg)
    if (
        current.batch.source.tenant_id != tenant_id
        or current.batch.source.repository_id != repository_id
        or current.batch.source.relative_path != relative_path
    ):
        raise RuntimeError("current source identity does not match its stable ID")
    return current


async def _inspect(args: argparse.Namespace) -> dict[str, object]:
    store, tenant_id, repository_id, relative_path, source_id = _store_and_identity(
        args
    )
    with store.source_lock(source_id):
        current = _load_current(
            store,
            tenant_id=tenant_id,
            repository_id=repository_id,
            relative_path=relative_path,
            source_id=source_id,
        )
        batch = current.batch
        async with _live_clients(store) as (
            postgres_pool,
            graph_driver,
            qdrant_store,
        ):
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
                qdrant_store=qdrant_store,
            )
            assert_projection_readback(batch, readback)
    return _result_payload(
        command="inspect",
        decision="verified",
        batch=batch,
        staged=None,
        applied=None,
        readback=readback,
        symbol=str(args.symbol) if args.symbol is not None else None,
    )


async def _tombstone(args: argparse.Namespace) -> dict[str, object]:
    store, tenant_id, repository_id, relative_path, source_id = _store_and_identity(
        args
    )
    with store.source_lock(source_id):
        current_record = _load_current(
            store,
            tenant_id=tenant_id,
            repository_id=repository_id,
            relative_path=relative_path,
            source_id=source_id,
        )
        current = current_record.batch
        batch = _build_tombstone(current)
        raw_source = store.read_content_artifact(current.source.raw_content_hash_sha256)
        staged = store.stage(raw_source=raw_source, batch=batch)
        decision, applied, readback = await _apply_and_verify(
            batch,
            current=current,
            artifact_store=store,
        )
        store.mark_applied(staged)
    return _result_payload(
        command="tombstone",
        decision=decision,
        batch=batch,
        staged=staged,
        applied=applied,
        readback=readback,
    )


async def _search(args: argparse.Namespace) -> dict[str, object]:
    tenant_id = _require_tenant_id(str(args.tenant_id))
    query_text = str(args.query)
    repository_id = (
        normalize_repository_id(str(args.repository_id))
        if args.repository_id is not None
        else None
    )
    store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    async with _live_qdrant_store(store) as qdrant_store:
        collection = await qdrant_store.ensure_collection()
        hits = await qdrant_store.search(
            query_text=query_text,
            tenant_id=tenant_id,
            repository_id=repository_id,
            limit=int(args.limit),
            score_threshold=(
                float(args.score_threshold)
                if args.score_threshold is not None
                else None
            ),
        )
    return {
        "collection": collection.model_dump(mode="json"),
        "command": "search",
        "query_sha256": sha256_hex(query_text.encode("utf-8")),
        "repository_id": repository_id,
        "result_count": len(hits),
        "results": [hit.model_dump(mode="json") for hit in hits],
        "tenant_id": tenant_id,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m omniintelligence.code_projection",
        description=(
            "Extract real code and materialize a deterministic projection into "
            "the existing dev-lab Postgres, Memgraph, and Qdrant services."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ingest", "inspect", "tombstone"):
        child = subparsers.add_parser(command)
        child.add_argument("--tenant-id", required=True)
        child.add_argument("--repository-id", required=True)
        child.add_argument(
            "--repository-instance-id",
            default=_DEFAULT_REPOSITORY_INSTANCE_ID,
            help=(
                "checkout instance this projection belongs to; folded into the "
                "policy scope and the stored projection repository identity "
                f"(default: {_DEFAULT_REPOSITORY_INSTANCE_ID})"
            ),
        )
        child.add_argument("--path", required=True)
        child.add_argument("--artifact-root", required=True)
        if command == "ingest":
            child.add_argument("--root", required=True)
        if command == "inspect":
            child.add_argument("--symbol")
    search = subparsers.add_parser("search")
    search.add_argument("--tenant-id", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--artifact-root", required=True)
    search.add_argument(
        "--repository-id",
        help=(
            "exact stored projection repository identity to filter on; for a "
            "non-canonical checkout pass the '<repository>/instances/<id>' form"
        ),
    )
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--score-threshold", type=float)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "ingest":
        return asyncio.run(_ingest(args))
    if args.command == "inspect":
        return asyncio.run(_inspect(args))
    if args.command == "tombstone":
        return asyncio.run(_tombstone(args))
    if args.command == "search":
        return asyncio.run(_search(args))
    msg = f"unsupported command: {args.command}"
    raise ValueError(msg)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one fail-closed operator command and emit a JSON receipt."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _dispatch(args)
    except Exception as exc:
        error = {
            "error": type(exc).__name__,
            "message": str(exc),
            "status": "failed",
        }
        sys.stderr.write(json.dumps(error, sort_keys=True) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no branch
    raise SystemExit(main())
