# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node CodeCrawlerEffect -- filesystem-based Python source file discovery.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic -- all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.

Responsibilities:
    - Consume code-crawl-requested.v1 events from Kafka
    - Scan configured repositories for Python source files using OnexTree
    - Emit code-file-discovered.v1 for each discovered .py file
    - Repo list is YAML-driven: adding a repo = adding a contract entry

Design Decisions:
    - Uses OnexTree generator for recursive filesystem scanning
    - Include/exclude patterns are per-repo in contract.yaml
    - file_hash = SHA-256 of file content for change detection

Related:
    - OMN-5658: Port OnexTree generator and models into omniintelligence
    - OMN-5657: AST-based code pattern extraction system (epic)
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeCodeCrawlerEffect(NodeEffect):
    """Declarative effect node for filesystem-based code file discovery.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - crawl_repos: Scan configured repos and emit code-file-discovered.v1

    Example:
        ```python
        from omniintelligence.nodes.node_code_crawler_effect import (
            NodeCodeCrawlerEffect,
            handle_code_crawl,
        )

        events = await handle_code_crawl(repos_config=contract_repos)
        ```
    """

    # Pure declarative shell -- all behavior defined in contract.yaml


__all__ = ["NodeCodeCrawlerEffect"]
