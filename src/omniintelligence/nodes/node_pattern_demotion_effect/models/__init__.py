"""Models for pattern_demotion_effect.

This module exports all input and output models for the pattern demotion
effect node, which checks and demotes validated patterns to deprecated
status based on rolling window failure metrics and cooldown periods.
"""

from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_check_result import (
    ModelDemotionCheckResult,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_gate_snapshot import (
    ModelDemotionGateSnapshot,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_request import (
    ModelDemotionCheckRequest,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_result import (
    ModelDemotionResult,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_effective_thresholds import (
    ModelEffectiveThresholds,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_pattern_deprecated_event import (
    ModelPatternDeprecatedEvent,
)

__all__ = [
    # Request and result models
    "ModelDemotionCheckRequest",
    "ModelDemotionCheckResult",
    # Gate snapshot and threshold models
    "ModelDemotionGateSnapshot",
    "ModelDemotionResult",
    "ModelEffectiveThresholds",
    # Event model
    "ModelPatternDeprecatedEvent",
]
