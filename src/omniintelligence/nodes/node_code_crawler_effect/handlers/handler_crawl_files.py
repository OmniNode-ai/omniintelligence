# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for crawling repository files and emitting discovery events."""

from __future__ import annotations

import fnmatch
import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
    ModelCrawlConfig,
    ModelRepoCrawlConfig,
)

logger = logging.getLogger(__name__)


def crawl_files(
    config: ModelCrawlConfig,
    *,
    crawl_id: str | None = None,
    repo_filter: str | None = None,
) -> Iterator[ModelCodeFileDiscoveredEvent]:
    """Walk configured repos and yield a discovery event per matching file.

    Args:
        config: Crawl configuration with repo list and patterns.
        crawl_id: Unique ID for this crawl run. Auto-generated if not provided.
        repo_filter: If set, only crawl this specific repo name.

    Yields:
        ModelCodeFileDiscoveredEvent for each file matching include patterns
        and not matching exclude patterns.
    """
    if crawl_id is None:
        crawl_id = f"crawl_{uuid4().hex[:12]}"

    for repo_config in config.repos:
        if not repo_config.enabled:
            logger.debug("Skipping disabled repo: %s", repo_config.name)
            continue

        if repo_filter and repo_config.name != repo_filter:
            continue

        yield from _crawl_repo(repo_config, crawl_id)


def _crawl_repo(
    repo_config: ModelRepoCrawlConfig,
    crawl_id: str,
) -> Iterator[ModelCodeFileDiscoveredEvent]:
    """Crawl a single repo directory."""
    repo_path = Path(repo_config.path)
    if not repo_path.exists():
        logger.warning("Repo path does not exist: %s", repo_path)
        return

    for include_pattern in repo_config.include:
        for file_path in repo_path.rglob(include_pattern.replace("**/*", "**/*")):
            if not file_path.is_file():
                continue

            # Check exclude patterns
            relative = str(file_path.relative_to(repo_path))
            if _matches_any_exclude(relative, repo_config.exclude):
                continue

            # Compute file hash
            file_hash = _compute_file_hash(file_path)

            yield ModelCodeFileDiscoveredEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                crawl_id=crawl_id,
                repo_name=repo_config.name,
                file_path=relative,
                file_hash=file_hash,
                file_extension=file_path.suffix,
            )


def _matches_any_exclude(relative_path: str, exclude_patterns: list[str]) -> bool:
    """Check if a relative path matches any exclude pattern."""
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_patterns)


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    hasher = hashlib.sha256()
    # io-audit: ignore-next-line file-io
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = ["crawl_files"]
