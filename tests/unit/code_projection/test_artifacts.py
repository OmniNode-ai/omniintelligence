# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Filesystem-state tests for deterministic code-projection artifacts."""

from __future__ import annotations

import hashlib
import multiprocessing
import threading
import time
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import omniintelligence.code_projection.artifacts as artifact_module
from omniintelligence.code_projection.artifacts import (
    CodeProjectionArtifactIntegrityError,
    CodeProjectionArtifactStore,
    CurrentCodeProjection,
    StagedCodeProjection,
)
from omniintelligence.code_projection.codec import build_code_projection_batch
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
)
from tests.unit.code_projection.fixture_vectors import (
    FIXTURE_REPOSITORY_ID,
    FIXTURE_ROOT,
    build_fixture_batches,
    fixture_bytes,
)

pytestmark = pytest.mark.unit


def _raw_greeter() -> bytes:
    return (FIXTURE_ROOT / "sources/greeter.py.fixture").read_bytes()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stage_fixture_contract_artifacts(
    store: CodeProjectionArtifactStore,
    batch: ModelCodeProjectionBatch,
    *,
    omit: frozenset[str] = frozenset(),
) -> dict[str, Path]:
    candidates = {
        _sha256(payload): payload
        for payload in (
            fixture_bytes("transform_manifest.json"),
            fixture_bytes("sanitized/greeter-class.txt"),
            fixture_bytes("sanitized/greeter-class-v2.txt"),
            fixture_bytes("sanitized/widget-interface.txt"),
        )
    }
    required = {
        batch.provenance.transform_manifest_hash_sha256,
        *(
            document.sanitized_content_hash_sha256
            for document in batch.semantic_documents
        ),
        *(
            evidence_ref.removeprefix("artifact://sha256/")
            for edge in batch.edges
            for evidence_ref in edge.evidence_refs
        ),
    }
    unresolved = required - candidates.keys()
    assert not unresolved
    staged_paths: dict[str, Path] = {}
    for digest in sorted(required - omit):
        artifact = store.stage_content_artifact(candidates[digest])
        assert artifact.content_hash_sha256 == digest
        staged_paths[digest] = artifact.artifact_path
    return staged_paths


def _without_edge_evidence(
    batch: ModelCodeProjectionBatch,
) -> ModelCodeProjectionBatch:
    return build_code_projection_batch(
        source=batch.source,
        cursor=batch.cursor,
        policy=batch.policy,
        provenance=batch.provenance,
        nodes=batch.nodes,
        edges=tuple(
            edge.model_copy(update={"evidence_refs": ()}) for edge in batch.edges
        ),
        semantic_documents=batch.semantic_documents,
    )


def _without_semantic_documents(
    batch: ModelCodeProjectionBatch,
) -> ModelCodeProjectionBatch:
    return build_code_projection_batch(
        source=batch.source,
        cursor=batch.cursor,
        policy=batch.policy,
        provenance=batch.provenance,
        nodes=batch.nodes,
        edges=batch.edges,
    )


def _wait_for_file(path: Path, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for coordination file: {path.name}")
        time.sleep(0.01)


def _mark_applied_race_worker(
    artifact_root: str,
    staged: StagedCodeProjection,
    worker_name: str,
    coordination_root: str,
) -> None:
    coordination = Path(coordination_root)
    coordination.joinpath(f"started-{worker_name}").touch()
    _wait_for_file(coordination / "go")
    original_load = CodeProjectionArtifactStore.load_current
    first_load = True

    def gated_load(
        self: CodeProjectionArtifactStore,
        source_id: str,
    ) -> CurrentCodeProjection | None:
        nonlocal first_load
        current = original_load(self, source_id)
        if first_load:
            first_load = False
            coordination.joinpath(f"ready-{worker_name}").touch()
            _wait_for_file(coordination / f"release-{worker_name}")
        return current

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(CodeProjectionArtifactStore, "load_current", gated_load)
    store = CodeProjectionArtifactStore(artifact_root)
    try:
        with store.source_lock(staged.source_id):
            store.mark_applied(staged)
    except Exception as exc:
        outcome = f"error:{type(exc).__name__}:{exc}"
    else:
        outcome = "success"
    finally:
        monkeypatch.undo()
    coordination.joinpath(f"result-{worker_name}").write_text(
        outcome,
        encoding="utf-8",
    )


def test_stage_writes_deterministic_objects_without_advancing_current(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path / "explicit-artifacts")

    first = store.stage(raw_source=_raw_greeter(), batch=batch)
    second = store.stage(raw_source=_raw_greeter(), batch=batch)

    assert first == second
    assert first.raw_artifact_path.read_bytes() == _raw_greeter()
    assert first.batch_artifact_path.read_bytes().endswith(b"\n")
    assert first.raw_artifact_path.name == batch.source.raw_content_hash_sha256
    assert first.batch_artifact_path.stem == first.batch_content_hash_sha256
    assert batch.source.repository_id not in first.raw_artifact_path.as_posix()
    assert batch.source.relative_path not in first.batch_artifact_path.as_posix()
    assert store.load_current_batch(batch.source.source_id) is None
    assert (
        store.find_current_batch(
            tenant_id=batch.source.tenant_id,
            repository_id=batch.source.repository_id,
            relative_path=batch.source.relative_path,
        )
        is None
    )
    with pytest.raises(FrozenInstanceError):
        first.batch_id = "forbidden"  # type: ignore[misc]  # intentional mutation


def test_relative_root_remains_anchored_after_working_directory_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_working_directory = tmp_path / "original"
    later_working_directory = tmp_path / "later"
    original_working_directory.mkdir()
    later_working_directory.mkdir()
    monkeypatch.chdir(original_working_directory)

    store = CodeProjectionArtifactStore("relative-artifacts")
    expected_root = original_working_directory / "relative-artifacts"
    monkeypatch.chdir(later_working_directory)
    staged = store.stage_content_artifact(b"anchored-content")

    assert store.root == expected_root
    assert store.root.is_absolute()
    assert staged.artifact_path.is_relative_to(expected_root)
    assert (
        store.read_content_artifact(staged.content_hash_sha256) == b"anchored-content"
    )
    assert not (later_working_directory / "relative-artifacts").exists()


def test_symlinked_store_root_is_rejected(tmp_path: Path) -> None:
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    symlinked_root = tmp_path / "artifact-root"
    symlinked_root.symlink_to(redirect, target_is_directory=True)

    with pytest.raises(
        CodeProjectionArtifactIntegrityError,
        match="symbolic link",
    ):
        CodeProjectionArtifactStore(symlinked_root)


def test_symlinked_objects_directory_cannot_redirect_writes(tmp_path: Path) -> None:
    store = CodeProjectionArtifactStore(tmp_path / "artifact-root")
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    (store.root / "objects").symlink_to(redirect, target_is_directory=True)

    with pytest.raises(
        CodeProjectionArtifactIntegrityError,
        match="symbolic link",
    ):
        store.stage_content_artifact(b"must-not-be-redirected")

    assert not tuple(redirect.iterdir())


def test_symlinked_current_directory_cannot_redirect_promotion(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path / "artifact-root")
    _stage_fixture_contract_artifacts(store, batch)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    (store.root / "current").symlink_to(redirect, target_is_directory=True)

    with store.source_lock(batch.source.source_id):
        with pytest.raises(
            CodeProjectionArtifactIntegrityError,
            match="symbolic link",
        ):
            store.mark_applied(staged)

    assert not tuple(redirect.iterdir())


def test_symlinked_locks_directory_cannot_redirect_lock_creation(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path / "artifact-root")
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    (store.root / "locks").symlink_to(redirect, target_is_directory=True)

    with pytest.raises(
        CodeProjectionArtifactIntegrityError,
        match="symbolic link",
    ):
        with store.source_lock(batch.source.source_id):
            pytest.fail("a symlinked lock directory must never be entered")

    assert not tuple(redirect.iterdir())


def test_directory_creation_and_idempotent_object_stage_are_synchronized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CodeProjectionArtifactStore(tmp_path / "artifact-root")
    synchronized: list[Path] = []
    original_sync_directory = artifact_module._sync_directory

    def record_sync(path: Path) -> None:
        synchronized.append(path)
        original_sync_directory(path)

    monkeypatch.setattr(artifact_module, "_sync_directory", record_sync)
    first = store.stage_content_artifact(b"durable-object")

    assert store.root in synchronized
    assert store.root / "objects" in synchronized
    assert store.root / "objects" / "raw" in synchronized
    assert first.artifact_path.parent in synchronized

    synchronized.clear()
    second = store.stage_content_artifact(b"durable-object")

    assert second == first
    assert first.artifact_path.parent in synchronized


def test_mark_applied_supports_source_and_logical_identity_lookup(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)
    _stage_fixture_contract_artifacts(store, batch)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)

    with store.source_lock(batch.source.source_id):
        current = store.mark_applied(staged)

    assert current.batch == batch
    assert current.raw_artifact_path == staged.raw_artifact_path
    assert current.batch_artifact_path == staged.batch_artifact_path
    assert current.state_path.name == f"{batch.source.source_id}.json"
    assert store.load_current_batch(batch.source.source_id) == batch
    assert (
        store.find_current_batch(
            tenant_id=batch.source.tenant_id,
            repository_id=FIXTURE_REPOSITORY_ID,
            relative_path="src\\fixtures\\greeter.py",
        )
        == batch
    )
    with store.source_lock(batch.source.source_id):
        assert store.mark_applied(staged) == current


@pytest.mark.parametrize("reference_kind", ["manifest", "document", "evidence"])
def test_mark_applied_rejects_missing_contracted_artifact_reference(
    tmp_path: Path,
    reference_kind: str,
) -> None:
    base = build_fixture_batches()["python_a_seq1.json"]
    if reference_kind == "manifest":
        batch = base
        missing_digest = batch.provenance.transform_manifest_hash_sha256
        expected_message = "provenance transform manifest"
    elif reference_kind == "document":
        batch = _without_edge_evidence(base)
        missing_digest = batch.semantic_documents[0].sanitized_content_hash_sha256
        expected_message = "semantic document"
    else:
        batch = _without_semantic_documents(base)
        missing_digest = (
            batch.edges[0].evidence_refs[0].removeprefix("artifact://sha256/")
        )
        expected_message = "evidence"
    store = CodeProjectionArtifactStore(tmp_path / reference_kind)
    _stage_fixture_contract_artifacts(
        store,
        batch,
        omit=frozenset({missing_digest}),
    )
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)

    with store.source_lock(batch.source.source_id):
        with pytest.raises(
            CodeProjectionArtifactIntegrityError,
            match=expected_message,
        ):
            store.mark_applied(staged)

    assert store.load_current(batch.source.source_id) is None


@pytest.mark.parametrize("reference_kind", ["manifest", "document", "evidence"])
def test_load_current_revalidates_tampered_contracted_artifact_reference(
    tmp_path: Path,
    reference_kind: str,
) -> None:
    base = build_fixture_batches()["python_a_seq1.json"]
    if reference_kind == "manifest":
        batch = base
        tampered_digest = batch.provenance.transform_manifest_hash_sha256
        expected_message = "provenance transform manifest"
    elif reference_kind == "document":
        batch = _without_edge_evidence(base)
        tampered_digest = batch.semantic_documents[0].sanitized_content_hash_sha256
        expected_message = "semantic document"
    else:
        batch = _without_semantic_documents(base)
        tampered_digest = (
            batch.edges[0].evidence_refs[0].removeprefix("artifact://sha256/")
        )
        expected_message = "evidence"
    store = CodeProjectionArtifactStore(tmp_path / reference_kind)
    artifact_paths = _stage_fixture_contract_artifacts(store, batch)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    with store.source_lock(batch.source.source_id):
        store.mark_applied(staged)

    artifact_paths[tampered_digest].write_bytes(b"tampered-reference")

    with pytest.raises(
        CodeProjectionArtifactIntegrityError,
        match=expected_message,
    ):
        store.load_current(batch.source.source_id)


def test_mark_applied_requires_lock_ownership_by_calling_thread(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)
    _stage_fixture_contract_artifacts(store, batch)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    entered = threading.Event()
    release = threading.Event()
    holder_errors: list[BaseException] = []

    def hold_source_lock() -> None:
        try:
            with store.source_lock(batch.source.source_id):
                entered.set()
                if not release.wait(timeout=10):
                    raise TimeoutError("timed out waiting to release source lock")
        except BaseException as exc:  # pragma: no cover - asserted in caller
            holder_errors.append(exc)

    holder = threading.Thread(target=hold_source_lock)
    holder.start()
    assert entered.wait(timeout=10)
    try:
        with pytest.raises(RuntimeError, match="matching source_lock"):
            store.mark_applied(staged)
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive()
    assert not holder_errors
    with store.source_lock(batch.source.source_id):
        assert store.mark_applied(staged).batch == batch


def test_raw_source_mismatch_fails_before_any_current_state_change(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="raw source digest"):
        store.stage(raw_source=b"different source", batch=batch)

    assert store.load_current_batch(batch.source.source_id) is None
    assert not (tmp_path / "current").exists()


@pytest.mark.parametrize("tamper_target", ["state", "batch", "raw"])
def test_current_load_rejects_noncanonical_or_tampered_bytes(
    tmp_path: Path,
    tamper_target: str,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path / tamper_target)
    _stage_fixture_contract_artifacts(store, batch)
    with store.source_lock(batch.source.source_id):
        current = store.mark_applied(
            store.stage(raw_source=_raw_greeter(), batch=batch)
        )

    if tamper_target == "state":
        current.state_path.write_bytes(b" " + current.state_path.read_bytes())
    elif tamper_target == "batch":
        current.batch_artifact_path.write_bytes(
            current.batch_artifact_path.read_bytes() + b"\n"
        )
    else:
        current.raw_artifact_path.write_bytes(
            current.raw_artifact_path.read_bytes() + b"tampered"
        )

    with pytest.raises(CodeProjectionArtifactIntegrityError):
        store.load_current_batch(batch.source.source_id)


def test_forged_staging_receipt_cannot_redirect_artifact_reads(tmp_path: Path) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    forged = replace(staged, raw_artifact_path=tmp_path / "attacker-selected")

    with store.source_lock(batch.source.source_id):
        with pytest.raises(
            CodeProjectionArtifactIntegrityError,
            match="raw artifact path",
        ):
            store.mark_applied(forged)

    assert store.load_current_batch(batch.source.source_id) is None


def test_tombstone_then_higher_sequence_recreate_remains_replayable(
    tmp_path: Path,
) -> None:
    batches = build_fixture_batches()
    snapshot = batches["python_a_seq3.json"]
    tombstone = batches["source_tombstone_seq4.json"]
    recreate_cursor = ModelCodeProjectionCursor(
        authority=snapshot.cursor.authority,
        partition=snapshot.source.source_id,
        sequence=5,
    )
    recreate = build_code_projection_batch(
        source=snapshot.source,
        cursor=recreate_cursor,
        policy=snapshot.policy,
        provenance=snapshot.provenance,
        nodes=snapshot.nodes,
        edges=snapshot.edges,
        semantic_documents=snapshot.semantic_documents,
    )
    raw_source = _raw_greeter()
    store = CodeProjectionArtifactStore(tmp_path)
    _stage_fixture_contract_artifacts(store, snapshot)

    with store.source_lock(snapshot.source.source_id):
        store.mark_applied(store.stage(raw_source=raw_source, batch=snapshot))
        store.mark_applied(store.stage(raw_source=raw_source, batch=tombstone))
    assert store.load_current_batch(snapshot.source.source_id) == tombstone

    stale = store.stage(raw_source=raw_source, batch=snapshot)
    with store.source_lock(snapshot.source.source_id):
        with pytest.raises(ValueError, match="stale"):
            store.mark_applied(stale)
    assert store.load_current_batch(snapshot.source.source_id) == tombstone

    with store.source_lock(snapshot.source.source_id):
        store.mark_applied(store.stage(raw_source=raw_source, batch=recreate))
    assert store.load_current_batch(snapshot.source.source_id) == recreate
    assert (
        store.find_current_batch(
            tenant_id=snapshot.source.tenant_id,
            repository_id=snapshot.source.repository_id,
            relative_path=snapshot.source.relative_path,
        )
        == recreate
    )


def test_existing_corrupt_immutable_object_is_never_silently_overwritten(
    tmp_path: Path,
) -> None:
    batch = build_fixture_batches()["python_a_seq1.json"]
    store = CodeProjectionArtifactStore(tmp_path)
    staged = store.stage(raw_source=_raw_greeter(), batch=batch)
    staged.raw_artifact_path.write_bytes(b"corrupt")

    with pytest.raises(
        CodeProjectionArtifactIntegrityError,
        match="existing content-addressed content artifact is corrupt",
    ):
        store.stage(raw_source=_raw_greeter(), batch=batch)

    assert staged.raw_artifact_path.read_bytes() == b"corrupt"
    assert store.load_current_batch(batch.source.source_id) is None


def test_current_pointer_update_is_serialized_across_processes(
    tmp_path: Path,
) -> None:
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("interprocess current-pointer proof requires fork")
    batches = build_fixture_batches()
    initial = batches["python_a_seq1.json"]
    stale_candidate = batches["python_a_seq3.json"]
    newest_candidate = batches["source_tombstone_seq4.json"]
    artifact_root = tmp_path / "artifacts"
    coordination = tmp_path / "coordination"
    coordination.mkdir()
    store = CodeProjectionArtifactStore(artifact_root)
    _stage_fixture_contract_artifacts(store, initial)
    with store.source_lock(initial.source.source_id):
        store.mark_applied(store.stage(raw_source=_raw_greeter(), batch=initial))
    staged = {
        "stale": store.stage(
            raw_source=_raw_greeter(),
            batch=stale_candidate,
        ),
        "newest": store.stage(
            raw_source=_raw_greeter(),
            batch=newest_candidate,
        ),
    }
    context = multiprocessing.get_context("fork")
    processes = {
        name: context.Process(
            target=_mark_applied_race_worker,
            args=(str(artifact_root), receipt, name, str(coordination)),
        )
        for name, receipt in staged.items()
    }
    for process in processes.values():
        process.start()
    for name in processes:
        _wait_for_file(coordination / f"started-{name}")
    coordination.joinpath("go").touch()

    deadline = time.monotonic() + 10.0
    first_ready: str | None = None
    while first_ready is None:
        for name in processes:
            if coordination.joinpath(f"ready-{name}").exists():
                first_ready = name
                break
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "neither current-pointer writer reached the read boundary"
            )
        time.sleep(0.01)
    other = "newest" if first_ready == "stale" else "stale"
    second_ready_deadline = time.monotonic() + 1.0
    while (
        not coordination.joinpath(f"ready-{other}").exists()
        and time.monotonic() < second_ready_deadline
    ):
        time.sleep(0.01)

    if coordination.joinpath(f"ready-{other}").exists():
        coordination.joinpath("release-newest").touch()
        _wait_for_file(coordination / "result-newest")
        coordination.joinpath("release-stale").touch()
    else:
        coordination.joinpath(f"release-{first_ready}").touch()
        _wait_for_file(coordination / f"result-{first_ready}")
        _wait_for_file(coordination / f"ready-{other}")
        coordination.joinpath(f"release-{other}").touch()

    for name, process in processes.items():
        _wait_for_file(coordination / f"result-{name}")
        process.join(timeout=10)
        assert process.exitcode == 0

    current = store.load_current_batch(initial.source.source_id)
    assert current == newest_candidate
