"""Pattern Extraction Compute Node.

This node extracts codebase patterns and insights from session snapshots.
It analyzes file access patterns, error patterns, architecture patterns,
and tool usage patterns to build a knowledge base for intelligent assistance.

The node is a pure compute node - it performs deterministic computation
without external I/O or side effects.
"""

from omniintelligence.nodes.pattern_extraction_compute.node import (
    NodePatternExtractionCompute,
)

__all__ = ["NodePatternExtractionCompute"]
