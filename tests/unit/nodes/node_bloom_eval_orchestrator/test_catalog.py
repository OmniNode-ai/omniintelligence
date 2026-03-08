from uuid import UUID

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.catalog import (
    BEHAVIOR_SPEC_CATALOG,
    get_spec,
    list_specs,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    FAILURE_MODE_DOMAIN,
    EnumFailureMode,
)


@pytest.mark.unit
def test_catalog_has_15_specs() -> None:
    assert len(BEHAVIOR_SPEC_CATALOG) == 15


@pytest.mark.unit
def test_list_specs_returns_15() -> None:
    assert len(list_specs()) == 15


@pytest.mark.unit
def test_get_spec_requirement_omission_uuid() -> None:
    spec = get_spec(EnumFailureMode.REQUIREMENT_OMISSION)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000001")


@pytest.mark.unit
def test_get_spec_invented_requirements_uuid() -> None:
    spec = get_spec(EnumFailureMode.INVENTED_REQUIREMENTS)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000002")


@pytest.mark.unit
def test_get_spec_compliance_theater_uuid() -> None:
    spec = get_spec(EnumFailureMode.COMPLIANCE_THEATER)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000005")


@pytest.mark.unit
def test_get_spec_unsafe_tool_sequencing_uuid() -> None:
    spec = get_spec(EnumFailureMode.UNSAFE_TOOL_SEQUENCING)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000006")


@pytest.mark.unit
def test_get_spec_spec_rewriting_uuid() -> None:
    spec = get_spec(EnumFailureMode.SPEC_REWRITING)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000010")


@pytest.mark.unit
def test_get_spec_regression_amnesia_uuid() -> None:
    spec = get_spec(EnumFailureMode.REGRESSION_AMNESIA)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000011")


@pytest.mark.unit
def test_get_spec_incorrect_suppression_uuid() -> None:
    spec = get_spec(EnumFailureMode.INCORRECT_SUPPRESSION)
    assert spec.spec_id == UUID("00000001-0000-0000-0000-000000000015")


@pytest.mark.unit
def test_no_duplicate_spec_ids() -> None:
    ids = [spec.spec_id for spec in BEHAVIOR_SPEC_CATALOG.values()]
    assert len(ids) == len(set(ids))


@pytest.mark.unit
def test_all_failure_modes_covered() -> None:
    for mode in EnumFailureMode:
        assert mode in BEHAVIOR_SPEC_CATALOG, f"{mode} not in catalog"


@pytest.mark.unit
def test_domain_assignment_contract_creation() -> None:
    contract_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.CONTRACT_CREATION
    ]
    for mode in contract_modes:
        assert BEHAVIOR_SPEC_CATALOG[mode].domain == EnumEvalDomain.CONTRACT_CREATION


@pytest.mark.unit
def test_domain_assignment_agent_execution() -> None:
    agent_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.AGENT_EXECUTION
    ]
    for mode in agent_modes:
        assert BEHAVIOR_SPEC_CATALOG[mode].domain == EnumEvalDomain.AGENT_EXECUTION


@pytest.mark.unit
def test_domain_assignment_memory_system() -> None:
    memory_modes = [
        m
        for m in EnumFailureMode
        if FAILURE_MODE_DOMAIN[m] == EnumEvalDomain.MEMORY_SYSTEM
    ]
    for mode in memory_modes:
        assert BEHAVIOR_SPEC_CATALOG[mode].domain == EnumEvalDomain.MEMORY_SYSTEM


@pytest.mark.unit
def test_spec_fields_non_empty() -> None:
    for spec in BEHAVIOR_SPEC_CATALOG.values():
        assert spec.description
        assert spec.scenario_prompt_template
        assert spec.expected_behavior
        assert len(spec.failure_indicators) >= 1
