# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for CI error classifier compute node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCiErrorClassifierOutput(BaseModel):
    """Output for NodeCiErrorClassifierCompute."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    classification: str = Field(description="Normalized error taxonomy value.")
    confidence: float = Field(
        description="Confidence in classification, clamped to [0.0, 1.0]."
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence snippets supporting the classification.",
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description="Items the classifier could not determine.",
    )


__all__ = ["ModelCiErrorClassifierOutput"]
