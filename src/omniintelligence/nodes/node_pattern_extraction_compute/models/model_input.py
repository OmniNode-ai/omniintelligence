"""Input Model for Pattern Extraction Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_extraction_config import (
    ModelExtractionConfig,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_session_snapshot import (
    ModelSessionSnapshot,
)


class ModelPatternExtractionInput(BaseModel):
    """Input for the Pattern Extraction Compute node."""

    session_snapshots: tuple[ModelSessionSnapshot, ...] = Field(
        ...,
        min_length=1,
        description="Session snapshots to analyze for patterns",
    )
    options: ModelExtractionConfig = Field(
        default_factory=ModelExtractionConfig,
        description="Extraction configuration options",
    )
    existing_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Existing insights to merge with (for incremental updates)",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternExtractionInput"]
