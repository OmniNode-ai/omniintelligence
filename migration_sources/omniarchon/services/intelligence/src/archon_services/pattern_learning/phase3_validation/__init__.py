"""
Phase 3: Validation Layer - Quality Gate Orchestration

This module provides automated quality gate enforcement for code validation,
implementing 5 comprehensive quality gates:
- ONEX Compliance Gate
- Test Coverage Gate
- Code Quality Gate
- Performance Gate
- Security Gate

Author: Archon Intelligence Team
Date: 2025-10-02
Track: Track 3 Phase 3
"""

from src.archon_services.pattern_learning.phase3_validation.model_contract_quality_gate import (
    EnumGateStatus,
    EnumGateType,
    EnumSeverity,
    ModelContractBase,
    ModelContractOrchestrator,
    ModelContractQualityGate,
    ModelGateConfig,
    ModelIssue,
    ModelQualityGateAggregatedResult,
    ModelQualityGateResult,
    ModelResult,
)
from src.archon_services.pattern_learning.phase3_validation.node_onex_validator_compute import (
    ModelOnexValidationInput,
    ModelOnexValidationOutput,
    NodeOnexValidatorCompute,
)
from src.archon_services.pattern_learning.phase3_validation.node_quality_gate_orchestrator import (
    ModelQualityGateInput,
    ModelQualityGateOutput,
    NodeQualityGateOrchestrator,
)

__all__ = [
    # Orchestrator
    "NodeQualityGateOrchestrator",
    "ModelQualityGateInput",
    "ModelQualityGateOutput",
    # ONEX Validator
    "NodeOnexValidatorCompute",
    "ModelOnexValidationInput",
    "ModelOnexValidationOutput",
    # Contracts and Models
    "ModelContractQualityGate",
    "ModelQualityGateResult",
    "ModelQualityGateAggregatedResult",
    "ModelGateConfig",
    "ModelIssue",
    "ModelResult",
    "ModelContractBase",
    "ModelContractOrchestrator",
    # Enums
    "EnumGateType",
    "EnumGateStatus",
    "EnumSeverity",
]
