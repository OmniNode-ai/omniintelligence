# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""OnexTree filesystem scanner and code crawl handler.

Ported from omninode_bridge intelligence/onextree/generator.py.
Scans configured repositories for Python source files and emits
ModelCodeFileDiscoveredEvent for each discovered file.

The handler reads repo configuration from the contract YAML so that
adding a new repository requires zero code changes.

Ticket: OMN-5658
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from omniintelligence.nodes.node_code_crawler_effect.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_onextree import (
    DEFAULT_EXCLUDE_PATTERNS,
    ModelOnextreeRoot,
    OnexTreeNode,
    ProjectStatistics,
)

logger = logging.getLogger(__name__)


def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern with ``**`` support to a regex string.

    Handles:
        - ``**`` matches any number of path segments (including zero)
        - ``*`` matches anything within a single path segment
        - ``?`` matches a single non-separator character
        - All other characters are escaped
    """
    result = ""
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            result += ".*"
            i += 2
            # Skip trailing separator after **
            if i < len(pattern) and pattern[i] == "/":
                i += 1
        elif pattern[i] == "*":
            result += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            result += "[^/]"
            i += 1
        else:
            result += re.escape(pattern[i])
            i += 1
    return "^" + result + "$"


# ---------------------------------------------------------------------------
# OnexTreeGenerator — filesystem scanner
# ---------------------------------------------------------------------------


class OnexTreeGenerator:
    """Generates OnexTree from filesystem.

    Scans a project root directory recursively, applying include/exclude
    glob patterns to filter files. Builds a tree of OnexTreeNode objects
    with project-level statistics.

    Performance target: < 100ms for 10K files.
    """

    def __init__(
        self,
        project_root: Path,
        exclude_patterns: list[str] | None = None,
        include_patterns: list[str] | None = None,
    ) -> None:
        """Initialize tree generator.

        Args:
            project_root: Root directory to scan.
            exclude_patterns: Glob patterns for paths to exclude.
                Uses DEFAULT_EXCLUDE_PATTERNS if None.
            include_patterns: Glob patterns for paths to include.
                If provided, only matching files are included.
                If None, all non-excluded files are included.
        """
        self.project_root = Path(project_root).resolve()
        self.exclude_patterns = exclude_patterns or list(DEFAULT_EXCLUDE_PATTERNS)
        self.include_patterns = include_patterns
        self.statistics = ProjectStatistics()

    async def generate_tree(self) -> ModelOnextreeRoot:
        """Generate complete tree from filesystem.

        Returns:
            ModelOnextreeRoot with complete tree and statistics.
        """
        self.statistics = ProjectStatistics()
        root_node = await self._scan_directory(self.project_root)
        self.statistics.last_updated = datetime.now()

        return ModelOnextreeRoot(
            project_root=str(self.project_root),
            generated_at=datetime.now(),
            tree=root_node,
            statistics=self.statistics,
        )

    async def _scan_directory(self, dir_path: Path) -> OnexTreeNode:
        """Recursively scan directory and build tree node."""
        children: list[OnexTreeNode] = []

        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name))

            for entry in entries:
                if self._should_exclude(entry):
                    continue

                try:
                    if entry.is_dir():
                        self.statistics.total_directories += 1
                        child_node = await self._scan_directory(entry)
                        children.append(child_node)
                    elif entry.is_file():
                        if self._should_include(entry):
                            self.statistics.total_files += 1
                            child_node = self._create_file_node(entry)
                            children.append(child_node)
                except (PermissionError, OSError) as e:
                    logger.debug("Skipping inaccessible path %s: %s", entry, e)
                    continue

        except PermissionError as e:
            logger.warning("Permission denied accessing directory %s: %s", dir_path, e)

        relative_path = str(dir_path.relative_to(self.project_root))
        if relative_path == ".":
            relative_path = ""

        return OnexTreeNode(
            path=relative_path,
            name=(
                dir_path.name
                if dir_path != self.project_root
                else self.project_root.name
            ),
            type="directory",
            size=None,
            extension=None,
            last_modified=None,
            children=children,
            inferred_purpose=None,
            architectural_pattern=None,
        )

    def _create_file_node(self, file_path: Path) -> OnexTreeNode:
        """Create node for a single file."""
        try:
            stat = file_path.stat()
            extension = file_path.suffix[1:] if file_path.suffix else None

            if extension:
                self.statistics.file_type_distribution[extension] = (
                    self.statistics.file_type_distribution.get(extension, 0) + 1
                )
            self.statistics.total_size_bytes += stat.st_size

            relative_path = str(file_path.relative_to(self.project_root))

            return OnexTreeNode(
                path=relative_path,
                name=file_path.name,
                type="file",
                size=stat.st_size,
                extension=extension,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                children=None,
                inferred_purpose=None,
                architectural_pattern=None,
            )

        except (OSError, PermissionError) as e:
            logger.debug("Error reading file metadata %s: %s", file_path, e)
            return OnexTreeNode(
                path=str(file_path.relative_to(self.project_root)),
                name=file_path.name,
                type="file",
                size=None,
                extension=None,
                last_modified=None,
                children=None,
                inferred_purpose=None,
                architectural_pattern=None,
            )

    def _should_exclude(self, path: Path) -> bool:
        """Check if path matches any exclusion patterns."""
        return any(fnmatch(path.name, pattern) for pattern in self.exclude_patterns)

    def _should_include(self, path: Path) -> bool:
        """Check if file matches any include patterns.

        If no include patterns are set, all files pass.
        Patterns are matched against the path relative to project_root
        using glob-style matching with ``**`` support.
        """
        if not self.include_patterns:
            return True
        relative = str(path.relative_to(self.project_root))
        return any(
            re.match(_glob_to_regex(pattern), relative) is not None
            for pattern in self.include_patterns
        )


# ---------------------------------------------------------------------------
# Crawl handler — reads contract config, runs generator, emits events
# ---------------------------------------------------------------------------


def _collect_python_files(tree: OnexTreeNode) -> list[OnexTreeNode]:
    """Recursively collect all file nodes from an OnexTree."""
    files: list[OnexTreeNode] = []
    if tree.type == "file":
        files.append(tree)
    elif tree.children:
        for child in tree.children:
            files.extend(_collect_python_files(child))
    return files


def _sha256_of_file(file_path: Path) -> str:
    """Return the SHA-256 hex digest of a file's content."""
    # io-audit: ignore-next-line file-io
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


async def handle_code_crawl(
    *,
    repos_config: list[dict[str, Any]],
    crawl_id: str | None = None,
) -> list[ModelCodeFileDiscoveredEvent]:
    """Crawl configured repositories and emit discovery events.

    Reads the repo list from contract config (passed in by the node shell).
    For each repo, runs OnexTreeGenerator with include/exclude patterns
    from the contract YAML, then emits a ModelCodeFileDiscoveredEvent for
    every discovered Python file.

    Args:
        repos_config: List of repo config dicts from contract.yaml, each with
            keys: name, path, include, exclude.
        crawl_id: Optional batch identifier. Generated if not provided.

    Returns:
        List of ModelCodeFileDiscoveredEvent for all discovered files.
    """
    if crawl_id is None:
        crawl_id = str(uuid.uuid4())

    events: list[ModelCodeFileDiscoveredEvent] = []

    for repo_cfg in repos_config:
        repo_name = repo_cfg["name"]
        raw_path = repo_cfg["path"]
        repo_path = Path(os.path.expandvars(raw_path))
        include_patterns: list[str] = repo_cfg.get("include", [])
        exclude_patterns: list[str] = repo_cfg.get(
            "exclude", list(DEFAULT_EXCLUDE_PATTERNS)
        )

        if not repo_path.is_dir():
            logger.warning("Repo path does not exist, skipping: %s", repo_path)
            continue

        generator = OnexTreeGenerator(
            project_root=repo_path,
            exclude_patterns=exclude_patterns,
            include_patterns=include_patterns if include_patterns else None,
        )

        tree_root = await generator.generate_tree()
        file_nodes = _collect_python_files(tree_root.tree)

        for node in file_nodes:
            full_path = repo_path / node.path
            try:
                source_content = full_path.read_text(encoding="utf-8")
                file_hash = hashlib.sha256(source_content.encode("utf-8")).hexdigest()
                file_size = len(source_content.encode("utf-8"))
            except (OSError, PermissionError, UnicodeDecodeError) as e:
                logger.warning("Cannot read file %s: %s", full_path, e)
                continue

            events.append(
                ModelCodeFileDiscoveredEvent(
                    event_id=str(uuid.uuid4()),
                    crawl_id=crawl_id,
                    repo_name=repo_name,
                    file_path=node.path,
                    file_hash=file_hash,
                    file_size_bytes=file_size,
                    source_content=source_content,
                    timestamp=datetime.now(tz=timezone.utc),
                )
            )

        logger.info(
            "Crawled %s: %d files discovered",
            repo_name,
            len([e for e in events if e.repo_name == repo_name]),
        )

    return events


__all__ = [
    "OnexTreeGenerator",
    "handle_code_crawl",
]
