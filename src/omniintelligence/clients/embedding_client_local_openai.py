# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Async embedding client for OpenAI-compatible local servers (e.g., MLX).

Provides an async HTTP client for generating text embeddings via any server
that implements the OpenAI /v1/embeddings API format. Designed for local MLX
servers but compatible with any OpenAI-API-compatible endpoint.

This client lives in omniintelligence.clients (not inside nodes/) to comply
with ARCH-002, which prohibits nodes from importing transport libraries
directly. Nodes receive clients via dependency injection.

Endpoint: ``LLM_EMBEDDING_URL`` env var or custom URL
API: POST /v1/embeddings with ``{"input": [...], "model": "..."}``

Example:
    ```python
    from omniintelligence.clients.embedding_client_local_openai import (
        EmbeddingClientLocalOpenAI,
    )
    from omniintelligence.nodes.node_embedding_generation_effect.models import (
        ModelEmbeddingClientConfig,
    )

    config = ModelEmbeddingClientConfig(base_url="http://localhost:8100")
    async with EmbeddingClientLocalOpenAI(config) as client:
        embeddings = await client.get_embeddings_batch(["Hello", "World"])
    ```

Ticket: OMN-368
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from omniintelligence.clients.embedding_client import (
    EmbeddingClientError,
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
    ModelEmbeddingClientConfig,
)

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

# HTTP status code boundaries for error classification
_HTTP_CLIENT_ERROR_MIN = 400
_HTTP_CLIENT_ERROR_MAX = 500  # Exclusive (4xx range)

# Default model name sent to OpenAI-compatible endpoints
_DEFAULT_MODEL_NAME = "default"


class EmbeddingClientLocalOpenAI:
    """Async client for OpenAI-compatible embedding servers.

    Uses the standard OpenAI ``/v1/embeddings`` API format. Compatible with
    MLX-based servers, vLLM, and any other server implementing the OpenAI
    embeddings API.

    Supports both context manager and manual lifecycle management. Shares
    the same error hierarchy as ``EmbeddingClient`` for seamless provider
    switching.

    Example (context manager):
        ```python
        config = ModelEmbeddingClientConfig(base_url="http://localhost:8100")
        async with EmbeddingClientLocalOpenAI(config) as client:
            embedding = await client.get_embedding("Hello world")
        ```

    Example (manual lifecycle):
        ```python
        config = ModelEmbeddingClientConfig(base_url="http://localhost:8100")
        client = EmbeddingClientLocalOpenAI(config)
        await client.connect()
        try:
            embeddings = await client.get_embeddings_batch(["a", "b", "c"])
        finally:
            await client.close()
        ```
    """

    def __init__(
        self,
        config: ModelEmbeddingClientConfig,
        *,
        model_name: str = _DEFAULT_MODEL_NAME,
    ) -> None:
        self._config = config
        self._model_name = model_name
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    @property
    def config(self) -> ModelEmbeddingClientConfig:
        """Return the client configuration."""
        return self._config

    @property
    def is_connected(self) -> bool:
        """True if the connection pool is active."""
        return self._connected and self._client is not None

    @property
    def embeddings_url(self) -> str:
        """Full URL for the /v1/embeddings endpoint."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/embeddings"

    async def connect(self) -> None:
        """Open the connection pool. Safe to call multiple times (idempotent)."""
        if self._connected:
            return
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._connected = True
        logger.debug(
            "EmbeddingClientLocalOpenAI connected to %s", self._config.base_url
        )

    async def close(self) -> None:
        """Close the connection pool. Safe to call multiple times (idempotent)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.debug("EmbeddingClientLocalOpenAI connection closed")

    async def __aenter__(self) -> EmbeddingClientLocalOpenAI:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def get_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses the OpenAI /v1/embeddings API format with a single input string.
        Retries on transient failures with exponential backoff. Does NOT
        retry on client errors (4xx).

        Args:
            text: Non-empty text to embed.

        Returns:
            A list of floats (embedding vector).

        Raises:
            EmbeddingClientError: If text is empty or response format is invalid.
            EmbeddingConnectionError: If connection fails after all retries.
            EmbeddingTimeoutError: If request times out after all retries.
        """
        if not text or not text.strip():
            raise EmbeddingClientError("Text cannot be empty")

        if not self._connected:
            await self.connect()

        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                return await self._execute_request([text])

            except httpx.TimeoutException as exc:
                last_exception = EmbeddingTimeoutError(
                    f"Embedding timeout after {self._config.timeout_seconds}s: {exc}"
                )
                logger.warning(
                    "Embedding timeout (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            except httpx.ConnectError as exc:
                last_exception = EmbeddingConnectionError(
                    f"Connection failed to {self._config.base_url}: {exc}"
                )
                logger.warning(
                    "Embedding connection error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            except httpx.HTTPStatusError as exc:
                # Do not retry on client errors (4xx)
                if (
                    _HTTP_CLIENT_ERROR_MIN
                    <= exc.response.status_code
                    < _HTTP_CLIENT_ERROR_MAX
                ):
                    raise EmbeddingClientError(
                        f"Embedding server client error: "
                        f"{exc.response.status_code} - {exc.response.text}"
                    ) from exc
                last_exception = EmbeddingClientError(
                    f"Embedding server error: {exc.response.status_code}"
                )
                logger.warning(
                    "Embedding server error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            # Exponential backoff (skip on final attempt)
            if attempt < self._config.max_retries:
                delay = self._config.retry_base_delay * (2**attempt)
                logger.debug("Retrying in %.2fs...", delay)
                await asyncio.sleep(delay)

        if last_exception is not None:
            raise last_exception

        raise EmbeddingClientError("Unexpected error: no exception captured")

    async def _execute_request(self, texts: list[str]) -> list[float]:
        """Send POST /v1/embeddings and parse the first embedding response.

        Args:
            texts: List of texts to embed (single element for get_embedding).

        Returns:
            Embedding vector as list of floats for the first input.

        Raises:
            EmbeddingClientError: If client is not connected or response is invalid.
            httpx.HTTPStatusError: If the server returns an error status.
            httpx.TimeoutException: If the request times out.
            httpx.ConnectError: If the connection fails.
        """
        if self._client is None:
            raise EmbeddingClientError("Client is not connected")

        payload: dict[str, str | list[str]] = {
            "input": texts if len(texts) > 1 else texts[0],
            "model": self._model_name,
        }

        response = await self._client.post(self.embeddings_url, json=payload)
        response.raise_for_status()

        data = response.json()
        return self._parse_openai_response(data, expected_count=1)[0]

    async def _execute_batch_request(self, texts: list[str]) -> list[list[float]]:
        """Send POST /v1/embeddings with multiple inputs and parse all embeddings.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors in input order.

        Raises:
            EmbeddingClientError: If client is not connected or response is invalid.
            httpx.HTTPStatusError: If the server returns an error status.
            httpx.TimeoutException: If the request times out.
            httpx.ConnectError: If the connection fails.
        """
        if self._client is None:
            raise EmbeddingClientError("Client is not connected")

        payload: dict[str, str | list[str]] = {
            "input": texts,
            "model": self._model_name,
        }

        response = await self._client.post(self.embeddings_url, json=payload)
        response.raise_for_status()

        data = response.json()
        return self._parse_openai_response(data, expected_count=len(texts))

    def _parse_openai_response(
        self,
        data: dict,  # type: ignore[type-arg]
        *,
        expected_count: int,
    ) -> list[list[float]]:
        """Parse an OpenAI-format embeddings response.

        Expected format:
            {
                "data": [
                    {"embedding": [...], "index": 0},
                    {"embedding": [...], "index": 1},
                    ...
                ],
                "model": "...",
                "usage": {...}
            }

        Args:
            data: Parsed JSON response.
            expected_count: Number of embeddings expected.

        Returns:
            List of embedding vectors sorted by index.

        Raises:
            EmbeddingClientError: If response format is invalid.
        """
        if not isinstance(data, dict) or "data" not in data:
            raise EmbeddingClientError(
                f"Unexpected response format: expected dict with 'data' key, "
                f"got {type(data)}"
            )

        items = data["data"]
        if not isinstance(items, list):
            raise EmbeddingClientError(f"Expected list for 'data', got {type(items)}")

        if len(items) != expected_count:
            raise EmbeddingClientError(
                f"Expected {expected_count} embeddings, got {len(items)}"
            )

        # Sort by index to ensure correct order
        sorted_items = sorted(items, key=lambda x: x.get("index", 0))

        embeddings: list[list[float]] = []
        for item in sorted_items:
            if not isinstance(item, dict) or "embedding" not in item:
                raise EmbeddingClientError(
                    f"Invalid embedding item format: {type(item)}"
                )
            embedding = item["embedding"]
            if not isinstance(embedding, list):
                raise EmbeddingClientError(
                    f"Expected list for embedding, got {type(embedding)}"
                )

            if (
                self._config.embedding_dimension > 0
                and len(embedding) != self._config.embedding_dimension
            ):
                logger.warning(
                    "Embedding dimension mismatch: expected %d, got %d",
                    self._config.embedding_dimension,
                    len(embedding),
                )

            embeddings.append(embedding)

        return embeddings

    async def get_embeddings_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts via a single API call.

        The OpenAI API natively supports batched input, so this sends all
        texts in one request rather than using concurrency control.

        Args:
            texts: List of non-empty texts to embed.

        Returns:
            List of embedding vectors in the same order as input texts.
            Empty list for empty input.

        Raises:
            EmbeddingClientError: If any embedding request fails after all retries.
        """
        if not texts:
            return []

        if not self._connected:
            await self.connect()

        last_exception: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                return await self._execute_batch_request(texts)

            except httpx.TimeoutException as exc:
                last_exception = EmbeddingTimeoutError(
                    f"Batch embedding timeout after "
                    f"{self._config.timeout_seconds}s: {exc}"
                )
                logger.warning(
                    "Batch embedding timeout (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            except httpx.ConnectError as exc:
                last_exception = EmbeddingConnectionError(
                    f"Connection failed to {self._config.base_url}: {exc}"
                )
                logger.warning(
                    "Batch embedding connection error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            except httpx.HTTPStatusError as exc:
                if (
                    _HTTP_CLIENT_ERROR_MIN
                    <= exc.response.status_code
                    < _HTTP_CLIENT_ERROR_MAX
                ):
                    raise EmbeddingClientError(
                        f"Embedding server client error: "
                        f"{exc.response.status_code} - {exc.response.text}"
                    ) from exc
                last_exception = EmbeddingClientError(
                    f"Embedding server error: {exc.response.status_code}"
                )
                logger.warning(
                    "Batch embedding server error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.max_retries + 1,
                    exc,
                )

            # Exponential backoff (skip on final attempt)
            if attempt < self._config.max_retries:
                delay = self._config.retry_base_delay * (2**attempt)
                logger.debug("Retrying in %.2fs...", delay)
                await asyncio.sleep(delay)

        if last_exception is not None:
            raise last_exception

        raise EmbeddingClientError("Unexpected error: no exception captured")

    async def health_check(self) -> bool:
        """Return True if the embedding server is reachable and responding."""
        try:
            await self.get_embedding("health check")
            return True
        except EmbeddingClientError:
            return False


__all__ = [
    "EmbeddingClientLocalOpenAI",
]
