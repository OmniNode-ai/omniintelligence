# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Per-stage search latency sample of the retrieval eval harness."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelStageLatencySample(BaseModel):
    """Per-stage timings for one search.

    Only the embed call is separable from outside ``search()``.  Vector search,
    policy/provenance checks and pack assembly all happen inside that single
    call and are not individually instrumented, so they are reported together as
    ``unseparated_remainder_ms`` rather than split by guesswork.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    embed_ms: float = Field(ge=0.0)
    total_ms: float = Field(ge=0.0)
    unseparated_remainder_ms: float = Field(ge=0.0)


__all__ = ["ModelStageLatencySample"]
