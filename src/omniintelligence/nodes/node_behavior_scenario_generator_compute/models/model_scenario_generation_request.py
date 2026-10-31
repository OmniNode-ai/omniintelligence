# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for behavior scenario generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_behavior_spec import (
    ModelBehaviorSpec,
)


class ModelScenarioGenerationRequest(BaseModel):
    """Request for behavior scenario generation."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    spec: ModelBehaviorSpec
    n: int
