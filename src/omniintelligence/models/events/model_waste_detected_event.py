# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for LLM waste detection findings."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WasteSeverity = Literal["LOW", "MEDIUM", "HIGH"]


class ModelWasteDetectedEvent(BaseModel):
    """Frozen waste finding event published by Task 10 waste detection."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    session_id: str = Field(min_length=1, description="Source LLM session ID")
    rule_id: str = Field(min_length=1, max_length=64, description="Waste rule ID")
    severity: WasteSeverity = Field(description="LOW, MEDIUM, or HIGH severity")
    waste_tokens: int = Field(ge=0, description="Tokens attributed to waste")
    waste_cost_usd: float = Field(ge=0.0, description="Cost attributed to waste")
    evidence: dict[str, object] = Field(
        default_factory=dict, description="Rule-specific deterministic evidence"
    )
    evidence_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="SHA-256 hash of canonical evidence JSON",
    )
    dedup_key: str = Field(
        min_length=1,
        description="Stable key derived from session_id + rule_id + evidence_hash",
    )
    recommendation: str | None = Field(default=None, description="Remediation advice")
    repo_name: str | None = Field(default=None, description="Attributed repository")
    machine_id: str | None = Field(default=None, description="Attributed machine")
    detected_at: datetime = Field(description="UTC timestamp of detection")

    @field_validator("detected_at")
    @classmethod
    def validate_detected_at_tz_aware(cls, value: datetime) -> datetime:
        """Validate that detected_at is timezone-aware."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("detected_at must be timezone-aware")
        return value


__all__ = ["ModelWasteDetectedEvent", "WasteSeverity"]
