# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""In-memory query engine with fast indexes for file tree lookups.

Ported from Archive/omninode_bridge OnexTreeQueryEngine. Adapted for
synchronous batch pipeline use (no asyncio lock) and contract-config-driven
index selection.

Performance targets (from contract config):
- Lookup: < 5ms
- Index rebuild: < 100ms for 10K files
- Memory: < 20MB for typical project

Reference: OMN-5673
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileNode:
    """Lightweight representation of a file or directory in the tree."""

    path: str
    name: str
    node_type: str  # "file" or "directory"
    extension: str | None = None


class OnexTreeQueryEngine:
    """Fast in-memory query engine for file trees.

    Uses up to 4 index types (configurable via contract config):
    1. exact_path: O(1) lookup by full path
    2. extension: O(1) lookup by file extension
    3. directory: O(1) lookup for directory children
    4. name: name-based similarity search
    """

    def __init__(self, *, enabled_indexes: list[str] | None = None) -> None:
        """Initialize query engine with configured indexes.

        Args:
            enabled_indexes: List of index types to build. If None, all 4
                are enabled. Valid types: exact_path, extension, directory, name.
        """
        all_indexes = {"exact_path", "extension", "directory", "name"}
        self._enabled = set(enabled_indexes) if enabled_indexes else all_indexes

        self._exact_path_index: dict[str, FileNode] = {}
        self._extension_index: dict[str, list[FileNode]] = {}
        self._directory_index: dict[str, list[FileNode]] = {}
        self._name_index: dict[str, list[FileNode]] = {}

    @classmethod
    def from_contract_config(cls, config: dict[str, Any]) -> OnexTreeQueryEngine:
        """Create engine from contract config's query_engine section.

        Args:
            config: The ``config.query_engine`` dict from contract.yaml.
        """
        if not config.get("enabled", True):
            # Explicitly empty set — no indexes built
            engine = cls.__new__(cls)
            engine._enabled = set()
            engine._exact_path_index = {}
            engine._extension_index = {}
            engine._directory_index = {}
            engine._name_index = {}
            return engine

        indexes_config = config.get("indexes", [])
        enabled = [idx["type"] for idx in indexes_config if isinstance(idx, dict)]
        return cls(enabled_indexes=enabled if enabled else None)

    def load_file_nodes(self, nodes: list[FileNode]) -> None:
        """Load file nodes and rebuild enabled indexes.

        Args:
            nodes: List of FileNode objects to index.
        """
        self._exact_path_index.clear()
        self._extension_index.clear()
        self._directory_index.clear()
        self._name_index.clear()

        for node in nodes:
            if "exact_path" in self._enabled:
                self._exact_path_index[node.path] = node

            if "extension" in self._enabled and node.extension:
                self._extension_index.setdefault(node.extension, []).append(node)

            if "directory" in self._enabled and node.node_type == "directory":
                # Index directory itself; children added separately
                self._directory_index.setdefault(node.path, [])

            if "name" in self._enabled:
                self._name_index.setdefault(node.name, []).append(node)

        # Build directory children index from file paths
        if "directory" in self._enabled:
            for node in nodes:
                if node.node_type == "file":
                    # Extract parent directory
                    last_slash = node.path.rfind("/")
                    parent = node.path[:last_slash] if last_slash >= 0 else ""
                    if parent in self._directory_index:
                        self._directory_index[parent].append(node)

    def lookup_path(self, file_path: str) -> FileNode | None:
        """O(1) exact path lookup. Returns None if not found."""
        return self._exact_path_index.get(file_path)

    def find_by_extension(self, extension: str, *, limit: int = 100) -> list[FileNode]:
        """O(1) lookup by file extension (without dot, e.g. 'py')."""
        results = self._extension_index.get(extension, [])
        return results[:limit]

    def get_directory_children(self, dir_path: str) -> list[FileNode]:
        """O(1) lookup for immediate children of a directory."""
        return self._directory_index.get(dir_path, [])

    def find_by_name(self, name: str, *, limit: int = 100) -> list[FileNode]:
        """O(1) exact name lookup."""
        results = self._name_index.get(name, [])
        return results[:limit]

    def find_similar_names(self, name: str, *, limit: int = 10) -> list[FileNode]:
        """O(n) substring match on names."""
        results: list[FileNode] = []
        name_lower = name.lower()

        for indexed_name, nodes in self._name_index.items():
            if name_lower in indexed_name.lower():
                results.extend(nodes)
                if len(results) >= limit:
                    break

        return results[:limit]

    @property
    def stats(self) -> dict[str, int]:
        """Return index sizes for diagnostics."""
        return {
            "exact_path_entries": len(self._exact_path_index),
            "extension_types": len(self._extension_index),
            "directories_indexed": len(self._directory_index),
            "unique_names": len(self._name_index),
        }
