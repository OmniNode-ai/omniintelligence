# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol handler adapter and LLM client adapter implementations.

Concrete implementations of the ProtocolHandler protocol for various
transport/wire protocols, plus LLM/API client adapters (moved from clients/
as part of OMN-11584 ONEX taxonomy restructure).

These live outside the nodes/ directory to comply with ONEX I/O audit and
cross-repo validation policies. Nodes receive adapters via dependency injection.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
    - OMN-11584: Restructure bare-noun directories to ONEX taxonomy
"""

from __future__ import annotations

from omniintelligence.adapters.adapter_bolt import BoltHandler
from omniintelligence.adapters.adapter_http_rest import HttpRestHandler
from omniintelligence.adapters.adapter_kafka import KafkaHandler
from omniintelligence.adapters.adapter_postgres import PostgresHandler
from omniintelligence.adapters.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
)
from omniintelligence.adapters.embedding_client_local_openai import (
    EmbeddingClientLocalOpenAI,
)
from omniintelligence.adapters.plan_reviewer_gemini_client import (
    ModelPlanReviewerGeminiConfig,
    PlanReviewerGeminiAuthError,
    PlanReviewerGeminiClient,
    PlanReviewerGeminiClientError,
    PlanReviewerGeminiTimeoutError,
)
from omniintelligence.adapters.plan_reviewer_z_ai_client import (
    ModelPlanReviewerZAIConfig,
    PlanReviewerZAIAuthError,
    PlanReviewerZAIClient,
    PlanReviewerZAIClientError,
    PlanReviewerZAITimeoutError,
)

__all__ = [
    "BoltHandler",
    "EmbeddingClient",
    "EmbeddingClientError",
    "EmbeddingClientLocalOpenAI",
    "EmbeddingConnectionError",
    "EmbeddingTimeoutError",
    "HttpRestHandler",
    "KafkaHandler",
    "ModelPlanReviewerGeminiConfig",
    "ModelPlanReviewerZAIConfig",
    "PostgresHandler",
    "PlanReviewerGeminiAuthError",
    "PlanReviewerGeminiClient",
    "PlanReviewerGeminiClientError",
    "PlanReviewerGeminiTimeoutError",
    "PlanReviewerZAIAuthError",
    "PlanReviewerZAIClient",
    "PlanReviewerZAIClientError",
    "PlanReviewerZAITimeoutError",
]
