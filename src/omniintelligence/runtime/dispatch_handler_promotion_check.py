# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Dispatch handler for periodic promotion-check commands.

Routes promotion-check-requested commands to the auto-promote handler,
which evaluates all candidate and provisional patterns against promotion
gates (including the bootstrap path for cold-start patterns).

Reference: OMN-5498 - Create promotion-check dispatch handler.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from omniintelligence.constants import TOPIC_PROMOTION_CHECK_CMD_V1
from omniintelligence.protocols import ProtocolPatternRepository
from omniintelligence.runtime.contract_topics import canonical_topic_to_dispatch_alias

if TYPE_CHECKING:
    from omniintelligence.protocols import (
        ProtocolIdempotencyStore,
        ProtocolKafkaPublisher,
    )

logger = logging.getLogger(__name__)

DISPATCH_ALIAS_PROMOTION_CHECK = canonical_topic_to_dispatch_alias(
    TOPIC_PROMOTION_CHECK_CMD_V1
)
"""Dispatch-compatible alias for promotion-check commands."""


def create_promotion_check_dispatch_handler(
    *,
    repository: ProtocolPatternRepository,
    idempotency_store: ProtocolIdempotencyStore | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str | None = None,
) -> Any:  # any-ok: dispatch handler callable
    """Create a dispatch handler that runs the auto-promotion check.

    Designed to be triggered by periodic promotion-check-requested commands
    from the promotion scheduler (OMN-5499).

    Args:
        repository: Database repository for pattern queries.
        idempotency_store: Optional idempotency store for transition dedup.
        kafka_producer: Optional Kafka publisher for transition events.
        publish_topic: Optional topic override for transition events.

    Returns:
        Async handler function compatible with MessageDispatchEngine.
    """

    async def handle(
        envelope: Any,  # any-ok: ModelEventEnvelope[object]
        context: Any,  # any-ok: ProtocolHandlerContext
    ) -> str:
        from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers import (
            apply_transition,
        )
        from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
            handle_auto_promote_check,
        )

        payload = envelope.payload if hasattr(envelope, "payload") else envelope
        if isinstance(payload, dict):
            raw_correlation_id = payload.get("correlation_id")
        else:
            raw_correlation_id = None

        correlation_id: UUID = (
            UUID(raw_correlation_id)
            if isinstance(raw_correlation_id, str) and raw_correlation_id
            else uuid4()
        )

        logger.info(
            "Promotion check triggered via dispatch",
            extra={"correlation_id": str(correlation_id)},
        )

        # Wrap apply_transition to match ProtocolApplyTransition signature
        # by pre-binding repository, idempotency_store, and producer.
        producer = kafka_producer

        result = await handle_auto_promote_check(
            repository=repository,
            apply_transition_fn=apply_transition,
            idempotency_store=idempotency_store,
            producer=producer,  # type: ignore[arg-type]
            correlation_id=correlation_id,
            publish_topic=publish_topic,
        )

        logger.info(
            "Promotion check completed",
            extra={
                "correlation_id": str(correlation_id),
                "candidates_checked": result["candidates_checked"],
                "candidates_promoted": result["candidates_promoted"],
                "provisionals_checked": result["provisionals_checked"],
                "provisionals_promoted": result["provisionals_promoted"],
            },
        )

        return (
            f"promotion_check_completed: "
            f"candidates={result['candidates_promoted']}/{result['candidates_checked']}, "
            f"provisionals={result['provisionals_promoted']}/{result['provisionals_checked']}"
        )

    return handle


__all__ = [
    "DISPATCH_ALIAS_PROMOTION_CHECK",
    "create_promotion_check_dispatch_handler",
]
