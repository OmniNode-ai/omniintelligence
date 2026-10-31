# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Group RoleOccurrence results into ModelNodeFamily instances by parent directory.

A ModelNodeFamily represents a group of role occurrences sharing the same parent
``node_*`` directory — the smallest architectural unit in the ONEX node system.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
)

_NODE_DIR_RE = re.compile(r"node_[a-z0-9_]+")


@dataclass(frozen=True)
class ModelNodeFamily:
    """A group of role occurrences sharing the same parent ``node_*`` directory."""

    directory_name: str
    directory_path: str
    source_repo: str
    roles: frozenset[str]
    occurrences: tuple[RoleOccurrence, ...]


def _extract_node_directory(file_path: str) -> str | None:
    """Return the deepest ``node_*`` directory segment from *file_path*, or None."""
    parts = PurePosixPath(file_path).parts
    match: str | None = None
    for part in parts:
        if _NODE_DIR_RE.fullmatch(part):
            match = part
    return match


def _extract_directory_path(file_path: str, dir_name: str) -> str:
    """Return the path up to and including *dir_name* within *file_path*."""
    idx = file_path.find(dir_name)
    if idx == -1:
        return dir_name
    return file_path[: idx + len(dir_name)]


def group_into_node_families(occs: list[RoleOccurrence]) -> list[ModelNodeFamily]:
    """Group role occurrences into :class:`ModelNodeFamily` instances by parent ``node_*`` directory.

    Occurrences whose ``file_path`` does not contain a ``node_*`` directory are
    silently dropped.
    """
    buckets: dict[tuple[str, str], list[RoleOccurrence]] = defaultdict(list)

    for occ in occs:
        dir_name = _extract_node_directory(occ.file_path)
        if dir_name is None:
            continue
        key = (dir_name, occ.source_repo)
        buckets[key].append(occ)

    families: list[ModelNodeFamily] = []
    for (dir_name, source_repo), bucket in sorted(buckets.items()):
        dir_path = _extract_directory_path(bucket[0].file_path, dir_name)
        roles = frozenset(occ.matched_role for occ in bucket)
        families.append(
            ModelNodeFamily(
                directory_name=dir_name,
                directory_path=dir_path,
                source_repo=source_repo,
                roles=roles,
                occurrences=tuple(bucket),
            )
        )

    return families
