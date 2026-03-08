from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_behavior_spec import (
    ModelBehaviorSpec,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


@pytest.fixture
def sample_spec() -> ModelBehaviorSpec:
    return ModelBehaviorSpec(
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
        domain=EnumEvalDomain.CONTRACT_CREATION,
        description="Test spec for requirement omission",
        scenario_prompt_template="Given {context}, generate a contract that omits {requirement}",
        expected_behavior="Contract should include all requirements",
        failure_indicators=["missing requirement", "incomplete contract"],
    )


@pytest.mark.unit
def test_model_behavior_spec_default_spec_id(sample_spec: ModelBehaviorSpec) -> None:
    assert isinstance(sample_spec.spec_id, UUID)


@pytest.mark.unit
def test_model_behavior_spec_frozen(sample_spec: ModelBehaviorSpec) -> None:
    assert sample_spec.model_config.get("frozen") is True


@pytest.mark.unit
def test_model_behavior_spec_round_trip_json(sample_spec: ModelBehaviorSpec) -> None:
    dumped = sample_spec.model_dump(mode="json")
    restored = ModelBehaviorSpec.model_validate(dumped)
    assert restored == sample_spec


@pytest.mark.unit
def test_model_behavior_spec_fields(sample_spec: ModelBehaviorSpec) -> None:
    assert sample_spec.failure_mode == EnumFailureMode.REQUIREMENT_OMISSION
    assert sample_spec.domain == EnumEvalDomain.CONTRACT_CREATION
    assert isinstance(sample_spec.failure_indicators, list)
    assert len(sample_spec.failure_indicators) == 2


@pytest.mark.unit
def test_model_behavior_spec_explicit_spec_id() -> None:
    fixed_id = uuid4()
    spec = ModelBehaviorSpec(
        spec_id=fixed_id,
        failure_mode=EnumFailureMode.COMPLIANCE_THEATER,
        domain=EnumEvalDomain.CONTRACT_CREATION,
        description="desc",
        scenario_prompt_template="template",
        expected_behavior="expected",
        failure_indicators=[],
    )
    assert spec.spec_id == fixed_id


@pytest.fixture
def sample_scenario(sample_spec: ModelBehaviorSpec) -> ModelEvalScenario:
    return ModelEvalScenario(
        spec_id=sample_spec.spec_id,
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
        input_text="Write a contract for feature X",
        context={"ticket_id": "OMN-1234", "requirements": ["req1", "req2"]},
    )


@pytest.mark.unit
def test_model_eval_scenario_default_ids(sample_scenario: ModelEvalScenario) -> None:
    assert isinstance(sample_scenario.scenario_id, UUID)
    assert isinstance(sample_scenario.generated_at, datetime)


@pytest.mark.unit
def test_model_eval_scenario_generated_at_utc(
    sample_scenario: ModelEvalScenario,
) -> None:
    assert sample_scenario.generated_at.tzinfo is not None
    assert sample_scenario.generated_at.tzinfo == UTC


@pytest.mark.unit
def test_model_eval_scenario_frozen(sample_scenario: ModelEvalScenario) -> None:
    assert sample_scenario.model_config.get("frozen") is True


@pytest.mark.unit
def test_model_eval_scenario_round_trip_json(
    sample_scenario: ModelEvalScenario,
) -> None:
    dumped = sample_scenario.model_dump(mode="json")
    restored = ModelEvalScenario.model_validate(dumped)
    assert restored == sample_scenario


@pytest.mark.unit
def test_model_eval_scenario_context_arbitrary_types(
    sample_spec: ModelBehaviorSpec,
) -> None:
    scenario = ModelEvalScenario(
        spec_id=sample_spec.spec_id,
        failure_mode=EnumFailureMode.INVENTED_REQUIREMENTS,
        input_text="text",
        context={"nested": {"key": [1, 2, 3]}, "flag": True},
    )
    assert scenario.context["nested"]["key"] == [1, 2, 3]
