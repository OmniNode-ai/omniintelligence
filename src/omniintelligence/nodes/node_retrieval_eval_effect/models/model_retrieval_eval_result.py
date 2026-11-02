# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed result of the retrieval eval handler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_retrieval_eval_effect.handlers.scorecard import (
    ModelLatencyReport,
    ModelScorecard,
)


class ModelRetrievalEvalResult(BaseModel):
    """The full harness output: the committed scorecard plus loose latency."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    scorecard: ModelScorecard
    latency: ModelLatencyReport


__all__ = ["ModelRetrievalEvalResult"]
