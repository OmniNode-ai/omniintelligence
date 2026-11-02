# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for the retrieval eval compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    ModelGoldenQuerySet,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    ModelReplayCorpus,
)


class ModelRetrievalEvalInput(BaseModel):
    """What to evaluate: a replay corpus and a golden query set.

    Either field left None resolves to the committed fixture: the frozen
    replay corpus under tests/fixtures/code_projection/v2 and the golden
    set under this node's baselines/.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    corpus: ModelReplayCorpus | None = Field(
        default=None,
        description="Replay corpus to evaluate; None loads the committed fixtures.",
    )
    golden: ModelGoldenQuerySet | None = Field(
        default=None,
        description="Golden query set to score; None loads the committed set.",
    )


__all__ = ["ModelRetrievalEvalInput"]
