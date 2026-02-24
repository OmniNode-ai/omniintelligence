# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Intent Drift Detect Compute Node — thin shell delegating to handler.

Detects when tool calls or file changes diverge from the declared intent class.
Returns a frozen ModelIntentDriftSignal when drift is detected, or None when clean.

Detection is observational only — it NEVER blocks execution.
Signals should be emitted to onex.evt.intent.drift.detected.v1 by the caller
(e.g. an orchestrator or effect node).

Reference: OMN-2489
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_intent_drift_detect_compute.handlers import (
    detect_drift,
)
from omniintelligence.nodes.node_intent_drift_detect_compute.models import (
    DriftDetectionSettings,
    ModelDriftSensitivity,
    ModelIntentDriftInput,
    ModelIntentDriftSignal,
)


class NodeIntentDriftDetectCompute(
    NodeCompute[ModelIntentDriftInput, ModelIntentDriftSignal | None]
):
    """Pure compute node for intent drift detection.

    Classifies each tool-call event for drift against the active session intent.
    Sensitivity thresholds are loaded from environment via DriftDetectionSettings
    on each compute call (settings are cheap to construct and reads env vars).

    This node is a thin shell following the ONEX declarative pattern.
    All detection logic is delegated to the handler function.

    Detection is observational only — it NEVER blocks execution.
    """

    async def compute(
        self, input_data: ModelIntentDriftInput
    ) -> ModelIntentDriftSignal | None:
        """Classify a tool-call event for drift.

        Sensitivity thresholds are loaded from environment on each call via
        DriftDetectionSettings, allowing runtime reconfiguration.

        Args:
            input_data: Frozen drift detection input with session, intent, and
                tool call information.

        Returns:
            Frozen ModelIntentDriftSignal if drift is detected, else None.
            Never raises — detection is always non-blocking.
        """
        sensitivity: ModelDriftSensitivity = DriftDetectionSettings().to_sensitivity()
        return detect_drift(input_data, sensitivity)


__all__ = ["NodeIntentDriftDetectCompute"]
