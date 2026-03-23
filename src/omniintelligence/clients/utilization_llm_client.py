# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Thin LLM client for utilization scoring via OpenAI-compatible API.

Minimal client matching ProtocolLlmClient.chat_completion interface.
Not reusing EvalLLMClient because it requires (generator_url, judge_url)
and has no chat_completion method.

Reference: OMN-5507 - Wire utilization scoring handler into dispatch engine.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)


class UtilizationLLMClient:
    """Minimal client for utilization scoring via local Qwen3-14B.

    Implements the chat_completion interface matching ProtocolLlmClient
    from node_pattern_compliance_effect.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        event_publisher: ProtocolKafkaPublisher | None = None,
        correlation_id: str = "unknown",
        session_id: str = "unknown",
    ) -> None:
        self._base_url = base_url or os.getenv(
            "LLM_CODER_FAST_URL", "http://192.168.86.201:8001"
        )
        self._client = httpx.AsyncClient(timeout=30.0)
        self._event_publisher = event_publisher
        self._correlation_id = correlation_id
        self._session_id = session_id

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str = "qwen3-14b",
        temperature: float = 0.1,
        max_tokens: int = 200,
    ) -> str:
        """Send a chat completion request to the OpenAI-compatible API.

        Returns:
            The content string from the first choice's message.
        """
        start_ms = time.perf_counter()
        response = await self._client.post(
            f"{self._base_url}/v1/chat/completions",
            json={
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        latency_ms = int((time.perf_counter() - start_ms) * 1000)
        response_data: dict[str, Any] = dict(response.json())

        # OMN-6129: Fire-and-forget LLM call telemetry emission
        await self._emit_call_completed(
            response_data=response_data,
            model_id=model,
            latency_ms=latency_ms,
        )

        return str(response_data["choices"][0]["message"]["content"])

    async def _emit_call_completed(
        self,
        *,
        response_data: dict[str, Any],
        model_id: str,
        latency_ms: int,
    ) -> None:
        """Fire-and-forget emission of LLM call telemetry event."""
        if self._event_publisher is None:
            return
        try:
            from datetime import UTC, datetime

            from omniintelligence.models.events.model_llm_call_completed_event import (
                ModelLLMCallCompletedEvent,
            )
            from omniintelligence.topics import IntentTopic

            usage = response_data.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))

            event = ModelLLMCallCompletedEvent(
                model_id=model_id,
                endpoint_url=self._base_url,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_usd=0.0,
                latency_ms=latency_ms,
                request_type="classification",
                correlation_id=self._correlation_id,
                session_id=self._session_id,
                emitted_at=datetime.now(UTC),
            )
            await self._event_publisher.publish(
                topic=IntentTopic.LLM_CALL_COMPLETED,
                key=self._correlation_id,
                value=event.model_dump(mode="json"),
            )
        except Exception:
            logger.warning("Failed to emit LLM call completed event", exc_info=True)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


__all__ = ["UtilizationLLMClient"]
