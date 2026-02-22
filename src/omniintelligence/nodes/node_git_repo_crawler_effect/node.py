# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node GitRepoCrawlerEffect — git-based document change detection.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic — all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.

Responsibilities:
    - Consume crawl-requested.v1 events from Kafka
    - Detect .md file changes using git HEAD SHA fast-path + file-level diffing
    - Emit document.discovered.v1, document.changed.v1, document.removed.v1
    - Update omnimemory_crawl_state after each successful crawl

Design Decisions:
    - ``source_version`` = file-level commit SHA (not HEAD)
      A file unchanged in N commits will not re-emit after HEAD advances N times.
    - HEAD SHA fast-path: if HEAD is unchanged vs stored, skip the entire repo.
    - Full file walk via ``git ls-files`` on first crawl or diff fallback.

Related:
    - OMN-2387: This node implementation
    - OMN-2388: LinearCrawlerEffect (companion node, Linear ticket discovery)
    - DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §5
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeGitRepoCrawlerEffect(NodeEffect):  # type: ignore[misc]
    """Declarative effect node for git-based document change detection.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - crawl_repo: Detect .md file changes and emit document lifecycle events

    Dependency Injection:
        The ``handle_git_repo_crawl`` handler accepts a ``ProtocolCrawlStateStore``
        instance. This is resolved by the caller or RuntimeHostProcess.

    Example:
        ```python
        from omniintelligence.nodes.node_git_repo_crawler_effect import (
            NodeGitRepoCrawlerEffect,
            handle_git_repo_crawl,
        )

        result = await handle_git_repo_crawl(
            ModelGitRepoCrawlInput(repo_path="/path/to/repo"),
            crawl_state=my_crawl_state_store,
        )
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeGitRepoCrawlerEffect"]
