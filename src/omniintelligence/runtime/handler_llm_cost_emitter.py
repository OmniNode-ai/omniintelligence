# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM cost telemetry emitter for intelligence dispatch engine.

Handler that publishes LLM call cost events to
``onex.evt.omniintelligence.llm-call-completed.v1`` for downstream
projection into omnidash's ``llm_cost_aggregates`` table.

The handler is fail-open: if the producer is None or publishing
fails, a warning is logged and the caller continues normally.

Payload fields match the omnidash consumer's ``projectLlmCostEvent``
primary (snake_case) paths.

Related:
    - OMN-6801: LLM cost events empty
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from omniintelligence.models.model_llm_cost_event_request import (
    ModelLlmCostEventRequest,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.topics import IntentTopic

logger = logging.getLogger(__name__)

LLM_COST_TOPIC: str = IntentTopic.LLM_CALL_COMPLETED.value
"""Canonical topic for LLM cost telemetry events."""


class HandlerLlmCostEmitter:
    """Publishes LLM cost telemetry events (fail-open)."""

    def __init__(
        self,
        producer: ProtocolKafkaPublisher | None,
        topic: str = LLM_COST_TOPIC,
    ) -> None:
        """Initialize with the (optional) Kafka publisher and target topic.

        Args:
            producer: Kafka publisher. If None, ``handle`` logs a warning and
                returns False.
            topic: Target Kafka topic for cost events.
        """
        self._producer = producer
        self._topic = topic

    async def handle(self, request: ModelLlmCostEventRequest) -> bool:
        """Emit an LLM cost telemetry event to Kafka (fail-open).

        Args:
            request: Cost telemetry for one LLM call.

        Returns:
            True if successfully published, False otherwise.
        """
        producer = self._producer
        if producer is None:
            logger.warning(
                "LLM cost event not emitted: producer is None "
                "(model_id=%s, correlation_id=%s)",
                request.model_id,
                request.correlation_id,
            )
            return False

        payload: dict[str, object] = {
            "model_id": request.model_id,
            "prompt_tokens": request.prompt_tokens,
            "completion_tokens": request.completion_tokens,
            "total_tokens": request.total_tokens,
            "estimated_cost_usd": request.estimated_cost_usd,
            "session_id": request.session_id,
            "correlation_id": str(request.correlation_id),
            "timestamp_iso": datetime.now(UTC).isoformat(),
            "endpoint_url": request.endpoint_url,
            "request_type": request.request_type,
            "latency_ms": request.latency_ms,
            "input_tokens": request.prompt_tokens,
            "output_tokens": request.completion_tokens,
            "cost_usd": request.estimated_cost_usd,
            "emitted_at": datetime.now(UTC).isoformat(),
        }
        if request.repo_name is not None:
            payload["repo_name"] = request.repo_name
        if request.machine_id is not None:
            payload["machine_id"] = request.machine_id

        try:
            await producer.publish(
                topic=self._topic,
                key=str(request.correlation_id),
                value=payload,
            )
            logger.debug(
                "LLM cost event emitted (model_id=%s, total_tokens=%d, "
                "correlation_id=%s)",
                request.model_id,
                request.total_tokens,
                request.correlation_id,
            )
            return True
        except Exception:
            logger.warning(
                "Failed to emit LLM cost event (model_id=%s, correlation_id=%s)",
                request.model_id,
                request.correlation_id,
                exc_info=True,
            )
            return False


__all__ = [
    "LLM_COST_TOPIC",
    "HandlerLlmCostEmitter",
]
