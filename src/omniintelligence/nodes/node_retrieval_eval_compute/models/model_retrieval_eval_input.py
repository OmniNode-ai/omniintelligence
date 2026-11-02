# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelRetrievalEvalInput -- the request of the retrieval eval compute node."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    ModelGoldenQuerySet,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    ModelReplayCorpus,
)


class ModelRetrievalEvalInput(BaseModel):
    """The parsed replay corpus and golden query set the harness scores.

    The node does no file I/O: the caller loads both, for example with
    ``omniintelligence.handlers.retrieval_eval_fixtures``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    corpus: ModelReplayCorpus = Field(description="The frozen replay corpus.")
    golden: ModelGoldenQuerySet = Field(description="The judged golden query set.")


__all__ = ["ModelRetrievalEvalInput"]
