# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for AST-based relationship detection between code entities.

Ported from omniarchon ``services/langextract/analysis/code_relationship_detector.py``
and adapted to the ONEX declarative handler pattern.  Adds ``implements`` and
``calls`` relationship types on top of the ``inherits``, ``imports``, and
``defines`` relationships already emitted by ``handler_ast_extract``.

Ticket: OMN-5660
"""

from __future__ import annotations

import ast
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_TRUST_TIERS: dict[str, dict[str, float | bool]] = {
    "strong": {"confidence": 0.95, "inject_into_context": True},
    "conservative": {"confidence": 0.80, "inject_into_context": True},
    "weak": {"confidence": 0.50, "inject_into_context": False},
}


@dataclass(frozen=True)
class RelationshipTypeConfig:
    """Per-relationship-type toggle derived from contract config."""

    relationship_type: str
    enabled: bool = True
    trust_tier: str = "strong"
    inject_into_context: bool = True


@dataclass(frozen=True)
class RelationshipDetectConfig:
    """Configuration for relationship detection, mirrors contract YAML."""

    types: list[RelationshipTypeConfig] = field(default_factory=list)

    def is_enabled(self, rel_type: str) -> bool:
        """Return whether the given relationship type is enabled."""
        for t in self.types:
            if t.relationship_type == rel_type:
                return t.enabled
        return False

    def get_trust_tier(self, rel_type: str) -> str:
        """Return the trust tier for the given relationship type."""
        for t in self.types:
            if t.relationship_type == rel_type:
                return t.trust_tier
        return "strong"

    def get_inject_into_context(self, rel_type: str) -> bool:
        """Return whether to inject into context for the given type."""
        for t in self.types:
            if t.relationship_type == rel_type:
                return t.inject_into_context
        return True


_DEFAULT_CONFIG = RelationshipDetectConfig(
    types=[
        RelationshipTypeConfig("inherits", True, "strong", True),
        RelationshipTypeConfig("imports", True, "strong", True),
        RelationshipTypeConfig("defines", True, "strong", True),
        RelationshipTypeConfig("implements", True, "conservative", True),
        RelationshipTypeConfig("calls", True, "weak", False),
    ]
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_relationships(
    source_code: str,
    file_path: str,
    repo_name: str,
    entities: list[ModelCodeEntity],
    config: list[dict[str, str | bool]] | None = None,
) -> list[ModelCodeRelationship]:
    """Detect relationships between code entities using AST analysis.

    Parameters
    ----------
    source_code:
        Raw Python source text.
    file_path:
        Path relative to repo root (e.g. ``src/pkg/module.py``).
    repo_name:
        Repository the source file belongs to.
    entities:
        Previously extracted entities from ``handler_ast_extract``.
    config:
        Optional list of relationship config dicts from the contract YAML.
        Each dict has keys: ``type``, ``enabled``, ``trust_tier``, and
        optionally ``inject_into_context``.

    Returns
    -------
    list[ModelCodeRelationship]
        Detected relationships.  This list contains **only** ``implements``
        and ``calls`` relationships; ``inherits``, ``imports``, and
        ``defines`` are already emitted by ``handler_ast_extract``.
    """
    cfg = _parse_config(config) if config else _DEFAULT_CONFIG

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        logger.warning("Relationship detection skipped for %s: %s", file_path, exc)
        return []

    module_path = _file_path_to_module(file_path)

    relationships: list[ModelCodeRelationship] = []

    # Collect import metadata for implements detection
    protocol_imports = _collect_protocol_imports(tree)

    if cfg.is_enabled("implements"):
        relationships.extend(
            _detect_implements(tree, module_path, protocol_imports, cfg)
        )

    if cfg.is_enabled("calls"):
        entity_names = {e.entity_name for e in entities}
        relationships.extend(_detect_calls(tree, module_path, entity_names, cfg))

    logger.info(
        "Relationship detection for %s: %d relationships (implements=%d, calls=%d)",
        file_path,
        len(relationships),
        sum(1 for r in relationships if r.relationship_type == "implements"),
        sum(1 for r in relationships if r.relationship_type == "calls"),
    )

    return relationships


# ---------------------------------------------------------------------------
# Implements detection (conservative gate)
# ---------------------------------------------------------------------------


def _collect_protocol_imports(tree: ast.Module) -> set[str]:
    """Collect names that are imported from modules containing 'Protocol'.

    We track two cases:
    1. ``from typing import Protocol`` — the name ``Protocol`` itself
    2. ``from some_module import SomeProtocol`` where the name ends with
       ``Protocol`` — heuristic for custom protocol classes

    Returns a set of imported names that are likely protocols.
    """
    protocol_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                actual_name = alias.asname if alias.asname else alias.name
                # Case 1: importing Protocol itself from typing
                if (
                    alias.name == "Protocol" and "typing" in node.module
                ) or actual_name.endswith("Protocol"):
                    protocol_names.add(actual_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                actual_name = alias.asname if alias.asname else alias.name
                if actual_name.endswith("Protocol"):
                    protocol_names.add(actual_name)
    return protocol_names


def _detect_implements(
    tree: ast.Module,
    module_path: str,
    protocol_imports: set[str],
    cfg: RelationshipDetectConfig,
) -> list[ModelCodeRelationship]:
    """Detect implements relationships with conservative gating.

    A class is considered to implement a protocol only when:
    1. One of its bases matches a name in ``protocol_imports``
    2. OR the base name ends with ``Protocol`` and is explicitly imported
    """
    relationships: list[ModelCodeRelationship] = []
    tier = cfg.get_trust_tier("implements")
    confidence = _TRUST_TIERS.get(tier, _TRUST_TIERS["conservative"])["confidence"]
    inject = cfg.get_inject_into_context("implements")

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        qualified = f"{module_path}.{node.name}"
        for base in node.bases:
            base_name = _extract_name(base)
            if base_name and base_name in protocol_imports:
                relationships.append(
                    ModelCodeRelationship(
                        id=str(uuid.uuid4()),
                        source_entity=qualified,
                        target_entity=base_name,
                        relationship_type="implements",
                        trust_tier=tier,
                        confidence=float(confidence),
                        evidence=[
                            f"class {node.name} implements {base_name} "
                            f"(name match + explicit import)"
                        ],
                        inject_into_context=inject,
                    )
                )
    return relationships


# ---------------------------------------------------------------------------
# Calls detection (weak tier)
# ---------------------------------------------------------------------------


def _detect_calls(
    tree: ast.Module,
    module_path: str,
    known_entity_names: set[str],
    cfg: RelationshipDetectConfig,
) -> list[ModelCodeRelationship]:
    """Detect function call relationships matched against known entities.

    Only emits relationships for calls that match a known entity name.
    Always sets ``inject_into_context=False`` (weak tier).
    """
    relationships: list[ModelCodeRelationship] = []
    tier = cfg.get_trust_tier("calls")
    confidence = _TRUST_TIERS.get(tier, _TRUST_TIERS["weak"])["confidence"]

    # Collect unique call targets
    call_targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _extract_name(node.func)
            if name:
                # Use the simple (leaf) name for matching
                simple_name = name.rsplit(".", 1)[-1]
                if simple_name in known_entity_names:
                    call_targets.add(simple_name)

    for target_name in sorted(call_targets):
        relationships.append(
            ModelCodeRelationship(
                id=str(uuid.uuid4()),
                source_entity=module_path,
                target_entity=target_name,
                relationship_type="calls",
                trust_tier=tier,
                confidence=float(confidence),
                evidence=[f"calls {target_name}"],
                inject_into_context=False,
            )
        )

    return relationships


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_name(node: ast.expr) -> str | None:
    """Extract a dotted name string from an AST expression node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value = _extract_name(node.value)
        if value:
            return f"{value}.{node.attr}"
        return node.attr
    return None


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


def _parse_config(
    raw: list[dict[str, str | bool]],
) -> RelationshipDetectConfig:
    """Parse contract YAML relationship config into typed config."""
    types: list[RelationshipTypeConfig] = []
    for entry in raw:
        types.append(
            RelationshipTypeConfig(
                relationship_type=str(entry.get("type", "")),
                enabled=bool(entry.get("enabled", True)),
                trust_tier=str(entry.get("trust_tier", "strong")),
                inject_into_context=bool(entry.get("inject_into_context", True)),
            )
        )
    return RelationshipDetectConfig(types=types)
