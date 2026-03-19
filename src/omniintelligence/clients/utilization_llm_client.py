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

import httpx

logger = logging.getLogger(__name__)


class UtilizationLLMClient:
    """Minimal client for utilization scoring via local Qwen3-14B.

    Implements the chat_completion interface matching ProtocolLlmClient
    from node_pattern_compliance_effect.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or os.getenv(
            "LLM_CODER_FAST_URL", "http://192.168.86.201:8001"
        )
        self._client = httpx.AsyncClient(timeout=30.0)

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
        return response.json()["choices"][0]["message"]["content"]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


__all__ = ["UtilizationLLMClient"]
