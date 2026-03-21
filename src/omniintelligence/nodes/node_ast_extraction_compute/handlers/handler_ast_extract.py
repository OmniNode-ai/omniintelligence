# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for AST-based entity extraction from Python source files.

Ported from omniarchon ``services/intelligence/extractors/base_extractor.py``
and adapted to the ONEX declarative handler pattern.

Ticket: OMN-5659
"""

from __future__ import annotations

import ast
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_relationship_detect import (
    detect_relationships,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
    ModelCodeEntitiesExtractedEvent,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extractor configuration (mirrors contract.yaml config.extractors)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractorConfig:
    """Per-extractor toggle and options derived from contract config."""

    classes_enabled: bool = True
    extract_bases: bool = True
    extract_methods: bool = True
    extract_decorators: bool = True
    extract_docstrings: bool = True
    protocols_enabled: bool = True
    extract_method_signatures: bool = True
    pydantic_models_enabled: bool = True
    extract_fields: bool = True
    extract_validators: bool = True
    functions_enabled: bool = True
    extract_signatures: bool = True
    extract_function_decorators: bool = True
    imports_enabled: bool = True
    module_constants_enabled: bool = True


_DEFAULT_CONFIG = ExtractorConfig()


# ---------------------------------------------------------------------------
# Input dataclass (decouples handler from Kafka envelope)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AstExtractInput:
    """Input for the AST extraction handler."""

    source_content: str
    source_path: str
    source_repo: str
    file_hash: str
    crawl_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: ExtractorConfig = _DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def handle_ast_extract(input_data: AstExtractInput) -> ModelCodeEntitiesExtractedEvent:
    """Extract entities and relationships from a Python source file.

    This is the single public entry point for the handler.  It returns a
    fully-populated ``ModelCodeEntitiesExtractedEvent`` regardless of
    whether parsing succeeds, partially succeeds, or fails with a syntax
    error.
    """
    module_path = _file_path_to_module(input_data.source_path)

    entities: list[ModelCodeEntity] = []
    relationships: list[ModelCodeRelationship] = []
    parse_status = "success"
    parse_error: str | None = None

    try:
        tree = ast.parse(input_data.source_content)
    except SyntaxError as exc:
        logger.warning(
            "AST parse failed for %s: %s",
            input_data.source_path,
            exc,
        )
        return ModelCodeEntitiesExtractedEvent(
            event_id=input_data.event_id,
            crawl_id=input_data.crawl_id,
            repo_name=input_data.source_repo,
            file_path=input_data.source_path,
            file_hash=input_data.file_hash,
            entities=[],
            relationships=[],
            parse_status="syntax_error",
            parse_error=str(exc),
            timestamp=datetime.now(timezone.utc),
        )

    cfg = input_data.config

    # --- Extract entities from top-level AST nodes ---
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            _extract_class(
                node,
                entities,
                relationships,
                module_path=module_path,
                source_repo=input_data.source_repo,
                source_path=input_data.source_path,
                file_hash=input_data.file_hash,
                cfg=cfg,
            )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if cfg.functions_enabled:
                entities.append(
                    _build_function_entity(
                        node,
                        module_path=module_path,
                        source_repo=input_data.source_repo,
                        source_path=input_data.source_path,
                        file_hash=input_data.file_hash,
                        cfg=cfg,
                    )
                )
                relationships.append(
                    ModelCodeRelationship(
                        id=str(uuid.uuid4()),
                        source_entity=module_path,
                        target_entity=f"{module_path}.{node.name}",
                        relationship_type="defines",
                        trust_tier="strong",
                        confidence=1.0,
                        evidence=[f"def {node.name}(...)"],
                    )
                )

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if cfg.imports_enabled:
                _extract_imports(
                    node,
                    entities,
                    relationships,
                    module_path=module_path,
                    source_repo=input_data.source_repo,
                    source_path=input_data.source_path,
                    file_hash=input_data.file_hash,
                )

        elif isinstance(node, ast.Assign):
            if cfg.module_constants_enabled:
                _extract_constants(
                    node,
                    entities,
                    module_path=module_path,
                    source_repo=input_data.source_repo,
                    source_path=input_data.source_path,
                    file_hash=input_data.file_hash,
                )

    # --- Post-processing: detect implements/calls relationships (OMN-5660) ---
    additional_rels = detect_relationships(
        source_code=input_data.source_content,
        file_path=input_data.source_path,
        repo_name=input_data.source_repo,
        entities=entities,
    )
    relationships.extend(additional_rels)

    return ModelCodeEntitiesExtractedEvent(
        event_id=input_data.event_id,
        crawl_id=input_data.crawl_id,
        repo_name=input_data.source_repo,
        file_path=input_data.source_path,
        file_hash=input_data.file_hash,
        entities=entities,
        relationships=relationships,
        parse_status=parse_status,
        parse_error=parse_error,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_UPPER_CASE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _file_path_to_module(file_path: str) -> str:
    """Convert a file path to a dotted module path.

    ``src/omniintelligence/nodes/foo/node.py``
    becomes ``omniintelligence.nodes.foo.node``.
    """
    path = file_path.replace("\\", "/")
    # Strip leading ``src/`` if present
    if path.startswith("src/"):
        path = path[4:]
    # Strip ``.py`` suffix
    if path.endswith(".py"):
        path = path[:-3]
    # Strip ``__init__`` suffix
    if path.endswith("/__init__"):
        path = path[: -len("/__init__")]
    return path.replace("/", ".")


def _get_docstring(node: ast.AST) -> str | None:
    """Return the docstring of a node, or ``None``."""
    return ast.get_docstring(node)


def _unparse_safe(node: ast.expr | None) -> str | None:
    """``ast.unparse`` that returns ``None`` on failure or ``None`` input."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return None


def _base_names(node: ast.ClassDef) -> list[str]:
    """Return a list of base-class name strings."""
    names: list[str] = []
    for base in node.bases:
        unparsed = _unparse_safe(base)
        if unparsed:
            names.append(unparsed)
    return names


def _classify_class(bases: list[str]) -> str:
    """Return the entity_type for a class based on its bases."""
    for b in bases:
        if "Protocol" in b:
            return "protocol"
        if "BaseModel" in b:
            return "model"
    return "class"


def _extract_method_info(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:
    """Build a method descriptor dict."""
    return {
        "name": method.name,
        "args": [arg.arg for arg in method.args.args],
        "return_type": _unparse_safe(method.returns),
        "decorators": [ast.unparse(d) for d in method.decorator_list],
    }


def _extract_pydantic_fields(node: ast.ClassDef) -> list[dict[str, Any]]:
    """Extract Pydantic-style field annotations from a class body."""
    fields: list[dict[str, Any]] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            field_info: dict[str, Any] = {
                "name": item.target.id,
                "type": _unparse_safe(item.annotation),
            }
            if item.value is not None:
                field_info["default"] = _unparse_safe(item.value)
            fields.append(field_info)
    return fields


# ---------------------------------------------------------------------------
# Entity builders
# ---------------------------------------------------------------------------


def _extract_class(
    node: ast.ClassDef,
    entities: list[ModelCodeEntity],
    relationships: list[ModelCodeRelationship],
    *,
    module_path: str,
    source_repo: str,
    source_path: str,
    file_hash: str,
    cfg: ExtractorConfig,
) -> None:
    """Extract a class entity and its relationships."""
    bases = _base_names(node) if cfg.extract_bases else []
    entity_type = _classify_class(bases)

    # Gate on config toggles
    if entity_type == "class" and not cfg.classes_enabled:
        return
    if entity_type == "protocol" and not cfg.protocols_enabled:
        return
    if entity_type == "model" and not cfg.pydantic_models_enabled:
        return

    qualified = f"{module_path}.{node.name}"

    methods: list[dict[str, Any]] = []
    if cfg.extract_methods:
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(_extract_method_info(item))

    fields: list[dict[str, Any]] = []
    if entity_type == "model" and cfg.extract_fields:
        fields = _extract_pydantic_fields(node)

    decorators: list[str] = []
    if cfg.extract_decorators:
        decorators = [ast.unparse(d) for d in node.decorator_list]

    docstring = _get_docstring(node) if cfg.extract_docstrings else None

    entities.append(
        ModelCodeEntity(
            id=str(uuid.uuid4()),
            entity_name=node.name,
            entity_type=entity_type,
            qualified_name=qualified,
            source_repo=source_repo,
            source_path=source_path,
            line_number=node.lineno,
            bases=bases,
            methods=methods,
            fields=fields,
            decorators=decorators,
            docstring=docstring,
            signature=None,
            file_hash=file_hash,
        )
    )

    # Inheritance relationships
    for base_name in bases:
        relationships.append(
            ModelCodeRelationship(
                id=str(uuid.uuid4()),
                source_entity=qualified,
                target_entity=base_name,
                relationship_type="inherits",
                trust_tier="strong",
                confidence=1.0,
                evidence=[f"class {node.name}({base_name})"],
            )
        )

    # "defines" relationship from module to class
    relationships.append(
        ModelCodeRelationship(
            id=str(uuid.uuid4()),
            source_entity=module_path,
            target_entity=qualified,
            relationship_type="defines",
            trust_tier="strong",
            confidence=1.0,
            evidence=[f"class {node.name}"],
        )
    )


def _build_function_entity(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    module_path: str,
    source_repo: str,
    source_path: str,
    file_hash: str,
    cfg: ExtractorConfig,
) -> ModelCodeEntity:
    """Build a ModelCodeEntity for a module-level function."""
    qualified = f"{module_path}.{node.name}"

    decorators: list[str] = []
    if cfg.extract_function_decorators:
        decorators = [ast.unparse(d) for d in node.decorator_list]

    signature: str | None = None
    if cfg.extract_signatures:
        try:
            args_str = ast.unparse(node.args)
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            signature = f"({args_str}){ret}"
        except Exception:  # noqa: BLE001
            signature = None

    docstring = _get_docstring(node) if cfg.extract_docstrings else None

    return ModelCodeEntity(
        id=str(uuid.uuid4()),
        entity_name=node.name,
        entity_type="function",
        qualified_name=qualified,
        source_repo=source_repo,
        source_path=source_path,
        line_number=node.lineno,
        bases=[],
        methods=[],
        fields=[],
        decorators=decorators,
        docstring=docstring,
        signature=signature,
        file_hash=file_hash,
    )


def _extract_imports(
    node: ast.Import | ast.ImportFrom,
    entities: list[ModelCodeEntity],
    relationships: list[ModelCodeRelationship],
    *,
    module_path: str,
    source_repo: str,
    source_path: str,
    file_hash: str,
) -> None:
    """Extract import entities and relationships."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            entities.append(
                ModelCodeEntity(
                    id=str(uuid.uuid4()),
                    entity_name=alias.name,
                    entity_type="import",
                    qualified_name=alias.name,
                    source_repo=source_repo,
                    source_path=source_path,
                    line_number=node.lineno,
                    file_hash=file_hash,
                )
            )
            relationships.append(
                ModelCodeRelationship(
                    id=str(uuid.uuid4()),
                    source_entity=module_path,
                    target_entity=alias.name,
                    relationship_type="imports",
                    trust_tier="strong",
                    confidence=1.0,
                    evidence=[f"import {alias.name}"],
                )
            )
    elif isinstance(node, ast.ImportFrom) and node.module:
        for alias in node.names:
            target = node.module if alias.name == "*" else f"{node.module}.{alias.name}"
            entities.append(
                ModelCodeEntity(
                    id=str(uuid.uuid4()),
                    entity_name=alias.name,
                    entity_type="import",
                    qualified_name=target,
                    source_repo=source_repo,
                    source_path=source_path,
                    line_number=node.lineno,
                    file_hash=file_hash,
                )
            )
            relationships.append(
                ModelCodeRelationship(
                    id=str(uuid.uuid4()),
                    source_entity=module_path,
                    target_entity=target,
                    relationship_type="imports",
                    trust_tier="strong",
                    confidence=1.0,
                    evidence=[f"from {node.module} import {alias.name}"],
                )
            )


def _extract_constants(
    node: ast.Assign,
    entities: list[ModelCodeEntity],
    *,
    module_path: str,
    source_repo: str,
    source_path: str,
    file_hash: str,
) -> None:
    """Extract module-level UPPER_CASE constant assignments."""
    for target in node.targets:
        if isinstance(target, ast.Name) and _UPPER_CASE_RE.match(target.id):
            entities.append(
                ModelCodeEntity(
                    id=str(uuid.uuid4()),
                    entity_name=target.id,
                    entity_type="constant",
                    qualified_name=f"{module_path}.{target.id}",
                    source_repo=source_repo,
                    source_path=source_path,
                    line_number=node.lineno,
                    file_hash=file_hash,
                )
            )
