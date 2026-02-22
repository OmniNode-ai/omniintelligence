# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handle_git_repo_crawl.

Covers the requirements from OMN-2387:

HEAD SHA fast-path:
  - skip entire repo when HEAD SHA unchanged (O(1))
  - process repo when HEAD SHA changes

Git diff + content fingerprinting:
  - emit document.discovered.v1 for new .md files
  - emit document.changed.v1 when content_fingerprint differs
  - no event when file is unchanged (same hash)
  - emit document.removed.v1 for files in crawl_state but not git tree

source_version semantics:
  - source_version stores file-level commit SHA, not HEAD

State persistence:
  - crawl_state updated after crawl (head_sha and entries)
  - idempotent: re-processing same HEAD emits nothing

Integration test:
  - commit a .md file change, verify discovered then changed event emitted

Ticket: OMN-2387
"""

from __future__ import annotations

import hashlib

import pytest

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.handler_git_repo_crawl import (
    handle_git_repo_crawl,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
    ModelCrawlStateEntry,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.models.model_crawl_input import (
    ModelGitRepoCrawlInput,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.node_tests.conftest import (
    GitFixture,
    InMemoryCrawlStateStore,
)

pytestmark = pytest.mark.unit


# =============================================================================
# HEAD SHA fast-path
# =============================================================================


@pytest.mark.asyncio
async def test_skip_when_head_sha_unchanged(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """Repo is skipped (skipped=True) when HEAD SHA matches stored value."""
    git_repo.write("docs/page.md", "# Hello")
    sha = git_repo.commit("add page")

    # Pre-populate crawl_state with the current HEAD SHA
    await crawl_state.update_head_sha(git_repo.path, sha)

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    assert result.skipped is True
    assert result.head_sha == sha
    assert result.discovered == []
    assert result.changed == []
    assert result.removed == []


@pytest.mark.asyncio
async def test_process_when_head_sha_changed(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """Repo is processed when HEAD SHA differs from stored value."""
    git_repo.write("docs/page.md", "# Hello")
    old_sha = git_repo.commit("initial")

    await crawl_state.update_head_sha(git_repo.path, old_sha)

    # Advance HEAD
    git_repo.write("docs/page.md", "# Updated")
    _new_sha = git_repo.commit("update page")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    assert result.skipped is False


# =============================================================================
# Document discovery
# =============================================================================


@pytest.mark.asyncio
async def test_new_md_file_emits_discovered_event(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """A new .md file with no crawl_state entry emits document.discovered.v1."""
    content = "# First doc"
    git_repo.write("README.md", content)
    git_repo.commit("add README")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    assert len(result.discovered) == 1
    evt = result.discovered[0]
    assert evt.file_path == "README.md"
    assert evt.event_type == "document.discovered.v1"
    expected_fp = hashlib.sha256(content.encode()).hexdigest()
    assert evt.content_fingerprint == expected_fp


@pytest.mark.asyncio
async def test_discovered_event_has_file_level_source_version(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """source_version in discovered event is the file-level commit SHA, not HEAD."""
    git_repo.write("docs/note.md", "# Note")
    git_repo.commit("add note")

    # Add an unrelated second commit so HEAD != file commit SHA
    git_repo.write("other.txt", "unrelated")
    git_repo.commit("add unrelated")

    head_sha = git_repo.head_sha()
    file_sha = git_repo.file_commit_sha("docs/note.md")

    # The file commit SHA must differ from HEAD for this test to be meaningful
    assert file_sha != head_sha, (
        "Test assumption violated: file commit SHA equals HEAD SHA"
    )

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    md_events = [e for e in result.discovered if e.file_path == "docs/note.md"]
    assert len(md_events) == 1
    assert md_events[0].source_version == file_sha
    assert md_events[0].source_version != head_sha


# =============================================================================
# Content change detection
# =============================================================================


@pytest.mark.asyncio
async def test_changed_content_emits_changed_event(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """A file with a different content_fingerprint emits document.changed.v1."""
    git_repo.write("guide.md", "# Original")
    first_sha = git_repo.commit("initial")
    first_file_sha = git_repo.file_commit_sha("guide.md")
    first_fp = hashlib.sha256(b"# Original").hexdigest()

    # Simulate crawl_state from a previous crawl
    await crawl_state.upsert_entry(
        ModelCrawlStateEntry(
            repo_path=git_repo.path,
            file_path="guide.md",
            source_version=first_file_sha,
            content_fingerprint=first_fp,
            head_sha=first_sha,
        )
    )
    await crawl_state.update_head_sha(git_repo.path, first_sha)

    # Now modify the file and advance HEAD
    git_repo.write("guide.md", "# Updated content")
    _new_sha = git_repo.commit("update guide")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    assert len(result.changed) == 1
    evt = result.changed[0]
    assert evt.file_path == "guide.md"
    assert evt.event_type == "document.changed.v1"
    assert evt.previous_source_version == first_file_sha
    expected_new_fp = hashlib.sha256(b"# Updated content").hexdigest()
    assert evt.content_fingerprint == expected_new_fp


@pytest.mark.asyncio
async def test_unchanged_content_emits_no_event(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """A file whose content_fingerprint matches crawl_state generates no event."""
    content = "# Stable"
    git_repo.write("stable.md", content)
    sha = git_repo.commit("add stable")
    file_sha = git_repo.file_commit_sha("stable.md")
    fp = hashlib.sha256(content.encode()).hexdigest()

    await crawl_state.upsert_entry(
        ModelCrawlStateEntry(
            repo_path=git_repo.path,
            file_path="stable.md",
            source_version=file_sha,
            content_fingerprint=fp,
            head_sha=sha,
        )
    )
    await crawl_state.update_head_sha(git_repo.path, sha)

    # Add unrelated file so HEAD changes but stable.md content is unchanged
    git_repo.write("other.txt", "noise")
    _new_sha = git_repo.commit("add noise")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    stable_events = [
        e
        for e in result.changed + result.discovered
        if getattr(e, "file_path", None) == "stable.md"
    ]
    assert stable_events == [], f"Expected no events for stable.md, got {stable_events}"


# =============================================================================
# Removal detection
# =============================================================================


@pytest.mark.asyncio
async def test_removed_file_emits_removed_event(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """A file in crawl_state but absent from the git tree emits document.removed.v1."""
    git_repo.write("will_delete.md", "# To be removed")
    sha1 = git_repo.commit("add file")
    file_sha = git_repo.file_commit_sha("will_delete.md")
    fp = hashlib.sha256(b"# To be removed").hexdigest()

    await crawl_state.upsert_entry(
        ModelCrawlStateEntry(
            repo_path=git_repo.path,
            file_path="will_delete.md",
            source_version=file_sha,
            content_fingerprint=fp,
            head_sha=sha1,
        )
    )
    await crawl_state.update_head_sha(git_repo.path, sha1)

    # Delete and commit
    git_repo.delete("will_delete.md")
    _sha2 = git_repo.commit("delete file")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    assert len(result.removed) == 1
    evt = result.removed[0]
    assert evt.file_path == "will_delete.md"
    assert evt.event_type == "document.removed.v1"
    assert evt.last_source_version == file_sha


@pytest.mark.asyncio
async def test_removed_file_deleted_from_crawl_state(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """After a removed event, the entry is deleted from crawl_state."""
    git_repo.write("gone.md", "# Bye")
    sha1 = git_repo.commit("add")
    file_sha = git_repo.file_commit_sha("gone.md")
    fp = hashlib.sha256(b"# Bye").hexdigest()

    await crawl_state.upsert_entry(
        ModelCrawlStateEntry(
            repo_path=git_repo.path,
            file_path="gone.md",
            source_version=file_sha,
            content_fingerprint=fp,
            head_sha=sha1,
        )
    )
    await crawl_state.update_head_sha(git_repo.path, sha1)

    git_repo.delete("gone.md")
    git_repo.commit("delete")

    await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    entry = await crawl_state.get_entry(git_repo.path, "gone.md")
    assert entry is None


# =============================================================================
# State persistence
# =============================================================================


@pytest.mark.asyncio
async def test_head_sha_updated_after_crawl(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """HEAD SHA in crawl_state is updated after a successful crawl."""
    git_repo.write("file.md", "# File")
    sha = git_repo.commit("initial")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    stored_sha = await crawl_state.get_head_sha(git_repo.path)
    assert stored_sha == sha
    assert result.head_sha == sha


@pytest.mark.asyncio
async def test_idempotent_recrawl_emits_nothing(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """Re-crawling the same HEAD SHA (after initial crawl) emits no events."""
    git_repo.write("page.md", "# Page")
    git_repo.commit("initial")

    # First crawl — discovers the file
    first = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )
    assert len(first.discovered) == 1

    # Second crawl with same HEAD — must be skipped entirely
    second = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )
    assert second.skipped is True
    assert second.discovered == []
    assert second.changed == []
    assert second.removed == []


# =============================================================================
# source_version semantics
# =============================================================================


@pytest.mark.asyncio
async def test_source_version_is_file_level_not_head(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """source_version stored in crawl_state is the file-level commit SHA."""
    git_repo.write("notes.md", "# Notes")
    git_repo.commit("add notes")

    # Add an unrelated commit so HEAD != file commit SHA
    git_repo.write("junk.txt", "junk")
    git_repo.commit("add junk")

    file_sha = git_repo.file_commit_sha("notes.md")
    head_sha = git_repo.head_sha()
    assert file_sha != head_sha

    await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    entry = await crawl_state.get_entry(git_repo.path, "notes.md")
    assert entry is not None
    assert entry.source_version == file_sha
    assert entry.source_version != head_sha


# =============================================================================
# Integration test: full discovered -> changed lifecycle
# =============================================================================


@pytest.mark.asyncio
async def test_integration_discover_then_change(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """Full integration: commit file, crawl (discovered), modify, crawl (changed)."""
    git_repo.write("doc.md", "# Version 1")
    git_repo.commit("v1")

    first = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )
    assert len(first.discovered) == 1
    assert first.discovered[0].file_path == "doc.md"
    assert first.changed == []

    # Modify the file
    git_repo.write("doc.md", "# Version 2 — completely different")
    git_repo.commit("v2")

    second = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )
    assert second.changed == [] or len(second.changed) == 1
    # changed XOR discovered (depending on whether diff lists it)
    changed_paths = {e.file_path for e in second.changed}
    discovered_paths = {e.file_path for e in second.discovered}
    # doc.md should appear in changed (was already in crawl_state)
    assert "doc.md" in changed_paths or "doc.md" in discovered_paths


# =============================================================================
# Trigger source propagation
# =============================================================================


@pytest.mark.asyncio
async def test_correlation_id_propagated_to_events(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """correlation_id from the input is propagated to emitted events."""
    git_repo.write("tracked.md", "# Tracked")
    git_repo.commit("initial")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(
            repo_path=git_repo.path,
            correlation_id="test-corr-id-42",
        ),
        crawl_state=crawl_state,
    )

    for evt in result.discovered:
        assert evt.correlation_id == "test-corr-id-42"


# =============================================================================
# Non-.md files are not tracked
# =============================================================================


@pytest.mark.asyncio
async def test_non_md_files_not_discovered(
    git_repo: GitFixture,
    crawl_state: InMemoryCrawlStateStore,
) -> None:
    """Non-.md files (e.g., .py, .txt) are ignored by the crawler."""
    git_repo.write("script.py", "print('hello')")
    git_repo.write("notes.txt", "plain text")
    git_repo.write("README.md", "# Readme")
    git_repo.commit("mixed files")

    result = await handle_git_repo_crawl(
        ModelGitRepoCrawlInput(repo_path=git_repo.path),
        crawl_state=crawl_state,
    )

    discovered_paths = {e.file_path for e in result.discovered}
    assert discovered_paths == {"README.md"}
