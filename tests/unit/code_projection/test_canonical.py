# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adversarial tests for deterministic projection primitives."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from omniintelligence.code_projection import (
    ModelCodeProjectionSpan,
    make_code_chunk,
    make_code_edge,
    make_code_node,
    make_code_source,
)
from omniintelligence.code_projection._canonical import (
    DuplicateJsonKeyError,
    canonical_json_bytes,
    normalize_relative_path,
    normalize_repository_id,
)

pytestmark = pytest.mark.unit


def test_posix_and_windows_separators_normalize_to_one_path() -> None:
    posix_path = normalize_relative_path("src/omniintelligence/café.py")
    windows_path = normalize_relative_path(
        "src\\omniintelligence\\cafe\N{COMBINING ACUTE ACCENT}.py"
    )

    assert posix_path == "src/omniintelligence/café.py"
    assert windows_path == posix_path


def _factory_ids(relative_path: str) -> tuple[str, str, str, str, str]:
    empty_hash = hashlib.sha256(b"").hexdigest()
    sanitized_hash = hashlib.sha256(b"sanitized").hexdigest()
    source = make_code_source(
        tenant_id="omninode-dev",
        repository_id="omninode/omniintelligence",
        relative_path=relative_path,
        source_version="commit:abc",
        raw_content_hash_sha256=empty_hash,
        byte_count=0,
        language="python",
    )
    node = make_code_node(
        source_id=source.source_id,
        entity_kind="class",
        qualified_name="omniintelligence.cafe\N{COMBINING ACUTE ACCENT}.Thing",
        display_name="Thing",
    )
    external = make_code_node(
        source_id=source.source_id,
        entity_kind="external_symbol",
        qualified_name="typing.Protocol",
    )
    edge = make_code_edge(
        source_id=source.source_id,
        source_node_id=node.node_id,
        target_node_id=external.node_id,
        relationship_kind="implements",
    )
    document = make_code_chunk(
        source_id=source.source_id,
        source_hash_sha256=empty_hash,
        chunk_key="symbol:Thing",
        chunk_kind="symbol",
        chunker_version="ast-span-v1",
        sanitized_content_hash_sha256=sanitized_hash,
        byte_count=len(b"sanitized"),
        anchor_node_id=node.node_id,
        source_span=ModelCodeProjectionSpan(start_line=1, end_line=2),
    )
    return (
        source.source_id,
        node.node_id,
        external.node_id,
        edge.edge_id,
        document.document_id,
    )


def test_factory_ids_are_literal_stable_and_checkout_root_independent() -> None:
    posix_root = PurePosixPath("/tmp/checkout-a")
    posix_full = posix_root / "src/omniintelligence/café.py"
    windows_root = PureWindowsPath(r"C:\Users\agent\checkout-b")
    windows_full = windows_root / "src/omniintelligence/café.py"

    posix_relative = posix_full.relative_to(posix_root).as_posix()
    windows_relative = str(windows_full.relative_to(windows_root))
    expected = (
        "csrc_v2_b519ae38b82c688dc3f58ef6049a02a3c20141d90254ba2441ffcfa8c55ab47b",
        "cnode_v2_554167b34d1094527e6d058d54e882e4b952b5a51c060383193feccdfa5f1436",
        "cnode_v2_87e5422af7b867fafffcbbc976a7402da76ce12e6cd2ca6e7cff5caae716f195",
        "cedge_v2_ccd5ad2690c2d55d1bc0c3f16e4d3ec0d814c39db7b43da19b83884f87f7e903",
        "cdoc_v2_a01732c5ac2b121d611bdc23e2fc825f9cf5ec487d119c9bc2bbad02a154015d",
    )

    assert _factory_ids(posix_relative) == expected
    assert _factory_ids(windows_relative) == expected
    assert not any(
        root.encode() in canonical_json_bytes(expected)
        for root in (str(posix_root), str(windows_root))
    )


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "//server/share/file.py",
        r"\\server\share\file.py",
        "C:/repo/file.py",
        r"c:\repo\file.py",
        "../outside.py",
        "src/../outside.py",
        "src/pkg/../../outside.py",
        "src/pkg/file.py\x00ignored",
        "",
        ".",
        "./",
        "~/.ssh/id_rsa",
        "~agent/checkout/file.py",
    ],
)
def test_path_authority_ambiguity_fails_closed(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_relative_path(path)


@pytest.mark.parametrize("repository_id", ["file:///tmp/repo", "FILE:///tmp/repo"])
def test_file_uri_repository_identity_fails_closed(repository_id: str) -> None:
    with pytest.raises(ValueError):
        normalize_repository_id(repository_id)


def test_reordered_inputs_produce_byte_identical_canonical_json() -> None:
    first = {
        "schema_version": "1.0.0",
        "path": "src/pkg/naïve.py",
        "metadata": {"visibility": "repository", "sequence": 7},
    }
    reordered = {
        "metadata": {"sequence": 7, "visibility": "repository"},
        "path": "src/pkg/nai\N{COMBINING DIAERESIS}ve.py",
        "schema_version": "1.0.0",
    }

    assert canonical_json_bytes(first) == canonical_json_bytes(reordered)
    assert b"na\xc3\xafve.py" in canonical_json_bytes(first)


def test_unicode_normalization_cannot_create_duplicate_canonical_keys() -> None:
    with pytest.raises(DuplicateJsonKeyError):
        canonical_json_bytes({"café": 1, "cafe\N{COMBINING ACUTE ACCENT}": 2})


@pytest.mark.parametrize("value", [1.0, float("nan"), float("inf")])
def test_floating_point_values_are_not_canonical_projection_data(value: float) -> None:
    with pytest.raises(TypeError):
        canonical_json_bytes({"confidence": value})
