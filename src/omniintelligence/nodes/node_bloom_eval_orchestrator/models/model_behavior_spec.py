from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)


class ModelBehaviorSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec_id: UUID = Field(default_factory=uuid4)
    failure_mode: EnumFailureMode
    domain: EnumEvalDomain
    description: str
    scenario_prompt_template: str
    expected_behavior: str
    failure_indicators: list[str]
