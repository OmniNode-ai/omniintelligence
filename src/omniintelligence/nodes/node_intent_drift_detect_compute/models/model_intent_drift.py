# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Frozen input/output models for the intent drift detect compute node.

Input:  ModelIntentDriftInput  — tool call event correlated with active intent
Output: ModelIntentDriftSignal — detected drift (or None when clean)

Schema Rules:
    - frozen=True (events are immutable after emission)
    - extra="forbid" (reject unknown fields)
    - from_attributes=True (pytest-xdist worker compatibility)
    - No datetime.now() defaults

Drift signal emitted to: onex.evt.intent.drift.detected.v1

Reference: OMN-2489
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict, Field


class ModelIntentDriftInput(BaseModel):
    """Input for the intent drift detect compute node.

    Represents a single tool-call event correlated with the active intent for
    the session. Drift detection runs per-tool-call, not in batches.

    Attributes:
        session_id: Session ID being monitored.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The active (classified) intent class for this session.
        tool_name: Name of the tool that was called (e.g. "Bash", "Write").
        files_modified: Paths of files touched in this tool call (may be empty).
        detected_at: Timestamp of the tool-call event (injected by caller).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    session_id: str = Field(..., description="Session ID being monitored")
    correlation_id: UUID = Field(
        ..., description="Correlation ID for distributed tracing"
    )
    intent_class: EnumIntentClass = Field(
        ..., description="The active (classified) intent class for this session"
    )
    tool_name: str = Field(
        ..., description="Name of the tool that was called (e.g. Bash, Write, Read)"
    )
    files_modified: list[str] = Field(
        default_factory=list,
        description="Paths of files touched in this tool call",
    )
    detected_at: datetime = Field(
        ...,
        description=(
            "Timestamp of the tool-call event. "
            "Must NOT use datetime.now() as default — callers inject explicitly."
        ),
    )


class ModelIntentDriftSignal(BaseModel):
    """Frozen drift signal emitted when tool behaviour diverges from declared intent.

    Published to onex.evt.intent.drift.detected.v1 when drift threshold is exceeded.
    Detection is observational only — it never blocks execution.

    Severity levels:
        info    — minor deviation; log only
        warning — notable deviation; operators should review
        alert   — strong divergence; immediate attention advised

    Attributes:
        event_type: Literal discriminator.
        session_id: Session ID where drift was detected.
        correlation_id: Correlation ID for distributed tracing.
        intent_class: The active intent class at time of detection.
        drift_type: Category of drift detected.
        severity: Severity of the drift signal.
        tool_name: The tool call that triggered drift detection.
        files_modified: Files touched by the triggering tool call.
        reason: Human-readable explanation of why drift was flagged.
        detected_at: Timestamp of the triggering tool-call event.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_type: Literal["IntentDriftSignal"] = "IntentDriftSignal"
    session_id: str = Field(..., description="Session ID where drift was detected")
    correlation_id: UUID = Field(
        ..., description="Correlation ID for distributed tracing"
    )
    intent_class: EnumIntentClass = Field(
        ..., description="The active intent class at time of detection"
    )
    drift_type: Literal["tool_mismatch", "file_surface", "scope_expansion"] = Field(
        ...,
        description=(
            "Category of drift: "
            "tool_mismatch=tool inconsistent with intent, "
            "file_surface=files outside expected scope, "
            "scope_expansion=execution scope grew beyond intent boundary"
        ),
    )
    severity: Literal["info", "warning", "alert"] = Field(
        ...,
        description="Severity: info=log only, warning=review advised, alert=immediate attention",
    )
    tool_name: str = Field(
        ..., description="The tool call that triggered drift detection"
    )
    files_modified: list[str] = Field(
        default_factory=list,
        description="Files touched by the triggering tool call",
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of why drift was flagged",
    )
    detected_at: datetime = Field(
        ...,
        description=(
            "Timestamp of the triggering tool-call event. "
            "Must NOT use datetime.now() as default — callers inject explicitly."
        ),
    )


__all__ = [
    "ModelIntentDriftInput",
    "ModelIntentDriftSignal",
]
