# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for node_dispatch_outcome_eval_effect."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EnumUsageSource(StrEnum):
    """Source quality for token/cost usage attribution."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class ModelCostProvenance(BaseModel):
    """Validated provenance for measured, estimated, or unknown usage."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    usage_source: EnumUsageSource = Field(
        ...,
        description="Whether usage/cost was measured, estimated, or unknown.",
    )
    estimation_method: str | None = Field(
        default=None,
        description="Estimator name or method. Required only for estimated usage.",
    )
    source_payload_hash: str | None = Field(
        default=None,
        description="Stable payload hash. Required only for measured usage.",
    )

    @model_validator(mode="after")
    def validate_source_requirements(self) -> ModelCostProvenance:
        """Require provenance fields that match the declared usage source."""
        if self.usage_source == EnumUsageSource.MEASURED:
            if self.source_payload_hash is None:
                raise ValueError("source_payload_hash is required for measured usage")
            if self.estimation_method is not None:
                raise ValueError("estimation_method must be null for measured usage")
            return self

        if self.usage_source == EnumUsageSource.ESTIMATED:
            if self.estimation_method is None:
                raise ValueError("estimation_method is required for estimated usage")
            if self.source_payload_hash is not None:
                raise ValueError("source_payload_hash must be null for estimated usage")
            return self

        if self.estimation_method is not None:
            raise ValueError("estimation_method must be null for unknown usage")
        if self.source_payload_hash is not None:
            raise ValueError("source_payload_hash must be null for unknown usage")
        return self


class ModelCallRecord(BaseModel):
    """Single model call attribution record for a dispatch completion event."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    cost_dollars: float = Field(default=0.0, ge=0.0)
    cost_provenance: ModelCostProvenance = Field(
        default_factory=lambda: ModelCostProvenance(
            usage_source=EnumUsageSource.UNKNOWN
        ),
    )


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
    model_calls: list[ModelCallRecord] = Field(
        default_factory=list,
        description="Model calls attributed to the dispatch.",
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
    cost_provenance: ModelCostProvenance = Field(
        ...,
        description="Envelope-level rollup of the model call cost provenance.",
    )


__all__ = [
    "EnumUsageSource",
    "ModelCallRecord",
    "ModelCostProvenance",
    "ModelInput",
]
