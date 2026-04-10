# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Dispatch handler for routing feedback events.

Routes onex.evt.omniclaude.routing-feedback.v1 events to the
node_routing_feedback_effect handler, which filters on feedback_status,
upserts produced events to routing_feedback_scores, and publishes
routing-feedback-processed.v1.

Also registers a drain handler for the deprecated legacy bare topic
``routing.feedback`` (OMN-2366).

Reference: OMN-8170
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from omniintelligence.constants import (
    TOPIC_LEGACY_ROUTING_FEEDBACK_BARE,
    TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1,
)
from omniintelligence.runtime.contract_topics import canonical_topic_to_dispatch_alias

if TYPE_CHECKING:
    from omniintelligence.protocols import (
        ProtocolKafkaPublisher,
        ProtocolPatternRepository,
    )

logger = logging.getLogger(__name__)

DISPATCH_ALIAS_ROUTING_FEEDBACK = canonical_topic_to_dispatch_alias(
    TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1
)
"""Dispatch-compatible alias for routing-feedback canonical topic.

Converts ``onex.evt.omniclaude.routing-feedback.v1`` →
``onex.events.omniclaude.routing-feedback.v1`` for MessageDispatchEngine routing.
"""

DISPATCH_ALIAS_LEGACY_ROUTING_FEEDBACK = TOPIC_LEGACY_ROUTING_FEEDBACK_BARE
"""Dispatch alias for the legacy bare topic ``routing.feedback`` (OMN-2366).

No ``.evt.`` segment to replace — passes through unchanged.
"""


def create_routing_feedback_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    kafka_producer: ProtocolKafkaPublisher | None = None,
) -> Any:  # any-ok: dispatch handler callable
    """Create a dispatch handler for routing feedback events.

    Delegates to ``process_routing_feedback`` from
    ``node_routing_feedback_effect``. Filters on ``feedback_status``:
    - ``"produced"``: upserts to routing_feedback_scores, publishes processed event
    - ``"skipped"``: logs skip_reason, no DB write

    Args:
        repository: Database repository for routing_feedback_scores upserts.
        kafka_producer: Optional Kafka publisher for routing-feedback-processed events.
            Absent = graceful degradation (DB write still succeeds).

    Returns:
        Async handler function compatible with MessageDispatchEngine.
    """

    async def handle(
        envelope: Any,  # any-ok: ModelEventEnvelope[object]
        context: Any,  # any-ok: ProtocolHandlerContext
    ) -> str:
        from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
            process_routing_feedback,
        )
        from omniintelligence.nodes.node_routing_feedback_effect.models import (
            ModelRoutingFeedbackPayload,
        )

        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        if not isinstance(payload, dict):
            raise ValueError(
                f"Unexpected payload type {type(payload).__name__} "
                "for routing-feedback handler — expected dict"
            )

        event = ModelRoutingFeedbackPayload.model_validate(payload)

        logger.info(
            "Routing feedback received via dispatch",
            extra={
                "session_id": event.session_id,
                "feedback_status": event.feedback_status,
                "correlation_id": str(event.correlation_id),
            },
        )

        result = await process_routing_feedback(
            event=event,
            repository=repository,
            kafka_publisher=kafka_producer,
        )

        logger.info(
            "Routing feedback processed via dispatch",
            extra={
                "session_id": result.session_id,
                "status": result.status.value,
                "was_upserted": result.was_upserted,
                "correlation_id": str(event.correlation_id),
            },
        )

        return (
            f"routing_feedback_processed: "
            f"session={result.session_id}, "
            f"status={result.status.value}, "
            f"upserted={result.was_upserted}"
        )

    return handle


def create_legacy_routing_feedback_drain_handler() -> (
    Any
):  # any-ok: dispatch handler callable
    """Create a no-op drain handler for the deprecated legacy bare topic (OMN-2366).

    The legacy ``routing.feedback`` topic predates the canonical naming convention.
    No active producers detected as of 2026-04-09. Drains residual messages and
    discards them with a warning log.

    Returns:
        Async handler function compatible with MessageDispatchEngine.
    """

    async def handle(
        envelope: Any,  # any-ok: ModelEventEnvelope[object]
        context: Any,  # any-ok: ProtocolHandlerContext
    ) -> str:
        from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
            handle_legacy_routing_feedback_drain,
        )

        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        raw_payload = payload if isinstance(payload, dict) else {}
        await handle_legacy_routing_feedback_drain(raw_payload)
        return "legacy_routing_feedback_drained"

    return handle


__all__ = [
    "DISPATCH_ALIAS_LEGACY_ROUTING_FEEDBACK",
    "DISPATCH_ALIAS_ROUTING_FEEDBACK",
    "create_legacy_routing_feedback_drain_handler",
    "create_routing_feedback_dispatch_handler",
]
