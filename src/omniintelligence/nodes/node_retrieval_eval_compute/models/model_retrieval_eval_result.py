# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output of the retrieval eval compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.scorecard import (
    ModelLatencyReport,
    ModelScorecard,
)


class ModelEvalResult(BaseModel):
    """The full harness output: the committed scorecard plus loose latency."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    scorecard: ModelScorecard
    latency: ModelLatencyReport


__all__ = ["ModelEvalResult"]
