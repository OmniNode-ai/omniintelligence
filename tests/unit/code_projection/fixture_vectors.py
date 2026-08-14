# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Builders for the checked-in OMN-16061 v1 replay vectors."""

from __future__ import annotations

import hashlib
from pathlib import Path

from omniintelligence.code_projection import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionSource,
    ModelCodeProjectionSpan,
    build_code_projection_batch,
    make_code_chunk,
    make_code_edge,
    make_code_node,
    make_code_source,
)
from omniintelligence.code_projection.models import ModelSourceLanguage

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures/code_projection/v1"
FIXTURE_REPOSITORY_ID = "github.com/OmniNode-ai/code-projection-fixtures"
FIXTURE_CURSOR_AUTHORITY = "omninode.fixture-ledger.v1"


def fixture_bytes(relative_path: str) -> bytes:
    """Read one immutable fixture artifact by repository-relative fixture path."""

    return (FIXTURE_ROOT / relative_path).read_bytes()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_ref(value: bytes) -> str:
    return f"artifact://sha256/{_sha256(value)}"


def _policy() -> ModelCodeProjectionPolicy:
    return ModelCodeProjectionPolicy(
        scope_ref="repository:github.com/OmniNode-ai/code-projection-fixtures",
        access_scope="repository",
        visibility="repository",
        redaction_state="sanitized",
        trust_tier="verified_source",
        retention_class="source_controlled",
        policy_version="fixture-policy-v1",
        metadata_allowlist_version="code-projection-metadata-v1",
    )


def _provenance() -> ModelCodeProjectionProvenance:
    transform_manifest = fixture_bytes("transform_manifest.json")
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection.fixture_vectors",
        producer_version="1.0.0",
        projection_builder_version="1.0.0",
        extractor_name="curated-fixture-mapper",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=_sha256(b"curated-fixture-mapper-config-v1"),
        transform_manifest_ref=_artifact_ref(transform_manifest),
        transform_manifest_hash_sha256=_sha256(transform_manifest),
        labeler_version=None,
        chunker_version="fixture-chunker-v1",
    )


def _source(
    *,
    physical_path: str,
    logical_path: str,
    source_revision: str,
    language: ModelSourceLanguage,
) -> tuple[ModelCodeProjectionSource, bytes]:
    raw_source = fixture_bytes(physical_path)
    return (
        make_code_source(
            repository_id=FIXTURE_REPOSITORY_ID,
            relative_path=logical_path,
            source_version=source_revision,
            raw_content_hash_sha256=_sha256(raw_source),
            byte_count=len(raw_source),
            language=language,
        ),
        raw_source,
    )


def _cursor(
    source: ModelCodeProjectionSource, *, sequence: int
) -> ModelCodeProjectionCursor:
    return ModelCodeProjectionCursor(
        authority=FIXTURE_CURSOR_AUTHORITY,
        partition=source.source_id,
        sequence=sequence,
    )


def _python_snapshot(
    *,
    source_fixture: str,
    sanitized_fixture: str,
    source_revision: str,
    sequence: int,
) -> ModelCodeProjectionBatch:
    source, _ = _source(
        physical_path=source_fixture,
        logical_path="src/fixtures/greeter.py",
        source_revision=source_revision,
        language="python",
    )
    greeter = make_code_node(
        source_id=source.source_id,
        entity_kind="class",
        qualified_name="fixtures.greeter.Greeter",
        display_name="Greeter",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=7, end_line=11),
    )
    greet = make_code_node(
        source_id=source.source_id,
        entity_kind="method",
        qualified_name="fixtures.greeter.Greeter.greet",
        display_name="greet",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=10, end_line=11),
    )
    build_greeter = make_code_node(
        source_id=source.source_id,
        entity_kind="function",
        qualified_name="fixtures.greeter.build_greeter",
        display_name="build_greeter",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=14, end_line=15),
    )
    external_str = make_code_node(
        source_id=source.source_id,
        entity_kind="external_symbol",
        qualified_name="builtins.str",
        display_name="str",
        symbol_visibility="public",
    )
    sanitized = fixture_bytes(sanitized_fixture)
    evidence_ref = _artifact_ref(sanitized)
    edges = (
        make_code_edge(
            source_id=source.source_id,
            source_node_id=greeter.node_id,
            target_node_id=greet.node_id,
            relationship_kind="defines",
            evidence_refs=(evidence_ref,),
        ),
        make_code_edge(
            source_id=source.source_id,
            source_node_id=greet.node_id,
            target_node_id=external_str.node_id,
            relationship_kind="references",
            evidence_refs=(evidence_ref,),
        ),
        make_code_edge(
            source_id=source.source_id,
            source_node_id=build_greeter.node_id,
            target_node_id=greeter.node_id,
            relationship_kind="calls",
            evidence_refs=(evidence_ref,),
        ),
    )
    document = make_code_chunk(
        source_id=source.source_id,
        source_hash_sha256=source.raw_content_hash_sha256,
        chunk_key="symbol:fixtures.greeter.Greeter",
        chunk_kind="symbol",
        anchor_node_id=greeter.node_id,
        source_span=greeter.source_span,
        chunker_version="fixture-chunker-v1",
        sanitized_content_hash_sha256=_sha256(sanitized),
        byte_count=len(sanitized),
    )
    return build_code_projection_batch(
        source=source,
        cursor=_cursor(source, sequence=sequence),
        policy=_policy(),
        provenance=_provenance(),
        nodes=(greeter, greet, build_greeter, external_str),
        edges=edges,
        semantic_documents=(document,),
    )


def _typescript_snapshot() -> ModelCodeProjectionBatch:
    source, _ = _source(
        physical_path="sources/widget.ts.fixture",
        logical_path="src/fixtures/widget.ts",
        source_revision="fixture-typescript-a",
        language="typescript",
    )
    widget = make_code_node(
        source_id=source.source_id,
        entity_kind="interface",
        qualified_name="fixtures.widget.Widget",
        display_name="Widget",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=5, end_line=7),
    )
    make_widget = make_code_node(
        source_id=source.source_id,
        entity_kind="function",
        qualified_name="fixtures.widget.makeWidget",
        display_name="makeWidget",
        symbol_visibility="public",
        source_span=ModelCodeProjectionSpan(start_line=9, end_line=11),
    )
    sanitized = fixture_bytes("sanitized/widget-interface.txt")
    evidence_ref = _artifact_ref(sanitized)
    relationship = make_code_edge(
        source_id=source.source_id,
        source_node_id=make_widget.node_id,
        target_node_id=widget.node_id,
        relationship_kind="references",
        confidence_basis_points=7_000,
        trust_tier="conservative",
        evidence_refs=(evidence_ref,),
    )
    document = make_code_chunk(
        source_id=source.source_id,
        source_hash_sha256=source.raw_content_hash_sha256,
        chunk_key="symbol:fixtures.widget.Widget",
        chunk_kind="symbol",
        anchor_node_id=widget.node_id,
        source_span=widget.source_span,
        chunker_version="fixture-chunker-v1",
        sanitized_content_hash_sha256=_sha256(sanitized),
        byte_count=len(sanitized),
    )
    return build_code_projection_batch(
        source=source,
        cursor=_cursor(source, sequence=1),
        policy=_policy(),
        provenance=_provenance(),
        nodes=(widget, make_widget),
        edges=(relationship,),
        semantic_documents=(document,),
    )


def _empty_snapshot() -> ModelCodeProjectionBatch:
    source, _ = _source(
        physical_path="sources/empty.py.fixture",
        logical_path="src/fixtures/empty.py",
        source_revision="fixture-empty-a",
        language="python",
    )
    return build_code_projection_batch(
        source=source,
        cursor=_cursor(source, sequence=1),
        policy=_policy(),
        provenance=_provenance(),
    )


def _tombstone(*, reason: str, sequence: int) -> ModelCodeProjectionBatch:
    source, _ = _source(
        physical_path="sources/greeter.py.fixture",
        logical_path="src/fixtures/greeter.py",
        source_revision=f"fixture-{reason}-{sequence}",
        language="python",
    )
    if reason == "source_deleted":
        tombstone_reason = "source_deleted"
    elif reason == "policy_revoked":
        tombstone_reason = "policy_revoked"
    else:
        msg = f"unsupported fixture tombstone reason: {reason}"
        raise ValueError(msg)
    return build_code_projection_batch(
        source=source,
        cursor=_cursor(source, sequence=sequence),
        policy=_policy(),
        provenance=_provenance(),
        operation="tombstone",
        tombstone_reason=tombstone_reason,
    )


def build_fixture_batches() -> dict[str, ModelCodeProjectionBatch]:
    """Return every v1 batch in deterministic fixture-manifest order."""

    return {
        "empty_python_seq1.json": _empty_snapshot(),
        "policy_tombstone_seq5.json": _tombstone(reason="policy_revoked", sequence=5),
        "python_a_seq1.json": _python_snapshot(
            source_fixture="sources/greeter.py.fixture",
            sanitized_fixture="sanitized/greeter-class.txt",
            source_revision="fixture-python-a1",
            sequence=1,
        ),
        "python_a_seq3.json": _python_snapshot(
            source_fixture="sources/greeter.py.fixture",
            sanitized_fixture="sanitized/greeter-class.txt",
            source_revision="fixture-python-a3",
            sequence=3,
        ),
        "python_b_seq2.json": _python_snapshot(
            source_fixture="sources/greeter_v2.py.fixture",
            sanitized_fixture="sanitized/greeter-class-v2.txt",
            source_revision="fixture-python-b2",
            sequence=2,
        ),
        "source_tombstone_seq4.json": _tombstone(reason="source_deleted", sequence=4),
        "typescript_seq1.json": _typescript_snapshot(),
    }
