# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute — thin shell delegating to HandlerRetrievalEval.

Runs the offline retrieval eval harness (replay scenarios, ranking metrics and
the scorecard) over the frozen code-projection fixtures.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
    ModelRetrievalEvalResult,
)


class NodeRetrievalEvalCompute(
    NodeCompute[ModelRetrievalEvalInput, ModelRetrievalEvalResult]
):
    """Compute node for the offline retrieval eval harness.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to HandlerRetrievalEval via contract handler_routing.
    """


__all__ = ["NodeRetrievalEvalCompute"]
