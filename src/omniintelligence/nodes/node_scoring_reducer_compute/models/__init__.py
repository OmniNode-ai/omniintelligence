# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Models for ScoringReducerCompute node.

Defines the core objective-function data models per OMN-2537 spec:
  - ObjectiveSpec, GateSpec, ShapedTermSpec
  - ScoreVector, EvaluationResult
  - EvidenceBundle, EvidenceItem
  - Supporting enums: GateType, RewardTargetType, PolicyType, ObjectiveLayer

These models will be promoted to omnibase_core once PR #538 merges.
"""

from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_gate_type import (
    EnumGateType,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_objective_layer import (
    EnumObjectiveLayer,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_policy_type import (
    EnumPolicyType,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_reward_target_type import (
    EnumRewardTargetType,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evaluation_result import (
    ModelEvaluationResult,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
    KNOWN_EVIDENCE_SOURCES,
    ModelEvidenceBundle,
    ModelEvidenceItem,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelGateSpec,
    ModelObjectiveSpec,
    ModelScoreRange,
    ModelShapedTermSpec,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_score_vector import (
    ModelScoreVector,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_scoring_input import (
    ModelScoringInput,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_scoring_output import (
    ModelScoringOutput,
)

__all__ = [
    "EnumGateType",
    "EnumObjectiveLayer",
    "EnumPolicyType",
    "EnumRewardTargetType",
    "KNOWN_EVIDENCE_SOURCES",
    "ModelEvidenceBundle",
    "ModelEvidenceItem",
    "ModelEvaluationResult",
    "ModelGateSpec",
    "ModelObjectiveSpec",
    "ModelScoreRange",
    "ModelScoreVector",
    "ModelShapedTermSpec",
    "ModelScoringInput",
    "ModelScoringOutput",
]
