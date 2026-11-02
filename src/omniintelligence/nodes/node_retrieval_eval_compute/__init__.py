# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Offline retrieval-quality eval for code-intelligence context packs.

Runs entirely from the frozen replay fixtures: no live Postgres, Memgraph or
Qdrant, no network and no model calls, so CI and a laptop produce the same
bytes.
"""

from omniintelligence.nodes.node_retrieval_eval_compute.node import (
    NodeRetrievalEvalCompute,
)

__all__ = ["NodeRetrievalEvalCompute"]
