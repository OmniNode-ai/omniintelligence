# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute -- declarative shell of the retrieval eval harness.

Runs the offline retrieval-quality eval harness over a parsed replay corpus and
golden query set. Routing lives in contract.yaml: the single operation
``run_retrieval_eval`` is bound to ``handle_retrieval_eval``.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    ModelEvalResult,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


class NodeRetrievalEvalCompute(NodeCompute[ModelRetrievalEvalInput, ModelEvalResult]):
    """Declarative compute node for the offline retrieval eval harness.

    All behavior is defined in contract.yaml and delegated to
    handle_retrieval_eval; this class contains no custom methods.
    """


__all__ = ["NodeRetrievalEvalCompute"]
