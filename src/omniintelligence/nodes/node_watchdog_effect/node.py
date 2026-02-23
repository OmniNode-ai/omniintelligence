# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Watchdog Effect — real-time filesystem watcher for unversioned critical files.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic — all behavior from handler_routing
    - Lightweight shell that delegates to handlers via direct invocation
    - Pattern: "Contract-driven, handlers wired externally"

Responsibilities:
    - Start FSEvents/inotify/polling observer on configured paths (~/.claude/)
    - Emit {env}.onex.cmd.omnimemory.crawl-requested.v1 on file change
    - Do NOT emit document events directly (delegates to FilesystemCrawlerEffect)
    - Gracefully fall back to polling if native OS API is unavailable

Design:
    omni_save/design/DESIGN_OMNIMEMORY_DOCUMENT_INGESTION_PIPELINE.md §4

Related Tickets:
    - OMN-2386: WatchdogEffect FSEvents/inotify real-time file watching
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeWatchdogEffect(NodeEffect):
    """Declarative effect node for real-time filesystem watching.

    This effect node is a lightweight shell that defines the I/O contract
    for OS-level filesystem change detection.  All routing and execution
    logic is driven by contract.yaml — this class contains NO custom routing
    code.

    Supported Operations (defined in contract.yaml handler_routing):
        - start_watching: Start the OS-level observer for configured paths
        - stop_watching: Gracefully stop the active observer

    Platform Support:
        - macOS: FSEventsObserver (native, via watchdog library)
        - Linux: InotifyObserver (native, via watchdog library)
        - Fallback: PollingObserver (5-second interval)

    Watched Paths (default, configurable):
        - ~/.claude/ (global standards, CLAUDE.md, memory files, plugin configs)

    Dependency Injection:
        Handlers receive dependencies directly via parameters (kafka_publisher,
        config, observer_factory).  This node contains NO instance variables
        for handlers or dependencies.

    Example:
        ```python
        from uuid import uuid4

        from omniintelligence.nodes.node_watchdog_effect.handlers import (
            start_watching,
        )
        from omniintelligence.nodes.node_watchdog_effect.models import (
            EnumWatchdogStatus,
            ModelWatchdogConfig,
        )

        result = await start_watching(
            config=ModelWatchdogConfig(),
            correlation_id=uuid4(),
            kafka_publisher=producer,
        )

        if result.status == EnumWatchdogStatus.STARTED:
            print(f"Observer started: {result.observer_type}")
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeWatchdogEffect"]
