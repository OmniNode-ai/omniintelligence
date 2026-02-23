# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Crawl Scheduler Effect - Periodic crawl trigger coordinator for Stream A.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via direct invocation
    - Pattern: "Contract-driven, handlers wired externally"

Responsibilities:
    - Emit {env}.onex.cmd.omnimemory.crawl-tick.v1 on RuntimeScheduler tick
    - Accept manual trigger via {env}.onex.cmd.omnimemory.crawl-requested.v1
    - Enforce per-source debounce windows (configurable, not hardcoded)
    - Drop subsequent triggers for same source_ref within window silently
    - Reset debounce window after document-indexed.v1 confirms completion

Design:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Related Tickets:
    - OMN-2384: CrawlSchedulerEffect implementation
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeCrawlSchedulerEffect(NodeEffect):
    """Declarative effect node for coordinating periodic crawl triggers.

    This effect node is a lightweight shell that defines the I/O contract
    for crawl scheduling.  All routing and execution logic is driven by
    contract.yaml — this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - schedule_crawl_tick: Emit crawl-tick.v1 on scheduler tick
        - handle_crawl_requested: Process manual trigger from crawl-requested.v1
        - handle_document_indexed: Reset debounce window on indexed confirmation

    Debounce Guard:
        Maintained in-memory via ``DebounceStateManager``.  Per-source windows:
          - FilesystemCrawler: 30 seconds
          - GitRepoCrawler:    5 minutes
          - LinearCrawler:     60 minutes
          - WatchdogCrawler:   30 seconds (same as filesystem)

    Dependency Injection:
        Handlers receive dependencies directly via parameters (kafka_publisher,
        debounce_state, config).  This node contains NO instance variables
        for handlers or dependencies.

    Example:
        ```python
        from omniintelligence.nodes.node_crawl_scheduler_effect.handlers import (
            schedule_crawl_tick,
        )
        from omniintelligence.nodes.node_crawl_scheduler_effect.models import (
            CrawlerType,
            ModelCrawlSchedulerConfig,
        )

        result = await schedule_crawl_tick(
            crawl_type=CrawlerType.FILESYSTEM,
            crawl_scope="omninode/omniintelligence",
            source_ref="/Volumes/PRO-G40/Code/omniintelligence",
            debounce_state=debounce_manager,
            config=ModelCrawlSchedulerConfig(),
            kafka_publisher=producer,
        )

        if result.status == EnumCrawlSchedulerStatus.EMITTED:
            print(f"Crawl tick emitted for {result.source_ref}")
        elif result.status == EnumCrawlSchedulerStatus.DEBOUNCED:
            print(f"Trigger dropped (window={result.debounce_window_seconds}s)")
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeCrawlSchedulerEffect"]
