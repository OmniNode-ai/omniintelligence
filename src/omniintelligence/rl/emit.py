# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Fire-and-forget emission helpers for RL routing decisions.

Provides a helper to emit rl-routing-decision.v1 events when the RL
policy makes a shadow-mode routing recommendation. Currently a stub
awaiting online RL inference integration.

Reference: OMN-6126 (Dashboard Data Pipeline Gaps)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)


async def emit_rl_routing_decision(
    *,
    kafka_producer: ProtocolKafkaPublisher | None,
    correlation_id: str,
    agent_selected: str,
    confidence: float,
    shadow_mode: bool = True,
    alternatives: list[dict[str, object]] | None = None,
) -> None:
    """Emit an RL routing decision event (fire-and-forget).

    Silently logs and returns on any failure -- never blocks the caller.

    Args:
        kafka_producer: Optional Kafka publisher. No-op when None.
        correlation_id: Distributed tracing correlation ID.
        agent_selected: The agent/backend selected by the RL policy.
        confidence: Policy confidence in the selection (0.0 - 1.0).
        shadow_mode: True for shadow comparison, False for live routing.
        alternatives: List of {agent, score} dicts for all candidates.
    """
    if kafka_producer is None:
        return
    try:
        from omniintelligence.constants import TOPIC_RL_ROUTING_DECISION_V1
        from omniintelligence.models.events.model_rl_routing_decision_event import (
            ModelRlRoutingAlternative,
            ModelRlRoutingDecisionEvent,
        )

        alt_models = [
            ModelRlRoutingAlternative(
                agent=str(a.get("agent", "")),
                score=float(a.get("score", 0.0)),
            )
            for a in (alternatives or [])
        ]

        event = ModelRlRoutingDecisionEvent(
            decision_id=str(uuid4()),
            correlation_id=correlation_id,
            agent_selected=agent_selected,
            confidence=confidence,
            shadow_mode=shadow_mode,
            alternatives=alt_models,
            decided_at=datetime.now(UTC),
        )
        await kafka_producer.publish(
            topic=TOPIC_RL_ROUTING_DECISION_V1,
            key=correlation_id,
            value=event.model_dump(mode="json"),
        )
    except Exception:
        logger.warning(
            "Failed to emit RL routing decision event (non-blocking)",
            exc_info=True,
        )


__all__ = ["emit_rl_routing_decision"]
