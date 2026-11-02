# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handler of node_retrieval_eval_effect.

The handler is built here, the one binding site, and the node runtime resolves
it through the function below instead of constructing it.
"""

from __future__ import annotations

from omniintelligence.nodes.node_retrieval_eval_effect.handlers.handler_retrieval_eval import (
    HandlerRetrievalEval,
)


def resolve_retrieval_eval_handler() -> HandlerRetrievalEval:
    """Resolve the HandlerRetrievalEval the node delegates to."""
    return HandlerRetrievalEval()


__all__ = ["resolve_retrieval_eval_handler"]
