# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event payload models for Kafka events.

This module contains Pydantic models for Kafka event payloads used in
the OmniIntelligence event bus:

Code analysis topics:
- ModelCodeAnalysisRequestPayload: Incoming analysis request events
- ModelCodeAnalysisCompletedPayload: Successful analysis result events
- ModelCodeAnalysisFailedPayload: Failed analysis error events

Intent Intelligence topics (OMN-2487):
- ModelIntentClassifiedEnvelope: onex.evt.intent.classified.v1
- ModelIntentDriftDetectedEnvelope: onex.evt.intent.drift.detected.v1
- ModelIntentOutcomeLabeledEnvelope: onex.evt.intent.outcome.labeled.v1
- ModelIntentPatternPromotedEnvelope: onex.evt.intent.pattern.promoted.v1

Migration Note:
    Code analysis models were extracted from the monolithic
    node_intelligence_adapter_effect.py as part of OMN-1437.
"""

from omniintelligence.models.events.model_code_analysis_completed import (
    ModelCodeAnalysisCompletedPayload,
)
from omniintelligence.models.events.model_code_analysis_failed import (
    ModelCodeAnalysisFailedPayload,
)
from omniintelligence.models.events.model_code_analysis_request import (
    ModelCodeAnalysisRequestPayload,
)
from omniintelligence.models.events.model_intent_event_envelopes import (
    ModelIntentClassifiedEnvelope,
    ModelIntentDriftDetectedEnvelope,
    ModelIntentOutcomeLabeledEnvelope,
    ModelIntentPatternPromotedEnvelope,
)
from omniintelligence.models.events.model_pattern_discovered_event import (
    ModelPatternDiscoveredEvent,
)
from omniintelligence.models.events.model_pattern_lifecycle_event import (
    ModelPatternLifecycleEvent,
)
from omniintelligence.models.events.model_pattern_projection_event import (
    ModelPatternProjectionEvent,
)

__all__ = [
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
    "ModelIntentClassifiedEnvelope",
    "ModelIntentDriftDetectedEnvelope",
    "ModelIntentOutcomeLabeledEnvelope",
    "ModelIntentPatternPromotedEnvelope",
    "ModelPatternDiscoveredEvent",
    "ModelPatternLifecycleEvent",
    "ModelPatternProjectionEvent",
]
