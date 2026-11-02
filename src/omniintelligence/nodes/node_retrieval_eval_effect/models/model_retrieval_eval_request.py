# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed request of the retrieval eval handler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_retrieval_eval_effect.handlers.golden import (
    ModelGoldenQuerySet,
)
from omniintelligence.nodes.node_retrieval_eval_effect.handlers.replay import (
    ModelReplayCorpus,
)


class ModelRetrievalEvalRequest(BaseModel):
    """What the harness runs over; None loads the committed default."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    corpus: ModelReplayCorpus | None = None
    golden: ModelGoldenQuerySet | None = None


__all__ = ["ModelRetrievalEvalRequest"]
