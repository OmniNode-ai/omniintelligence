# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for memory evaluation."""

from __future__ import annotations

from omnibase_core.types import JsonType
from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


class ModelMemoryEvalRequest(BaseModel):
    """Request for memory evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    scenarios: list[ModelEvalScenario]
    memory_output: str
    memory_context: dict[str, JsonType]
