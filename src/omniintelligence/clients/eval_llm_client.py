# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Async LLM client for Bloom evaluation framework.

Provides scenario generation (Qwen3-14B via generator_url) and
soft judgment (DeepSeek-R1 via judge_url) using OpenAI-compatible vLLM.

ARCH-002 compliant: URLs injected via constructor (no env var reads).
Lives in clients/, not nodes/, per isolation convention.

Telemetry (OMN-5184):
    Optional ``event_publisher`` emits ``ModelLLMCallCompletedEvent`` after
    each successful LLM call.  Emission is fire-and-forget — failures are
    logged but never block the LLM call result.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from types import TracebackType

    from omniintelligence.runtime.adapters import AdapterKafkaPublisher

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_MODEL = "default"
_RETRY_BASE_DELAY = 1.0
_HTTP_CLIENT_ERR_MIN = 400
_HTTP_CLIENT_ERR_MAX = 500


class EvalLLMClientError(Exception):
    """Base error for EvalLLMClient failures."""


class EvalLLMConnectionError(EvalLLMClientError):
    """Connection to LLM endpoint failed."""


class EvalLLMTimeoutError(EvalLLMClientError):
    """Request to LLM endpoint timed out."""


class EvalLLMClient:
    """Async client for Bloom eval LLM calls.

    Two endpoints:
    - generator_url: scenario generation (Qwen3-14B, port 8001)
    - judge_url: soft judgment (DeepSeek-R1, port 8101)

    Both use POST /v1/chat/completions (OpenAI-compatible).
    Context manager or manual connect/close lifecycle supported.
    """

    def __init__(
        self,
        generator_url: str,
        judge_url: str,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        event_publisher: AdapterKafkaPublisher | None = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._generator_url = generator_url.rstrip("/")
        self._judge_url = judge_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._connected = False
        self._event_publisher = event_publisher
        self._correlation_id = correlation_id or ""
        self._session_id = session_id or ""

    async def connect(self) -> None:
        if self._connected:
            return
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._connected = True

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def __aenter__(self) -> EvalLLMClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def generate_scenarios(
        self,
        prompt_template: str,
        n: int = 5,
        *,
        model: str = _DEFAULT_MODEL,
    ) -> list[str]:
        """Generate adversarial evaluation scenarios via generator endpoint.

        Sends to generator_url/v1/chat/completions. Returns list of n strings.
        """
        if not self._connected:
            await self.connect()

        url = f"{self._generator_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate {n} distinct evaluation scenarios for: {prompt_template}",
                }
            ],
            "n": n,
            "temperature": 0.8,
        }
        start = time.monotonic()
        response_data = await self._post_with_retry(url, payload)
        latency_ms = int((time.monotonic() - start) * 1000)
        await self._emit_call_completed(
            response_data=response_data,
            model_id=model,
            endpoint_url=self._generator_url,
            request_type="completion",
            latency_ms=latency_ms,
        )
        choices = response_data.get("choices", [])
        return [c["message"]["content"] for c in choices[:n]]

    async def judge_output(
        self,
        prompt: str,
        output: str,
        failure_indicators: list[str],
        *,
        model: str = _DEFAULT_MODEL,
    ) -> dict[str, Any]:
        """Judge agent output for failure mode indicators via judge endpoint.

        Sends to judge_url/v1/chat/completions. Returns structured dict with
        soft evaluation scores.
        """
        if not self._connected:
            await self.connect()

        indicators_str = ", ".join(failure_indicators)
        url = f"{self._judge_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an evaluator. Return JSON with keys: "
                        "metamorphic_stability_score (0-1), compliance_theater_risk (0-1), "
                        "ambiguity_flags (list[str]), invented_requirements (list[str]), "
                        "missing_acceptance_criteria (list[str])."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Prompt: {prompt}\n\nOutput: {output}\n\n"
                        f"Check for failure indicators: {indicators_str}"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        start = time.monotonic()
        response_data = await self._post_with_retry(url, payload)
        latency_ms = int((time.monotonic() - start) * 1000)
        await self._emit_call_completed(
            response_data=response_data,
            model_id=model,
            endpoint_url=self._judge_url,
            request_type="reasoning",
            latency_ms=latency_ms,
        )
        return response_data

    async def _emit_call_completed(
        self,
        *,
        response_data: dict[str, Any],
        model_id: str,
        endpoint_url: str,
        request_type: str,
        latency_ms: int,
    ) -> None:
        """Fire-and-forget emission of LLM call telemetry event.

        Silently logs and returns on any failure — never blocks the caller.
        """
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
                endpoint_url=endpoint_url,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_usd=0.0,
                latency_ms=latency_ms,
                request_type=request_type,
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

    async def _post_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self._client is None:
            raise EvalLLMClientError("Client is not connected")

        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, json=payload)
                response.raise_for_status()
                return dict(response.json())

            except httpx.TimeoutException as exc:
                last_exception = EvalLLMTimeoutError(
                    f"Timeout after {self._timeout_seconds}s: {exc}"
                )

            except httpx.ConnectError as exc:
                last_exception = EvalLLMConnectionError(
                    f"Connection failed to {url}: {exc}"
                )

            except httpx.HTTPStatusError as exc:
                if (
                    _HTTP_CLIENT_ERR_MIN
                    <= exc.response.status_code
                    < _HTTP_CLIENT_ERR_MAX
                ):
                    raise EvalLLMClientError(
                        f"Client error {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                last_exception = EvalLLMClientError(
                    f"Server error {exc.response.status_code}"
                )

            if attempt < self._max_retries:
                await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))

        if last_exception is not None:
            raise last_exception
        raise EvalLLMClientError("Unexpected error: no exception captured")


__all__ = [
    "EvalLLMClient",
    "EvalLLMClientError",
    "EvalLLMConnectionError",
    "EvalLLMTimeoutError",
]
