# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Entry handler of NodeRetrievalEvalCompute (OMN-21945).

Runs the offline retrieval eval harness and returns the scorecard as data.  A
harness that cannot run (missing or malformed fixtures or golden set) is a
structured error in the output, never a raised exception.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.golden import (
    load_golden_query_set,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.replay import (
    load_replay_corpus,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    run_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models.model_retrieval_eval_input import (
    ModelRetrievalEvalInput,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models.model_retrieval_eval_output import (
    ModelRetrievalEvalOutput,
)

logger = logging.getLogger(__name__)


async def handle_retrieval_eval(
    request: ModelRetrievalEvalInput,
) -> ModelRetrievalEvalOutput:
    """Run the harness for ``request`` and return its scorecard."""

    try:
        corpus = load_replay_corpus(request.fixture_root)
        golden = load_golden_query_set(request.golden_set_path)
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning(
            "retrieval eval inputs could not be loaded: %s",
            exc,
            extra={"correlation_id": str(request.correlation_id)},
        )
        return ModelRetrievalEvalOutput(
            correlation_id=request.correlation_id,
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    result = await run_eval(corpus=corpus, golden=golden)
    passed = all(scenario.passed for scenario in result.scorecard.scenarios)
    logger.info(
        "retrieval eval finished: passed=%s",
        passed,
        extra={"correlation_id": str(request.correlation_id)},
    )
    return ModelRetrievalEvalOutput(
        correlation_id=request.correlation_id,
        passed=passed,
        result=result,
    )


__all__ = ["handle_retrieval_eval"]
