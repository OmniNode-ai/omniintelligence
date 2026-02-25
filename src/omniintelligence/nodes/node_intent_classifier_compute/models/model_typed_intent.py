"""ModelTypedIntent — typed intent classification output for the 8-class system.

This model carries the resolved intent class, confidence score, and the
per-class config (model hint, temperature, validator set, sandbox flag).
It is produced by the intent_classifier_compute node and emitted to
``onex.evt.intent.classified.v1``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_typed_intent_config import (
    ModelTypedIntentConfig,
)


class ModelTypedIntent(BaseModel):
    """Typed intent classification result for the 8-class system.

    Carries the resolved intent class, confidence score, and the resolved
    per-class config that drives downstream behavior (model selection,
    temperature, validators, sandbox enforcement).

    Attributes:
        intent_class: The resolved typed intent class.
        confidence: Confidence score for this classification (0.0 to 1.0).
        config: Per-class config resolved from the config table.
        fallback: Whether this result used the fallback (ANALYSIS) class
            because confidence was below threshold.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    intent_class: EnumIntentClass = Field(
        ...,
        description="Resolved typed intent class from the 8-class system",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification (0.0 to 1.0)",
    )
    config: ModelTypedIntentConfig = Field(
        ...,
        description="Per-class config resolved from the intent class config table",
    )
    fallback: bool = Field(
        default=False,
        description=(
            "True when ANALYSIS class was used as fallback because confidence "
            "was below the configured threshold"
        ),
    )

    @property
    def model_hint(self) -> str:
        """Shortcut for the recommended model from config."""
        return self.config.model_hint

    @property
    def temperature(self) -> float:
        """Shortcut for the recommended temperature from config."""
        return self.config.temperature

    @property
    def validator_set(self) -> list[str]:
        """Shortcut for the validator set from config."""
        return self.config.validator_set

    @property
    def sandbox(self) -> bool:
        """Shortcut for the sandbox enforcement flag from config."""
        return self.config.sandbox


__all__ = ["ModelTypedIntent"]
