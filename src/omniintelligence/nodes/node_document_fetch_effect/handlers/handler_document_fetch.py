# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler for DocumentFetchEffect — raw document content fetcher.

Fetch algorithm (from OMN-2389 design doc §8):

  FILESYSTEM / WATCHDOG:
    1. Read file from source_ref (absolute path on disk).
    2. If file not found: return FILE_NOT_FOUND with removed event.
    3. Return raw content with resolved_source_version=None.

  GIT_REPO:
    1. Construct full path from repo_path + source_ref.
    2. Read file from disk.
    3. If file not found: return FILE_NOT_FOUND with removed event.
    4. Resolve file-level git SHA via ``git log -1 --format=%H -- <path>``.
    5. If SHA resolution fails: return GIT_SHA_UNAVAILABLE (content still returned).
    6. Return raw content with resolved_source_version=file_sha.

  LINEAR:
    1. Fetch markdown content from blob store by source_ref.
    2. If blob not found or fetch fails: return FETCH_FAILED.
    3. Return raw content with resolved_source_version=None
       (updatedAt is already in the triggering event).

Ticket: OMN-2389
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_document_fetch_effect.handlers.protocol_blob_store import (
        ProtocolBlobStore,
    )

from omniintelligence.nodes.node_document_fetch_effect.models.enum_fetch_status import (
    EnumFetchStatus,
)
from omniintelligence.nodes.node_document_fetch_effect.models.model_document_fetch_input import (
    ModelDocumentFetchInput,
)
from omniintelligence.nodes.node_document_fetch_effect.models.model_document_fetch_output import (
    ModelDocumentFetchOutput,
    ModelDocumentRemovedEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal git helper
# ---------------------------------------------------------------------------


def _resolve_git_file_sha(repo_path: str, file_path: str) -> str | None:
    """Return the file-level git commit SHA, or None on failure.

    Uses ``git log -1 --format=%H -- <file_path>`` to get the SHA of the
    most recent commit that modified the file.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return result.stdout.strip()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Internal fetch helpers
# ---------------------------------------------------------------------------


def _fetch_from_disk(path: str) -> str | None:
    """Read file content from disk. Returns None if file not found."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(f"Cannot read {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_document_fetch(
    input_data: ModelDocumentFetchInput,
    *,
    blob_store: ProtocolBlobStore | None = None,
) -> ModelDocumentFetchOutput:
    """Fetch raw document content based on crawler_type.

    Args:
        input_data: Fetch request with source_ref, crawler_type, and optional
            repo_path (required for git_repo).
        blob_store: Blob store for LINEAR document content retrieval.
            Required when crawler_type is "linear".

    Returns:
        ModelDocumentFetchOutput with status, raw_content, and optional
        removed_event. Passed directly to DocumentParserCompute in-process.
    """
    source_ref = input_data.source_ref
    crawler_type = input_data.crawler_type
    crawl_scope = input_data.crawl_scope
    correlation_id = input_data.correlation_id

    # ------------------------------------------------------------------
    # FILESYSTEM / WATCHDOG: read from source_ref as absolute path
    # ------------------------------------------------------------------
    if crawler_type in ("filesystem", "watchdog"):
        raw = _fetch_from_disk(source_ref)
        if raw is None:
            logger.info(
                "Document not found at fetch time (crawler=%s, ref=%s) — emitting removed",
                crawler_type,
                source_ref,
            )
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.FILE_NOT_FOUND,
                removed_event=ModelDocumentRemovedEvent(
                    source_ref=source_ref,
                    crawl_scope=crawl_scope,
                    correlation_id=correlation_id,
                ),
                error=f"File not found: {source_ref}",
                correlation_id=correlation_id,
            )
        return ModelDocumentFetchOutput(
            source_ref=source_ref,
            crawl_scope=crawl_scope,
            status=EnumFetchStatus.SUCCESS,
            raw_content=raw,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # GIT_REPO: read from repo_path + source_ref, resolve file SHA
    # ------------------------------------------------------------------
    if crawler_type == "git_repo":
        if input_data.repo_path is None:
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.FETCH_FAILED,
                error="repo_path is required for crawler_type='git_repo'",
                correlation_id=correlation_id,
            )

        full_path = str(Path(input_data.repo_path) / source_ref)
        raw = _fetch_from_disk(full_path)

        if raw is None:
            logger.info(
                "Git document not found at fetch time (ref=%s, repo=%s) — emitting removed",
                source_ref,
                input_data.repo_path,
            )
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.FILE_NOT_FOUND,
                removed_event=ModelDocumentRemovedEvent(
                    source_ref=source_ref,
                    crawl_scope=crawl_scope,
                    correlation_id=correlation_id,
                ),
                error=f"File not found: {full_path}",
                correlation_id=correlation_id,
            )

        # Resolve file-level git SHA (best-effort)
        git_sha = _resolve_git_file_sha(input_data.repo_path, source_ref)

        if git_sha is None:
            logger.warning(
                "Git SHA resolution failed for %s in %s — continuing without version",
                source_ref,
                input_data.repo_path,
            )
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.GIT_SHA_UNAVAILABLE,
                raw_content=raw,
                resolved_source_version=None,
                correlation_id=correlation_id,
            )

        return ModelDocumentFetchOutput(
            source_ref=source_ref,
            crawl_scope=crawl_scope,
            status=EnumFetchStatus.SUCCESS,
            raw_content=raw,
            resolved_source_version=git_sha,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # LINEAR: fetch from blob store
    # ------------------------------------------------------------------
    if crawler_type == "linear":
        if blob_store is None:
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.FETCH_FAILED,
                error="blob_store is required for crawler_type='linear'",
                correlation_id=correlation_id,
            )

        try:
            raw = await blob_store.get(source_ref)
        except (RuntimeError, KeyError) as exc:
            logger.error(
                "Blob store fetch failed for Linear item %s: %s",
                source_ref,
                exc,
            )
            return ModelDocumentFetchOutput(
                source_ref=source_ref,
                crawl_scope=crawl_scope,
                status=EnumFetchStatus.FETCH_FAILED,
                error=str(exc),
                correlation_id=correlation_id,
            )

        return ModelDocumentFetchOutput(
            source_ref=source_ref,
            crawl_scope=crawl_scope,
            status=EnumFetchStatus.SUCCESS,
            raw_content=raw,
            # source_version for LINEAR is the updatedAt from the triggering event;
            # callers should use the event's source_version field directly.
            resolved_source_version=None,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Unknown crawler_type (should not happen with typed input)
    # ------------------------------------------------------------------
    return ModelDocumentFetchOutput(
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        status=EnumFetchStatus.FETCH_FAILED,
        error=f"Unknown crawler_type: {crawler_type!r}",
        correlation_id=correlation_id,
    )


__all__ = ["handle_document_fetch"]
