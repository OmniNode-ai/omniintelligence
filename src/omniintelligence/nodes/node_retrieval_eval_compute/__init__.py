# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Offline retrieval-quality eval harness for code-intelligence context packs.

COMPUTE node: ``handle(ModelRetrievalEvalRequest) -> ModelEvalResult`` runs the
R1-R6 replay scenarios and the golden query set and returns the scorecard plus
the latency report. ``runtime_retrieval_eval`` is the node's command line.

Runs entirely from the frozen replay fixtures: no live Postgres, Memgraph, or
Qdrant, no network, and no model calls, so CI and a laptop produce the same
bytes.
"""
