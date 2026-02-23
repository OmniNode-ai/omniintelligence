# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_git_repo_crawler_effect tests.

Provides:
  - InMemoryCrawlStateStore: in-memory ProtocolCrawlStateStore implementation
  - GitFixture: helper that creates a real git repo on disk using subprocess
  - Pytest fixtures wrapping the above

Ticket: OMN-2387
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
    ModelCrawlStateEntry,
    ProtocolCrawlStateStore,
)

# ---------------------------------------------------------------------------
# In-memory crawl state store
# ---------------------------------------------------------------------------


class InMemoryCrawlStateStore:
    """Thread-safe in-memory implementation of ProtocolCrawlStateStore.

    Used exclusively in tests. No external dependencies required.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ModelCrawlStateEntry] = {}
        self._head_shas: dict[str, str] = {}
        assert isinstance(self, ProtocolCrawlStateStore)

    async def get_head_sha(self, repo_path: str) -> str | None:
        return self._head_shas.get(repo_path)

    async def get_all_entries(self, repo_path: str) -> list[ModelCrawlStateEntry]:
        return [entry for (rp, _fp), entry in self._entries.items() if rp == repo_path]

    async def get_entry(
        self, repo_path: str, file_path: str
    ) -> ModelCrawlStateEntry | None:
        return self._entries.get((repo_path, file_path))

    async def upsert_entry(self, entry: ModelCrawlStateEntry) -> None:
        self._entries[(entry.repo_path, entry.file_path)] = entry

    async def delete_entry(self, repo_path: str, file_path: str) -> None:
        self._entries.pop((repo_path, file_path), None)

    async def update_head_sha(self, repo_path: str, head_sha: str) -> None:
        self._head_shas[repo_path] = head_sha

    # --- Helpers for test assertions ---

    def entry_count(self, repo_path: str) -> int:
        return sum(1 for (rp, _) in self._entries if rp == repo_path)


# ---------------------------------------------------------------------------
# Minimal git repo fixture helper
# ---------------------------------------------------------------------------


def _run(args: list[str], cwd: str) -> str:
    """Run a command, raise RuntimeError on failure, return stdout."""
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": "/tmp",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


class GitFixture:
    """Creates and manages a minimal git repository for tests.

    Usage:
        fixture = GitFixture()
        fixture.init()
        fixture.write("docs/README.md", "# Hello")
        fixture.commit("add README")
        sha = fixture.head_sha()
        ...
        fixture.cleanup()
    """

    def __init__(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self.path = self._tmpdir

    def init(self) -> None:
        _run(["git", "init"], cwd=self.path)
        _run(["git", "config", "user.email", "test@test.com"], cwd=self.path)
        _run(["git", "config", "user.name", "Test"], cwd=self.path)

    def write(self, rel_path: str, content: str) -> str:
        """Write a file to the repo and return its SHA-256."""
        full = Path(self.path) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()

    def delete(self, rel_path: str) -> None:
        full = Path(self.path) / rel_path
        full.unlink(missing_ok=True)

    def add_all(self) -> None:
        _run(["git", "add", "-A"], cwd=self.path)

    def commit(self, message: str = "test commit") -> str:
        """Commit all staged changes and return the new HEAD SHA."""
        _run(["git", "add", "-A"], cwd=self.path)
        _run(["git", "commit", "-m", message], cwd=self.path)
        return self.head_sha()

    def head_sha(self) -> str:
        return _run(["git", "rev-parse", "HEAD"], cwd=self.path)

    def file_commit_sha(self, rel_path: str) -> str:
        return _run(
            ["git", "log", "-1", "--format=%H", "--", rel_path],
            cwd=self.path,
        )

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def crawl_state() -> InMemoryCrawlStateStore:
    """Fresh in-memory crawl state store."""
    return InMemoryCrawlStateStore()


@pytest.fixture
def git_repo() -> Generator[GitFixture, None, None]:
    """Initialised git repository in a temp directory."""
    fixture = GitFixture()
    fixture.init()
    yield fixture
    fixture.cleanup()
