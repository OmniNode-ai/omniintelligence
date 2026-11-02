# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for NodeRetrievalEvalCompute (OMN-21945)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    ModelEvalResult,
)


class ModelRetrievalEvalOutput(BaseModel):
    """Result of one harness run.

    ``result`` carries the scorecard and the latency report when the harness
    ran; ``error`` carries the reason when it could not run.  ``passed`` is
    true only when the harness ran and every replay scenario passed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID
    passed: bool
    result: ModelEvalResult | None = None
    error: str | None = None


__all__ = ["ModelRetrievalEvalOutput"]
