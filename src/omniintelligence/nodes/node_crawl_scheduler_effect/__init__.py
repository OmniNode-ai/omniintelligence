"""CrawlSchedulerEffect — periodic crawl trigger coordinator for Stream A.

Emits crawl-tick.v1 commands and enforces per-source debounce windows
to prevent phantom duplication in the document ingestion pipeline.

Reference: OMN-2384
"""

from omniintelligence.nodes.node_crawl_scheduler_effect.node import (
    NodeCrawlSchedulerEffect,
)

__all__ = ["NodeCrawlSchedulerEffect"]
