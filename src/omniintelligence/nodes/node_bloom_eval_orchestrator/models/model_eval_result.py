from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)


class ModelEvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_pass: bool
    trace_coverage_pct: float
    missing_acceptance_criteria: list[str]
    invented_requirements: list[str]
    ambiguity_flags: list[str]
    reference_integrity_pass: bool
    metamorphic_stability_score: float
    compliance_theater_risk: float
    failure_mode: EnumFailureMode
    scenario_id: UUID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def eval_passed(self) -> bool:
        return (
            self.schema_pass
            and self.trace_coverage_pct >= 0.8
            and self.reference_integrity_pass
        )


class ModelEvalSuiteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    suite_id: UUID
    spec_id: UUID
    failure_mode: EnumFailureMode
    results: list[ModelEvalResult]
    total_scenarios: int
    passed_count: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failure_rate(self) -> float:
        if self.total_scenarios == 0:
            return 0.0
        return 1.0 - self.passed_count / self.total_scenarios

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed_threshold(self) -> bool:
        return self.failure_rate <= 0.2
