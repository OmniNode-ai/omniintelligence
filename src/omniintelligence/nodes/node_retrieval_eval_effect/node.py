# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Retrieval Eval Effect Node - declarative shell.

Runs the offline retrieval-quality eval harness (OMN-16522): it reads the
frozen code projection replay fixtures and the committed golden query set,
replays the scenarios and returns the scorecard plus the latency report.
It is an effect node because reading those files is I/O; all behavior lives
in the handler that contract.yaml binds.
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeRetrievalEvalEffect(NodeEffect):
    """Declarative effect node for the offline retrieval eval harness."""

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeRetrievalEvalEffect"]
