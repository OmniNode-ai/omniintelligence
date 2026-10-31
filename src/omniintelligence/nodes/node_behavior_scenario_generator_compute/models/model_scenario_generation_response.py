# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Response containing generated behavior scenarios."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


class ModelScenarioGenerationResponse(BaseModel):
    """Response containing generated behavior scenarios."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    scenarios: list[ModelEvalScenario]
