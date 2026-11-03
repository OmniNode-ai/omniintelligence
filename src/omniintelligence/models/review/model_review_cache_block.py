# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One text block of a review request with its cache TTL (OMN-22343)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.review.model_review_prompt_cache import EnumCacheTtl


class ModelReviewCacheBlock(BaseModel):
    """A text block; a set ``cache_ttl`` ends a cached prefix at this block."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    cache_ttl: EnumCacheTtl | None = Field(default=None)


__all__ = ["ModelReviewCacheBlock"]
