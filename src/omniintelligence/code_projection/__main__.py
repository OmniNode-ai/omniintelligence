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
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import asyncpg
import yaml
from neo4j import AsyncDriver, AsyncGraphDatabase

import omniintelligence.nodes.node_ast_extraction_compute as ast_extraction_package
from omniintelligence.code_projection._canonical import (
    normalize_relative_path,
    normalize_repository_id,
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
from omniintelligence.code_projection.extraction import project_source
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

_CURSOR_AUTHORITY = "omniintelligence.code-projection.dev-lab.v1"
_PRODUCER_VERSION = "1.0.0"
_LAB_REPOSITORY_PREFIX = "lab/"


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


def _policy(repository_id: str) -> ModelCodeProjectionPolicy:
    return ModelCodeProjectionPolicy(
        scope_ref=f"repository:{repository_id}",
        access_scope="repository",
        visibility="repository",
        redaction_state="not_required",
        trust_tier="verified_source",
        retention_class="source_controlled",
        policy_version="dev-lab-code-ingestion-v1",
        metadata_allowlist_version="code-projection-metadata-v1",
    )


def _provenance(
    configuration: _ExtractionConfiguration,
) -> ModelCodeProjectionProvenance:
    contract_hash = configuration.contract_hash_sha256
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection",
        producer_version=_PRODUCER_VERSION,
        projection_builder_version="1.0.0",
        extractor_name="python-ast-and-multilang-regex",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=contract_hash,
        transform_manifest_ref=f"artifact://sha256/{contract_hash}",
        transform_manifest_hash_sha256=contract_hash,
        labeler_version="deterministic-classifier-quality-semantic-v1",
        chunker_version=None,
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
    if not postgres_url:
        raise ValueError(
            "OMNIINTELLIGENCE_DB_URL is not bound by the active runtime overlay"
        )
    if not graph_uri:
        raise ValueError(
            "ARCH_GRAPH_BOLT_URI is not bound by the active runtime overlay"
        )
    return _LiveClientConfiguration(
        postgres_url=postgres_url,
        graph_uri=graph_uri,
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
    repository_id: str,
    relative_path: str,
    current: ModelCodeProjectionBatch | None,
    configuration: _ExtractionConfiguration,
) -> ModelCodeProjectionBatch:
    source_hash = sha256_hex(raw_source)
    sequence = _next_sequence(current, incoming_hash=source_hash)

    def build(cursor_sequence: int) -> ModelCodeProjectionBatch:
        return project_source(
            raw_source=raw_source,
            repository_id=repository_id,
            relative_path=relative_path,
            source_version=f"sha256:{source_hash}",
            language=_language(relative_path),
            cursor_authority=_CURSOR_AUTHORITY,
            cursor_sequence=cursor_sequence,
            policy=_policy(repository_id),
            provenance=_provenance(configuration),
            classification_config=configuration.classification,
            quality_config=configuration.quality,
            language_extractor_config=configuration.languages,
        )

    batch = build(sequence)
    if (
        current is not None
        and sequence == current.cursor.sequence
        and batch.batch_id != current.batch_id
    ):
        return build(sequence + 1)
    return batch


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


@asynccontextmanager
async def _live_clients() -> AsyncIterator[tuple[asyncpg.Pool, AsyncDriver]]:
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
        yield pool, graph_driver
    finally:
        await graph_driver.close()
        await pool.close()


async def _apply_and_verify(
    batch: ModelCodeProjectionBatch,
    *,
    current: ModelCodeProjectionBatch | None,
) -> tuple[str, ModelProjectionApplyReport | None, ModelProjectionReadback]:
    replay = plan_code_projection_replay(
        batch,
        current.manifest if current is not None else None,
    )
    if replay.decision in {"stale", "conflict"}:
        msg = f"refusing {replay.decision} live projection"
        raise RuntimeError(msg)
    decision: str = replay.decision
    async with _live_clients() as (postgres_pool, graph_driver):
        apply_report: ModelProjectionApplyReport | None = None
        if decision == "replace":
            apply_report = await apply_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
            )
        try:
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
            )
            assert_projection_readback(batch, readback)
        except ProjectionReadbackIntegrityError:
            if decision != "noop":
                raise
            apply_report = await apply_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
            )
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
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
        },
    }


async def _ingest(args: argparse.Namespace) -> dict[str, object]:
    repository_id = _require_lab_repository_id(str(args.repository_id))
    source_path, relative_path = _resolve_source_path(
        Path(str(args.root)),
        str(args.path),
    )
    store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    source_id = derive_code_source_id(
        repository_id=repository_id,
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
        batch = _build_snapshot(
            raw_source=raw_source,
            repository_id=repository_id,
            relative_path=relative_path,
            current=current,
            configuration=configuration,
        )
        staged = store.stage(raw_source=raw_source, batch=batch)
        decision, applied, readback = await _apply_and_verify(batch, current=current)
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
]:
    repository_id = _require_lab_repository_id(str(args.repository_id))
    relative_path = normalize_relative_path(str(args.path))
    store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    source_id = derive_code_source_id(
        repository_id=repository_id,
        relative_path=relative_path,
    )
    return store, repository_id, relative_path, source_id


def _load_current(
    store: CodeProjectionArtifactStore,
    *,
    repository_id: str,
    relative_path: str,
    source_id: str,
) -> CurrentCodeProjection:
    current = store.load_current(source_id)
    if current is None:
        msg = f"no applied projection exists for {repository_id}:{relative_path}"
        raise FileNotFoundError(msg)
    if (
        current.batch.source.repository_id != repository_id
        or current.batch.source.relative_path != relative_path
    ):
        raise RuntimeError("current source identity does not match its stable ID")
    return current


async def _inspect(args: argparse.Namespace) -> dict[str, object]:
    store, repository_id, relative_path, source_id = _store_and_identity(args)
    with store.source_lock(source_id):
        current = _load_current(
            store,
            repository_id=repository_id,
            relative_path=relative_path,
            source_id=source_id,
        )
        batch = current.batch
        async with _live_clients() as (postgres_pool, graph_driver):
            readback = await read_code_projection(
                batch,
                postgres_pool=postgres_pool,
                graph_driver=graph_driver,
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
    store, repository_id, relative_path, source_id = _store_and_identity(args)
    with store.source_lock(source_id):
        current_record = _load_current(
            store,
            repository_id=repository_id,
            relative_path=relative_path,
            source_id=source_id,
        )
        current = current_record.batch
        batch = _build_tombstone(current)
        raw_source = store.read_content_artifact(current.source.raw_content_hash_sha256)
        staged = store.stage(raw_source=raw_source, batch=batch)
        decision, applied, readback = await _apply_and_verify(batch, current=current)
        store.mark_applied(staged)
    return _result_payload(
        command="tombstone",
        decision=decision,
        batch=batch,
        staged=staged,
        applied=applied,
        readback=readback,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m omniintelligence.code_projection",
        description=(
            "Extract real code and materialize a deterministic projection into "
            "the existing dev-lab Postgres and Memgraph services."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ingest", "inspect", "tombstone"):
        child = subparsers.add_parser(command)
        child.add_argument("--repository-id", required=True)
        child.add_argument("--path", required=True)
        child.add_argument("--artifact-root", required=True)
        if command == "ingest":
            child.add_argument("--root", required=True)
        if command == "inspect":
            child.add_argument("--symbol")
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "ingest":
        return asyncio.run(_ingest(args))
    if args.command == "inspect":
        return asyncio.run(_inspect(args))
    if args.command == "tombstone":
        return asyncio.run(_tombstone(args))
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
