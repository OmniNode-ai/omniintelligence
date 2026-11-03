# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request to lay a review prompt out for the provider's prompt cache (OMN-22343)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_prompt_cache import (
    ModelReviewPromptCache,
)


class ModelReviewCacheLayoutRequest(BaseModel):
    """The built prompt, the voter's focus, and the voter's cache policy.

    Attributes:
        system_prompt: Rubric, catalog and standing rules, focus not yet added.
        user_prompt: The per-PR diff prompt.
        review_focus: The voter's emphasis, the one part that differs per voter.
        cache: The voter's policy (from the overlay).
        wire: ``gateway_markers`` (an OpenAI-compatible Claude gateway splits on
            boundary markers) or ``native_blocks`` (direct Messages call).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    review_focus: str = Field(default="")
    cache: ModelReviewPromptCache
    wire: Literal["gateway_markers", "native_blocks"]


__all__ = ["ModelReviewCacheLayoutRequest"]
