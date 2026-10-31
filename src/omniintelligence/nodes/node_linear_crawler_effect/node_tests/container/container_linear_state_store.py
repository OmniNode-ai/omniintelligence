# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""In-memory ProtocolLinearStateStore for the node_linear_crawler_effect tests.

The in-memory implementation is built here, the one binding site, and the test
fixtures resolve it through ``default_linear_state_store`` instead of constructing it (OMN-21680).
"""

from __future__ import annotations

from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
    ModelLinearStateEntry,
    ProtocolLinearStateStore,
)


class InMemoryLinearStateStore:
    """Thread-safe in-memory implementation of ProtocolLinearStateStore.

    Used exclusively in tests. No external dependencies required.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ModelLinearStateEntry] = {}
        assert isinstance(self, ProtocolLinearStateStore)

    async def get_all_entries(self, crawl_scope: str) -> list[ModelLinearStateEntry]:
        return [
            entry
            for (scope, _ref), entry in self._entries.items()
            if scope == crawl_scope
        ]

    async def get_entry(
        self, crawl_scope: str, source_ref: str
    ) -> ModelLinearStateEntry | None:
        return self._entries.get((crawl_scope, source_ref))

    async def upsert_entry(self, entry: ModelLinearStateEntry) -> None:
        self._entries[(entry.crawl_scope, entry.source_ref)] = entry

    async def delete_entry(self, crawl_scope: str, source_ref: str) -> None:
        self._entries.pop((crawl_scope, source_ref), None)

    # --- Test helpers ---

    def entry_count(self, crawl_scope: str) -> int:
        return sum(1 for (scope, _) in self._entries if scope == crawl_scope)


def default_linear_state_store() -> InMemoryLinearStateStore:
    """Resolve the default InMemoryLinearStateStore the node tests run against."""
    return InMemoryLinearStateStore()
