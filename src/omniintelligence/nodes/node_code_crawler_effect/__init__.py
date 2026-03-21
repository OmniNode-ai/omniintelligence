# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""CodeCrawlerEffect node.

Scans configured repositories for Python source files using OnexTree
filesystem scanning and emits code-file-discovered.v1 events for each
discovered file. Repo configuration is YAML-driven via contract.yaml.

Key Components:
    - NodeCodeCrawlerEffect: Pure declarative effect node (thin shell)
    - OnexTreeGenerator: Filesystem scanner with include/exclude patterns
    - ModelCodeFileDiscoveredEvent: Wire event for discovered Python files
    - ModelOnextreeRoot: Root model for OnexTree representation
    - OnexTreeNode: Single node in the OnexTree hierarchy
    - ProjectStatistics: Aggregate statistics from a scan
    - handle_code_crawl: Main handler consuming contract config

Usage:
    from omniintelligence.nodes.node_code_crawler_effect import (
        NodeCodeCrawlerEffect,
        handle_code_crawl,
        ModelCodeFileDiscoveredEvent,
    )

Reference:
    - OMN-5658: Port OnexTree generator and models
    - OMN-5657: AST-based code pattern extraction (epic)
"""

from omniintelligence.nodes.node_code_crawler_effect.handlers import (
    OnexTreeGenerator,
    handle_code_crawl,
)
from omniintelligence.nodes.node_code_crawler_effect.models import (
    DEFAULT_EXCLUDE_PATTERNS,
    ModelCodeFileDiscoveredEvent,
    ModelOnextreeRoot,
    OnexTreeNode,
    ProjectStatistics,
)
from omniintelligence.nodes.node_code_crawler_effect.node import (
    NodeCodeCrawlerEffect,
)

__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "ModelCodeFileDiscoveredEvent",
    "ModelOnextreeRoot",
    "NodeCodeCrawlerEffect",
    "OnexTreeGenerator",
    "OnexTreeNode",
    "ProjectStatistics",
    "handle_code_crawl",
]
