# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""handle_retrieval_eval -- the handler the retrieval eval contract binds."""

from __future__ import annotations

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    load_golden_query_set,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    load_replay_corpus,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    ModelEvalResult,
    run_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


async def handle_retrieval_eval(request: ModelRetrievalEvalInput) -> ModelEvalResult:
    """Run the offline harness over the requested fixtures and golden set."""

    return await run_eval(
        corpus=load_replay_corpus(request.fixture_root),
        golden=load_golden_query_set(request.golden_set_path),
    )


__all__ = ["handle_retrieval_eval"]
