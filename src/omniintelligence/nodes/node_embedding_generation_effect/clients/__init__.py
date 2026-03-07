# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Re-exports for embedding clients from omniintelligence.clients.

The embedding client implementations live in omniintelligence.clients (outside
nodes/) to comply with ARCH-002 — nodes must not import transport libraries
(httpx, aiohttp, etc.) directly. This module re-exports the clients so that
existing node-level imports continue to work.
"""

from __future__ import annotations

from omniintelligence.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
)
from omniintelligence.clients.embedding_client_local_openai import (
    EmbeddingClientLocalOpenAI,
)

__all__ = [
    "EmbeddingClient",
    "EmbeddingClientError",
    "EmbeddingClientLocalOpenAI",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
]
