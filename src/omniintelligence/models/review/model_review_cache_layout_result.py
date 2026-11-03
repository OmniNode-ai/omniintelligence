# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Result of laying a review prompt out for the prompt cache (OMN-22343)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_cache_block import (
    ModelReviewCacheBlock,
)


class ModelReviewCacheLayoutResult(BaseModel):
    """Marked strings for a gateway, or ordered blocks for a native call.

    Attributes:
        system_prompt: System text (gateway wire; boundary marker before the rules).
        user_prompt: User text (gateway wire; boundary marker before the focus).
        system_blocks: System blocks in order (native wire; empty otherwise).
        user_blocks: User blocks, diff first, focus last (native wire).
        breakpoints: Number of cache_control breakpoints in the native blocks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_prompt: str = Field(default="")
    user_prompt: str = Field(default="")
    system_blocks: tuple[ModelReviewCacheBlock, ...] = Field(default=())
    user_blocks: tuple[ModelReviewCacheBlock, ...] = Field(default=())
    breakpoints: int = Field(default=0, ge=0, le=4)


__all__ = ["ModelReviewCacheLayoutResult"]
