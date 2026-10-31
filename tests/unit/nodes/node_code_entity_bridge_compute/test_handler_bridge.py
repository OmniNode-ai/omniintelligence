# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the code entity bridge compute handler.

Ticket: OMN-7863
"""

from __future__ import annotations

import uuid

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_code_entity_bridge_compute.handlers import (
    handler_bridge as canonical_handler,
)
from omniintelligence.nodes.node_code_entity_bridge_compute.handlers.handler_bridge import (
    _build_signature,
    _extract_keywords,
    _sha256,
)
from omniintelligence.nodes.node_code_entity_bridge_compute.models.model_input import (
    ModelCodeEntityBridgeInput,
)


def _make_class_entity(
    name: str = "MyClass",
    qualified: str = "omniintelligence.nodes.foo.MyClass",
    bases: list[str] | None = None,
    docstring: str | None = "Does something useful.",
    confidence: float = 1.0,
) -> ModelCodeEntity:
    return ModelCodeEntity(
        id=str(uuid.uuid4()),
        entity_name=name,
        entity_type="class",
        qualified_name=qualified,
        source_repo="omniintelligence",
        source_path="src/omniintelligence/nodes/foo/node.py",
        line_number=10,
        bases=bases or [],
        docstring=docstring,
        file_hash="abc123",
        confidence=confidence,
    )


def _make_function_entity(
    name: str = "handle_foo",
    qualified: str = "omniintelligence.nodes.foo.handle_foo",
    docstring: str | None = "Handle foo operation.",
    confidence: float = 1.0,
) -> ModelCodeEntity:
    return ModelCodeEntity(
        id=str(uuid.uuid4()),
        entity_name=name,
        entity_type="function",
        qualified_name=qualified,
        source_repo="omniintelligence",
        source_path="src/omniintelligence/nodes/foo/handlers/handler_foo.py",
        docstring=docstring,
        file_hash="def456",
        confidence=confidence,
    )


def _make_import_entity(name: str = "asyncio") -> ModelCodeEntity:
    return ModelCodeEntity(
        id=str(uuid.uuid4()),
        entity_name=name,
        entity_type="import",
        qualified_name=name,
        source_repo="omniintelligence",
        source_path="src/omniintelligence/nodes/foo/node.py",
        file_hash="abc123",
    )


def _make_bridge_input(
    entities: list[ModelCodeEntity],
    min_confidence: float = 0.7,
    canary_id: str | None = None,
) -> ModelCodeEntityBridgeInput:
    return ModelCodeEntityBridgeInput(
        correlation_id=uuid.uuid4(),
        entities=entities,
        source_repo="omniintelligence",
        canary_id=canary_id,
        min_confidence=min_confidence,
    )


# =============================================================================
# Signature and hash helpers
# =============================================================================


@pytest.mark.unit
def test_build_signature_class_with_bases_and_docstring() -> None:
    entity = _make_class_entity(
        name="NodeFoo",
        qualified="omniintelligence.nodes.foo.NodeFoo",
        bases=["NodeCompute", "BaseModel"],
        docstring="Thin shell for foo.",
    )
    sig = _build_signature(entity)
    # bases are sorted
    assert (
        sig
        == "class:omniintelligence.nodes.foo.NodeFoo:BaseModel,NodeCompute:Thin shell for foo."
    )


@pytest.mark.unit
def test_build_signature_function_no_docstring() -> None:
    entity = _make_function_entity(docstring=None)
    sig = _build_signature(entity)
    assert sig == "function:omniintelligence.nodes.foo.handle_foo"


@pytest.mark.unit
def test_sha256_is_stable() -> None:
    sig = "class:omniintelligence.foo.Bar"
    h1 = _sha256(sig)
    h2 = _sha256(sig)
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.unit
def test_sha256_case_insensitive() -> None:
    assert _sha256("Class:Foo") == _sha256("class:foo")


# =============================================================================
# Keyword extraction
# =============================================================================


@pytest.mark.unit
def test_extract_keywords_includes_name_and_qualified_parts() -> None:
    entity = _make_class_entity(
        name="PatternBridge",
        qualified="omniintelligence.nodes.bridge.PatternBridge",
        bases=["BaseCompute"],
    )
    kws = _extract_keywords(entity)
    assert "patternbridge" in kws
    assert "omniintelligence" in kws
    assert "nodes" in kws
    assert "bridge" in kws
    assert "basecompute" in kws


@pytest.mark.unit
def test_extract_keywords_no_duplicates() -> None:
    entity = _make_class_entity(
        name="Foo",
        qualified="bar.Foo",
    )
    kws = _extract_keywords(entity)
    assert len(kws) == len(set(kws))


# =============================================================================
# Bridge handler — filtering
# =============================================================================


@pytest.mark.unit
def test_import_entities_are_skipped() -> None:
    entities = [_make_import_entity("asyncio"), _make_class_entity()]
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input(entities)
    )
    assert result.skipped_count == 1
    assert len(result.derived_patterns) == 1


@pytest.mark.unit
def test_low_confidence_entities_are_skipped() -> None:
    entities = [
        _make_class_entity(confidence=0.4),
        _make_class_entity(name="HighConf", qualified="foo.HighConf", confidence=1.0),
    ]
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input(entities, min_confidence=0.7)
    )
    assert result.skipped_count == 1
    assert len(result.derived_patterns) == 1


@pytest.mark.unit
def test_all_supported_entity_types_are_derived() -> None:
    entities = [
        _make_class_entity(name="C", qualified="m.C"),
        _make_function_entity(name="f", qualified="m.f"),
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="Proto",
            entity_type="protocol",
            qualified_name="m.Proto",
            source_repo="omniintelligence",
            source_path="m.py",
            file_hash="x",
            confidence=1.0,
        ),
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name="Model",
            entity_type="model",
            qualified_name="m.Model",
            source_repo="omniintelligence",
            source_path="m.py",
            file_hash="x",
            confidence=1.0,
        ),
    ]
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input(entities)
    )
    assert len(result.derived_patterns) == 4
    assert result.skipped_count == 0


# =============================================================================
# Bridge handler — output fields
# =============================================================================


@pytest.mark.unit
def test_derived_pattern_has_correct_fields() -> None:
    entity = _make_class_entity(
        name="MyNode",
        qualified="omniintelligence.nodes.my.MyNode",
        bases=["NodeCompute"],
        docstring="Thin shell.",
    )
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input([entity])
    )
    assert len(result.derived_patterns) == 1
    p = result.derived_patterns[0]

    assert p.entity_type == "class"
    assert "mynode" in [k.lower() for k in p.keywords]
    assert len(p.signature_hash) == 64
    assert p.pattern_signature.startswith("class:")
    assert p.domain_id == "code_structure"
    assert p.project_scope is None
    assert p.canary_id is None
    assert p.compiled_snippet is not None


@pytest.mark.unit
def test_canary_id_propagated() -> None:
    entity = _make_class_entity()
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input([entity], canary_id="canary-v1")
    )
    assert result.derived_patterns[0].canary_id == "canary-v1"


@pytest.mark.unit
def test_source_entity_id_is_recorded() -> None:
    entity = _make_class_entity()
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input([entity])
    )
    assert entity.id in result.derived_patterns[0].source_entity_ids


@pytest.mark.unit
def test_duration_ms_is_positive() -> None:
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input([_make_class_entity()])
    )
    assert result.duration_ms >= 0.0


@pytest.mark.unit
def test_empty_entities_returns_empty_output() -> None:
    result = canonical_handler.HandlerCodeEntityBridge().handle(_make_bridge_input([]))
    assert len(result.derived_patterns) == 0
    assert result.skipped_count == 0
    assert result.error_count == 0


# =============================================================================
# Signature uniqueness
# =============================================================================


@pytest.mark.unit
def test_different_entities_produce_different_signatures() -> None:
    e1 = _make_class_entity(name="Foo", qualified="m.Foo")
    e2 = _make_class_entity(name="Bar", qualified="m.Bar")
    result = canonical_handler.HandlerCodeEntityBridge().handle(
        _make_bridge_input([e1, e2])
    )
    sigs = {p.pattern_signature for p in result.derived_patterns}
    hashes = {p.signature_hash for p in result.derived_patterns}
    assert len(sigs) == 2
    assert len(hashes) == 2


# Shared with the coverage receipt recorder; no random input defaults.
CANONICAL_PARITY_CASES = [
    {
        "case": "empty",
        "input": {
            "correlation_id": "11111111-1111-1111-1111-111111111111",
            "source_repo": "parity",
            "entities": [],
        },
        "derive": [],
        "skipped": 0,
        "errors": 0,
    },
    {
        "case": "class_metadata",
        "input": {
            "correlation_id": "11111111-1111-1111-1111-111111111111",
            "source_repo": "parity",
            "entities": [
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "class",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "bases": ["ZBase", "ABase"],
                    "decorators": ["registered"],
                    "methods": [{"name": "run"}],
                    "docstring": "Worker docs.\nMore.",
                }
            ],
            "project_scope": "scope",
            "canary_id": "canary",
            "domain_id": "custom",
        },
        "derive": [0],
        "skipped": 0,
        "errors": 0,
    },
    {
        "case": "function",
        "input": {
            "correlation_id": "11111111-1111-1111-1111-111111111111",
            "source_repo": "parity",
            "entities": [
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "function",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "signature": "def work(x):",
                    "docstring": None,
                }
            ],
        },
        "derive": [0],
        "skipped": 0,
        "errors": 0,
    },
    {
        "case": "filtered",
        "input": {
            "correlation_id": "11111111-1111-1111-1111-111111111111",
            "source_repo": "parity",
            "entities": [
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "import",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                },
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "class",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "confidence": 0.6,
                },
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "protocol",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "confidence": 0.7,
                },
            ],
        },
        "derive": [2],
        "skipped": 2,
        "errors": 0,
    },
    {
        "case": "derivation_error",
        "input": {
            "correlation_id": "11111111-1111-1111-1111-111111111111",
            "source_repo": "parity",
            "entities": [
                {
                    "id": "entity-1",
                    "entity_name": "Worker",
                    "entity_type": "class",
                    "qualified_name": "pkg.Worker",
                    "source_repo": "parity",
                    "source_path": "pkg.py",
                    "file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "confidence": 1.2,
                }
            ],
        },
        "derive": [],
        "skipped": 0,
        "errors": 1,
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("payload", CANONICAL_PARITY_CASES, ids=lambda p: p["case"])
def test_canonical_dispatch_matches_preserved_core(payload, monkeypatch):
    """Compare canonical dispatch with the git-preserved core on branch cases.

    Resolve the class inside the test so the legacy tree collects successfully
    and fails this assertion, rather than failing import/collection.
    """
    handler_class = getattr(canonical_handler, "HandlerCodeEntityBridge", None)
    assert handler_class is not None, "canonical handle(request) class is required"
    from omniintelligence.nodes.node_code_entity_bridge_compute.models.model_input import (
        ModelCodeEntityBridgeInput,
    )

    request = ModelCodeEntityBridgeInput.model_validate(payload["input"])
    # Only nondeterministic clocks/IDs are controlled; the algorithm runs normally.
    from uuid import UUID

    monkeypatch.setattr("time.perf_counter", lambda: 100.0)
    monkeypatch.setattr(
        "uuid.uuid4", lambda: UUID("22222222-2222-2222-2222-222222222222")
    )
    from omniintelligence.nodes.node_code_entity_bridge_compute.models.model_output import (
        ModelCodeEntityBridgeOutput,
    )

    expected = ModelCodeEntityBridgeOutput(
        correlation_id=request.correlation_id,
        source_repo=request.source_repo,
        derived_patterns=[
            canonical_handler._derive_pattern(request.entities[i], request)
            for i in payload["derive"]
        ],
        skipped_count=payload["skipped"],
        error_count=payload["errors"],
        duration_ms=0.0,
    )
    assert handler_class().handle(request) == expected
