# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for NodeMemoryEvalCompute."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


class ModelMemoryEvalInput(BaseModel):
    """Input for memory evaluation compute node.

    Carries all parameters required by handle_memory_evaluation.
    ``judge_caller`` is excluded from serialization and must be provided
    at runtime.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    scenarios: list[ModelEvalScenario] = Field(
        description="Pre-generated MEMORY_SYSTEM evaluation scenarios."
    )
    memory_output: str = Field(description="Agent memory output string to evaluate.")
    memory_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata passed to judge_caller.",
    )
    judge_caller: Callable[[str, str, list[str]], Awaitable[dict[str, Any]]] = Field(
        description="Async judge callable.",
        exclude=True,
    )
