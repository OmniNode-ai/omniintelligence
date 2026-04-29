# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""LLM cost telemetry emitter for intelligence dispatch engine.

Utility function that publishes LLM call cost events to
``onex.evt.omniintelligence.llm-call-completed.v1`` for downstream
projection into omnidash's ``llm_cost_aggregates`` table.

The emit function is fail-open: if the producer is None or publishing
fails, a warning is logged and the caller continues normally.

Payload fields match the omnidash consumer's ``projectLlmCostEvent``
primary (snake_case) paths.

Related:
    - OMN-6801: LLM cost events empty
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.topics import IntentTopic

logger = logging.getLogger(__name__)

LLM_COST_TOPIC: str = IntentTopic.LLM_CALL_COMPLETED.value
"""Canonical topic for LLM cost telemetry events."""


async def emit_llm_cost_event(
    producer: ProtocolKafkaPublisher | None,
    topic: str,
    *,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated_cost_usd: float,
    session_id: str,
    correlation_id: str | UUID,
    endpoint_url: str = "",
    request_type: str = "completion",
    latency_ms: int = 0,
    repo_name: str | None = None,
    machine_id: str | None = None,
) -> bool:
    """Emit an LLM cost telemetry event to Kafka (fail-open).

    Args:
        producer: Kafka publisher. If None, logs warning and returns False.
        topic: Target Kafka topic for cost events.
        model_id: LLM model identifier (e.g. "qwen3-14b").
        prompt_tokens: Number of prompt/input tokens.
        completion_tokens: Number of completion/output tokens.
        total_tokens: Total tokens (prompt + completion).
        estimated_cost_usd: Estimated cost in USD.
        session_id: Session ID for attribution.
        correlation_id: Correlation ID for tracing.
        endpoint_url: LLM endpoint URL.
        request_type: Request type (completion, chat, embedding).
        latency_ms: Request latency in milliseconds.
        repo_name: Optional repository name for cost attribution.
        machine_id: Optional machine identifier for cost attribution.

    Returns:
        True if successfully published, False otherwise.
    """
    if producer is None:
        logger.warning(
            "LLM cost event not emitted: producer is None "
            "(model_id=%s, correlation_id=%s)",
            model_id,
            correlation_id,
        )
        return False

    payload: dict[str, object] = {
        "model_id": model_id,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "session_id": session_id,
        "correlation_id": str(correlation_id),
        "timestamp_iso": datetime.now(UTC).isoformat(),
        "endpoint_url": endpoint_url,
        "request_type": request_type,
        "latency_ms": latency_ms,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "cost_usd": estimated_cost_usd,
        "emitted_at": datetime.now(UTC).isoformat(),
    }
    if repo_name is not None:
        payload["repo_name"] = repo_name
    if machine_id is not None:
        payload["machine_id"] = machine_id

    try:
        await producer.publish(
            topic=topic,
            key=str(correlation_id),
            value=payload,
        )
        logger.debug(
            "LLM cost event emitted (model_id=%s, total_tokens=%d, correlation_id=%s)",
            model_id,
            total_tokens,
            correlation_id,
        )
        return True
    except Exception:
        logger.warning(
            "Failed to emit LLM cost event (model_id=%s, correlation_id=%s)",
            model_id,
            correlation_id,
            exc_info=True,
        )
        return False


__all__ = [
    "LLM_COST_TOPIC",
    "emit_llm_cost_event",
]
