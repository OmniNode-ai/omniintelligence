# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Operator-boundary tests for executable dev-lab code ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel

import omniintelligence.code_projection.__main__ as cli
import omniintelligence.nodes.node_ast_extraction_compute as ast_extraction_package
from omniintelligence.code_projection._canonical import canonical_json_bytes
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.codec import (
    derive_code_source_id as canonical_derive_code_source_id,
)
from omniintelligence.code_projection.codec import plan_code_projection_replay
from omniintelligence.code_projection.materializer import (
    ModelProjectionApplyReport,
    ModelProjectionEdgeReadback,
    ModelProjectionNodeReadback,
    ModelProjectionReadback,
    _decoded_labels,
    _decoded_record_payload,
    _metadata_mapping,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionNode,
)
from tests.unit.code_projection.fixture_vectors import build_fixture_batches

pytestmark = pytest.mark.unit

_LAB_REPOSITORY_ID = "lab/omn-16061/cli-proof"
_RELATIVE_PATH = "src/sample.py"
_SOURCE_A = b'''"""Small executable projection fixture."""\n\n\nclass Greeter:\n    def greet(self, name: str) -> str:\n        return name\n'''
_SOURCE_B = _SOURCE_A + b"\n\ndef build_greeter() -> Greeter:\n    return Greeter()\n"


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


def _matching_readback(batch: ModelCodeProjectionBatch) -> ModelProjectionReadback:
    node_names = {node.node_id: node.qualified_name for node in batch.nodes}
    return ModelProjectionReadback(
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
                    sorted(f"{label.namespace}={label.value}" for label in node.labels)
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
                    sorted(f"{label.namespace}={label.value}" for label in node.labels)
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


async def _fake_apply_and_verify(
    batch: ModelCodeProjectionBatch,
    *,
    current: ModelCodeProjectionBatch | None,
) -> tuple[str, ModelProjectionApplyReport | None, ModelProjectionReadback]:
    replay = plan_code_projection_replay(
        batch,
        current.manifest if current is not None else None,
    )
    if replay.decision in {"stale", "conflict"}:
        raise RuntimeError(f"unexpected {replay.decision} projection in test")
    applied = (
        ModelProjectionApplyReport(
            source_id=batch.source.source_id,
            batch_id=batch.batch_id,
            operation=batch.operation,
            postgres_nodes_written=len(batch.nodes),
            postgres_edges_written=len(batch.edges),
            postgres_nodes_deleted=0,
            graph_nodes_written=len(batch.nodes),
            graph_edges_written=len(batch.edges),
        )
        if replay.decision == "replace"
        else None
    )
    return replay.decision, applied, _matching_readback(batch)


def _write_source(root: Path, payload: bytes = _SOURCE_A) -> Path:
    source_path = root / _RELATIVE_PATH
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)
    return source_path


def _ingest_argv(root: Path, artifact_root: Path) -> list[str]:
    return [
        "ingest",
        "--repository-id",
        _LAB_REPOSITORY_ID,
        "--root",
        str(root),
        "--path",
        _RELATIVE_PATH,
        "--artifact-root",
        str(artifact_root),
    ]


def _state_argv(command: str, artifact_root: Path) -> list[str]:
    return [
        command,
        "--repository-id",
        _LAB_REPOSITORY_ID,
        "--path",
        _RELATIVE_PATH,
        "--artifact-root",
        str(artifact_root),
    ]


def _invoke_success(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> dict[str, Any]:
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_ingest_cli_executes_real_extraction_and_noops_identical_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    first = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    second = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)

    assert first["command"] == "ingest"
    assert first["decision"] == "replace"
    assert first["source"]["cursor_sequence"] == 1
    assert first["projection"]["nodes"] > 0
    assert first["readback"]["graph_node_count"] == first["projection"]["nodes"]
    assert second["decision"] == "noop"
    assert second["apply"] is None
    assert second["batch_id"] == first["batch_id"]
    assert second["source"]["cursor_sequence"] == 1

    current = CodeProjectionArtifactStore(artifact_root).find_current_batch(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )
    assert current is not None
    assert current.batch_id == first["batch_id"]


def test_unchanged_source_advances_sequence_when_projection_config_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    first = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    configuration = cli._load_extraction_configuration()
    changed_configuration = replace(
        configuration,
        contract_hash_sha256=hashlib.sha256(
            configuration.contract_bytes + b"\n# sequence-change-proof\n"
        ).hexdigest(),
        contract_bytes=configuration.contract_bytes + b"\n# sequence-change-proof\n",
    )
    monkeypatch.setattr(
        cli,
        "_load_extraction_configuration",
        lambda: changed_configuration,
    )

    second = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)

    assert second["decision"] == "replace"
    assert second["batch_id"] != first["batch_id"]
    assert (
        second["source"]["raw_content_hash_sha256"]
        == (first["source"]["raw_content_hash_sha256"])
    )
    assert second["source"]["cursor_sequence"] == 2


def test_changed_source_advances_sequence_and_current_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    source_path = _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    first = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    source_path.write_bytes(_SOURCE_B)
    second = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)

    assert second["decision"] == "replace"
    assert second["batch_id"] != first["batch_id"]
    assert (
        second["source"]["raw_content_hash_sha256"]
        != (first["source"]["raw_content_hash_sha256"])
    )
    assert second["source"]["cursor_sequence"] == 2


def test_source_capture_occurs_after_winning_the_source_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    source_path = _write_source(source_root)
    args = cli._parser().parse_args(_ingest_argv(source_root, artifact_root))
    original_derive = canonical_derive_code_source_id
    first_reached_lock_boundary = threading.Event()
    allow_first_to_acquire = threading.Event()
    results: dict[str, dict[str, object]] = {}
    failures: list[BaseException] = []

    def delayed_derive(*, repository_id: str, relative_path: str) -> str:
        source_id = original_derive(
            repository_id=repository_id,
            relative_path=relative_path,
        )
        if threading.current_thread().name == "older-caller":
            first_reached_lock_boundary.set()
            if not allow_first_to_acquire.wait(timeout=10):
                raise TimeoutError("newer caller did not complete in time")
        return source_id

    def run_ingest(result_name: str) -> None:
        try:
            results[result_name] = asyncio.run(cli._ingest(args))
        except BaseException as exc:  # pragma: no cover - surfaced below
            failures.append(exc)

    monkeypatch.setattr(cli, "derive_code_source_id", delayed_derive)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    older = threading.Thread(
        target=run_ingest,
        args=("older",),
        name="older-caller",
    )
    older.start()
    assert first_reached_lock_boundary.wait(timeout=10)

    # The older invocation has resolved identity but must not have captured A.
    # Let a newer caller win the lock after the authoritative file becomes B.
    source_path.write_bytes(_SOURCE_B)
    newer = threading.Thread(
        target=run_ingest,
        args=("newer",),
        name="newer-caller",
    )
    newer.start()
    newer.join(timeout=10)
    assert not newer.is_alive()
    allow_first_to_acquire.set()
    older.join(timeout=10)
    assert not older.is_alive()
    assert failures == []

    newer_result = cast(dict[str, Any], results["newer"])
    older_result = cast(dict[str, Any], results["older"])
    expected_hash = hashlib.sha256(_SOURCE_B).hexdigest()
    assert newer_result["decision"] == "replace"
    assert older_result["decision"] == "noop"
    assert newer_result["batch_id"] == older_result["batch_id"]
    assert newer_result["source"] == older_result["source"]
    assert newer_result["source"]["cursor_sequence"] == 1
    assert newer_result["source"]["raw_content_hash_sha256"] == expected_hash


def test_failed_live_apply_never_advances_current_artifact_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)

    async def fail_apply(
        batch: ModelCodeProjectionBatch,
        *,
        current: ModelCodeProjectionBatch | None,
    ) -> tuple[str, ModelProjectionApplyReport | None, ModelProjectionReadback]:
        del batch, current
        raise RuntimeError("simulated lab write failure")

    monkeypatch.setattr(cli, "_apply_and_verify", fail_apply)

    assert cli.main(_ingest_argv(source_root, artifact_root)) == 1
    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert captured.out == ""
    assert error == {
        "error": "RuntimeError",
        "message": "simulated lab write failure",
        "status": "failed",
    }
    assert (
        CodeProjectionArtifactStore(artifact_root).find_current_batch(
            repository_id=_LAB_REPOSITORY_ID,
            relative_path=_RELATIVE_PATH,
        )
        is None
    )


def test_retained_raw_source_never_claims_to_be_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    raw_source = _SOURCE_A + b'\nAPI_TOKEN = "retained-verbatim-proof"\n'
    _write_source(source_root, raw_source)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    current = CodeProjectionArtifactStore(artifact_root).find_current(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )

    assert current is not None
    assert current.raw_artifact_path.read_bytes() == raw_source
    assert current.batch.policy.redaction_state == "not_required"


def test_content_addressed_transform_manifest_resolves_in_artifact_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)

    _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    current = CodeProjectionArtifactStore(artifact_root).find_current_batch(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )

    assert current is not None
    manifest_digest = current.provenance.transform_manifest_hash_sha256
    assert current.provenance.transform_manifest_ref == (
        f"artifact://sha256/{manifest_digest}"
    )
    resolved_artifacts = [
        path
        for path in artifact_root.rglob("*")
        if path.is_file()
        and hashlib.sha256(path.read_bytes()).hexdigest() == manifest_digest
    ]
    assert resolved_artifacts, (
        "transform_manifest_ref claims a content-addressed artifact that is not staged"
    )


@pytest.mark.parametrize(
    "corruption_kind",
    [
        "readback_drift",
        "malformed_metadata",
        "malformed_labels",
        "malformed_record",
        "malformed_evidence",
    ],
)
async def test_identical_replay_repairs_backend_drift_before_returning_success(
    corruption_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    exact = _matching_readback(batch)
    drifted = exact.model_copy(update={"postgres_nodes": ()})
    postgres = object()
    graph = object()
    read_attempts = 0
    apply_calls: list[ModelCodeProjectionBatch] = []

    @asynccontextmanager
    async def fake_live_clients() -> Any:
        yield postgres, graph

    async def fake_read(
        incoming: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionReadback:
        nonlocal read_attempts
        assert incoming == batch
        assert postgres_pool is postgres
        assert graph_driver is graph
        read_attempts += 1
        if read_attempts == 1:
            if corruption_kind == "readback_drift":
                return drifted
            if corruption_kind == "malformed_metadata":
                _metadata_mapping('{"code_projection":')
            elif corruption_kind == "malformed_labels":
                _decoded_labels('[{"namespace":')
            elif corruption_kind == "malformed_record":
                _decoded_record_payload('{"display_name":')
            else:
                _decoded_record_payload('{"evidence_refs":[')
            raise AssertionError("malformed payload decoder did not fail closed")
        return exact

    async def fake_apply(
        incoming: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionApplyReport:
        assert postgres_pool is postgres
        assert graph_driver is graph
        apply_calls.append(incoming)
        return ModelProjectionApplyReport(
            source_id=incoming.source.source_id,
            batch_id=incoming.batch_id,
            operation=incoming.operation,
            postgres_nodes_written=len(incoming.nodes),
            postgres_edges_written=len(incoming.edges),
            postgres_nodes_deleted=0,
            graph_nodes_written=len(incoming.nodes),
            graph_edges_written=len(incoming.edges),
        )

    monkeypatch.setattr(cli, "_live_clients", fake_live_clients)
    monkeypatch.setattr(cli, "read_code_projection", fake_read)
    monkeypatch.setattr(cli, "apply_code_projection", fake_apply)

    decision, applied, readback = await cli._apply_and_verify(batch, current=batch)

    assert decision == "repair"
    assert applied is not None
    assert apply_calls == [batch]
    assert readback == exact
    assert read_attempts == 2


@pytest.mark.parametrize(
    "backend_failure",
    [
        ConnectionError("backend connection failed"),
        PermissionError("backend authentication failed"),
        RuntimeError("backend query programming failure"),
    ],
)
async def test_identical_replay_does_not_repair_non_integrity_backend_failures(
    backend_failure: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    postgres = object()
    graph = object()
    apply_calls = 0

    @asynccontextmanager
    async def fake_live_clients() -> Any:
        yield postgres, graph

    async def fake_read(
        incoming: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionReadback:
        assert incoming == batch
        assert postgres_pool is postgres
        assert graph_driver is graph
        raise backend_failure

    async def fake_apply(
        incoming: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionApplyReport:
        nonlocal apply_calls
        del incoming, postgres_pool, graph_driver
        apply_calls += 1
        raise AssertionError("non-integrity backend failure triggered repair")

    monkeypatch.setattr(cli, "_live_clients", fake_live_clients)
    monkeypatch.setattr(cli, "read_code_projection", fake_read)
    monkeypatch.setattr(cli, "apply_code_projection", fake_apply)

    with pytest.raises(type(backend_failure), match=str(backend_failure)):
        await cli._apply_and_verify(batch, current=batch)

    assert apply_calls == 0


def test_tombstone_cli_advances_once_then_noops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)
    _invoke_success(_ingest_argv(source_root, artifact_root), capsys)

    deleted = _invoke_success(_state_argv("tombstone", artifact_root), capsys)
    repeated = _invoke_success(_state_argv("tombstone", artifact_root), capsys)

    assert deleted["decision"] == "replace"
    assert deleted["apply"]["operation"] == "tombstone"
    assert deleted["projection"] == {
        "edges": 0,
        "nodes": 0,
        "semantic_documents": 0,
    }
    assert deleted["source"]["cursor_sequence"] == 2
    assert repeated["decision"] == "noop"
    assert repeated["apply"] is None
    assert repeated["batch_id"] == deleted["batch_id"]
    assert repeated["source"]["cursor_sequence"] == 2

    current = CodeProjectionArtifactStore(artifact_root).find_current_batch(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )
    assert current is not None
    assert current.operation == "tombstone"


def test_inspect_cli_reads_the_applied_projection_without_mutating_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)
    ingested = _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    current = CodeProjectionArtifactStore(artifact_root).find_current_batch(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )
    assert current is not None
    postgres = object()
    graph = object()

    @asynccontextmanager
    async def fake_live_clients() -> Any:
        yield postgres, graph

    async def fake_read(
        batch: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionReadback:
        assert batch == current
        assert postgres_pool is postgres
        assert graph_driver is graph
        return _matching_readback(batch)

    monkeypatch.setattr(cli, "_live_clients", fake_live_clients)
    monkeypatch.setattr(cli, "read_code_projection", fake_read)

    inspected = _invoke_success(_state_argv("inspect", artifact_root), capsys)

    assert inspected["command"] == "inspect"
    assert inspected["decision"] == "verified"
    assert inspected["apply"] is None
    assert inspected["artifacts"] is None
    assert inspected["batch_id"] == ingested["batch_id"]


def test_inspect_cli_filters_by_qualified_symbol_and_fails_closed_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "repository"
    artifact_root = tmp_path / "artifacts"
    _write_source(source_root)
    monkeypatch.setattr(cli, "_apply_and_verify", _fake_apply_and_verify)
    _invoke_success(_ingest_argv(source_root, artifact_root), capsys)
    current = CodeProjectionArtifactStore(artifact_root).find_current_batch(
        repository_id=_LAB_REPOSITORY_ID,
        relative_path=_RELATIVE_PATH,
    )
    assert current is not None
    symbol = current.nodes[0].qualified_name

    @asynccontextmanager
    async def fake_live_clients() -> Any:
        yield object(), object()

    async def fake_read(
        batch: ModelCodeProjectionBatch,
        *,
        postgres_pool: object,
        graph_driver: object,
    ) -> ModelProjectionReadback:
        del postgres_pool, graph_driver
        return _matching_readback(batch)

    monkeypatch.setattr(cli, "_live_clients", fake_live_clients)
    monkeypatch.setattr(cli, "read_code_projection", fake_read)
    symbol_argv = [*_state_argv("inspect", artifact_root), "--symbol", symbol]

    selected = _invoke_success(symbol_argv, capsys)

    assert [
        node["qualified_name"] for node in selected["readback"]["selected_nodes"]
    ] == [symbol]
    assert all(
        edge["source_qualified_name"] == symbol
        or edge["target_qualified_name"] == symbol
        for edge in selected["readback"]["selected_edges"]
    )

    missing_argv = [
        *_state_argv("inspect", artifact_root),
        "--symbol",
        "sample.does_not_exist",
    ]
    assert cli.main(missing_argv) == 1
    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert captured.out == ""
    assert error["error"] == "LookupError"
    assert error["message"] == "projection symbol not found: sample.does_not_exist"


@pytest.mark.parametrize(
    "repository_id",
    [
        "github.com/OmniNode-ai/omniintelligence",
        "lab/",
        "lab//unnamed",
        "lab/unnamed/",
        "Lab/omn-16061/proof",
    ],
)
def test_live_commands_reject_noncanonical_or_empty_lab_namespaces(
    repository_id: str,
) -> None:
    with pytest.raises(ValueError, match="namespaced repository_id"):
        cli._require_lab_repository_id(repository_id)


def test_live_commands_accept_an_explicit_nonempty_lab_namespace() -> None:
    assert cli._require_lab_repository_id(_LAB_REPOSITORY_ID) == _LAB_REPOSITORY_ID


def test_ingest_cli_rejects_non_lab_repository_before_creating_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact_root = tmp_path / "artifacts"
    argv = _ingest_argv(tmp_path, artifact_root)
    argv[2] = "github.com/OmniNode-ai/omniintelligence"

    assert cli.main(argv) == 1

    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert captured.out == ""
    assert error["status"] == "failed"
    assert error["error"] == "ValueError"
    assert "namespaced repository_id" in error["message"]
    assert not artifact_root.exists()


def test_source_path_is_canonicalized_and_confined_to_declared_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    source_path = _write_source(root)
    resolved, canonical = cli._resolve_source_path(root, "./src\\sample.py")

    assert resolved == source_path.resolve()
    assert canonical == _RELATIVE_PATH

    with pytest.raises(ValueError, match="traverse parents"):
        cli._resolve_source_path(root, "../outside.py")

    outside = tmp_path / "outside.py"
    outside.write_bytes(_SOURCE_A)
    symlink = root / "src/symlink.py"
    symlink.symlink_to(outside)
    with pytest.raises(ValueError, match="outside the declared repository root"):
        cli._resolve_source_path(root, "src/symlink.py")


def test_extraction_configuration_is_loaded_from_package_contract_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_file = tmp_path / "node_ast_extraction_compute/__init__.py"
    package_file.parent.mkdir()
    package_file.write_text("", encoding="utf-8")
    contract = b"""configuration:
  deterministic_classification:
    enabled: true
  quality_scoring:
    enabled: true
  language_extractors:
    python:
      enabled: true
"""
    package_file.with_name("contract.yaml").write_bytes(contract)
    monkeypatch.setattr(ast_extraction_package, "__file__", str(package_file))

    configuration = cli._load_extraction_configuration()

    assert configuration.classification == {"enabled": True}
    assert configuration.quality == {"enabled": True}
    assert configuration.languages == {"python": {"enabled": True}}
    assert configuration.contract_hash_sha256 == hashlib.sha256(contract).hexdigest()
    assert configuration.contract_bytes == contract


def test_extraction_configuration_fails_closed_when_required_map_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_file = tmp_path / "node_ast_extraction_compute/__init__.py"
    package_file.parent.mkdir()
    package_file.write_text("", encoding="utf-8")
    package_file.with_name("contract.yaml").write_text(
        "configuration:\n  deterministic_classification: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ast_extraction_package, "__file__", str(package_file))

    with pytest.raises(ValueError, match="quality_scoring must be a mapping"):
        cli._load_extraction_configuration()
