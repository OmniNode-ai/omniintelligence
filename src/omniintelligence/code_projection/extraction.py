# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pure source-to-batch mapping for deterministic code projections.

The existing AST and regex extractors contain runtime-oriented fields such as
UUIDs and timestamps.  This module deliberately treats those fields as
transport metadata: only source-derived values are mapped into the canonical
projection builders.  Re-running the mapper with identical inputs therefore
produces byte-identical batches.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from omniintelligence.code_projection._canonical import (
    normalize_relative_path,
    normalize_text,
    sha256_hex,
)
from omniintelligence.code_projection.codec import (
    build_code_projection_batch,
    make_code_edge,
    make_code_node,
    make_code_source,
)
from omniintelligence.code_projection.models import (
    ModelCodeProjectionBatch,
    ModelCodeProjectionCursor,
    ModelCodeProjectionEdge,
    ModelCodeProjectionLabel,
    ModelCodeProjectionNode,
    ModelCodeProjectionPolicy,
    ModelCodeProjectionProvenance,
    ModelCodeProjectionSpan,
    ModelEntityKind,
    ModelRelationshipKind,
    ModelRelationshipTrustTier,
    ModelSourceLanguage,
    ModelSymbolVisibility,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
    AstExtractInput,
    handle_ast_extract,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_deterministic_classify import (
    DeterministicClassifier,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_multilang_extract import (
    MultiLangExtractor,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_quality_score import (
    QualityScorer,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.handler_semantic_analysis import (
    ANALYSIS_VERSION_STR,
    analyze_semantics,
)
from omniintelligence.nodes.node_semantic_analysis_compute.handlers.protocols import (
    SemanticAnalysisResult,
)

_MAPPER_VERSION = "1.0.0"
_AST_EXTRACTOR_VERSION = "1.0.0"
_REGEX_EXTRACTOR_VERSION = "1.0.0"
_CLASSIFIER_VERSION = "1.0.0"
_QUALITY_SCORER_VERSION = "1.0.0"

_ENTITY_KIND_BY_EXTRACTED_TYPE: dict[str, ModelEntityKind] = {
    "class": "class",
    "constant": "constant",
    "enum": "enum",
    "function": "function",
    "import": "import",
    "interface": "interface",
    "method": "method",
    "model": "model",
    "module": "module",
    "protocol": "protocol",
    "type_alias": "type_alias",
}
_RELATIONSHIP_KIND_BY_EXTRACTED_TYPE: dict[str, ModelRelationshipKind] = {
    "calls": "calls",
    "contains": "contains",
    "defines": "defines",
    "implements": "implements",
    "imports": "imports",
    "inherits": "inherits",
    "references": "references",
}
_TRUST_TIERS: dict[str, ModelRelationshipTrustTier] = {
    "conservative": "conservative",
    "strong": "strong",
    "weak": "weak",
}
_EXTENSION_BY_LANGUAGE: dict[ModelSourceLanguage, frozenset[str]] = {
    "javascript": frozenset({"js", "jsx"}),
    "python": frozenset({"py"}),
    "typescript": frozenset({"ts", "tsx"}),
}


class CodeProjectionExtractionError(ValueError):
    """Raised when source cannot produce an authoritative projection snapshot."""


@dataclass(frozen=True)
class _ExtractedSource:
    entities: tuple[ModelCodeEntity, ...]
    relationships: tuple[ModelCodeRelationship, ...]
    semantic_result: SemanticAnalysisResult | None


def _basis_points(value: float, *, field_name: str) -> int:
    if not 0.0 <= value <= 1.0:
        msg = f"{field_name} must be between zero and one"
        raise CodeProjectionExtractionError(msg)
    return int(
        (Decimal(str(value)) * Decimal(10_000)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def _module_qualified_name(relative_path: str) -> str:
    path = normalize_relative_path(relative_path)
    if path.startswith("src/"):
        path = path[4:]
    path = path.rsplit(".", maxsplit=1)[0]
    if path.endswith("/__init__"):
        path = path[: -len("/__init__")]
    qualified_name = normalize_text(path.replace("/", "."))
    if not qualified_name:
        msg = "source path must resolve to a non-empty module name"
        raise CodeProjectionExtractionError(msg)
    return qualified_name


def _source_extension(relative_path: str, language: ModelSourceLanguage) -> str:
    normalized_path = normalize_relative_path(relative_path)
    suffix = normalized_path.rsplit(".", maxsplit=1)
    extension = suffix[1].lower() if len(suffix) == 2 else ""
    if extension not in _EXTENSION_BY_LANGUAGE[language]:
        expected = ", ".join(sorted(_EXTENSION_BY_LANGUAGE[language]))
        msg = (
            f"source path extension {extension!r} does not match {language}; "
            f"expected one of: {expected}"
        )
        raise CodeProjectionExtractionError(msg)
    return extension


def _extract_python(
    *,
    source_text: str,
    relative_path: str,
    repository_id: str,
    source_hash: str,
) -> _ExtractedSource:
    event = handle_ast_extract(
        AstExtractInput(
            source_content=source_text,
            source_path=relative_path,
            source_repo=repository_id,
            file_hash=source_hash,
            crawl_id=f"code-projection:{source_hash}",
            event_id=f"code-projection:{source_hash}",
        )
    )
    if event.parse_status != "success":
        msg = f"Python AST extraction failed for {relative_path}: {event.parse_status}"
        raise CodeProjectionExtractionError(msg)

    semantic_result: SemanticAnalysisResult | None = None
    if source_text.strip():
        analyzed = analyze_semantics(source_text, language="python")
        if not analyzed["success"] or not analyzed["parse_ok"]:
            msg = f"semantic analysis failed for {relative_path}"
            raise CodeProjectionExtractionError(msg)
        semantic_result = analyzed

    return _ExtractedSource(
        entities=tuple(event.entities),
        relationships=tuple(event.relationships),
        semantic_result=semantic_result,
    )


def _multilang_qualified_name(
    entity: ModelCodeEntity, *, module_qualified_name: str
) -> str:
    if entity.entity_type == "import":
        return normalize_text(entity.entity_name)
    return normalize_text(f"{module_qualified_name}.{entity.entity_name}")


def _extract_multilang(
    *,
    source_text: str,
    relative_path: str,
    repository_id: str,
    source_hash: str,
    extension: str,
    language_extractor_config: Mapping[str, Any] | None,
) -> _ExtractedSource:
    if language_extractor_config is None:
        msg = "non-Python extraction requires explicit language_extractor_config"
        raise CodeProjectionExtractionError(msg)

    extractor = MultiLangExtractor(dict(language_extractor_config))
    if not extractor.can_extract(extension):
        msg = f"no enabled deterministic extractor for .{extension}"
        raise CodeProjectionExtractionError(msg)

    module_qualified_name = _module_qualified_name(relative_path)
    raw_entities = extractor.extract(
        source_content=source_text,
        source_path=relative_path,
        source_repo=repository_id,
        file_hash=source_hash,
        extension=extension,
    )
    normalized_entities: list[ModelCodeEntity] = []
    for raw_entity in raw_entities:
        entity = ModelCodeEntity.model_validate(raw_entity)
        normalized_entities.append(
            entity.model_copy(
                update={
                    "qualified_name": _multilang_qualified_name(
                        entity,
                        module_qualified_name=module_qualified_name,
                    )
                }
            )
        )
    entities = tuple(normalized_entities)

    relationships: list[ModelCodeRelationship] = []
    for index, entity in enumerate(entities):
        relationship_type = "imports" if entity.entity_type == "import" else "defines"
        relationships.append(
            ModelCodeRelationship(
                id=f"code-projection:{source_hash}:{index}:{relationship_type}",
                source_entity=module_qualified_name,
                target_entity=entity.qualified_name,
                relationship_type=relationship_type,
                trust_tier="strong",
                confidence=entity.confidence,
            )
        )
        for base_index, base in enumerate(entity.bases):
            relationships.append(
                ModelCodeRelationship(
                    id=(f"code-projection:{source_hash}:{index}:inherits:{base_index}"),
                    source_entity=entity.qualified_name,
                    target_entity=base,
                    relationship_type="inherits",
                    trust_tier="conservative",
                    confidence=entity.confidence,
                )
            )

    return _ExtractedSource(
        entities=entities,
        relationships=tuple(relationships),
        semantic_result=None,
    )


def _semantic_spans(
    result: SemanticAnalysisResult | None,
) -> dict[tuple[str, str, int], ModelCodeProjectionSpan]:
    if result is None:
        return {}
    spans: dict[tuple[str, str, int], ModelCodeProjectionSpan] = {}
    for entity in result["entities"]:
        key = (entity["name"], entity["entity_type"], entity["line_start"])
        spans[key] = ModelCodeProjectionSpan(
            start_line=entity["line_start"],
            end_line=entity["line_end"],
        )
    return spans


def _span_for_entity(
    entity: ModelCodeEntity,
    semantic_spans: Mapping[tuple[str, str, int], ModelCodeProjectionSpan],
) -> ModelCodeProjectionSpan | None:
    if entity.line_number is None:
        return None
    semantic_type = (
        "class"
        if entity.entity_type in {"class", "model", "protocol"}
        else entity.entity_type
    )
    key = (entity.entity_name, semantic_type, entity.line_number)
    return semantic_spans.get(
        key,
        ModelCodeProjectionSpan(
            start_line=entity.line_number,
            end_line=entity.line_number,
        ),
    )


def _visibility(
    entity_kind: ModelEntityKind, display_name: str
) -> ModelSymbolVisibility:
    if entity_kind in {"import", "module"}:
        return "module"
    if display_name.startswith("__") and display_name.endswith("__"):
        return "public"
    if display_name.startswith("__"):
        return "private"
    if display_name.startswith("_"):
        return "protected"
    return "public"


def _label(
    *,
    namespace: str,
    value: str,
    confidence_basis_points: int,
    producer: str,
    producer_version: str,
) -> ModelCodeProjectionLabel:
    return ModelCodeProjectionLabel(
        namespace=normalize_text(namespace),
        value=normalize_text(value),
        confidence_basis_points=confidence_basis_points,
        producer=normalize_text(producer),
        producer_version=normalize_text(producer_version),
    )


def _source_slice(
    source_text: str, source_span: ModelCodeProjectionSpan | None
) -> str | None:
    if source_span is None:
        return None
    lines = source_text.splitlines(keepends=True)
    return "".join(lines[source_span.start_line - 1 : source_span.end_line])


def _entity_labels(
    *,
    entity: ModelCodeEntity,
    entity_kind: ModelEntityKind,
    source_text: str,
    source_span: ModelCodeProjectionSpan | None,
    language: ModelSourceLanguage,
    classification_config: Mapping[str, Any] | None,
    quality_config: Mapping[str, Any] | None,
) -> tuple[ModelCodeProjectionLabel, ...]:
    extractor_name = "python-ast" if language == "python" else "regex-extractor"
    extractor_version = (
        _AST_EXTRACTOR_VERSION if language == "python" else _REGEX_EXTRACTOR_VERSION
    )
    labels = [
        _label(
            namespace="onex.entity-kind",
            value=entity_kind,
            confidence_basis_points=_basis_points(
                entity.confidence, field_name="entity confidence"
            ),
            producer=extractor_name,
            producer_version=extractor_version,
        )
    ]

    if classification_config is not None:
        classification_result = DeterministicClassifier(
            dict(classification_config)
        ).classify(
            entity_name=entity.entity_name,
            bases=entity.bases,
            methods=[dict(method) for method in entity.methods],
            decorators=entity.decorators,
            docstring=entity.docstring,
        )
        labels.append(
            _label(
                namespace="onex.node-archetype",
                value=classification_result.node_type,
                confidence_basis_points=_basis_points(
                    classification_result.confidence,
                    field_name="classification confidence",
                ),
                producer="deterministic-classifier",
                producer_version=_CLASSIFIER_VERSION,
            )
        )

    if quality_config is not None:
        entity_source = (
            None if entity_kind == "import" else _source_slice(source_text, source_span)
        )
        quality_result = QualityScorer(dict(quality_config)).score(
            source_code=entity_source,
            entity_type=entity.entity_type,
            entity_name=entity.entity_name,
        )
        labels.append(
            _label(
                namespace="onex.code-quality",
                value="deterministic-score",
                confidence_basis_points=_basis_points(
                    quality_result.overall_score, field_name="quality score"
                ),
                producer="quality-scorer",
                producer_version=_QUALITY_SCORER_VERSION,
            )
        )

    return tuple(labels)


def _module_labels(
    *,
    language: ModelSourceLanguage,
    source_text: str,
    semantic_result: SemanticAnalysisResult | None,
    quality_config: Mapping[str, Any] | None,
) -> tuple[ModelCodeProjectionLabel, ...]:
    labels = [
        _label(
            namespace="onex.entity-kind",
            value="module",
            confidence_basis_points=10_000,
            producer="code-projection-mapper",
            producer_version=_MAPPER_VERSION,
        ),
        _label(
            namespace="onex.source-language",
            value=language,
            confidence_basis_points=10_000,
            producer="code-projection-mapper",
            producer_version=_MAPPER_VERSION,
        ),
    ]
    if semantic_result is not None:
        features = semantic_result["semantic_features"]
        labels.append(
            _label(
                namespace="onex.semantic-purpose",
                value=features["code_purpose"],
                confidence_basis_points=10_000,
                producer="semantic-analysis",
                producer_version=ANALYSIS_VERSION_STR,
            )
        )
        for framework in sorted(set(features["detected_frameworks"])):
            labels.append(
                _label(
                    namespace="onex.semantic-framework",
                    value=framework,
                    confidence_basis_points=10_000,
                    producer="semantic-analysis",
                    producer_version=ANALYSIS_VERSION_STR,
                )
            )
        for pattern in sorted(set(features["detected_patterns"])):
            labels.append(
                _label(
                    namespace="onex.semantic-pattern",
                    value=pattern,
                    confidence_basis_points=10_000,
                    producer="semantic-analysis",
                    producer_version=ANALYSIS_VERSION_STR,
                )
            )

    if quality_config is not None:
        result = QualityScorer(dict(quality_config)).score(
            source_code=source_text,
            entity_type="module",
            entity_name="module",
        )
        labels.append(
            _label(
                namespace="onex.code-quality",
                value="deterministic-score",
                confidence_basis_points=_basis_points(
                    result.overall_score, field_name="quality score"
                ),
                producer="quality-scorer",
                producer_version=_QUALITY_SCORER_VERSION,
            )
        )

    if len(labels) > 32:
        msg = "semantic analysis produced more labels than projection v1 permits"
        raise CodeProjectionExtractionError(msg)
    return tuple(labels)


def _entity_kind(entity: ModelCodeEntity) -> ModelEntityKind:
    entity_type = entity.entity_type
    if entity_type == "protocol":
        direct_protocol_base = any(
            base.rsplit(".", maxsplit=1)[-1] == "Protocol" for base in entity.bases
        )
        if not direct_protocol_base and not entity.entity_name.endswith("Protocol"):
            # The legacy AST extractor classifies every base containing the word
            # "Protocol" as a protocol declaration.  An implementation such as
            # ``FileWriter(WriterProtocol)`` is still a class, however.
            return "class"
    try:
        return _ENTITY_KIND_BY_EXTRACTED_TYPE[entity_type]
    except KeyError as exc:
        msg = f"unsupported extracted entity type: {entity_type}"
        raise CodeProjectionExtractionError(msg) from exc


def _relationship_kind(relationship_type: str) -> ModelRelationshipKind:
    try:
        return _RELATIONSHIP_KIND_BY_EXTRACTED_TYPE[relationship_type]
    except KeyError as exc:
        msg = f"unsupported extracted relationship type: {relationship_type}"
        raise CodeProjectionExtractionError(msg) from exc


def _trust_tier(trust_tier: str) -> ModelRelationshipTrustTier:
    try:
        return _TRUST_TIERS[trust_tier]
    except KeyError as exc:
        msg = f"unsupported extracted relationship trust tier: {trust_tier}"
        raise CodeProjectionExtractionError(msg) from exc


def _deduplicate_nodes(
    nodes: Sequence[ModelCodeProjectionNode],
) -> dict[str, ModelCodeProjectionNode]:
    by_id: dict[str, ModelCodeProjectionNode] = {}
    for node in sorted(
        nodes,
        key=lambda item: (
            item.node_id,
            item.source_span.start_line if item.source_span is not None else 0,
        ),
    ):
        # A stable node identity can appear more than once for repeated imports.
        # The earliest declaration is the canonical source anchor.
        by_id.setdefault(node.node_id, node)
    return by_id


def _endpoint_indexes(
    nodes: Mapping[str, ModelCodeProjectionNode],
) -> tuple[
    dict[str, list[ModelCodeProjectionNode]],
    dict[str, list[ModelCodeProjectionNode]],
]:
    by_qualified_name: dict[str, list[ModelCodeProjectionNode]] = defaultdict(list)
    by_simple_name: dict[str, list[ModelCodeProjectionNode]] = defaultdict(list)
    for node in nodes.values():
        by_qualified_name[node.qualified_name].append(node)
        by_simple_name[node.display_name].append(node)
    return dict(by_qualified_name), dict(by_simple_name)


def _resolve_endpoint(
    endpoint: str,
    *,
    source_id: str,
    nodes: dict[str, ModelCodeProjectionNode],
    by_qualified_name: Mapping[str, Sequence[ModelCodeProjectionNode]],
    by_simple_name: Mapping[str, Sequence[ModelCodeProjectionNode]],
    external_nodes: dict[str, ModelCodeProjectionNode],
) -> ModelCodeProjectionNode:
    canonical_endpoint = normalize_text(endpoint)
    if not canonical_endpoint or canonical_endpoint != canonical_endpoint.strip():
        msg = "relationship endpoint must be non-empty canonical text"
        raise CodeProjectionExtractionError(msg)

    exact = tuple(by_qualified_name.get(canonical_endpoint, ()))
    if len(exact) == 1:
        return exact[0]

    simple = tuple(by_simple_name.get(canonical_endpoint, ()))
    if len(simple) == 1:
        return simple[0]

    external = external_nodes.get(canonical_endpoint)
    if external is None:
        external = make_code_node(
            source_id=source_id,
            entity_kind="external_symbol",
            qualified_name=canonical_endpoint,
            symbol_visibility="public",
            labels=(
                _label(
                    namespace="onex.entity-kind",
                    value="external_symbol",
                    confidence_basis_points=10_000,
                    producer="code-projection-mapper",
                    producer_version=_MAPPER_VERSION,
                ),
            ),
        )
        external_nodes[canonical_endpoint] = external
        nodes[external.node_id] = external
    return external


def _build_edges(
    *,
    relationships: Sequence[ModelCodeRelationship],
    source_id: str,
    source_artifact_ref: str,
    nodes: dict[str, ModelCodeProjectionNode],
) -> tuple[ModelCodeProjectionEdge, ...]:
    by_qualified_name, by_simple_name = _endpoint_indexes(nodes)
    external_nodes: dict[str, ModelCodeProjectionNode] = {}
    edges: dict[str, ModelCodeProjectionEdge] = {}
    for relationship in relationships:
        source_node = _resolve_endpoint(
            relationship.source_entity,
            source_id=source_id,
            nodes=nodes,
            by_qualified_name=by_qualified_name,
            by_simple_name=by_simple_name,
            external_nodes=external_nodes,
        )
        target_node = _resolve_endpoint(
            relationship.target_entity,
            source_id=source_id,
            nodes=nodes,
            by_qualified_name=by_qualified_name,
            by_simple_name=by_simple_name,
            external_nodes=external_nodes,
        )
        edge = make_code_edge(
            source_id=source_id,
            source_node_id=source_node.node_id,
            target_node_id=target_node.node_id,
            relationship_kind=_relationship_kind(relationship.relationship_type),
            confidence_basis_points=_basis_points(
                relationship.confidence,
                field_name="relationship confidence",
            ),
            trust_tier=_trust_tier(relationship.trust_tier),
            evidence_refs=(source_artifact_ref,),
            context_eligible=relationship.inject_into_context,
        )
        previous = edges.get(edge.edge_id)
        if previous is not None and previous != edge:
            msg = f"conflicting duplicate relationship: {edge.edge_id}"
            raise CodeProjectionExtractionError(msg)
        edges[edge.edge_id] = edge
    return tuple(edges.values())


def project_source(
    *,
    raw_source: bytes,
    repository_id: str,
    relative_path: str,
    source_version: str,
    language: ModelSourceLanguage,
    cursor_authority: str,
    cursor_sequence: int,
    policy: ModelCodeProjectionPolicy,
    provenance: ModelCodeProjectionProvenance,
    classification_config: Mapping[str, Any] | None = None,
    quality_config: Mapping[str, Any] | None = None,
    language_extractor_config: Mapping[str, Any] | None = None,
) -> ModelCodeProjectionBatch:
    """Map exact source bytes into one closed deterministic projection batch.

    The function performs no filesystem, storage, network, or model I/O.
    Configuration and authority envelopes are explicit inputs; runtime UUIDs,
    timestamps, and analyzer timing metadata never enter the result.  A parse
    or extraction failure raises ``CodeProjectionExtractionError`` instead of
    manufacturing an authoritative empty snapshot.
    """

    canonical_path = normalize_relative_path(relative_path)
    extension = _source_extension(canonical_path, language)
    try:
        source_text = raw_source.decode("utf-8")
    except UnicodeDecodeError as exc:
        msg = f"source is not valid UTF-8: {canonical_path}"
        raise CodeProjectionExtractionError(msg) from exc

    source_hash = sha256_hex(raw_source)
    source = make_code_source(
        repository_id=repository_id,
        relative_path=canonical_path,
        source_version=source_version,
        raw_content_hash_sha256=source_hash,
        byte_count=len(raw_source),
        language=language,
    )
    cursor = ModelCodeProjectionCursor(
        authority=cursor_authority,
        partition=source.source_id,
        sequence=cursor_sequence,
    )

    if language == "python":
        extracted = _extract_python(
            source_text=source_text,
            relative_path=canonical_path,
            repository_id=source.repository_id,
            source_hash=source_hash,
        )
    else:
        extracted = _extract_multilang(
            source_text=source_text,
            relative_path=canonical_path,
            repository_id=source.repository_id,
            source_hash=source_hash,
            extension=extension,
            language_extractor_config=language_extractor_config,
        )

    if not extracted.entities and not extracted.relationships:
        return build_code_projection_batch(
            source=source,
            cursor=cursor,
            policy=policy,
            provenance=provenance,
        )

    module_qualified_name = _module_qualified_name(canonical_path)
    line_count = max(1, len(source_text.splitlines()))
    module = make_code_node(
        source_id=source.source_id,
        entity_kind="module",
        qualified_name=module_qualified_name,
        symbol_visibility="module",
        source_span=ModelCodeProjectionSpan(start_line=1, end_line=line_count),
        labels=_module_labels(
            language=language,
            source_text=source_text,
            semantic_result=extracted.semantic_result,
            quality_config=quality_config,
        ),
    )

    spans = _semantic_spans(extracted.semantic_result)
    declared_nodes: list[ModelCodeProjectionNode] = [module]
    for entity in extracted.entities:
        entity_kind = _entity_kind(entity)
        source_span = _span_for_entity(entity, spans)
        declared_nodes.append(
            make_code_node(
                source_id=source.source_id,
                entity_kind=entity_kind,
                qualified_name=entity.qualified_name,
                display_name=entity.entity_name,
                symbol_visibility=_visibility(entity_kind, entity.entity_name),
                source_span=source_span,
                labels=_entity_labels(
                    entity=entity,
                    entity_kind=entity_kind,
                    source_text=source_text,
                    source_span=source_span,
                    language=language,
                    classification_config=classification_config,
                    quality_config=quality_config,
                ),
            )
        )

    nodes = _deduplicate_nodes(declared_nodes)
    edges = _build_edges(
        relationships=extracted.relationships,
        source_id=source.source_id,
        source_artifact_ref=source.artifact_ref,
        nodes=nodes,
    )
    return build_code_projection_batch(
        source=source,
        cursor=cursor,
        policy=policy,
        provenance=provenance,
        nodes=tuple(nodes.values()),
        edges=edges,
    )


__all__ = ["CodeProjectionExtractionError", "project_source"]
