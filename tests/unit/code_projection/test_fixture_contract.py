# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Drift tests for the checked-in code-projection schema and replay vectors."""

from __future__ import annotations

import hashlib
import json

import pytest

from omniintelligence.code_projection import (
    ModelCodeProjectionBatch,
    parse_code_projection_batch,
    plan_code_projection_replay,
    serialize_code_projection_batch,
)
from omniintelligence.code_projection._canonical import canonical_json_bytes
from tests.unit.code_projection.fixture_vectors import (
    FIXTURE_ROOT,
    build_fixture_batches,
)

pytestmark = pytest.mark.unit

_REPOSITORY_ROOT = FIXTURE_ROOT.parents[3]
_SCHEMA_PATH = FIXTURE_ROOT / "code_projection_batch_v1.schema.json"
_SCHEMA_DIGEST_PATH = FIXTURE_ROOT / "code_projection_batch_v1.schema.sha256"
_REPLAY_MANIFEST_PATH = FIXTURE_ROOT / "replay_manifest.json"
_FROZEN_SCHEMA_SHA256 = "91183d15b1aa9c9c3c4190af880de1196fbdd696f355e2a9dcec8f37b3f81aa1"  # pragma: allowlist secret  # noqa: E501
_AUTHORITY_BASE_COMMIT = (
    "8c67665add2b611307a78a3f351e0fac18c5bad8"  # pragma: allowlist secret  # noqa: E501
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_manifest() -> dict[str, object]:
    decoded = json.loads(_REPLAY_MANIFEST_PATH.read_bytes())
    assert isinstance(decoded, dict)
    return decoded


def _load_batch(name: str) -> ModelCodeProjectionBatch:
    return parse_code_projection_batch((FIXTURE_ROOT / "batches" / name).read_bytes())


def test_checked_in_schema_and_digest_match_the_frozen_model() -> None:
    expected_schema = (
        canonical_json_bytes(ModelCodeProjectionBatch.model_json_schema()) + b"\n"
    )
    checked_in_schema = _SCHEMA_PATH.read_bytes()
    digest_line = _SCHEMA_DIGEST_PATH.read_text(encoding="utf-8").strip()
    digest, filename = digest_line.split(maxsplit=1)

    assert checked_in_schema == expected_schema
    assert filename == _SCHEMA_PATH.name
    assert digest == _sha256(checked_in_schema)
    assert digest == _FROZEN_SCHEMA_SHA256


def test_checked_in_batches_are_exact_factory_outputs_and_roundtrip() -> None:
    batches = build_fixture_batches()

    assert set(batches) == {
        path.name for path in (FIXTURE_ROOT / "batches").glob("*.json")
    }
    for name, batch in batches.items():
        checked_in = (FIXTURE_ROOT / "batches" / name).read_bytes()
        assert checked_in.endswith(b"\n")
        assert not checked_in.endswith(b"\n\n")
        assert checked_in == serialize_code_projection_batch(batch)
        assert parse_code_projection_batch(checked_in) == batch


def test_replay_manifest_is_canonical_and_pins_every_artifact_hash() -> None:
    raw_manifest = _REPLAY_MANIFEST_PATH.read_bytes()
    manifest = _load_manifest()

    assert raw_manifest == canonical_json_bytes(manifest) + b"\n"
    assert manifest["ticket"] == "OMN-16061"
    assert manifest["authority_base_commit"] == _AUTHORITY_BASE_COMMIT
    assert manifest["canonical_framing"] == (
        "utf-8+nfc+sorted-keys+compact-json+single-lf"
    )
    assert manifest["no_network_required"] is True
    assert manifest["no_inline_source_or_chunk_text"] is True
    assert manifest["exact_test_command"] == (
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-sync pytest "
        "-p pytest_asyncio.plugin tests/unit/code_projection -q"
    )

    hashed_entries = [manifest["schema"], manifest["transform_manifest"]]
    declared_content_fixture_paths: set[str] = set()
    for collection_name in (
        "source_fixtures",
        "sanitized_artifacts",
        "batch_fixtures",
    ):
        collection = manifest[collection_name]
        assert isinstance(collection, list)
        hashed_entries.extend(collection)
        if collection_name in {"source_fixtures", "sanitized_artifacts"}:
            for raw_entry in collection:
                assert isinstance(raw_entry, dict)
                path = raw_entry["path"]
                assert isinstance(path, str)
                declared_content_fixture_paths.add(path)

    actual_content_fixture_paths = {
        path.relative_to(_REPOSITORY_ROOT).as_posix()
        for directory_name in ("sources", "sanitized")
        for path in (FIXTURE_ROOT / directory_name).rglob("*")
        if path.is_file()
    }
    assert declared_content_fixture_paths == actual_content_fixture_paths

    for raw_entry in hashed_entries:
        assert isinstance(raw_entry, dict)
        path = raw_entry["path"]
        expected_digest = raw_entry["sha256"]
        expected_byte_count = raw_entry["byte_count"]
        assert isinstance(path, str)
        assert isinstance(expected_digest, str)
        assert isinstance(expected_byte_count, int)
        artifact = (_REPOSITORY_ROOT / path).read_bytes()
        assert _sha256(artifact) == expected_digest
        assert len(artifact) == expected_byte_count


def test_fixture_batches_never_inline_raw_or_sanitized_text() -> None:
    forbidden_bodies = [
        path.read_bytes()
        for directory in (FIXTURE_ROOT / "sources", FIXTURE_ROOT / "sanitized")
        for path in directory.iterdir()
        if path.is_file() and path.stat().st_size > 0
    ]

    for path in (FIXTURE_ROOT / "batches").glob("*.json"):
        wire = path.read_bytes()
        assert not any(body in wire for body in forbidden_bodies)
        assert b"RAW_PYTHON_FIXTURE_BODY" not in wire
        assert b"RAW_TYPESCRIPT_FIXTURE_BODY" not in wire
        assert b"source_content" not in wire
        assert b"chunk_text" not in wire


def test_a_to_b_to_a_and_explicit_tombstones_are_replayable() -> None:
    first_a = _load_batch("python_a_seq1.json")
    middle_b = _load_batch("python_b_seq2.json")
    reverted_a = _load_batch("python_a_seq3.json")
    source_tombstone = _load_batch("source_tombstone_seq4.json")
    policy_tombstone = _load_batch("policy_tombstone_seq5.json")

    to_b = plan_code_projection_replay(middle_b, first_a.manifest)
    to_a = plan_code_projection_replay(reverted_a, middle_b.manifest)
    delete_source = plan_code_projection_replay(source_tombstone, reverted_a.manifest)
    revoke_policy = plan_code_projection_replay(policy_tombstone, reverted_a.manifest)

    assert to_b.decision == to_a.decision == "replace"
    assert first_a.source.raw_content_hash_sha256 == (
        reverted_a.source.raw_content_hash_sha256
    )
    assert first_a.batch_id != reverted_a.batch_id
    assert reverted_a.cursor.sequence == 3
    assert to_a.upsert_node_ids == reverted_a.manifest.node_ids
    assert source_tombstone.tombstone_reason == "source_deleted"
    assert policy_tombstone.tombstone_reason == "policy_revoked"
    assert delete_source.delete_node_ids == reverted_a.manifest.node_ids
    assert revoke_policy.delete_node_ids == reverted_a.manifest.node_ids
    assert not delete_source.upsert_node_ids
    assert not revoke_policy.upsert_node_ids


def test_empty_source_is_a_snapshot_not_a_deletion() -> None:
    empty = _load_batch("empty_python_seq1.json")

    assert empty.operation == "snapshot"
    assert empty.tombstone_reason is None
    assert empty.source.byte_count == 0
    assert empty.source.raw_content_hash_sha256 == hashlib.sha256(b"").hexdigest()
    assert empty.nodes == empty.edges == empty.semantic_documents == ()
