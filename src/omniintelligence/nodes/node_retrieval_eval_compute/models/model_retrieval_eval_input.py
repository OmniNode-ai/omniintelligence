# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the retrieval eval compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    ModelGoldenQuerySet,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    ModelReplayCorpus,
)


class ModelRetrievalEvalInput(BaseModel):
    """What one harness run evaluates.

    Both fields default to the committed artifacts: the frozen replay fixtures
    and the judged golden query set shipped beside the node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    corpus: ModelReplayCorpus | None = None
    golden: ModelGoldenQuerySet | None = None


__all__ = ["ModelRetrievalEvalInput"]
