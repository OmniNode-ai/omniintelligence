# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute: declarative shell driven by contract.yaml.

All handler dispatch is declared in contract.yaml via ``handler_routing``,
which binds handle_retrieval_eval. The node contains no custom code.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelEvalResult,
    ModelRetrievalEvalInput,
)


class NodeRetrievalEvalCompute(NodeCompute[ModelRetrievalEvalInput, ModelEvalResult]):
    """Declarative compute node that runs the offline retrieval eval.

    contract.yaml routes the run_retrieval_eval operation to
    handle_retrieval_eval; this class declares only the input and output types.
    """


__all__ = ["NodeRetrievalEvalCompute"]
