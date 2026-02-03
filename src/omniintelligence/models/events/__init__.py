"""Event payload models for code analysis Kafka events.

This module contains Pydantic models for Kafka event payloads used in
the OmniIntelligence code analysis event bus:

- ModelCodeAnalysisRequestPayload: Incoming analysis request events
- ModelCodeAnalysisCompletedPayload: Successful analysis result events
- ModelCodeAnalysisFailedPayload: Failed analysis error events

These models define the contracts for the following Kafka topics:
- dev.archon-intelligence.intelligence.code-analysis-requested.v1
- dev.archon-intelligence.intelligence.code-analysis-completed.v1
- dev.archon-intelligence.intelligence.code-analysis-failed.v1

Migration Note:
    These models were extracted from the monolithic
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
from omniintelligence.models.events.model_pattern_lifecycle_event import (
    ModelPatternLifecycleEvent,
)

__all__ = [
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
    "ModelPatternLifecycleEvent",
]
