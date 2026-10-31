# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""In-memory ProtocolCrawlStateStore for the node_git_repo_crawler_effect tests.

The in-memory implementation is built here, the one binding site, and the test
fixtures resolve it through ``default_crawl_state_store`` instead of constructing it (OMN-21680).
"""

from __future__ import annotations

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
    ModelCrawlStateEntry,
    ProtocolCrawlStateStore,
)


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


def default_crawl_state_store() -> InMemoryCrawlStateStore:
    """Resolve the default InMemoryCrawlStateStore the node tests run against."""
    return InMemoryCrawlStateStore()
