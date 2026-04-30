# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelInput(BaseModel):
    """Dispatch worker completion event consumed from omniclaude."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    task_id: str = Field(
        ...,
        min_length=1,
        description="Task identifier associated with the dispatch.",
    )
    dispatch_id: str = Field(
        ...,
        min_length=1,
        description="Dispatch identifier for this worker execution.",
    )
    ticket_id: str | None = Field(
        default=None,
        description="Optional ticket identifier associated with the dispatch.",
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Terminal dispatch status from the producer.",
    )
    artifact_path: str | None = Field(
        default=None,
        description="Optional path to the dispatch artifact.",
    )
    model_calls: int = Field(
        ...,
        ge=0,
        description="Number of model calls attributed to the dispatch.",
    )
    token_cost: int = Field(
        ...,
        ge=0,
        description="Token cost attributed to the dispatch.",
    )
    dollars_cost: float = Field(
        ...,
        ge=0.0,
        description="Dollar cost attributed to the dispatch.",
    )


__all__ = ["ModelInput"]
