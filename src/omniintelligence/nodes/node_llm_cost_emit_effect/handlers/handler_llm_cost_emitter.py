# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM cost telemetry emitter for intelligence dispatch engine.

Handler that publishes LLM call cost events to
``onex.evt.omniintelligence.llm-call-completed.v1`` for downstream
projection into omnidash's ``llm_cost_aggregates`` table.

The emitter is fail-open: if the producer is None or publishing
fails, a warning is logged and the caller continues normally.

Payload fields match the omnidash consumer's ``projectLlmCostEvent``
primary (snake_case) paths.

Related:
    - OMN-6801: LLM cost events empty
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from omniintelligence.nodes.node_llm_cost_emit_effect.models.model_llm_cost_emit_request import (
    ModelLlmCostEmitRequest,
)
from omniintelligence.nodes.node_llm_cost_emit_effect.models.model_llm_cost_emit_result import (
    ModelLlmCostEmitResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.topics import IntentTopic

logger = logging.getLogger(__name__)

LLM_COST_TOPIC: str = IntentTopic.LLM_CALL_COMPLETED.value
"""Canonical topic for LLM cost telemetry events."""


class HandlerLlmCostEmitter:
    """Publish LLM call cost events through an injected producer (fail-open)."""

    def __init__(
        self,
        producer: ProtocolKafkaPublisher | None,
        topic: str = LLM_COST_TOPIC,
    ) -> None:
        self._producer = producer
        self._topic = topic

    async def handle(self, request: ModelLlmCostEmitRequest) -> ModelLlmCostEmitResult:
        """Emit an LLM cost telemetry event to Kafka (fail-open).

        Returns:
            ``emitted=True`` if successfully published, ``emitted=False`` when the
            producer is None or publishing failed (a warning is logged, nothing
            is raised).
        """
        producer = self._producer
        if producer is None:
            logger.warning(
                "LLM cost event not emitted: producer is None "
                "(model_id=%s, correlation_id=%s)",
                request.model_id,
                request.correlation_id,
            )
            return ModelLlmCostEmitResult(emitted=False)

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
                "LLM cost event emitted (model_id=%s, total_tokens=%d, correlation_id=%s)",
                request.model_id,
                request.total_tokens,
                request.correlation_id,
            )
            return ModelLlmCostEmitResult(emitted=True)
        except Exception:
            logger.warning(
                "Failed to emit LLM cost event (model_id=%s, correlation_id=%s)",
                request.model_id,
                request.correlation_id,
                exc_info=True,
            )
            return ModelLlmCostEmitResult(emitted=False)


__all__ = [
    "LLM_COST_TOPIC",
    "HandlerLlmCostEmitter",
]
