# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Async embedding client for Qwen3-Embedding-8B-4bit server (port 8100).

Provides an async HTTP client for generating 1024-dimensional text embeddings
via the MLX Qwen3-Embedding server. The client supports connection pooling,
automatic retries with exponential backoff, and semaphore-based concurrency
control for batch operations.

This client lives in omniintelligence.clients (not inside nodes/) to comply
with ARCH-002, which prohibits nodes from importing transport libraries
directly. Nodes receive clients via dependency injection.

Endpoint: `LLM_EMBEDDING_URL` env var → `http://192.168.86.200:8100`
Model: Qwen3-Embedding-8B-4bit | Dimension: 1024 | Distance: Cosine

Example:
    ```python
    import os
    from omniintelligence.clients import EmbeddingClient
    from omniintelligence.nodes.node_embedding_generation_effect.models import (
        ModelEmbeddingClientConfig,
    )

    config = ModelEmbeddingClientConfig(
        base_url=os.environ["LLM_EMBEDDING_URL"]
    )
    async with EmbeddingClient(config) as client:
        embeddings = await client.get_embeddings_batch(["Hello", "World"])
        assert len(embeddings[0]) == 1024
    ```

Ticket: OMN-2392
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
    ModelEmbeddingClientConfig,
)

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

# HTTP status code boundaries for error classification
_HTTP_CLIENT_ERROR_MIN = 400
_HTTP_CLIENT_ERROR_MAX = 500  # Exclusive (4xx range)


class EmbeddingClientError(Exception):
    """Base exception for embedding client errors."""


class EmbeddingConnectionError(EmbeddingClientError):
    """Raised when connection to the embedding server fails."""


class EmbeddingTimeoutError(EmbeddingClientError):
    """Raised when an embedding request times out."""


class EmbeddingClient:
    """Async client for Qwen3-Embedding server with connection pooling.

    Maintains a persistent httpx.AsyncClient for connection reuse, which
    significantly improves throughput for batch embedding operations.

    Supports both context manager and manual lifecycle management.

    Example (context manager):
        ```python
        config = ModelEmbeddingClientConfig(base_url="http://192.168.86.200:8100")
        async with EmbeddingClient(config) as client:
            embedding = await client.get_embedding("Hello world")
            assert len(embedding) == 1024
        ```

    Example (manual lifecycle):
        ```python
        config = ModelEmbeddingClientConfig(base_url="http://192.168.86.200:8100")
        client = EmbeddingClient(config)
        await client.connect()
        try:
            embeddings = await client.get_embeddings_batch(["a", "b", "c"])
        finally:
            await client.close()
        ```
    """

    def __init__(self, config: ModelEmbeddingClientConfig) -> None:
        self._config = config
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
    def embed_url(self) -> str:
        """Full URL for the /embed endpoint."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/embed"

    async def connect(self) -> None:
        """Open the connection pool. Safe to call multiple times (idempotent)."""
        if self._connected:
            return
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeout_seconds),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._connected = True
        logger.debug("EmbeddingClient connected to %s", self._config.base_url)

    async def close(self) -> None:
        """Close the connection pool. Safe to call multiple times (idempotent)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.debug("EmbeddingClient connection closed")

    async def __aenter__(self) -> EmbeddingClient:
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
        """Generate a 1024-dimensional embedding vector for the given text.

        Retries on transient failures with exponential backoff. Does NOT
        retry on client errors (4xx).

        Args:
            text: Non-empty text to embed.

        Returns:
            A list of floats (1024-dimensional embedding vector).

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
                return await self._execute_request(text)

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

    async def _execute_request(self, text: str) -> list[float]:
        """Send POST /embed and parse the embedding response.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            EmbeddingClientError: If client is not connected or response is invalid.
            httpx.HTTPStatusError: If the server returns an error status.
            httpx.TimeoutException: If the request times out.
            httpx.ConnectError: If the connection fails.
        """
        if self._client is None:
            raise EmbeddingClientError("Client is not connected")

        response = await self._client.post(self.embed_url, json={"text": text})
        response.raise_for_status()

        data = response.json()

        embedding: list[float]
        if isinstance(data, list):
            embedding = data
        elif isinstance(data, dict) and "embedding" in data:
            embedding = data["embedding"]
        else:
            raise EmbeddingClientError(
                f"Unexpected response format from embedding server: {type(data)}"
            )

        if not isinstance(embedding, list):
            raise EmbeddingClientError(
                f"Expected list for embedding, got {type(embedding)}"
            )

        if len(embedding) != self._config.embedding_dimension:
            logger.warning(
                "Embedding dimension mismatch: expected %d, got %d",
                self._config.embedding_dimension,
                len(embedding),
            )

        return embedding

    async def get_embeddings_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts with controlled concurrency.

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

        semaphore = asyncio.Semaphore(self._config.max_concurrency)

        async def _embed_one(text: str) -> list[float]:
            async with semaphore:
                return await self.get_embedding(text)

        tasks = [_embed_one(text) for text in texts]
        return await asyncio.gather(*tasks)

    async def health_check(self) -> bool:
        """Return True if the embedding server is reachable and responding."""
        try:
            await self.get_embedding("health check")
            return True
        except EmbeddingClientError:
            return False


__all__ = [
    "EmbeddingClient",
    "EmbeddingClientError",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
]
