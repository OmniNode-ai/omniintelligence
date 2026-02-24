# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Drift detection sensitivity configuration.

Defines per-drift-type thresholds and per-intent-class tool allowlists.
All values are conservative defaults (warn on suspicious, not alert).

Reference: OMN-2489
"""

from __future__ import annotations

from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Per-intent-class tool allowlists
# ---------------------------------------------------------------------------
# Tools in the "expected" set are normal for this intent.
# Tools in the "suspicious" set trigger tool_mismatch drift.
# FEATURE has an empty suspicious set — it has broad scope.
# ---------------------------------------------------------------------------
_TOOL_ALLOWLISTS: dict[EnumIntentClass, set[str]] = {
    EnumIntentClass.BUGFIX: {"Read", "Grep", "Edit", "Bash"},
    EnumIntentClass.DOCUMENTATION: {"Write", "Read"},
    EnumIntentClass.SECURITY: {"Read", "Grep", "Bash"},
    EnumIntentClass.REFACTOR: {"Read", "Edit", "Grep"},
    EnumIntentClass.FEATURE: {"Read", "Write", "Edit", "Bash", "Glob"},
    EnumIntentClass.ANALYSIS: {"Read", "Grep", "Glob", "Bash"},
    EnumIntentClass.CONFIGURATION: {"Read", "Edit", "Write", "Bash"},
    EnumIntentClass.MIGRATION: {"Read", "Edit", "Write", "Bash", "Glob"},
}

# Tools that are suspicious (but not necessarily blocked) per intent class.
# FEATURE is intentionally empty — broad scope is expected.
_SUSPICIOUS_TOOLS: dict[EnumIntentClass, set[str]] = {
    EnumIntentClass.BUGFIX: {"Write"},
    EnumIntentClass.DOCUMENTATION: {"Bash", "Edit"},
    EnumIntentClass.SECURITY: {"Edit", "Write"},
    EnumIntentClass.REFACTOR: {"Write"},
    EnumIntentClass.FEATURE: set(),  # no restrictions — broad scope
    EnumIntentClass.ANALYSIS: {"Write", "Edit"},
    EnumIntentClass.CONFIGURATION: set(),  # configuration needs broad write access
    EnumIntentClass.MIGRATION: set(),  # migration needs broad write access
}


def get_tool_allowlist(intent_class: EnumIntentClass) -> set[str]:
    """Return the expected tool set for the given intent class."""
    return _TOOL_ALLOWLISTS.get(intent_class, set())


def get_suspicious_tools(intent_class: EnumIntentClass) -> set[str]:
    """Return suspicious tools for the given intent class."""
    return _SUSPICIOUS_TOOLS.get(intent_class, set())


class ModelDriftSensitivity(BaseModel):
    """Per-drift-type sensitivity thresholds.

    Thresholds map to severity:
        [0.0, 0.33)  -> info
        [0.33, 0.66) -> warning
        [0.66, 1.0]  -> alert

    Attributes:
        tool_mismatch_threshold: Sensitivity for tool_mismatch drift (0.0=silent, 1.0=hair-trigger).
        file_surface_threshold: Sensitivity for file_surface drift.
        scope_expansion_threshold: Sensitivity for scope_expansion drift.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    tool_mismatch_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sensitivity for tool_mismatch drift (0.0=off, 1.0=max sensitivity)",
    )
    file_surface_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Sensitivity for file_surface drift",
    )
    scope_expansion_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Sensitivity for scope_expansion drift",
    )


class DriftDetectionSettings(BaseSettings):
    """Pydantic Settings for drift detection — loaded from environment.

    All drift thresholds are configurable via environment variables.
    Defaults are conservative (warn on suspicious patterns, not alert).

    Environment variables:
        DRIFT_TOOL_MISMATCH_THRESHOLD: float (default 0.5)
        DRIFT_FILE_SURFACE_THRESHOLD: float (default 0.4)
        DRIFT_SCOPE_EXPANSION_THRESHOLD: float (default 0.6)
    """

    model_config = SettingsConfigDict(
        env_prefix="DRIFT_",
        extra="ignore",
    )

    tool_mismatch_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sensitivity for tool_mismatch drift",
    )
    file_surface_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Sensitivity for file_surface drift",
    )
    scope_expansion_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Sensitivity for scope_expansion drift",
    )

    def to_sensitivity(self) -> ModelDriftSensitivity:
        """Convert settings to a frozen ModelDriftSensitivity instance."""
        return ModelDriftSensitivity(
            tool_mismatch_threshold=self.tool_mismatch_threshold,
            file_surface_threshold=self.file_surface_threshold,
            scope_expansion_threshold=self.scope_expansion_threshold,
        )


__all__ = [
    "DriftDetectionSettings",
    "ModelDriftSensitivity",
    "get_suspicious_tools",
    "get_tool_allowlist",
]
