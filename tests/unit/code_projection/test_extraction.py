# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for deterministic mapping from real source bytes into projections."""

from __future__ import annotations

import hashlib

import pytest

from omniintelligence.code_projection.codec import serialize_code_projection_batch
from omniintelligence.code_projection.extraction import (
    CodeProjectionExtractionError,
    project_source,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
)

pytestmark = pytest.mark.unit

_CLASSIFICATION_CONFIG = {
    "scoring_weights": {
        "domain": 0.0,
        "operation": 0.0,
        "keyword": 1.0,
        "feature": 0.0,
    },
    "classifications": {
        "effect": {
            "keywords": ["file", "persist"],
            "domains": [],
            "operations": [],
            "features": [],
        },
        "compute": {
            "keywords": ["calculate", "parse"],
            "domains": [],
            "operations": [],
            "features": [],
        },
    },
    "min_confidence": 0.1,
}

_LANGUAGE_EXTRACTOR_CONFIG = {
    "typescript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "class": (
                r"class\s+([A-Za-z_][A-Za-z0-9_]*)"
                r"(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{"
            ),
            "function": (
                r"(?:export\s+)?(?:async\s+)?function\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
            ),
            "interface": (
                r"(?:export\s+)?interface\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+[^{]+)?\s*\{"
            ),
        },
    },
    "javascript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "class": (
                r"class\s+([A-Za-z_][A-Za-z0-9_]*)"
                r"(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{"
            ),
            "function": (
                r"(?:export\s+)?(?:async\s+)?function\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
            ),
            "arrow_function": (
                r"(?:export\s+)?(?:const|let)\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\("
            ),
        },
    },
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _policy() -> ModelCodeProjectionPolicy:
    return ModelCodeProjectionPolicy(
        scope_ref="repository:github.com/OmniNode-ai/omniintelligence",
        access_scope="repository",
        visibility="repository",
        redaction_state="not_required",
        trust_tier="verified_source",
        retention_class="source_controlled",
        policy_version="code-ingestion-policy-v1",
        metadata_allowlist_version="code-projection-metadata-v1",
    )


def _provenance() -> ModelCodeProjectionProvenance:
    config_hash = _sha256(b"ast-extraction-contract-v1")
    manifest_hash = _sha256(b"code-projection-transform-manifest-v1")
    return ModelCodeProjectionProvenance(
        producer="omniintelligence.code_projection.extraction",
        producer_version="1.0.0",
        projection_builder_version="1.0.0",
        extractor_name="contract-driven-source-extractor",
        extractor_version="1.0.0",
        extractor_config_hash_sha256=config_hash,
        transform_manifest_ref=f"artifact://sha256/{manifest_hash}",
        transform_manifest_hash_sha256=manifest_hash,
        labeler_version="deterministic-labeler-v1",
    )


def _project_python(raw_source: bytes) -> ModelCodeProjectionBatch:
    return project_source(
        raw_source=raw_source,
        repository_id="github.com/OmniNode-ai/omniintelligence",
        relative_path="src/example/writers.py",
        source_version="commit:0123456789abcdef",
        language="python",
        cursor_authority="git:omniintelligence",
        cursor_sequence=7,
        policy=_policy(),
        provenance=_provenance(),
        classification_config=_CLASSIFICATION_CONFIG,
        quality_config={},
    )


def test_python_source_maps_deterministically_with_closed_relationships() -> None:
    raw_source = b'''from typing import Protocol

class WriterProtocol(Protocol):
    """SENSITIVE_DOCSTRING_SENTINEL must not enter the projection."""

    def persist(self, value: str) -> None:
        ...

class FileWriter(WriterProtocol):
    def persist(self, value: str) -> None:
        return None

class Job(BaseService):
    pass

def build_writer() -> FileWriter:
    return FileWriter()
'''

    first = _project_python(raw_source)
    second = _project_python(raw_source)

    assert serialize_code_projection_batch(first) == serialize_code_projection_batch(
        second
    )
    assert first.batch_id == second.batch_id
    assert first.source.raw_content_hash_sha256 == _sha256(raw_source)
    assert first.source.byte_count == len(raw_source)

    nodes_by_name = {node.qualified_name: node for node in first.nodes}
    assert nodes_by_name["example.writers"].entity_kind == "module"
    assert nodes_by_name["example.writers.WriterProtocol"].entity_kind == "protocol"
    assert nodes_by_name["typing.Protocol"].entity_kind == "import"
    assert nodes_by_name["BaseService"].entity_kind == "external_symbol"
    assert nodes_by_name["BaseService"].resolution_state == "external_symbol"
    assert nodes_by_name["example.writers.FileWriter"].source_span is not None
    assert nodes_by_name["example.writers.FileWriter"].source_span.end_line == 11

    file_writer_labels = {
        (label.namespace, label.value): label
        for label in nodes_by_name["example.writers.FileWriter"].labels
    }
    assert ("onex.entity-kind", "class") in file_writer_labels
    assert ("onex.node-archetype", "effect") in file_writer_labels
    assert ("onex.code-quality", "deterministic-score") in file_writer_labels

    module_namespaces = {
        label.namespace for label in nodes_by_name["example.writers"].labels
    }
    assert "onex.semantic-purpose" in module_namespaces
    assert "onex.source-language" in module_namespaces

    node_ids = {node.node_id for node in first.nodes}
    assert first.edges
    assert all(edge.source_node_id in node_ids for edge in first.edges)
    assert all(edge.target_node_id in node_ids for edge in first.edges)
    assert any(
        edge.relationship_kind == "inherits"
        and edge.target_node_id == nodes_by_name["BaseService"].node_id
        for edge in first.edges
    )

    serialized = serialize_code_projection_batch(first)
    assert b"SENSITIVE_DOCSTRING_SENTINEL" not in serialized
    assert raw_source not in serialized


def test_typescript_source_uses_contract_config_and_externalizes_base() -> None:
    raw_source = b"""export interface Widget {
    id: string;
}

export class WidgetStore extends ExternalStore {
}

export function makeWidget(): Widget {
    return {id: "one"};
}
"""

    batch = project_source(
        raw_source=raw_source,
        repository_id="github.com/OmniNode-ai/omnidash",
        relative_path="src/features/widget.ts",
        source_version="commit:fedcba9876543210",
        language="typescript",
        cursor_authority="git:omnidash",
        cursor_sequence=3,
        policy=_policy(),
        provenance=_provenance(),
        classification_config=_CLASSIFICATION_CONFIG,
        quality_config={},
        language_extractor_config=_LANGUAGE_EXTRACTOR_CONFIG,
    )

    nodes_by_name = {node.qualified_name: node for node in batch.nodes}
    assert nodes_by_name["features.widget"].entity_kind == "module"
    assert nodes_by_name["features.widget.Widget"].entity_kind == "interface"
    assert nodes_by_name["features.widget.WidgetStore"].entity_kind == "class"
    assert nodes_by_name["features.widget.makeWidget"].entity_kind == "function"
    assert nodes_by_name["ExternalStore"].entity_kind == "external_symbol"

    node_ids = {node.node_id for node in batch.nodes}
    assert len(batch.edges) == 4
    assert all(edge.source_node_id in node_ids for edge in batch.edges)
    assert all(edge.target_node_id in node_ids for edge in batch.edges)
    assert any(
        edge.relationship_kind == "inherits"
        and edge.target_node_id == nodes_by_name["ExternalStore"].node_id
        for edge in batch.edges
    )


def test_javascript_source_uses_same_deterministic_multilang_seam() -> None:
    raw_source = b"""export class Handler extends BaseHandler {
}

export const runHandler = async () => {
    return new Handler();
};
"""

    batch = project_source(
        raw_source=raw_source,
        repository_id="github.com/OmniNode-ai/omnidash",
        relative_path="src/features/handler.js",
        source_version="commit:1234567890abcdef",
        language="javascript",
        cursor_authority="git:omnidash",
        cursor_sequence=4,
        policy=_policy(),
        provenance=_provenance(),
        language_extractor_config=_LANGUAGE_EXTRACTOR_CONFIG,
    )

    nodes_by_name = {node.qualified_name: node for node in batch.nodes}
    assert nodes_by_name["features.handler.Handler"].entity_kind == "class"
    assert nodes_by_name["features.handler.runHandler"].entity_kind == "function"
    assert nodes_by_name["BaseHandler"].entity_kind == "external_symbol"
    assert len(batch.edges) == 3


def test_empty_python_source_is_an_explicit_empty_snapshot() -> None:
    batch = _project_python(b"")

    assert batch.operation == "snapshot"
    assert batch.nodes == ()
    assert batch.edges == ()
    assert batch.semantic_documents == ()


def test_syntax_error_does_not_become_authoritative_empty_snapshot() -> None:
    with pytest.raises(CodeProjectionExtractionError, match="AST extraction failed"):
        _project_python(b"def broken(:\n    pass\n")


def test_non_python_requires_explicit_contract_config() -> None:
    with pytest.raises(
        CodeProjectionExtractionError,
        match="explicit language_extractor_config",
    ):
        project_source(
            raw_source=b"export interface Widget {}\n",
            repository_id="github.com/OmniNode-ai/omnidash",
            relative_path="src/widget.ts",
            source_version="commit:one",
            language="typescript",
            cursor_authority="git:omnidash",
            cursor_sequence=1,
            policy=_policy(),
            provenance=_provenance(),
        )


def test_language_and_source_extension_must_agree() -> None:
    with pytest.raises(CodeProjectionExtractionError, match="does not match python"):
        project_source(
            raw_source=b"export interface Widget {}\n",
            repository_id="github.com/OmniNode-ai/omnidash",
            relative_path="src/widget.ts",
            source_version="commit:one",
            language="python",
            cursor_authority="git:omnidash",
            cursor_sequence=1,
            policy=_policy(),
            provenance=_provenance(),
        )


def test_invalid_utf8_fails_closed() -> None:
    with pytest.raises(CodeProjectionExtractionError, match="not valid UTF-8"):
        _project_python(b"\xff\xfe")
