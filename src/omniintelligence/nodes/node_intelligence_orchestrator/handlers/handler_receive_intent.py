# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler for receiving and logging intents from the intelligence reducer.

Orchestrator side of the reducer-to-orchestrator
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
from typing import Any
from uuid import UUID

from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.payloads import ModelPayloadExtension

from omniintelligence.nodes.node_intelligence_orchestrator.models import (
    ModelReceiveIntentRequest,
    ModelReceiveIntentsRequest,
    ModelReceiveIntentsResponse,
)
from omniintelligence.nodes.node_intelligence_orchestrator.models.model_intent_receipt import (
    ModelIntentReceipt,
)

logger = logging.getLogger(__name__)


def request_from_dispatch_payload(
    payload: dict[str, Any], correlation_id: UUID
) -> ModelReceiveIntentRequest:
    """Build the typed request from a dispatch-bridge payload dict.

    The ``payload`` nested field of ``ModelIntent`` uses ProtocolIntentPayload (a
    runtime-checkable Protocol) which cannot be deserialized from raw dicts via
    model_validate, so a lightweight ModelPayloadExtension stands in for it.
    """
    raw_payload = payload.get("payload") or {}
    intent_kwargs: dict[str, Any] = {
        "intent_type": str(payload.get("intent_type", "unknown")),
        "target": str(payload.get("target", "dispatch://bridge")),
        "payload": ModelPayloadExtension(
            intent_type="extension",
            extension_type=str(raw_payload.get("extension_type", "dispatch.bridge")),
            plugin_name=str(
                raw_payload.get("plugin_name", "intelligence-orchestrator")
            ),
        ),
    }
    if payload.get("intent_id") is not None:
        intent_kwargs["intent_id"] = UUID(str(payload["intent_id"]))
    intent = ModelIntent(**intent_kwargs)
    return ModelReceiveIntentRequest(correlation_id=correlation_id, intent=intent)


class HandlerReceiveIntent:
    """Receive and record one reducer intent."""

    def handle(self, request: ModelReceiveIntentRequest) -> ModelIntentReceipt:
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
            request: Reducer intent and optional correlation ID for tracing.

        Returns:
            ModelIntentReceipt confirming the intent was received and recorded.
        """
        intent = request.intent
        correlation_id = request.correlation_id
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


class HandlerReceiveIntents:
    """Receive and record a batch of reducer intents."""

    def handle(
        self, request: ModelReceiveIntentsRequest
    ) -> ModelReceiveIntentsResponse:
        """Receive and log a batch of intents from reducer output.

        Batch handler for processing all intents from a ModelReducerOutput.
        Calls HandlerReceiveIntent for each intent and collects receipts.

        Args:
            request: Reducer intents and optional correlation ID for tracing.

        Returns:
            ModelReceiveIntentsResponse with a receipt for each processed intent.
        """
        intents = request.intents
        correlation_id = request.correlation_id
        if not intents:
            logger.debug(
                "No intents to process from reducer output",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                },
            )
            return ModelReceiveIntentsResponse(receipts=())

        logger.info(
            "Processing intent batch from reducer",
            extra={
                "intent_count": len(intents),
                "correlation_id": str(correlation_id) if correlation_id else None,
            },
        )

        receipts = []
        for intent in intents:
            receipt = HandlerReceiveIntent().handle(
                ModelReceiveIntentRequest(correlation_id=correlation_id, intent=intent)
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

        return ModelReceiveIntentsResponse(receipts=tuple(receipts))


__all__ = [
    "HandlerReceiveIntent",
    "HandlerReceiveIntents",
    "request_from_dispatch_payload",
]
