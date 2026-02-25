# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""GitRepoCrawlerEffect node.

Discovers and tracks .md document changes across git repositories using
HEAD SHA as a cheap repo-level fast-path before performing file-level
content-fingerprint diffing.

Key Components:
    - NodeGitRepoCrawlerEffect: Pure declarative effect node (thin shell)
    - ModelGitRepoCrawlInput: Crawl request from crawl-requested.v1
    - ModelDocumentDiscoveredEvent: New .md file found
    - ModelDocumentChangedEvent: .md file content changed
    - ModelDocumentRemovedEvent: .md file no longer in git tree
    - ModelGitRepoCrawlOutput: Aggregate crawl result
    - ProtocolCrawlStateStore: Interface for omnimemory_crawl_state persistence
    - ModelCrawlStateEntry: Single row from omnimemory_crawl_state

Change Detection Algorithm:
    1. HEAD SHA fast-path: skip repo if HEAD unchanged (O(1))
    2. git diff --name-only <old>..<new> filtered to *.md
    3. Per file: git log -1 --format=%H for file-level SHA + SHA-256(content)
    4. Emit document.removed.v1 for files in crawl_state but not in git tree
    5. Emit document.discovered.v1 for new files
    6. Update omnimemory_crawl_state

Usage:
    from omniintelligence.nodes.node_git_repo_crawler_effect import (
        NodeGitRepoCrawlerEffect,
        handle_git_repo_crawl,
        ModelGitRepoCrawlInput,
    )

Reference:
    - OMN-2387: GitRepoCrawlerEffect implementation
"""

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers import (
    ModelCrawlStateEntry,
    ProtocolCrawlStateStore,
    handle_git_repo_crawl,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.models import (
    ModelDocumentChangedEvent,
    ModelDocumentDiscoveredEvent,
    ModelDocumentRemovedEvent,
    ModelGitRepoCrawlInput,
    ModelGitRepoCrawlOutput,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.node import (
    NodeGitRepoCrawlerEffect,
)

__all__ = [
    "ModelCrawlStateEntry",
    "ModelDocumentChangedEvent",
    "ModelDocumentDiscoveredEvent",
    "ModelDocumentRemovedEvent",
    "ModelGitRepoCrawlInput",
    "ModelGitRepoCrawlOutput",
    "NodeGitRepoCrawlerEffect",
    "ProtocolCrawlStateStore",
    "handle_git_repo_crawl",
]
