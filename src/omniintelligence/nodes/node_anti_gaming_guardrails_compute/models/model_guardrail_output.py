# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for AntiGamingGuardrailsCompute node (OMN-2563)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_alert_event import (
    ModelAntiGamingAlertUnion,
    ModelDiversityConstraintViolation,
)


class ModelGuardrailOutput(BaseModel):
    """Output from the AntiGamingGuardrailsCompute node.

    Contains all detected alerts and whether the evaluation should be vetoed.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="Run ID that was checked.")

    # Non-blocking alerts (informational)
    alerts: tuple[ModelAntiGamingAlertUnion, ...] = Field(
        default=(),
        description=(
            "Non-blocking anti-gaming alerts (Goodhart, reward hacking, drift). "
            "Do not veto the evaluation."
        ),
    )

    # Diversity violation (VETO — causes evaluation to fail)
    diversity_violation: ModelDiversityConstraintViolation | None = Field(
        default=None,
        description=(
            "Diversity constraint violation, if any. "
            "VETO: presence of this field means the evaluation must be rejected."
        ),
    )

    @property
    def should_veto(self) -> bool:
        """True if the evaluation should be rejected (diversity violation)."""
        return self.diversity_violation is not None

    @property
    def alert_count(self) -> int:
        """Total number of non-blocking alerts raised."""
        return len(self.alerts)


__all__ = ["ModelGuardrailOutput"]
