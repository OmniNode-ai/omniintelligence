# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelOutput(BaseModel):
    """Normalized dispatch outcome evaluation event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: Literal["PASS", "FAIL", "ERROR"] = Field(
        ...,
        description="Skeleton verdict derived from dispatch status.",
    )
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Future quality score. None for the OMN-10380 skeleton.",
    )
    token_cost: int = Field(
        ...,
        ge=0,
        description="Token cost carried from the source payload.",
    )
    dollars_cost: float = Field(
        ...,
        ge=0.0,
        description="Dollar cost carried from the source payload.",
    )
    model_calls: int = Field(
        ...,
        ge=0,
        description="Model call count carried from the source payload.",
    )
    usage_source: str | None = Field(
        default=None,
        description="Future usage-source marker. None for the OMN-10380 skeleton.",
    )
    estimation_method: str | None = Field(
        default=None,
        description="Future cost estimation method. None for the OMN-10380 skeleton.",
    )
    source_payload_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of the source payload.",
    )
    published_event_id: str | None = Field(
        default=None,
        description="Published event identifier. None until publishing is wired.",
    )
    evaluated_at: AwareDatetime = Field(
        ...,
        description="Timestamp when the dispatch outcome was evaluated.",
    )
    eval_latency_ms: int = Field(
        ...,
        ge=0,
        description="Evaluation latency in milliseconds.",
    )


__all__ = ["ModelOutput"]
