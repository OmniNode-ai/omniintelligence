# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_linear_crawler_effect tests.

Provides:
  - InMemoryLinearStateStore: in-memory ProtocolLinearStateStore implementation
  - MockLinearClient: configurable mock implementing ProtocolLinearClient

Ticket: OMN-2388
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
    ModelLinearItemContent,
    ModelLinearItemSummary,
    ModelLinearStateEntry,
    ProtocolLinearClient,
    ProtocolLinearStateStore,
)

# ---------------------------------------------------------------------------
# In-memory state store
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Mock Linear client
# ---------------------------------------------------------------------------


class MockLinearClient:
    """Configurable mock implementation of ProtocolLinearClient.

    Callers configure what the client returns by setting:
      - ``issue_summaries``: returned by list_issues
      - ``doc_summaries``: returned by list_documents
      - ``issue_contents``: mapping from source_ref → ModelLinearItemContent
      - ``doc_contents``: mapping from source_ref → ModelLinearItemContent
      - ``list_issues_error``: if set, list_issues raises this error
      - ``list_docs_error``: if set, list_documents raises this error
      - ``fetch_errors``: mapping from source_ref → exception (get_issue/get_document)
    """

    def __init__(self) -> None:
        self.issue_summaries: list[ModelLinearItemSummary] = []
        self.doc_summaries: list[ModelLinearItemSummary] = []
        self.issue_contents: dict[str, ModelLinearItemContent] = {}
        self.doc_contents: dict[str, ModelLinearItemContent] = {}
        self.list_issues_error: Exception | None = None
        self.list_docs_error: Exception | None = None
        self.fetch_errors: dict[str, Exception] = {}

        # Introspection: track what was fetched
        self.fetched_issues: list[str] = []
        self.fetched_docs: list[str] = []

        assert isinstance(self, ProtocolLinearClient)

    async def list_issues(
        self,
        team_id: str,
        project_id: str | None = None,
    ) -> list[ModelLinearItemSummary]:
        if self.list_issues_error is not None:
            raise self.list_issues_error
        return list(self.issue_summaries)

    async def list_documents(
        self,
        team_id: str,
        project_id: str | None = None,
    ) -> list[ModelLinearItemSummary]:
        if self.list_docs_error is not None:
            raise self.list_docs_error
        return list(self.doc_summaries)

    async def get_issue(self, source_ref: str) -> ModelLinearItemContent:
        if source_ref in self.fetch_errors:
            raise self.fetch_errors[source_ref]
        self.fetched_issues.append(source_ref)
        if source_ref not in self.issue_contents:
            raise RuntimeError(f"No content configured for issue {source_ref}")
        return self.issue_contents[source_ref]

    async def get_document(self, source_ref: str) -> ModelLinearItemContent:
        if source_ref in self.fetch_errors:
            raise self.fetch_errors[source_ref]
        self.fetched_docs.append(source_ref)
        if source_ref not in self.doc_contents:
            raise RuntimeError(f"No content configured for document {source_ref}")
        return self.doc_contents[source_ref]

    def add_issue(
        self,
        source_ref: str,
        updated_at: str,
        markdown: str,
        project_id: str | None = None,
    ) -> None:
        """Helper to configure both summary and content for an issue."""
        self.issue_summaries.append(
            ModelLinearItemSummary(
                source_ref=source_ref,
                updated_at=updated_at,
                item_type="issue",
                project_id=project_id,
            )
        )
        self.issue_contents[source_ref] = ModelLinearItemContent(
            source_ref=source_ref,
            updated_at=updated_at,
            markdown=markdown,
            project_id=project_id,
        )

    def add_document(
        self,
        source_ref: str,
        updated_at: str,
        markdown: str,
        project_id: str | None = None,
    ) -> None:
        """Helper to configure both summary and content for a document."""
        self.doc_summaries.append(
            ModelLinearItemSummary(
                source_ref=source_ref,
                updated_at=updated_at,
                item_type="document",
                project_id=project_id,
            )
        )
        self.doc_contents[source_ref] = ModelLinearItemContent(
            source_ref=source_ref,
            updated_at=updated_at,
            markdown=markdown,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def linear_state() -> InMemoryLinearStateStore:
    """Fresh in-memory Linear state store."""
    return InMemoryLinearStateStore()


@pytest.fixture
def linear_client() -> MockLinearClient:
    """Fresh mock Linear client with no configured items."""
    return MockLinearClient()
