# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Domain candidate model for pattern classification."""

from pydantic import BaseModel, ConfigDict, Field


class ModelDomainCandidate(BaseModel):
    """A candidate domain classification with its confidence score.

    Represents one entry in the domain_candidates JSONB array stored
    in the learned_patterns table. Each candidate pairs a domain
    identifier with a confidence score indicating how well the
    pattern matches that domain.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    domain: str = Field(..., description="Domain identifier for this candidate")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this domain classification",
    )


__all__ = ["ModelDomainCandidate"]
