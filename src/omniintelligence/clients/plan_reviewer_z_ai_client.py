# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Z.AI GLM-4 LLM client for NodePlanReviewerMultiCompute.

Calls the Z.AI OpenAI-compatible chat completions endpoint using
``Z_AI_API_KEY`` and ``Z_AI_API_URL``.  The wire format is identical to
the OpenAI chat completions spec, so this client can be swapped with other
plan-reviewer clients without any handler changes.

Default endpoint: https://api.z.ai/api/paas/v4/chat/completions

Environment:
    Z_AI_API_KEY: Z.AI platform API key.
    Z_AI_API_URL: Z.AI base URL (used to derive the chat completions path).

Example::

    import os
    from omniintelligence.clients.plan_reviewer_z_ai_client import (
        PlanReviewerZAIClient,
        ModelPlanReviewerZAIConfig,
    )

    config = ModelPlanReviewerZAIConfig(
        api_key=os.environ["Z_AI_API_KEY"],
        chat_url=os.environ.get(
            "Z_AI_API_URL",
            "https://api.z.ai/api/paas/v4/chat/completions",
        ),
    )
    async with PlanReviewerZAIClient(config) as client:
        reply = await client.chat(
            messages=[{"role": "user", "content": "Review this plan."}]
        )

Ticket: OMN-3286
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_Z_AI_DEFAULT_CHAT_URL = "https://api.z.ai/api/paas/v4/chat/completions"
_DEFAULT_MODEL = "glm-4-plus"
_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_MAX_TOKENS = 2048
_HTTP_CLIENT_ERROR_MIN = 400
_HTTP_CLIENT_ERROR_MAX = 500  # exclusive (4xx range)


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class ModelPlanReviewerZAIConfig(BaseModel):
    """Configuration for the Z.AI GLM-4 plan-reviewer client.

    Attributes:
        api_key: Z.AI API key (``Z_AI_API_KEY``).
        chat_url: Full URL for the chat completions endpoint.
            Defaults to ``https://api.z.ai/api/paas/v4/chat/completions``.
        model: GLM model name.
        timeout_seconds: HTTP request timeout in seconds.
        max_tokens: Maximum tokens in the model reply.
        temperature: Sampling temperature (0 = deterministic).
    """

    model_config = {"frozen": True, "extra": "ignore"}

    api_key: str = Field(description="Z.AI API key (Z_AI_API_KEY).")
    chat_url: str = Field(
        default=_Z_AI_DEFAULT_CHAT_URL,
        description=(
            "Full URL for the Z.AI OpenAI-compat chat completions endpoint. "
            "Override with Z_AI_API_URL when deploying to a custom base URL."
        ),
    )
    model: str = Field(
        default=_DEFAULT_MODEL,
        description="GLM model name.",
    )
    timeout_seconds: float = Field(
        default=_DEFAULT_TIMEOUT_SECONDS,
        description="HTTP request timeout in seconds.",
    )
    max_tokens: int = Field(
        default=_DEFAULT_MAX_TOKENS,
        description="Maximum tokens in the model reply.",
    )
    temperature: float = Field(
        default=0.1,
        description="Sampling temperature (0 = deterministic).",
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PlanReviewerZAIClientError(Exception):
    """Base exception for Z.AI plan-reviewer client errors."""


class PlanReviewerZAIAuthError(PlanReviewerZAIClientError):
    """Raised when authentication fails (401/403)."""


class PlanReviewerZAITimeoutError(PlanReviewerZAIClientError):
    """Raised when a request times out."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PlanReviewerZAIClient:
    """Async client for Z.AI GLM-4 via the OpenAI-compatible endpoint.

    Uses a persistent ``httpx.AsyncClient`` for connection reuse.
    Supports context-manager and manual lifecycle management.

    Example (context manager)::

        async with PlanReviewerZAIClient(config) as client:
            reply = await client.chat(messages=[...])

    Example (manual lifecycle)::

        client = PlanReviewerZAIClient(config)
        await client.connect()
        try:
            reply = await client.chat(messages=[...])
        finally:
            await client.close()
    """

    def __init__(self, config: ModelPlanReviewerZAIConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    @property
    def config(self) -> ModelPlanReviewerZAIConfig:
        """Return the client configuration."""
        return self._config

    @property
    def is_connected(self) -> bool:
        """True if the connection pool is active."""
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Open the connection pool. Idempotent."""
        if self._connected:
            return
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._connected = True
        logger.debug("PlanReviewerZAIClient connected to %s", self._config.chat_url)

    async def close(self) -> None:
        """Close the connection pool. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.debug("PlanReviewerZAIClient connection closed")

    async def __aenter__(self) -> PlanReviewerZAIClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a chat request to Z.AI GLM-4 and return the reply content.

        Args:
            messages: OpenAI-compat message list
                (e.g. ``[{"role": "user", "content": "..."}]``).
            max_tokens: Override for ``config.max_tokens``.
            temperature: Override for ``config.temperature``.

        Returns:
            The assistant reply content string.

        Raises:
            PlanReviewerZAIClientError: On response format errors.
            PlanReviewerZAIAuthError: On 401/403 responses.
            PlanReviewerZAITimeoutError: On request timeout.
        """
        if not self._connected:
            await self.connect()

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": max_tokens
            if max_tokens is not None
            else self._config.max_tokens,
            "temperature": temperature
            if temperature is not None
            else self._config.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        return await self._execute_chat(payload, headers)

    async def _execute_chat(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> str:
        """POST to the chat completions endpoint and parse the response.

        Args:
            payload: JSON request body.
            headers: HTTP headers including Authorization.

        Returns:
            Assistant reply content string.

        Raises:
            PlanReviewerZAIClientError: On parse failure or missing fields.
            PlanReviewerZAIAuthError: On 401/403 status codes.
            PlanReviewerZAITimeoutError: On timeout.
        """
        if self._client is None:
            raise PlanReviewerZAIClientError("Client is not connected")

        try:
            response = await self._client.post(
                self._config.chat_url,
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise PlanReviewerZAITimeoutError(
                f"Z.AI request timed out after {self._config.timeout_seconds}s: {exc}"
            ) from exc

        # Auth errors get a specific exception type
        if response.status_code in (401, 403):
            raise PlanReviewerZAIAuthError(
                f"Z.AI authentication failed: {response.status_code} - {response.text}"
            )

        if (
            _HTTP_CLIENT_ERROR_MIN <= response.status_code < _HTTP_CLIENT_ERROR_MAX
            or response.status_code >= 500
        ):
            raise PlanReviewerZAIClientError(
                f"Z.AI API error: {response.status_code} - {response.text}"
            )

        try:
            data = response.json()
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise PlanReviewerZAIClientError(
                f"Unexpected Z.AI response format: {exc} | body={response.text[:200]}"
            ) from exc

        logger.debug(
            "PlanReviewerZAIClient received %d chars from %s",
            len(content),
            self._config.model,
        )
        return content


__all__ = [
    "ModelPlanReviewerZAIConfig",
    "PlanReviewerZAIAuthError",
    "PlanReviewerZAIClient",
    "PlanReviewerZAIClientError",
    "PlanReviewerZAITimeoutError",
]
