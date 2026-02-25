# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node GmailIntentEvaluatorEffect — evaluate Gmail intent signals via DeepSeek R1.

Subscribes to gmail-intent-received.v1 events. For each event:
  - Selects the best candidate URL (Tier 1-4 preference)
  - Fetches URL content (512KB cap, HTML/JSON/text)
  - Queries omnimemory for duplicate detection
  - Calls DeepSeek R1 for verdict (SURFACE / WATCHLIST / SKIP)
  - Posts to Slack if verdict == SURFACE (rate-limited 5/hour)
  - Emits gmail-intent-evaluated.v1 (always) + gmail-intent-surfaced.v1 (SURFACE only)
  - Writes idempotency record to gmail_intent_evaluations table

This node follows the ONEX declarative pattern:
  - DECLARATIVE effect driven by contract.yaml
  - I/O effect: HTTP, omnimemory, LLM, Slack, Postgres
  - Lightweight shell that delegates to HandlerGmailIntentEvaluate

Does NOT:
  - Parse or classify intent (DeepSeek R1 does this)
  - Ingest documents into omnimemory
  - Manage Gmail labels (handled by node_gmail_intent_poller_effect)

Related:
  - OMN-2787: Gmail Intent Evaluator epic
  - OMN-2791: This node shell + contract
  - OMN-2790: HandlerGmailIntentEvaluate implementation
  - OMN-2788: Models
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeGmailIntentEvaluatorEffect(NodeEffect):
    """Declarative effect node for evaluating Gmail intent signals.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml. The node itself contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - gmail.evaluate_intent: Evaluate a single Gmail intent signal end-to-end

    Example:
        ```python
        from omniintelligence.nodes.node_gmail_intent_evaluator_effect.handlers import (
            handle_gmail_intent_evaluate,
        )
        from omniintelligence.nodes.node_gmail_intent_evaluator_effect.models import (
            ModelGmailIntentEvaluatorConfig,
        )

        config = ModelGmailIntentEvaluatorConfig(
            message_id="msg-001",
            subject="github.com/example/repo",
            body_text="Interesting Rust async runtime",
            urls=["https://github.com/example/repo"],
            source_label="To Read",
            sender="sender@example.com",
            received_at="2026-02-25T00:00:00Z",
        )
        result = await handle_gmail_intent_evaluate(config)
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeGmailIntentEvaluatorEffect"]
