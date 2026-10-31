# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for agent behavior evaluation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


class ModelAgentBehaviorEvalRequest(BaseModel):
    """Request for agent behavior evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    scenarios: list[ModelEvalScenario]
    agent_output: str
