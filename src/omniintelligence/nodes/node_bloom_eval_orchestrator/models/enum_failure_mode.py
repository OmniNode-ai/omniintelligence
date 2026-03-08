from enum import Enum

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)


class EnumFailureMode(str, Enum):
    """All 15 failure modes across 3 evaluation domains.

    Each member maps to exactly one EnumEvalDomain via FAILURE_MODE_DOMAIN.
    The enum value is the canonical string identifier used in BehaviorSpec YAML.
    """

    # CONTRACT_CREATION (5)
    REQUIREMENT_OMISSION = "requirement_omission"
    INVENTED_REQUIREMENTS = "invented_requirements"
    TRACEABILITY_FAILURE = "traceability_failure"
    PARAPHRASE_INSTABILITY = "paraphrase_instability"
    COMPLIANCE_THEATER = "compliance_theater"

    # AGENT_EXECUTION (5)
    UNSAFE_TOOL_SEQUENCING = "unsafe_tool_sequencing"
    FALSE_COMPLETION_CLAIMS = "false_completion_claims"
    STALE_MEMORY_OBEDIENCE = "stale_memory_obedience"
    REFUSAL_DRIFT = "refusal_drift"
    SPEC_REWRITING = "spec_rewriting"

    # MEMORY_SYSTEM (5)
    REGRESSION_AMNESIA = "regression_amnesia"
    OVER_TRUST_PRIOR_CONTEXT = "over_trust_prior_context"
    CROSS_TASK_CONTAMINATION = "cross_task_contamination"
    FAILURE_TO_SURFACE_MEMORY = "failure_to_surface_memory"
    INCORRECT_SUPPRESSION = "incorrect_suppression"


FAILURE_MODE_DOMAIN: dict[EnumFailureMode, EnumEvalDomain] = {
    EnumFailureMode.REQUIREMENT_OMISSION: EnumEvalDomain.CONTRACT_CREATION,
    EnumFailureMode.INVENTED_REQUIREMENTS: EnumEvalDomain.CONTRACT_CREATION,
    EnumFailureMode.TRACEABILITY_FAILURE: EnumEvalDomain.CONTRACT_CREATION,
    EnumFailureMode.PARAPHRASE_INSTABILITY: EnumEvalDomain.CONTRACT_CREATION,
    EnumFailureMode.COMPLIANCE_THEATER: EnumEvalDomain.CONTRACT_CREATION,
    EnumFailureMode.UNSAFE_TOOL_SEQUENCING: EnumEvalDomain.AGENT_EXECUTION,
    EnumFailureMode.FALSE_COMPLETION_CLAIMS: EnumEvalDomain.AGENT_EXECUTION,
    EnumFailureMode.STALE_MEMORY_OBEDIENCE: EnumEvalDomain.AGENT_EXECUTION,
    EnumFailureMode.REFUSAL_DRIFT: EnumEvalDomain.AGENT_EXECUTION,
    EnumFailureMode.SPEC_REWRITING: EnumEvalDomain.AGENT_EXECUTION,
    EnumFailureMode.REGRESSION_AMNESIA: EnumEvalDomain.MEMORY_SYSTEM,
    EnumFailureMode.OVER_TRUST_PRIOR_CONTEXT: EnumEvalDomain.MEMORY_SYSTEM,
    EnumFailureMode.CROSS_TASK_CONTAMINATION: EnumEvalDomain.MEMORY_SYSTEM,
    EnumFailureMode.FAILURE_TO_SURFACE_MEMORY: EnumEvalDomain.MEMORY_SYSTEM,
    EnumFailureMode.INCORRECT_SUPPRESSION: EnumEvalDomain.MEMORY_SYSTEM,
}
