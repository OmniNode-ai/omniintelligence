# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""handle_retrieval_eval -- the handler the retrieval eval contract binds."""

from __future__ import annotations

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    ModelEvalResult,
    run_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


async def handle_retrieval_eval(request: ModelRetrievalEvalInput) -> ModelEvalResult:
    """Run the offline harness over the requested corpus and golden set."""

    return await run_eval(corpus=request.corpus, golden=request.golden)


__all__ = ["handle_retrieval_eval"]
