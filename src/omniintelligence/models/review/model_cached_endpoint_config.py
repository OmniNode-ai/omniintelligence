# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A review voter's endpoint config plus its prompt-cache policy (OMN-22343)."""

from __future__ import annotations

from pydantic import Field

from omniintelligence.models.review.model_review_prompt_cache import (
    ModelReviewPromptCache,
)
from omniintelligence.review_pairing.models_external_review import ModelEndpointConfig


class ModelCachedEndpointConfig(ModelEndpointConfig):
    """``ModelEndpointConfig`` of an overlay voter, with the overlay's policy.

    The registry's own entries stay plain ``ModelEndpointConfig`` and send what
    they always sent; only a voter resolved from the overlay carries a policy.
    """

    prompt_cache: ModelReviewPromptCache = Field(
        default_factory=ModelReviewPromptCache,
        description="Which stable blocks the provider caches, from the overlay.",
    )


__all__ = ["ModelCachedEndpointConfig"]
