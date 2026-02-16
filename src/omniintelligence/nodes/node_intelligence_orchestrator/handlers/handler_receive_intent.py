# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for receiving and logging intents from the intelligence reducer.

This handler implements the orchestrator side of the reducer-to-orchestrator
intent channel. When the reducer emits ModelIntent objects as part of its
state transition output, the orchestrator receives them through this handler.

The handler:
    1. Logs the intent with structured fields (correlation_id, intent_type, target)
    2. Records the intent metadata in a ModelIntentReceipt
    3. Returns the receipt for observability

Design Principles:
    - Pure function with no side effects beyond logging
    - Returns structured result, never raises domain exceptions
    - Follows the ONEX handler pattern (handler owns all business logic)
    - No promotion gating, lifecycle transitions, or feedback loops

Explicitly Excludes (per OMN-2034 scope):
    - Promotion gating logic
    - Lifecycle state transitions
    - Feedback loops
    - Intent routing to effect nodes

Ticket: OMN-2034
"""

from __future__ import annotations

import logging
from uuid import UUID

from omnibase_core.models.reducer.model_intent import ModelIntent

from omniintelligence.nodes.node_intelligence_orchestrator.models.model_intent_receipt import (
    ModelIntentReceipt,
)

logger = logging.getLogger(__name__)


def handle_receive_intent(
    intent: ModelIntent,
    *,
    correlation_id: UUID | None = None,
) -> ModelIntentReceipt:
    """Receive and log an intent emitted by the intelligence reducer.

    This is the entry point for the orchestrator's intent reception channel.
    It logs the intent with structured context and returns a receipt confirming
    the intent was received.

    The handler extracts key fields from the intent for logging:
    - intent_id: Unique identifier for tracing
    - intent_type: Type for routing context (e.g., "extension")
    - target: Target URI (e.g., "postgres://patterns/{id}")
    - payload.intent_type: Payload-level type discriminator
    - priority: Execution priority

    Args:
        intent: The ModelIntent emitted by the reducer.
        correlation_id: Optional correlation ID for distributed tracing.
            If not provided, defaults to None in the receipt.

    Returns:
        ModelIntentReceipt confirming the intent was received and recorded.
    """
    # Extract payload intent_type safely (getattr avoids suppressing
    # property-access errors that hasattr would silently swallow).
    _intent_type = getattr(intent.payload, "intent_type", None)
    payload_intent_type: str | None = (
        str(_intent_type) if _intent_type is not None else None
    )

    logger.info(
        "Intent received from reducer",
        extra={
            "intent_id": str(intent.intent_id),
            "intent_type": intent.intent_type,
            "target": intent.target,
            "payload_intent_type": payload_intent_type,
            "priority": intent.priority,
            "correlation_id": str(correlation_id) if correlation_id else None,
            "lease_id": str(intent.lease_id) if intent.lease_id else None,
            "epoch": intent.epoch,
        },
    )

    return ModelIntentReceipt(
        received=True,
        intent_id=intent.intent_id,
        intent_type=intent.intent_type,
        target=intent.target,
        correlation_id=correlation_id,
        message=f"Intent '{intent.intent_type}' targeting '{intent.target}' received and recorded",
    )


def handle_receive_intents(
    intents: tuple[ModelIntent, ...],
    *,
    correlation_id: UUID | None = None,
) -> list[ModelIntentReceipt]:
    """Receive and log a batch of intents from reducer output.

    Convenience function for processing all intents from a ModelReducerOutput.
    Calls handle_receive_intent for each intent and collects receipts.

    Args:
        intents: Tuple of ModelIntent objects from reducer output.
        correlation_id: Optional correlation ID for distributed tracing.

    Returns:
        List of ModelIntentReceipt for each processed intent.
    """
    if not intents:
        logger.debug(
            "No intents to process from reducer output",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
            },
        )
        return []

    logger.info(
        "Processing intent batch from reducer",
        extra={
            "intent_count": len(intents),
            "correlation_id": str(correlation_id) if correlation_id else None,
        },
    )

    receipts = []
    for intent in intents:
        receipt = handle_receive_intent(
            intent,
            correlation_id=correlation_id,
        )
        receipts.append(receipt)

    logger.info(
        "Intent batch processing complete",
        extra={
            "processed_count": len(receipts),
            "all_received": all(r.received for r in receipts),
            "correlation_id": str(correlation_id) if correlation_id else None,
        },
    )

    return receipts


__all__ = ["handle_receive_intent", "handle_receive_intents"]
