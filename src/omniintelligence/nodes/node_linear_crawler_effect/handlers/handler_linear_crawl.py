# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for LinearCrawlerEffect — Linear ticket and document ingestion.

Two-phase fetch algorithm (from OMN-2388 design doc §5):

  Phase 1 (cheap list):
    1. List all issues for the team/project: returns id + updatedAt only.
    2. Compare updatedAt to stored source_version in linear_state.
       If unchanged: skip (no full fetch). Mark as seen.
  Phase 2 (expensive full fetch, only for changed items):
    3. Fetch full content (title + description + state + labels).
    4. Compute SHA-256(formatted_markdown).
       If hash unchanged (metadata-only update):
         → Update source_version in state. No event.
       If hash differs:
         → Emit document.changed.v1. Update state.
    5. Items in state but absent from list: emit document.removed.v1.
    6. Items not in state: emit document.discovered.v1.

Rate limiting: Linear API rate limits full fetches. The cheap list phase
skips 95%+ of issues on steady-state crawls.

Ticket: OMN-2388
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
        ProtocolLinearClient,
        ProtocolLinearStateStore,
    )

from omniintelligence.nodes.node_linear_crawler_effect.handlers.protocol_linear_state import (
    ModelLinearStateEntry,
)
from omniintelligence.nodes.node_linear_crawler_effect.models.model_linear_crawl_input import (
    ModelLinearCrawlInput,
)
from omniintelligence.nodes.node_linear_crawler_effect.models.model_linear_crawl_output import (
    ModelDocumentChangedEvent,
    ModelDocumentDiscoveredEvent,
    ModelDocumentRemovedEvent,
    ModelLinearCrawlOutput,
)

logger = logging.getLogger(__name__)


def _sha256_of_content(content: str) -> str:
    """Return the SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def handle_linear_crawl(
    input_data: ModelLinearCrawlInput,
    *,
    linear_state: ProtocolLinearStateStore,
    linear_client: ProtocolLinearClient,
) -> ModelLinearCrawlOutput:
    """Perform two-phase Linear crawl for a single team/project.

    Steps:
        1. List all issues via the cheap API (id + updatedAt only).
        2. For each issue, compare updatedAt to stored source_version.
           If unchanged: skip (no full fetch).
        3. For items whose updatedAt changed: fetch full content.
           Compute SHA-256 and compare to stored content_fingerprint.
           If content unchanged: update source_version only (no event).
           If content changed and item was in state: emit changed.
           If item not in state: emit discovered.
        4. Items in state but not in list: emit removed.
        5. Persist updated state entries.

    Args:
        input_data: Crawl request with team_id, crawl_scope, optional project_id.
        linear_state: Persistence interface for omnimemory_linear_state.
        linear_client: Abstraction over the Linear MCP API.

    Returns:
        ModelLinearCrawlOutput with discovered/changed/removed counts
        and per-ref error messages.
    """
    team_id = input_data.team_id
    crawl_scope = input_data.crawl_scope
    project_id = input_data.project_id
    correlation_id = input_data.correlation_id

    # ------------------------------------------------------------------
    # Step 1 — cheap list phase (issues)
    # ------------------------------------------------------------------
    try:
        issue_summaries = await linear_client.list_issues(
            team_id=team_id,
            project_id=project_id,
        )
    except Exception as exc:
        logger.error(
            "list_issues failed for team=%s project=%s: %s",
            team_id,
            project_id,
            exc,
        )
        return ModelLinearCrawlOutput(
            team_id=team_id,
            crawl_scope=crawl_scope,
            errors={"__list_issues__": str(exc)},
        )

    try:
        doc_summaries = await linear_client.list_documents(
            team_id=team_id,
            project_id=project_id,
        )
    except Exception as exc:
        logger.error(
            "list_documents failed for team=%s project=%s: %s",
            team_id,
            project_id,
            exc,
        )
        return ModelLinearCrawlOutput(
            team_id=team_id,
            crawl_scope=crawl_scope,
            errors={"__list_documents__": str(exc)},
        )

    # Combine both lists; track all source_refs seen in this crawl
    all_summaries = issue_summaries + doc_summaries
    seen_refs: set[str] = {s.source_ref for s in all_summaries}

    # ------------------------------------------------------------------
    # Step 2 — load current state
    # ------------------------------------------------------------------
    existing_entries: dict[str, ModelLinearStateEntry] = {
        entry.source_ref: entry
        for entry in await linear_state.get_all_entries(crawl_scope)
    }

    discovered: list[ModelDocumentDiscoveredEvent] = []
    changed: list[ModelDocumentChangedEvent] = []
    errors: dict[str, str] = {}
    skipped = 0

    # ------------------------------------------------------------------
    # Step 3 — process each item (two-phase)
    # ------------------------------------------------------------------
    for summary in all_summaries:
        source_ref = summary.source_ref
        new_updated_at = summary.updated_at
        existing = existing_entries.get(source_ref)

        # Cheap comparison: skip if updatedAt matches stored source_version
        if existing is not None and existing.source_version == new_updated_at:
            skipped += 1
            continue

        # updatedAt changed (or first time) — fetch full content
        try:
            if summary.item_type == "document":
                content = await linear_client.get_document(source_ref)
            else:
                content = await linear_client.get_issue(source_ref)
        except Exception as exc:
            errors[source_ref] = str(exc)
            logger.warning(
                "Failed to fetch %s %s: %s",
                summary.item_type,
                source_ref,
                exc,
            )
            continue

        new_fingerprint = _sha256_of_content(content.markdown)

        if existing is None:
            # New item — emit discovered
            discovered.append(
                ModelDocumentDiscoveredEvent(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    source_version=new_updated_at,
                    content_fingerprint=new_fingerprint,
                    correlation_id=correlation_id,
                )
            )
            await linear_state.upsert_entry(
                ModelLinearStateEntry(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    source_version=new_updated_at,
                    content_fingerprint=new_fingerprint,
                )
            )
        elif new_fingerprint != existing.content_fingerprint:
            # Content changed — emit changed
            changed.append(
                ModelDocumentChangedEvent(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    source_version=new_updated_at,
                    previous_source_version=existing.source_version,
                    content_fingerprint=new_fingerprint,
                    correlation_id=correlation_id,
                )
            )
            await linear_state.upsert_entry(
                ModelLinearStateEntry(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    source_version=new_updated_at,
                    content_fingerprint=new_fingerprint,
                )
            )
        else:
            # Content unchanged — metadata-only update; update source_version only
            await linear_state.upsert_entry(
                ModelLinearStateEntry(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    source_version=new_updated_at,
                    content_fingerprint=existing.content_fingerprint,
                )
            )
            skipped += 1
            logger.debug(
                "Metadata-only update for %s %s (updatedAt changed, content unchanged)",
                summary.item_type,
                source_ref,
            )

    # ------------------------------------------------------------------
    # Step 4 — detect removed items
    # ------------------------------------------------------------------
    removed: list[ModelDocumentRemovedEvent] = []

    for source_ref, entry in existing_entries.items():
        if source_ref not in seen_refs:
            removed.append(
                ModelDocumentRemovedEvent(
                    crawl_scope=crawl_scope,
                    source_ref=source_ref,
                    last_source_version=entry.source_version,
                    correlation_id=correlation_id,
                )
            )
            await linear_state.delete_entry(crawl_scope, source_ref)

    logger.info(
        "Linear crawl complete for team=%s scope=%s: "
        "discovered=%d changed=%d removed=%d skipped=%d errors=%d",
        team_id,
        crawl_scope,
        len(discovered),
        len(changed),
        len(removed),
        skipped,
        len(errors),
    )

    return ModelLinearCrawlOutput(
        team_id=team_id,
        crawl_scope=crawl_scope,
        discovered=discovered,
        changed=changed,
        removed=removed,
        skipped=skipped,
        errors=errors,
    )


__all__ = ["handle_linear_crawl"]
