import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    FAILURE_MODE_DOMAIN,
    EnumFailureMode,
)


@pytest.mark.unit
def test_failure_mode_total_count() -> None:
    assert len(list(EnumFailureMode)) == 15


@pytest.mark.unit
def test_eval_domain_total_count() -> None:
    assert len(list(EnumEvalDomain)) == 3


@pytest.mark.unit
def test_failure_mode_contract_creation_members() -> None:
    contract_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.CONTRACT_CREATION
    ]
    assert len(contract_modes) == 5
    names = {m.value for m in contract_modes}
    assert names == {
        "requirement_omission",
        "invented_requirements",
        "traceability_failure",
        "paraphrase_instability",
        "compliance_theater",
    }


@pytest.mark.unit
def test_failure_mode_agent_execution_members() -> None:
    agent_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.AGENT_EXECUTION
    ]
    assert len(agent_modes) == 5
    names = {m.value for m in agent_modes}
    assert names == {
        "unsafe_tool_sequencing",
        "false_completion_claims",
        "stale_memory_obedience",
        "refusal_drift",
        "spec_rewriting",
    }


@pytest.mark.unit
def test_failure_mode_memory_system_members() -> None:
    memory_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.MEMORY_SYSTEM
    ]
    assert len(memory_modes) == 5
    names = {m.value for m in memory_modes}
    assert names == {
        "regression_amnesia",
        "over_trust_prior_context",
        "cross_task_contamination",
        "failure_to_surface_memory",
        "incorrect_suppression",
    }


@pytest.mark.unit
def test_failure_mode_domain_mapping_complete() -> None:
    for mode in EnumFailureMode:
        assert mode in FAILURE_MODE_DOMAIN, f"{mode} missing from FAILURE_MODE_DOMAIN"
        assert isinstance(FAILURE_MODE_DOMAIN[mode], EnumEvalDomain)


@pytest.mark.unit
def test_enum_failure_mode_values_are_strings() -> None:
    for mode in EnumFailureMode:
        assert isinstance(mode.value, str)
        assert mode.value == mode.value.lower()


@pytest.mark.unit
def test_enum_eval_domain_values_are_strings() -> None:
    for domain in EnumEvalDomain:
        assert isinstance(domain.value, str)
