# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for NodeContractEvalCompute."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


class ModelContractEvalInput(BaseModel):
    """Input for two-layer contract evaluation compute.

    ``judge_caller`` is excluded from serialization and must be injected by the
    runtime/orchestrator because it owns the LLM client boundary.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    contract_dict: dict[str, Any] = Field(description="Raw contract to evaluate.")
    scenario: ModelEvalScenario = Field(description="Bloom eval scenario context.")
    ticket_requirements: list[str] = Field(
        default_factory=list,
        description="Ticket requirements used for trace coverage validation.",
    )
    judge_caller: Callable[[str, str, list[str]], Awaitable[dict[str, Any]]] = Field(
        description="Async LLM judge callable.",
        exclude=True,
    )


__all__ = ["ModelContractEvalInput"]
