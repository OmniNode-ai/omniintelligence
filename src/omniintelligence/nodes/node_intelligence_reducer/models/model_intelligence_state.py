# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Immutable state snapshot for intelligence reducer operations.

This model is the T_Output type parameter for ModelReducerOutput[ModelIntelligenceState].
It replaces the untyped dict[str, Any] that was previously used as the reducer result,
providing full type safety, schema enforcement, and IDE autocomplete.

Fields capture the FSM state after a reducer operation:
    - Common fields (fsm_type, entity_id, success, action) present in all outputs
    - Transition fields (from_status, to_status, trigger) for state transition context
    - Error fields (error_code, error_message) populated only on failure

Design:
    - Flat model with optional error fields (matches PatternLifecycleTransitionResult pattern)
    - frozen=True for immutability (ONEX pure reducer pattern)
    - extra="forbid" for strict schema enforcement
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelIntelligenceState(BaseModel):
    """Immutable FSM state snapshot returned by intelligence reducer handlers.

    This is the typed result in ModelReducerOutput[ModelIntelligenceState],
    replacing the previous dict[str, Any] usage.

    Attributes:
        fsm_type: The FSM type that was processed (e.g., "PATTERN_LIFECYCLE").
        entity_id: Entity identifier (pattern_id for PATTERN_LIFECYCLE).
        success: Whether the state transition succeeded.
        from_status: Source state before the transition.
        to_status: Target state after the transition (or attempted target on failure).
        trigger: The action/trigger that caused the transition.
        correlation_id: Correlation ID for end-to-end distributed tracing.
        error_code: Machine-readable error code (populated on failure only).
        error_message: Human-readable error message (populated on failure only).
    """

    fsm_type: str = Field(
        ...,
        description="FSM type that was processed (e.g., PATTERN_LIFECYCLE)",
    )
    entity_id: str = Field(
        ...,
        description="Entity identifier (pattern_id for PATTERN_LIFECYCLE)",
    )
    success: bool = Field(
        ...,
        description="Whether the state transition succeeded",
    )
    from_status: str = Field(
        ...,
        description="Source state before the transition",
    )
    to_status: str | None = Field(
        default=None,
        description="Target state after the transition",
    )
    trigger: str = Field(
        ...,
        description="Action/trigger that caused the transition",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for end-to-end distributed tracing",
    )
    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code (failure only)",
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error message (failure only)",
    )

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


__all__ = ["ModelIntelligenceState"]
