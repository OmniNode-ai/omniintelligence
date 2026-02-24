# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""HTTP clients for omniintelligence infrastructure.

These clients live outside the nodes/ directory so that ARCH-002 applies only
to the node business logic. Nodes must never import transport libraries directly;
they receive clients via dependency injection.
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
