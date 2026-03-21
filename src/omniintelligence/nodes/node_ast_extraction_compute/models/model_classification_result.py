# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Classification result model for deterministic node classification.

Reference: OMN-5674
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelClassificationResult(BaseModel):
    """Result of deterministic node type classification.

    Contains node type, confidence score, and alternatives with scores.
    Simpler than the archived ModelClassificationResult — no template or PRD coupling.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_type: str = Field(
        description="Classified node type (e.g. effect, compute, reducer, orchestrator, unclassified)"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    alternatives: dict[str, float] = Field(
        default_factory=dict,
        description="Alternative classifications with confidence scores",
    )
