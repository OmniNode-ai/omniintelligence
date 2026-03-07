# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Embedding provider enum for EmbeddingGenerationEffect.

Defines the supported embedding server backends. Each provider uses
a different HTTP API format:

  - QWEN3: Custom /embed endpoint (Qwen3-Embedding-8B-4bit server)
  - LOCAL_OPENAI: OpenAI-compatible /v1/embeddings endpoint (MLX server)

Ticket: OMN-368
"""

from __future__ import annotations

from enum import StrEnum


class EnumEmbeddingProvider(StrEnum):
    """Supported embedding provider backends.

    Attributes:
        QWEN3: Qwen3-Embedding-8B-4bit server with custom /embed endpoint.
        LOCAL_OPENAI: Local OpenAI-compatible server (e.g., MLX) with
            /v1/embeddings endpoint.
    """

    QWEN3 = "qwen3"
    LOCAL_OPENAI = "local_openai"


__all__ = ["EnumEmbeddingProvider"]
