# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Node Evidence Collection Effect — ONEX EFFECT node for objective evaluation wiring.

This effect node collects structured evidence from agent session check results
(ChangeFrame gate outputs, test results, static analysis, cost/latency telemetry)
and feeds it into the objective evaluation pipeline at session end.

ONEX Node Type: EFFECT (has external I/O — Kafka, PostgreSQL)

Design:
    - Declarative contract-driven shell (like all ONEX effect nodes).
    - Delegates execution to handler_evidence_collection.collect_and_evaluate.
    - Non-blocking: evaluation is dispatched as an asyncio task and must not
      delay session completion.

Integration point:
    handle_stop() in node_claude_hook_event_effect/handlers/handler_claude_event.py
    calls fire_and_forget_evaluate() wrapped in asyncio.create_task().

Ticket: OMN-2578
"""

from __future__ import annotations

try:
    from omnibase_core.nodes.node_effect import NodeEffect as _NodeEffect

    _BASE_CLASS = _NodeEffect
except ImportError:
    # omnibase_core not yet installed (pre-release environment).
    # Use object as base class — this is only a temporary fallback.
    _BASE_CLASS = object  # type: ignore[assignment,misc]

__all__ = ["NodeEvidenceCollectionEffect"]


class NodeEvidenceCollectionEffect(_BASE_CLASS):  # type: ignore[valid-type,misc]
    """ONEX EFFECT node for wiring objective evaluation into agent execution traces.

    Lightweight declarative shell. All logic is in the handlers.

    Supported operations (via handler):
        - collect_and_evaluate: Collect evidence and drive full evaluation pipeline.
        - fire_and_forget_evaluate: Non-blocking wrapper for use in handle_stop.

    The actual execution is performed by:
        - EvidenceCollector (pure, no I/O): extracts EvidenceItem dicts
        - collect_and_evaluate (async, has I/O): Kafka + DB
        - fire_and_forget_evaluate: asyncio task wrapper for handle_stop integration
    """
