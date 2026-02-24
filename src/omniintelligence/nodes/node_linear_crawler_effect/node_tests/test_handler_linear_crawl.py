# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handle_linear_crawl.

Covers the requirements from OMN-2388:

Two-phase fetch:
  - skip full fetch when updatedAt is unchanged (cheap comparison)
  - fetch full content only when updatedAt changed

Content fingerprinting:
  - emit document.discovered.v1 for new Linear items
  - emit document.changed.v1 when content SHA-256 differs
  - no event (only state update) for metadata-only changes (hash unchanged)
  - emit document.removed.v1 for items absent from list response

source_version semantics:
  - source_version stores updatedAt ISO timestamp

State persistence:
  - linear_state updated after crawl
  - idempotent: re-processing same updatedAt emits nothing

Error handling:
  - list error returns early with error in output
  - per-item fetch error is recorded; other items continue

Scope mapping:
  - ModelLinearScopeConfig.resolve_scope returns correct scope

Ticket: OMN-2388
"""

from __future__ import annotations

import hashlib

import pytest

from omniintelligence.nodes.node_linear_crawler_effect.handlers.handler_linear_crawl import (
    handle_linear_crawl,
)
from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
    ModelLinearStateEntry,
)
from omniintelligence.nodes.node_linear_crawler_effect.models.model_linear_crawl_input import (
    ModelLinearCrawlInput,
)
from omniintelligence.nodes.node_linear_crawler_effect.models.model_linear_scope_config import (
    DEFAULT_SCOPE_CONFIG,
    ModelLinearScopeConfig,
    ModelLinearScopeMapping,
)
from omniintelligence.nodes.node_linear_crawler_effect.node_tests.conftest import (
    InMemoryLinearStateStore,
    MockLinearClient,
)

pytestmark = pytest.mark.unit

SCOPE = "omninode/test"
TEAM_ID = "omninode"


def _fp(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


# =============================================================================
# Document discovery
# =============================================================================


@pytest.mark.asyncio
async def test_new_issue_emits_discovered_event(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """A new Linear issue emits document.discovered.v1."""
    linear_client.add_issue("OMN-1", "2026-01-01T00:00:00Z", "# Ticket 1\n\nContent")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert len(result.discovered) == 1
    evt = result.discovered[0]
    assert evt.source_ref == "OMN-1"
    assert evt.event_type == "document.discovered.v1"
    assert evt.source_version == "2026-01-01T00:00:00Z"
    assert evt.crawl_scope == SCOPE
    assert evt.content_fingerprint == _fp("# Ticket 1\n\nContent")


@pytest.mark.asyncio
async def test_new_document_emits_discovered_event(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """A new Linear document emits document.discovered.v1."""
    linear_client.add_document("doc-abc", "2026-01-15T00:00:00Z", "# Design Doc")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert len(result.discovered) == 1
    evt = result.discovered[0]
    assert evt.source_ref == "doc-abc"
    assert evt.event_type == "document.discovered.v1"


# =============================================================================
# Two-phase fetch: cheap comparison
# =============================================================================


@pytest.mark.asyncio
async def test_unchanged_updated_at_skips_full_fetch(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """When updatedAt matches stored source_version, full fetch is skipped."""
    markdown = "# Ticket 1\n\nContent"
    updated_at = "2026-01-01T00:00:00Z"
    linear_client.add_issue("OMN-1", updated_at, markdown)

    # Pre-populate state with same updatedAt
    await linear_state.upsert_entry(
        ModelLinearStateEntry(
            crawl_scope=SCOPE,
            source_ref="OMN-1",
            source_version=updated_at,
            content_fingerprint=_fp(markdown),
        )
    )

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert result.skipped == 1
    assert result.discovered == []
    assert result.changed == []
    # Full fetch was NOT performed
    assert linear_client.fetched_issues == []


@pytest.mark.asyncio
async def test_changed_updated_at_triggers_full_fetch(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """When updatedAt differs from stored value, full fetch is performed."""
    old_updated_at = "2026-01-01T00:00:00Z"
    new_updated_at = "2026-01-02T00:00:00Z"
    old_markdown = "# Original"
    new_markdown = "# Updated content"

    linear_client.add_issue("OMN-1", new_updated_at, new_markdown)

    # State has the old updatedAt
    await linear_state.upsert_entry(
        ModelLinearStateEntry(
            crawl_scope=SCOPE,
            source_ref="OMN-1",
            source_version=old_updated_at,
            content_fingerprint=_fp(old_markdown),
        )
    )

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert len(result.changed) == 1
    evt = result.changed[0]
    assert evt.source_ref == "OMN-1"
    assert evt.event_type == "document.changed.v1"
    assert evt.source_version == new_updated_at
    assert evt.previous_source_version == old_updated_at
    assert evt.content_fingerprint == _fp(new_markdown)
    # Full fetch WAS performed
    assert "OMN-1" in linear_client.fetched_issues


# =============================================================================
# Metadata-only update (updatedAt changed, content unchanged)
# =============================================================================


@pytest.mark.asyncio
async def test_metadata_only_update_emits_no_event(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """When updatedAt changes but content hash is identical, no event is emitted."""
    markdown = "# Same content"
    old_updated_at = "2026-01-01T00:00:00Z"
    new_updated_at = "2026-01-02T00:00:00Z"  # Different timestamp, same content

    linear_client.add_issue("OMN-2", new_updated_at, markdown)

    await linear_state.upsert_entry(
        ModelLinearStateEntry(
            crawl_scope=SCOPE,
            source_ref="OMN-2",
            source_version=old_updated_at,
            content_fingerprint=_fp(markdown),
        )
    )

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert result.discovered == []
    assert result.changed == []
    # source_version updated in state (even though no event)
    entry = await linear_state.get_entry(SCOPE, "OMN-2")
    assert entry is not None
    assert entry.source_version == new_updated_at


# =============================================================================
# Removal detection
# =============================================================================


@pytest.mark.asyncio
async def test_removed_item_emits_removed_event(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """An item in linear_state but absent from list response emits document.removed.v1."""
    # State has OMN-3 but the client returns nothing
    await linear_state.upsert_entry(
        ModelLinearStateEntry(
            crawl_scope=SCOPE,
            source_ref="OMN-3",
            source_version="2026-01-01T00:00:00Z",
            content_fingerprint=_fp("# Gone"),
        )
    )

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert len(result.removed) == 1
    evt = result.removed[0]
    assert evt.source_ref == "OMN-3"
    assert evt.event_type == "document.removed.v1"
    assert evt.last_source_version == "2026-01-01T00:00:00Z"

    # Entry removed from state
    entry = await linear_state.get_entry(SCOPE, "OMN-3")
    assert entry is None


# =============================================================================
# State persistence
# =============================================================================


@pytest.mark.asyncio
async def test_state_persisted_after_discovery(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """After discovering a new item, state entry is created."""
    markdown = "# New Ticket"
    linear_client.add_issue("OMN-4", "2026-01-01T12:00:00Z", markdown)

    await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    entry = await linear_state.get_entry(SCOPE, "OMN-4")
    assert entry is not None
    assert entry.source_version == "2026-01-01T12:00:00Z"
    assert entry.content_fingerprint == _fp(markdown)


@pytest.mark.asyncio
async def test_idempotent_recrawl_with_same_updated_at(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """Re-crawling with the same updatedAt emits nothing and skips full fetch."""
    markdown = "# Stable"
    updated_at = "2026-01-01T00:00:00Z"
    linear_client.add_issue("OMN-5", updated_at, markdown)

    # First crawl
    first = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )
    assert len(first.discovered) == 1

    # Second crawl with same data
    second = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )
    assert second.discovered == []
    assert second.changed == []
    assert second.skipped == 1
    # Only fetched once (on the first crawl)
    assert linear_client.fetched_issues.count("OMN-5") == 1


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.asyncio
async def test_list_issues_error_returns_early(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """If list_issues raises, the handler returns early with an error."""
    linear_client.list_issues_error = RuntimeError("Linear API unavailable")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    assert result.discovered == []
    assert result.changed == []
    assert "__list_issues__" in result.errors


@pytest.mark.asyncio
async def test_per_item_fetch_error_continues_others(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """A fetch error on one item is recorded but other items are still processed."""
    linear_client.add_issue("OMN-FAIL", "2026-01-01T00:00:00Z", "never reached")
    linear_client.add_issue("OMN-OK", "2026-01-01T00:00:00Z", "# Works")
    linear_client.fetch_errors["OMN-FAIL"] = RuntimeError("rate limited")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    # OMN-FAIL is in errors
    assert "OMN-FAIL" in result.errors
    # OMN-OK was still processed
    discovered_refs = {e.source_ref for e in result.discovered}
    assert "OMN-OK" in discovered_refs


# =============================================================================
# Correlation ID propagation
# =============================================================================


@pytest.mark.asyncio
async def test_correlation_id_propagated_to_events(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """correlation_id from input is propagated to all emitted events."""
    linear_client.add_issue("OMN-6", "2026-01-01T00:00:00Z", "# Content")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(
            team_id=TEAM_ID,
            crawl_scope=SCOPE,
            correlation_id="test-corr-88",
        ),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    for evt in result.discovered:
        assert evt.correlation_id == "test-corr-88"


# =============================================================================
# Mixed issues and documents
# =============================================================================


@pytest.mark.asyncio
async def test_issues_and_documents_processed_together(
    linear_state: InMemoryLinearStateStore,
    linear_client: MockLinearClient,
) -> None:
    """Both issues and documents are discovered in the same crawl."""
    linear_client.add_issue("OMN-10", "2026-01-01T00:00:00Z", "# Issue 10")
    linear_client.add_document("doc-XYZ", "2026-01-01T00:00:00Z", "# Design Doc")

    result = await handle_linear_crawl(
        ModelLinearCrawlInput(team_id=TEAM_ID, crawl_scope=SCOPE),
        linear_state=linear_state,
        linear_client=linear_client,
    )

    discovered_refs = {e.source_ref for e in result.discovered}
    assert discovered_refs == {"OMN-10", "doc-XYZ"}


# =============================================================================
# ModelLinearScopeConfig tests
# =============================================================================


def test_scope_config_project_specific_match() -> None:
    """Project-specific mapping wins over team-level catch-all."""
    scope = DEFAULT_SCOPE_CONFIG.resolve_scope("omninode", "omniintelligence")
    assert scope == "omninode/omniintelligence"


def test_scope_config_team_level_fallback() -> None:
    """Team-level mapping matches when no project_id given."""
    scope = DEFAULT_SCOPE_CONFIG.resolve_scope("omninode", None)
    assert scope == "omninode/shared"


def test_scope_config_team_level_with_unmatched_project() -> None:
    """Team-level mapping matches when project_id doesn't match any specific mapping."""
    scope = DEFAULT_SCOPE_CONFIG.resolve_scope("omninode", "some-other-project")
    assert scope == "omninode/shared"


def test_scope_config_no_match() -> None:
    """Returns None when team_id doesn't match any mapping."""
    scope = DEFAULT_SCOPE_CONFIG.resolve_scope("unknown-team", None)
    assert scope is None


def test_scope_config_custom_mappings() -> None:
    """Custom ModelLinearScopeConfig resolves custom scopes."""
    config = ModelLinearScopeConfig(
        mappings=(
            ModelLinearScopeMapping(
                team_id="myteam",
                project_id="special",
                crawl_scope="myteam/special",
            ),
            ModelLinearScopeMapping(
                team_id="myteam",
                project_id=None,
                crawl_scope="myteam/general",
            ),
        )
    )
    assert config.resolve_scope("myteam", "special") == "myteam/special"
    assert config.resolve_scope("myteam", "other") == "myteam/general"
    assert config.resolve_scope("myteam", None) == "myteam/general"
    assert config.resolve_scope("other", None) is None
