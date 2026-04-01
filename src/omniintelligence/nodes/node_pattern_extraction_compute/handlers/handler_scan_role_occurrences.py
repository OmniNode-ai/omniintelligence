# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Scan a directory tree for role occurrences of a structural pattern.

Walks a directory, extracts AST entities from each .py file found,
and matches entities against each role in the pattern definition.

This finds individual role occurrences (Sense 1), NOT grouped pattern
instances (Sense 2). See plan terminology section.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_extract_ast import (
    extract_entities_from_source,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_match_pattern import (
    match_pattern_role,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoleOccurrence:
    """A single class that matches a pattern role by direct inheritance.

    This is a role occurrence, not a grouped pattern instance. Multiple
    RoleOccurrences from related files would need to be grouped to form
    a full architectural pattern instance (future work).
    """

    pattern_name: str
    matched_role: str
    entity_name: str
    qualified_name: str
    file_path: str
    source_repo: str
    bases: list[str]


def scan_directory_for_role_occurrences(
    directory: Path,
    pattern: ModelPatternDefinition,
    *,
    source_repo: str,
    repo_root: Path | None = None,
) -> list[RoleOccurrence]:
    """Scan all .py files in a directory tree for role matches.

    Args:
        directory: Root directory to scan.
        pattern: Pattern definition to match against.
        source_repo: Repository name for extracted entities.
        repo_root: Repository root for relative path computation.
            If None, uses directory's parent.

    Returns:
        List of detected role occurrences.
    """
    if repo_root is None:
        repo_root = directory.parent

    occurrences: list[RoleOccurrence] = []

    py_files = sorted(directory.rglob("*.py"))
    for py_file in py_files:
        if py_file.name.startswith("test_") or "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        rel_path = str(py_file.relative_to(repo_root))
        result = extract_entities_from_source(
            source,
            file_path=rel_path,
            source_repo=source_repo,
        )

        for role in pattern.roles:
            matches = match_pattern_role(role, result.entities)
            for entity in matches:
                occurrences.append(
                    RoleOccurrence(
                        pattern_name=pattern.pattern_name,
                        matched_role=role.role_name,
                        entity_name=entity.entity_name,
                        qualified_name=entity.qualified_name,
                        file_path=entity.source_path,
                        source_repo=source_repo,
                        bases=entity.bases,
                    )
                )

    return occurrences
