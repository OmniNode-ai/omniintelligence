# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reducer intent payload model for Intelligence Reducer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumFSMType, EnumOrchestratorWorkflowType


class ModelReducerIntentPayload(BaseModel):
    """Typed payload for reducer intents.

    Contains the data needed by the intent target (orchestrator, Kafka, etc.).
    """

    # Workflow trigger fields
    operation_type: EnumOrchestratorWorkflowType | None = Field(
        default=None,
        description="Operation type for workflow triggers",
    )
    entity_id: str | None = Field(
        default=None,
        description="Entity ID for the workflow",
    )
    fsm_type: EnumFSMType | None = Field(
        default=None,
        description="FSM type for context",
    )
    current_state: str | None = Field(
        default=None,
        description="Current FSM state",
    )

    # Event publish fields
    topic: str | None = Field(
        default=None,
        description="Kafka topic for event publish intents",
    )
    event_type: str | None = Field(
        default=None,
        description="Event type identifier",
    )
    event_data: str | None = Field(
        default=None,
        description="Serialized event data",
    )

    # Additional context
    source_action: str | None = Field(
        default=None,
        description="The action that triggered this intent",
    )
    priority: int | None = Field(
        default=None,
        description="Priority level for intent processing",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelReducerIntentPayload"]
