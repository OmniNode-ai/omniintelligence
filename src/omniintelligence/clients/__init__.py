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
from omniintelligence.clients.embedding_client_local_openai import (
    EmbeddingClientLocalOpenAI,
)
from omniintelligence.clients.plan_reviewer_gemini_client import (
    ModelPlanReviewerGeminiConfig,
    PlanReviewerGeminiAuthError,
    PlanReviewerGeminiClient,
    PlanReviewerGeminiClientError,
    PlanReviewerGeminiTimeoutError,
)
from omniintelligence.clients.plan_reviewer_z_ai_client import (
    ModelPlanReviewerZAIConfig,
    PlanReviewerZAIAuthError,
    PlanReviewerZAIClient,
    PlanReviewerZAIClientError,
    PlanReviewerZAITimeoutError,
)

__all__ = [
    "EmbeddingClient",
    "EmbeddingClientError",
    "EmbeddingClientLocalOpenAI",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
    "ModelPlanReviewerGeminiConfig",
    "ModelPlanReviewerZAIConfig",
    "PlanReviewerGeminiAuthError",
    "PlanReviewerGeminiClient",
    "PlanReviewerGeminiClientError",
    "PlanReviewerGeminiTimeoutError",
    "PlanReviewerZAIAuthError",
    "PlanReviewerZAIClient",
    "PlanReviewerZAIClientError",
    "PlanReviewerZAITimeoutError",
]
