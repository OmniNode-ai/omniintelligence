# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST-based Python source code entity extraction handler.

Extracts classes, functions, imports, constants, and their relationships
from Python source using the stdlib ast module. All entities have
confidence=1.0 (AST is authoritative for Python source).

Trust tiers:
- strong: INHERITS, IMPORTS (syntactically certain)
- moderate: CONTAINS, DEFINES (structural)
- weak: CALLS (behavioral, best-effort)

Field mapping (aligned with ModelCodeEntity contract):
- id: UUID string
- entity_name: simple name
- entity_type: class/function/import/constant/module
- qualified_name: dotted module path
- source_path: file path relative to repo
- line_number: starting line
- file_hash: SHA256 of source content
"""

from __future__ import annotations

import ast
import hashlib
import logging
import uuid
from dataclasses import dataclass, field

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)

logger = logging.getLogger(__name__)


def _make_id() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


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


def _file_path_to_module(file_path: str) -> str:
    """Convert a file path to a dotted module path.

    ``src/omniintelligence/nodes/foo/node.py``
    becomes ``omniintelligence.nodes.foo.node``.
    """
    path = file_path.replace("\\", "/")
    if path.startswith("src/"):
        path = path[4:]
    if path.endswith(".py"):
        path = path[:-3]
    if path.endswith("/__init__"):
        path = path[: -len("/__init__")]
    return path.replace("/", ".")


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
    module_path = _file_path_to_module(file_path)

    # Module-level entity
    result.entities.append(
        ModelCodeEntity(
            id=_make_id(),
            entity_name=module_path,
            entity_type="module",
            qualified_name=module_path,
            source_repo=source_repo,
            source_path=file_path,
            line_number=1,
            file_hash=file_hash,
        )
    )

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            _extract_class(
                node,
                result,
                file_path,
                file_hash,
                source_repo,
                module_path,
                source_code,
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _extract_function(
                node, result, file_path, file_hash, source_repo, module_path
            )
        elif isinstance(node, ast.Import):
            _extract_import(
                node, result, module_path, source_repo, file_path, file_hash
            )
        elif isinstance(node, ast.ImportFrom):
            _extract_import_from(
                node, result, module_path, source_repo, file_path, file_hash
            )
        elif isinstance(node, ast.Assign):
            _extract_constant(
                node, result, file_path, file_hash, source_repo, module_path
            )

    return result


def _extract_class(
    node: ast.ClassDef,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_path: str,
    source_code: str,
) -> None:
    bases = [ast.unparse(b) for b in node.bases]
    qualified = f"{module_path}.{node.name}"
    methods: list[str] = []

    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            methods.append(item.name)

    result.entities.append(
        ModelCodeEntity(
            id=_make_id(),
            entity_name=node.name,
            entity_type="class",
            qualified_name=qualified,
            source_repo=source_repo,
            source_path=file_path,
            line_number=node.lineno,
            bases=bases,
            methods=[{"name": m} for m in methods],
            decorators=_get_decorators(node),
            docstring=_get_docstring(node),
            file_hash=file_hash,
        )
    )

    # CONTAINS: module -> class
    result.relationships.append(
        ModelCodeRelationship(
            id=_make_id(),
            source_entity=module_path,
            target_entity=qualified,
            relationship_type="contains",
            trust_tier="moderate",
            confidence=1.0,
            evidence=[f"module contains class {node.name}"],
        )
    )

    # INHERITS: class -> each base
    for base_name in bases:
        result.relationships.append(
            ModelCodeRelationship(
                id=_make_id(),
                source_entity=qualified,
                target_entity=base_name,
                relationship_type="inherits",
                trust_tier="strong",
                confidence=1.0,
                evidence=[f"class {node.name}({base_name})"],
            )
        )

    # DEFINES: class -> method (extract methods as entities too)
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            method_qualified = f"{qualified}.{item.name}"
            result.entities.append(
                ModelCodeEntity(
                    id=_make_id(),
                    entity_name=f"{node.name}.{item.name}",
                    entity_type="function",
                    qualified_name=method_qualified,
                    source_repo=source_repo,
                    source_path=file_path,
                    line_number=item.lineno,
                    decorators=_get_decorators(item),
                    docstring=_get_docstring(item),
                    file_hash=file_hash,
                )
            )
            result.relationships.append(
                ModelCodeRelationship(
                    id=_make_id(),
                    source_entity=qualified,
                    target_entity=method_qualified,
                    relationship_type="defines",
                    trust_tier="moderate",
                    confidence=1.0,
                    evidence=[f"class {node.name} defines method {item.name}"],
                )
            )

            # CALLS: best-effort extraction from method body
            _extract_calls(item, result, method_qualified)


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_path: str,
) -> None:
    qualified = f"{module_path}.{node.name}"

    result.entities.append(
        ModelCodeEntity(
            id=_make_id(),
            entity_name=node.name,
            entity_type="function",
            qualified_name=qualified,
            source_repo=source_repo,
            source_path=file_path,
            line_number=node.lineno,
            decorators=_get_decorators(node),
            docstring=_get_docstring(node),
            file_hash=file_hash,
        )
    )

    # CONTAINS: module -> function
    result.relationships.append(
        ModelCodeRelationship(
            id=_make_id(),
            source_entity=module_path,
            target_entity=qualified,
            relationship_type="contains",
            trust_tier="moderate",
            confidence=1.0,
            evidence=[f"module contains function {node.name}"],
        )
    )

    # CALLS: best-effort extraction
    _extract_calls(node, result, qualified)


def _extract_import(
    node: ast.Import,
    result: AstExtractionResult,
    module_path: str,
    source_repo: str,
    file_path: str,
    file_hash: str,
) -> None:
    for alias in node.names:
        result.entities.append(
            ModelCodeEntity(
                id=_make_id(),
                entity_name=alias.name,
                entity_type="import",
                qualified_name=alias.name,
                source_repo=source_repo,
                source_path=file_path,
                line_number=node.lineno,
                file_hash=file_hash,
            )
        )
        result.relationships.append(
            ModelCodeRelationship(
                id=_make_id(),
                source_entity=module_path,
                target_entity=alias.name,
                relationship_type="imports",
                trust_tier="strong",
                confidence=1.0,
                evidence=[f"import {alias.name}"],
            )
        )


def _extract_import_from(
    node: ast.ImportFrom,
    result: AstExtractionResult,
    module_path: str,
    source_repo: str,
    file_path: str,
    file_hash: str,
) -> None:
    if node.module:
        for alias in node.names:
            target = node.module if alias.name == "*" else f"{node.module}.{alias.name}"
            result.entities.append(
                ModelCodeEntity(
                    id=_make_id(),
                    entity_name=alias.name,
                    entity_type="import",
                    qualified_name=target,
                    source_repo=source_repo,
                    source_path=file_path,
                    line_number=node.lineno,
                    file_hash=file_hash,
                )
            )
            result.relationships.append(
                ModelCodeRelationship(
                    id=_make_id(),
                    source_entity=module_path,
                    target_entity=target,
                    relationship_type="imports",
                    trust_tier="strong",
                    confidence=1.0,
                    evidence=[f"from {node.module} import {alias.name}"],
                )
            )


def _extract_constant(
    node: ast.Assign,
    result: AstExtractionResult,
    file_path: str,
    file_hash: str,
    source_repo: str,
    module_path: str,
) -> None:
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            qualified = f"{module_path}.{target.id}"
            result.entities.append(
                ModelCodeEntity(
                    id=_make_id(),
                    entity_name=target.id,
                    entity_type="constant",
                    qualified_name=qualified,
                    source_repo=source_repo,
                    source_path=file_path,
                    line_number=node.lineno,
                    file_hash=file_hash,
                )
            )
            result.relationships.append(
                ModelCodeRelationship(
                    id=_make_id(),
                    source_entity=module_path,
                    target_entity=qualified,
                    relationship_type="defines",
                    trust_tier="moderate",
                    confidence=1.0,
                    evidence=[f"module defines constant {target.id}"],
                )
            )


def _extract_calls(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    result: AstExtractionResult,
    source_qualified: str,
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
                result.relationships.append(
                    ModelCodeRelationship(
                        id=_make_id(),
                        source_entity=source_qualified,
                        target_entity=callee_name,
                        relationship_type="calls",
                        trust_tier="weak",
                        confidence=0.5,
                        evidence=[f"calls {callee_name}"],
                        inject_into_context=False,
                    )
                )


__all__ = ["AstExtractionResult", "extract_entities_from_source"]
