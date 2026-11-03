# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Prompt-cache policy of one review voter (OMN-22343).

Declared in the review voters overlay (review_voters_overlay.v1/v2), never in
code. Provider rules this model enforces (Anthropic prompt-caching docs): at
most four ``cache_control`` breakpoints per request; TTL ``5m`` or ``1h``; a
longer TTL must precede a shorter one (render order is tools, system, messages).
Default disabled: a voter that declares nothing sends exactly what it sent.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EnumCacheTtl = Literal["5m", "1h"]


class ModelReviewPromptCache(BaseModel):
    """Which stable blocks of a review request are cached, and for how long.

    Attributes:
        enabled: Lay the request out stable-prefix-first with breakpoints.
        system_ttl: TTL of the cached system blocks (rubric and catalog, then the
            repository's standing rules). None leaves the system uncached.
        diff_ttl: TTL of the cached diff block, which precedes the voter's own
            uncached persona text. None leaves the diff uncached.
        max_breakpoints: Most breakpoints placed (provider limit: four).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=False)
    system_ttl: EnumCacheTtl | None = Field(default="1h")
    diff_ttl: EnumCacheTtl | None = Field(default="5m")
    max_breakpoints: int = Field(default=4, ge=1, le=4)

    @model_validator(mode="after")
    def _longer_ttl_first(self) -> ModelReviewPromptCache:
        if self.system_ttl == "5m" and self.diff_ttl == "1h":
            raise ValueError(
                "a 1h diff entry cannot follow a 5m system entry: the provider "
                "requires longer TTLs to appear first"
            )
        return self


__all__ = ["EnumCacheTtl", "ModelReviewPromptCache"]
