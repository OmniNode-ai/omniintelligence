# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handle_document_fetch.

Covers the requirements from OMN-2389:

FILESYSTEM fetch path:
  - success: file exists at source_ref
  - file_not_found: file missing at fetch time → removed event emitted
  - no resolved_source_version (None for filesystem)

GIT_REPO fetch path:
  - success: file exists + git SHA resolved
  - git_sha_unavailable: file exists but git SHA fails → content still returned
  - file_not_found: file missing → removed event emitted
  - missing repo_path returns fetch_failed

WATCHDOG fetch path:
  - same as FILESYSTEM (shared code path)

LINEAR fetch path:
  - success: blob store returns content
  - fetch_failed: blob store raises KeyError
  - missing blob_store returns fetch_failed

Ticket: OMN-2389
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from omniintelligence.nodes.node_document_fetch_effect.handlers.handler_document_fetch import (
    handle_document_fetch,
)
from omniintelligence.nodes.node_document_fetch_effect.models.enum_fetch_status import (
    EnumFetchStatus,
)
from omniintelligence.nodes.node_document_fetch_effect.models.model_document_fetch_input import (
    ModelDocumentFetchInput,
)
from omniintelligence.nodes.node_document_fetch_effect.node_tests.conftest import (
    GitRepoFixture,
    InMemoryBlobStore,
)

pytestmark = pytest.mark.unit

SCOPE = "omninode/test"


# =============================================================================
# FILESYSTEM fetch path
# =============================================================================


@pytest.mark.asyncio
async def test_filesystem_success() -> None:
    """Filesystem fetch succeeds when file exists at source_ref."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Hello World")
        tmp_path = f.name

    try:
        result = await handle_document_fetch(
            ModelDocumentFetchInput(
                source_ref=tmp_path,
                crawler_type="filesystem",
                crawl_scope=SCOPE,
            ),
        )

        assert result.status == EnumFetchStatus.SUCCESS
        assert result.raw_content == "# Hello World"
        assert result.resolved_source_version is None
        assert result.removed_event is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_filesystem_file_not_found() -> None:
    """Filesystem fetch returns FILE_NOT_FOUND when file is missing."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="/nonexistent/path/to/file.md",
            crawler_type="filesystem",
            crawl_scope=SCOPE,
            correlation_id="test-corr-1",
        ),
    )

    assert result.status == EnumFetchStatus.FILE_NOT_FOUND
    assert result.raw_content is None
    assert result.removed_event is not None
    assert result.removed_event.source_ref == "/nonexistent/path/to/file.md"
    assert result.removed_event.crawl_scope == SCOPE
    assert result.removed_event.event_type == "document.removed.v1"
    assert result.removed_event.correlation_id == "test-corr-1"


@pytest.mark.asyncio
async def test_watchdog_success() -> None:
    """Watchdog fetch path uses the same filesystem logic."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Watchdog Content")
        tmp_path = f.name

    try:
        result = await handle_document_fetch(
            ModelDocumentFetchInput(
                source_ref=tmp_path,
                crawler_type="watchdog",
                crawl_scope=SCOPE,
            ),
        )

        assert result.status == EnumFetchStatus.SUCCESS
        assert result.raw_content == "# Watchdog Content"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =============================================================================
# GIT_REPO fetch path
# =============================================================================


@pytest.mark.asyncio
async def test_git_repo_success(
    git_repo: GitRepoFixture,
) -> None:
    """Git repo fetch succeeds: file exists and git SHA resolved."""
    git_repo.write("docs/guide.md", "# Git Guide")
    git_repo.commit("add guide")

    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="docs/guide.md",
            crawler_type="git_repo",
            repo_path=git_repo.path,
            crawl_scope=SCOPE,
        ),
    )

    assert result.status == EnumFetchStatus.SUCCESS
    assert result.raw_content == "# Git Guide"
    assert result.resolved_source_version is not None
    assert len(result.resolved_source_version) == 40  # git SHA is 40 hex chars


@pytest.mark.asyncio
async def test_git_repo_file_not_found(
    git_repo: GitRepoFixture,
) -> None:
    """Git repo fetch returns FILE_NOT_FOUND when file is missing."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="missing/file.md",
            crawler_type="git_repo",
            repo_path=git_repo.path,
            crawl_scope=SCOPE,
        ),
    )

    assert result.status == EnumFetchStatus.FILE_NOT_FOUND
    assert result.removed_event is not None
    assert result.removed_event.source_ref == "missing/file.md"


@pytest.mark.asyncio
async def test_git_repo_missing_repo_path() -> None:
    """Git repo fetch fails gracefully when repo_path is not provided."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="docs/file.md",
            crawler_type="git_repo",
            crawl_scope=SCOPE,
        ),
    )

    assert result.status == EnumFetchStatus.FETCH_FAILED
    assert result.error is not None
    assert "repo_path" in result.error


@pytest.mark.asyncio
async def test_git_repo_sha_unavailable_when_file_untracked(
    git_repo: GitRepoFixture,
) -> None:
    """Git SHA is None for a file that exists on disk but is not committed."""
    # Write file to disk but do NOT commit it
    git_repo.write("untracked.md", "# Untracked")

    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="untracked.md",
            crawler_type="git_repo",
            repo_path=git_repo.path,
            crawl_scope=SCOPE,
        ),
    )

    # File exists (readable from disk) but git SHA returns empty
    assert result.status == EnumFetchStatus.GIT_SHA_UNAVAILABLE
    assert result.raw_content == "# Untracked"
    assert result.resolved_source_version is None


# =============================================================================
# LINEAR fetch path
# =============================================================================


@pytest.mark.asyncio
async def test_linear_success(
    blob_store: InMemoryBlobStore,
) -> None:
    """Linear fetch succeeds when blob store returns content."""
    blob_store.put("OMN-1234", "# Ticket 1234\n\nContent here.")

    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="OMN-1234",
            crawler_type="linear",
            crawl_scope=SCOPE,
        ),
        blob_store=blob_store,
    )

    assert result.status == EnumFetchStatus.SUCCESS
    assert result.raw_content == "# Ticket 1234\n\nContent here."
    assert result.resolved_source_version is None  # updatedAt is in the event


@pytest.mark.asyncio
async def test_linear_blob_not_found(
    blob_store: InMemoryBlobStore,
) -> None:
    """Linear fetch returns FETCH_FAILED when blob is not in store."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="OMN-9999",
            crawler_type="linear",
            crawl_scope=SCOPE,
        ),
        blob_store=blob_store,
    )

    assert result.status == EnumFetchStatus.FETCH_FAILED
    assert result.raw_content is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_linear_missing_blob_store() -> None:
    """Linear fetch returns FETCH_FAILED when no blob_store provided."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="OMN-1234",
            crawler_type="linear",
            crawl_scope=SCOPE,
        ),
        blob_store=None,
    )

    assert result.status == EnumFetchStatus.FETCH_FAILED
    assert "blob_store" in (result.error or "")


# =============================================================================
# Correlation ID propagation
# =============================================================================


@pytest.mark.asyncio
async def test_correlation_id_propagated() -> None:
    """correlation_id from input is propagated to the output."""
    result = await handle_document_fetch(
        ModelDocumentFetchInput(
            source_ref="/nonexistent.md",
            crawler_type="filesystem",
            crawl_scope=SCOPE,
            correlation_id="corr-xyz-42",
        ),
    )

    assert result.correlation_id == "corr-xyz-42"
    if result.removed_event is not None:
        assert result.removed_event.correlation_id == "corr-xyz-42"
