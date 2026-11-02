# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handlers of the retrieval eval compute node.

``handler_retrieval_eval`` is the bound handler; ``golden``, ``metrics``,
``replay`` and ``scorecard`` are the pure modules it composes.  Import them by
their own module path: re-exporting here would make the input model, which
imports ``golden`` and ``replay``, circular with the handler.
"""
