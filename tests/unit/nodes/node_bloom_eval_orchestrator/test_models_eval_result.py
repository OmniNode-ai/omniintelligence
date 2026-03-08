from uuid import uuid4

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
    ModelEvalSuiteResult,
)


def _make_result(
    *,
    schema_pass: bool = True,
    trace_coverage_pct: float = 0.9,
    reference_integrity_pass: bool = True,
    failure_mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
) -> ModelEvalResult:
    return ModelEvalResult(
        schema_pass=schema_pass,
        trace_coverage_pct=trace_coverage_pct,
        missing_acceptance_criteria=[],
        invented_requirements=[],
        ambiguity_flags=[],
        reference_integrity_pass=reference_integrity_pass,
        metamorphic_stability_score=0.95,
        compliance_theater_risk=0.05,
        failure_mode=failure_mode,
        scenario_id=uuid4(),
    )


@pytest.mark.unit
def test_eval_passed_all_conditions_met() -> None:
    result = _make_result(
        schema_pass=True, trace_coverage_pct=0.9, reference_integrity_pass=True
    )
    assert result.eval_passed is True


@pytest.mark.unit
def test_eval_passed_schema_fail() -> None:
    result = _make_result(
        schema_pass=False, trace_coverage_pct=0.9, reference_integrity_pass=True
    )
    assert result.eval_passed is False


@pytest.mark.unit
def test_eval_passed_low_trace_coverage() -> None:
    result = _make_result(
        schema_pass=True, trace_coverage_pct=0.79, reference_integrity_pass=True
    )
    assert result.eval_passed is False


@pytest.mark.unit
def test_eval_passed_exact_trace_threshold() -> None:
    result = _make_result(
        schema_pass=True, trace_coverage_pct=0.8, reference_integrity_pass=True
    )
    assert result.eval_passed is True


@pytest.mark.unit
def test_eval_passed_reference_integrity_fail() -> None:
    result = _make_result(
        schema_pass=True, trace_coverage_pct=0.9, reference_integrity_pass=False
    )
    assert result.eval_passed is False


@pytest.mark.unit
def test_eval_result_round_trip_json() -> None:
    result = _make_result()
    dumped = result.model_dump(mode="json")
    restored = ModelEvalResult.model_validate(dumped)
    assert restored == result


@pytest.mark.unit
def test_eval_result_frozen() -> None:
    result = _make_result()
    assert result.model_config.get("frozen") is True


@pytest.mark.unit
def test_suite_result_failure_rate_8_of_10() -> None:
    passing = [_make_result() for _ in range(8)]
    failing = [_make_result(schema_pass=False) for _ in range(2)]
    suite = ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=uuid4(),
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
        results=passing + failing,
        total_scenarios=10,
        passed_count=8,
    )
    assert suite.failure_rate == pytest.approx(0.2)
    assert suite.passed_threshold is True


@pytest.mark.unit
def test_suite_result_failure_rate_exceeds_threshold() -> None:
    suite = ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=uuid4(),
        failure_mode=EnumFailureMode.INVENTED_REQUIREMENTS,
        results=[],
        total_scenarios=10,
        passed_count=7,
    )
    assert suite.failure_rate == pytest.approx(0.3)
    assert suite.passed_threshold is False


@pytest.mark.unit
def test_suite_result_zero_total_scenarios() -> None:
    suite = ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=uuid4(),
        failure_mode=EnumFailureMode.TRACEABILITY_FAILURE,
        results=[],
        total_scenarios=0,
        passed_count=0,
    )
    assert suite.failure_rate == 0.0
    assert suite.passed_threshold is True


@pytest.mark.unit
def test_suite_result_round_trip_json() -> None:
    suite = ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=uuid4(),
        failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
        results=[_make_result()],
        total_scenarios=1,
        passed_count=1,
    )
    dumped = suite.model_dump(mode="json")
    restored = ModelEvalSuiteResult.model_validate(dumped)
    assert restored == suite


@pytest.mark.unit
def test_suite_result_frozen() -> None:
    suite = ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=uuid4(),
        failure_mode=EnumFailureMode.COMPLIANCE_THEATER,
        results=[],
        total_scenarios=0,
        passed_count=0,
    )
    assert suite.model_config.get("frozen") is True
