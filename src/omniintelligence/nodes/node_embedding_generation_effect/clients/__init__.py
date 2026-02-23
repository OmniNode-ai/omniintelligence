# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Re-exports for EmbeddingClient from omniintelligence.clients.

The EmbeddingClient implementation lives in omniintelligence.clients (outside
nodes/) to comply with ARCH-002 — nodes must not import transport libraries
(httpx, aiohttp, etc.) directly. This module re-exports the client so that
existing node-level imports continue to work.
"""

from __future__ import annotations

from omniintelligence.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
)

__all__ = [
    "EmbeddingClient",
    "EmbeddingClientError",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
]
