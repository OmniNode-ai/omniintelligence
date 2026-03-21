# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST-based Python source code entity extraction handler.

Extracts classes, functions, imports, constants, and their relationships
from Python source using the stdlib ast module. All entities have
confidence=1.0 (AST is authoritative for Python source).

Trust tiers:
- conservative: INHERITS, IMPORTS (syntactically certain)
- moderate: CONTAINS, DEFINES (structural)
- weak: CALLS (behavioral, best-effort)
"""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from omniintelligence.enums import EnumEntityType, EnumRelationshipType
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)

logger = logging.getLogger(__name__)


def _make_entity_id(prefix: str, name: str) -> str:
    """Generate a deterministic entity ID."""
    return f"{prefix}_{name}"


def _make_rel_id() -> str:
    return f"rel_{uuid4().hex[:12]}"


def _get_docstring(node: ast.AST) -> str | None:
    """Extract docstring from a class or function node."""
    return ast.get_docstring(node)


def _get_decorators(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Extract decorator names."""
    decorators: list[str] = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.unparse(dec))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(ast.unparse(dec.func))
    return decorators


@dataclass
class AstExtractionResult:
    """Result of AST extraction for a single file."""

    entities: list[ModelCodeEntity] = field(default_factory=list)
    relationships: list[ModelCodeRelationship] = field(default_factory=list)


def extract_entities_from_source(
    source_code: str,
    *,
    file_path: str,
    source_repo: str,
    file_hash: str | None = None,
) -> AstExtractionResult:
    """Extract code entities and relationships from Python source via AST.

    Args:
        source_code: Python source code string.
        file_path: Relative file path within the repo.
        source_repo: Repository name.
        file_hash: SHA256 hash of the file content. Computed if not provided.

    Returns:
        AstExtractionResult with entities and relationships.
    """
    if file_hash is None:
        file_hash = hashlib.sha256(source_code.encode()).hexdigest()

    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError:
        logger.warning("Failed to parse %s in %s: syntax error", file_path, source_repo)
        return AstExtractionResult()

    result = AstExtractionResult()

    # Module-level entity
    module_name = file_path.replace("/", ".").removesuffix(".py")
    module_id = _make_entity_id("mod", module_name)
    result.entities.append(
        ModelCodeEntity(
            entity_id=module_id,
            entity_type=EnumEntityType.MODULE,
            name=module_name,
            file_path=file_path,
            file_hash=file_hash,
            source_repo=source_repo,
            line_start=0,
            line_end=len(source_code.splitlines()),
        )
    )

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            _extract_class(
                node, result, file_path, file_hash, source_repo, module_id, source_code
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _extract_function(
                node, result, file_path, file_hash, source_repo, module_id, source_code
            )
        elif isinstance(node, ast.Import):
            _extract_import(node, result, module_id)
        elif isinstance(node, ast.ImportFrom):
            _extract_import_from(node, result, module_id)
        elif isinstance(node, ast.Assign):
            _extract_constant(
                node, result, file_path, file_hash, source_repo, module_id
            )

    return result


def _extract_class(
    node: ast.ClassDef,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_id: str,
    source_code: str,
) -> None:
    class_id = _make_entity_id("cls", node.name)
    bases = [ast.unparse(b) for b in node.bases]
    methods: list[str] = []

    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            methods.append(item.name)

    result.entities.append(
        ModelCodeEntity(
            entity_id=class_id,
            entity_type=EnumEntityType.CLASS,
            name=node.name,
            file_path=file_path,
            file_hash=file_hash,
            source_repo=source_repo,
            line_start=node.lineno - 1,
            line_end=node.end_lineno or node.lineno,
            bases=bases,
            methods=methods,
            decorators=_get_decorators(node),
            docstring=_get_docstring(node),
            source_code=ast.get_source_segment(source_code, node),
        )
    )

    # CONTAINS: module -> class
    result.relationships.append(
        ModelCodeRelationship(
            relationship_id=_make_rel_id(),
            source_entity_id=module_id,
            target_entity_id=class_id,
            relationship_type=EnumRelationshipType.CONTAINS,
            trust_tier="moderate",
        )
    )

    # INHERITS: class -> each base
    for base_name in bases:
        base_id = _make_entity_id("cls", base_name)
        result.relationships.append(
            ModelCodeRelationship(
                relationship_id=_make_rel_id(),
                source_entity_id=class_id,
                target_entity_id=base_id,
                relationship_type=EnumRelationshipType.EXTENDS,
                trust_tier="conservative",
            )
        )

    # DEFINES: class -> method (extract methods as entities too)
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            method_id = _make_entity_id("fn", f"{node.name}.{item.name}")
            result.entities.append(
                ModelCodeEntity(
                    entity_id=method_id,
                    entity_type=EnumEntityType.FUNCTION,
                    name=f"{node.name}.{item.name}",
                    file_path=file_path,
                    file_hash=file_hash,
                    source_repo=source_repo,
                    line_start=item.lineno - 1,
                    line_end=item.end_lineno or item.lineno,
                    decorators=_get_decorators(item),
                    docstring=_get_docstring(item),
                )
            )
            result.relationships.append(
                ModelCodeRelationship(
                    relationship_id=_make_rel_id(),
                    source_entity_id=class_id,
                    target_entity_id=method_id,
                    relationship_type=EnumRelationshipType.DEFINES,
                    trust_tier="moderate",
                )
            )

            # CALLS: best-effort extraction from method body
            _extract_calls(item, result, method_id)


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_id: str,
    source_code: str,
) -> None:
    fn_id = _make_entity_id("fn", node.name)

    result.entities.append(
        ModelCodeEntity(
            entity_id=fn_id,
            entity_type=EnumEntityType.FUNCTION,
            name=node.name,
            file_path=file_path,
            file_hash=file_hash,
            source_repo=source_repo,
            line_start=node.lineno - 1,
            line_end=node.end_lineno or node.lineno,
            decorators=_get_decorators(node),
            docstring=_get_docstring(node),
            source_code=ast.get_source_segment(source_code, node),
        )
    )

    # CONTAINS: module -> function
    result.relationships.append(
        ModelCodeRelationship(
            relationship_id=_make_rel_id(),
            source_entity_id=module_id,
            target_entity_id=fn_id,
            relationship_type=EnumRelationshipType.CONTAINS,
            trust_tier="moderate",
        )
    )

    # CALLS: best-effort extraction
    _extract_calls(node, result, fn_id)


def _extract_import(
    node: ast.Import,
    result: AstExtractionResult,
    module_id: str,
) -> None:
    for alias in node.names:
        target_id = _make_entity_id("mod", alias.name)
        result.relationships.append(
            ModelCodeRelationship(
                relationship_id=_make_rel_id(),
                source_entity_id=module_id,
                target_entity_id=target_id,
                relationship_type=EnumRelationshipType.IMPORTS,
                trust_tier="conservative",
            )
        )


def _extract_import_from(
    node: ast.ImportFrom,
    result: AstExtractionResult,
    module_id: str,
) -> None:
    if node.module:
        target_id = _make_entity_id("mod", node.module)
        result.relationships.append(
            ModelCodeRelationship(
                relationship_id=_make_rel_id(),
                source_entity_id=module_id,
                target_entity_id=target_id,
                relationship_type=EnumRelationshipType.IMPORTS,
                trust_tier="conservative",
            )
        )


def _extract_constant(
    node: ast.Assign,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_id: str,
) -> None:
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            const_id = _make_entity_id("const", target.id)
            result.entities.append(
                ModelCodeEntity(
                    entity_id=const_id,
                    entity_type=EnumEntityType.CONSTANT,
                    name=target.id,
                    file_path=file_path,
                    file_hash=file_hash,
                    source_repo=source_repo,
                    line_start=node.lineno - 1,
                    line_end=node.end_lineno or node.lineno,
                )
            )
            result.relationships.append(
                ModelCodeRelationship(
                    relationship_id=_make_rel_id(),
                    source_entity_id=module_id,
                    target_entity_id=const_id,
                    relationship_type=EnumRelationshipType.DEFINES,
                    trust_tier="moderate",
                )
            )


def _extract_calls(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    result: AstExtractionResult,
    source_id: str,
) -> None:
    """Best-effort extraction of function calls from a function body."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            callee_name: str | None = None
            if isinstance(child.func, ast.Name):
                callee_name = child.func.id
            elif isinstance(child.func, ast.Attribute):
                callee_name = child.func.attr

            if callee_name:
                target_id = _make_entity_id("fn", callee_name)
                result.relationships.append(
                    ModelCodeRelationship(
                        relationship_id=_make_rel_id(),
                        source_entity_id=source_id,
                        target_entity_id=target_id,
                        relationship_type=EnumRelationshipType.CALLS,
                        trust_tier="weak",
                    )
                )


__all__ = ["AstExtractionResult", "extract_entities_from_source"]
