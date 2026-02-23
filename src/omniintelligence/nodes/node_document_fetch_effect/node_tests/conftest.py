# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_document_fetch_effect tests.

Provides:
  - InMemoryBlobStore: in-memory ProtocolBlobStore implementation
  - GitRepoFixture: minimal git repo for testing GIT_REPO fetch path

Ticket: OMN-2389
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from omniintelligence.nodes.node_document_fetch_effect.handlers.protocol_blob_store import (
    ProtocolBlobStore,
)


class InMemoryBlobStore:
    """In-memory blob store for testing the LINEAR fetch path."""

    def __init__(self) -> None:
        self._blobs: dict[str, str] = {}
        assert isinstance(self, ProtocolBlobStore)

    def put(self, source_ref: str, content: str) -> None:
        """Store content by source_ref."""
        self._blobs[source_ref] = content

    async def get(self, source_ref: str) -> str:
        if source_ref not in self._blobs:
            raise KeyError(f"Blob not found: {source_ref}")
        return self._blobs[source_ref]


class GitRepoFixture:
    """Minimal real git repository for testing GIT_REPO fetch path."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self.path = self._tmpdir

    def init(self) -> None:
        env = {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": "/tmp",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        }
        subprocess.run(["git", "init"], cwd=self.path, capture_output=True, env=env)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.path,
            capture_output=True,
            env=env,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.path,
            capture_output=True,
            env=env,
        )

    def write(self, rel_path: str, content: str) -> None:
        """Write a file to the repo."""
        full = Path(self.path) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def commit(self, message: str = "test") -> None:
        env = {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": "/tmp",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        }
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.path,
            capture_output=True,
            env=env,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.path,
            capture_output=True,
            env=env,
        )

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)


@pytest.fixture
def blob_store() -> InMemoryBlobStore:
    """Fresh in-memory blob store."""
    return InMemoryBlobStore()


@pytest.fixture
def git_repo() -> Generator[GitRepoFixture, None, None]:
    """Initialised git repository in a temp directory."""
    fixture = GitRepoFixture()
    fixture.init()
    yield fixture
    fixture.cleanup()
