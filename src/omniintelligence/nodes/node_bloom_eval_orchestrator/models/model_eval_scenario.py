from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)


class ModelEvalScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: UUID = Field(default_factory=uuid4)
    spec_id: UUID
    failure_mode: EnumFailureMode
    input_text: str
    context: dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
