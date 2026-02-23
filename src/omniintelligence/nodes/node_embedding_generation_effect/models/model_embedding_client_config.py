# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Configuration model for the embedding HTTP client.

Ticket: OMN-2392
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelEmbeddingClientConfig(BaseModel):
    """Configuration for the embedding server HTTP client.

    Attributes:
        base_url: Base URL for the Qwen3-Embedding server (from LLM_EMBEDDING_URL).
        embedding_dimension: Expected dimension of embedding vectors (default: 1024).
        timeout_seconds: HTTP request timeout in seconds.
        max_retries: Maximum number of retry attempts per request.
        retry_base_delay: Base delay in seconds for exponential backoff.
        max_concurrency: Maximum concurrent embedding requests.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    base_url: str = Field(description="Base URL for the Qwen3-Embedding server.")
    embedding_dimension: int = Field(
        default=1024,
        description="Expected dimension of embedding vectors.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds.",
    )
    max_retries: int = Field(
        default=5,
        description="Maximum number of retry attempts per request.",
    )
    retry_base_delay: float = Field(
        default=0.5,
        description="Base delay in seconds for exponential backoff.",
    )
    max_concurrency: int = Field(
        default=5,
        description="Maximum number of concurrent embedding requests.",
    )


__all__ = ["ModelEmbeddingClientConfig"]
