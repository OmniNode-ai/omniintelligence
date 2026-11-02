# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Offline retrieval-quality eval harness for code-intelligence context packs.

Runs entirely from the frozen replay fixtures: no live Postgres, Memgraph, or
Qdrant, no network, and no model calls, so CI and a laptop produce the same
bytes.
"""

from __future__ import annotations

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.handler_retrieval_eval import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    DEFAULT_FIXTURE_ROOT,
    HARNESS_EMBEDDING_MODEL,
    HARNESS_EMBEDDING_MODEL_VERSION,
    REPLAY_LANES,
    DeterministicEmbedder,
    IndexedMemoryQdrant,
    ModelReplayCorpus,
    ModelReplayLane,
    ModelStageLatencySample,
    ProtocolTimedEmbedder,
    ReplayGenerationResolver,
    ReplayState,
    open_replay_state,
)

__all__ = [
    "DEFAULT_FIXTURE_ROOT",
    "HARNESS_EMBEDDING_MODEL",
    "HARNESS_EMBEDDING_MODEL_VERSION",
    "REPLAY_LANES",
    "DeterministicEmbedder",
    "IndexedMemoryQdrant",
    "ModelReplayCorpus",
    "ModelStageLatencySample",
    "ProtocolTimedEmbedder",
    "ModelReplayLane",
    "ReplayGenerationResolver",
    "ReplayState",
    "handle_retrieval_eval",
    "open_replay_state",
]
