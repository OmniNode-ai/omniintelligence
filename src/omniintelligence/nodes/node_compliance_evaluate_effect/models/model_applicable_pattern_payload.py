"""Pattern payload model for compliance-evaluate commands.

Ticket: OMN-2339
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelApplicablePatternPayload(BaseModel):
    """A pattern serialized inside a compliance-evaluate command.

    Mirrors the fields that omniclaude places in the Kafka payload for
    each pattern.  Kept separate from ModelApplicablePattern (OMN-2256)
    so the two nodes evolve independently.

    Attributes:
        pattern_id: Unique identifier for the pattern.
        pattern_signature: The pattern signature text.
        domain_id: Domain the pattern belongs to.
        confidence: Confidence score (0.0-1.0).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the pattern",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Pattern signature text describing what the pattern enforces",
    )
    domain_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Domain the pattern belongs to",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the pattern (0.0-1.0)",
    )


__all__ = ["ModelApplicablePatternPayload"]
