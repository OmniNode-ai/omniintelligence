# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Frozen request for intent drift detection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_drift_detect_compute.models.model_drift_config import (
    ModelDriftSensitivity,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.models.model_intent_drift import (
    ModelIntentDriftInput,
)


class ModelDriftDetectRequest(BaseModel):
    """Tool-call event and sensitivity thresholds for drift detection."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    input_data: ModelIntentDriftInput
    sensitivity: ModelDriftSensitivity


__all__ = ["ModelDriftDetectRequest"]
