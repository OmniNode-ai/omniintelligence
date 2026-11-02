# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""File boundary of the retrieval eval node (OMN-16522, OMN-21945).

The node is pure: it is handed a parsed replay corpus and golden query set.
Reading the committed fixtures and writing the baseline scorecard happen here,
at the caller's boundary -- in the node's command line runtime and in tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from omniintelligence.code_projection.codec import parse_code_projection_batch
from omniintelligence.models.code_projection import artifact_ref_for
from omniintelligence.nodes.node_retrieval_eval_compute.baselines import (
    BASELINE_SCORECARD_PATH,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    DEFAULT_GOLDEN_SET_PATH,
    ModelGoldenQuerySet,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    DEFAULT_FIXTURE_ROOT,
    ModelReplayCorpus,
)


def load_replay_corpus(fixture_root: Path | None = None) -> ModelReplayCorpus:
    """Load every batch and sanitized artifact under ``fixture_root``."""

    root = DEFAULT_FIXTURE_ROOT if fixture_root is None else fixture_root
    batches = {
        path.name: parse_code_projection_batch(path.read_bytes())
        for path in sorted((root / "batches").glob("*.json"))
    }
    artifacts: dict[str, bytes] = {}
    for path in filter(Path.is_file, sorted((root / "sanitized").iterdir())):
        payload = path.read_bytes()
        artifacts[artifact_ref_for(hashlib.sha256(payload).hexdigest())] = payload
    return ModelReplayCorpus(
        fixture_root=root,
        batches=batches,
        artifacts=artifacts,
    )


def load_golden_query_set(path: Path | None = None) -> ModelGoldenQuerySet:
    """Load and validate the committed golden query set."""

    source = DEFAULT_GOLDEN_SET_PATH if path is None else path
    return ModelGoldenQuerySet.model_validate(
        json.loads(source.read_text(encoding="utf-8"))
    )


def write_baseline_scorecard(payload: bytes, path: Path | None = None) -> Path:
    """Write the canonical scorecard bytes to the committed baseline."""

    target = BASELINE_SCORECARD_PATH if path is None else path
    target.write_bytes(payload)
    return target


__all__ = [
    "load_golden_query_set",
    "load_replay_corpus",
    "write_baseline_scorecard",
]
