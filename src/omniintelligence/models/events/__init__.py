"""Event payload models for intelligence adapter events.

This module contains Pydantic models for Kafka event payloads used by
the intelligence adapter node:

- ModelCodeAnalysisRequestPayload: Incoming analysis request events
- ModelCodeAnalysisCompletedPayload: Successful analysis result events
- ModelCodeAnalysisFailedPayload: Failed analysis error events

These models are referenced by the contract.yaml consumed_events and
published_events sections.

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

__all__ = [
    "ModelCodeAnalysisCompletedPayload",
    "ModelCodeAnalysisFailedPayload",
    "ModelCodeAnalysisRequestPayload",
]
