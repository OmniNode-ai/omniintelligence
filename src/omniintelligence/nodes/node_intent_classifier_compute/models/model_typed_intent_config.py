"""Typed intent config table for the 8-class classification system.

Per-class configuration drives downstream behavior: model selection,
temperature, validator set, permission scope, and sandbox enforcement.
All values are config-table-driven — no hardcoded class conditionals.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)


class ModelTypedIntentConfig(BaseModel):
    """Per-class configuration for a typed intent.

    Attributes:
        intent_class: The intent class this config applies to.
        model_hint: Recommended model for this intent class.
        temperature: Recommended LLM temperature for this intent class.
        validator_set: List of validators to apply for this intent class.
        sandbox: Whether this intent class requires sandbox enforcement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    intent_class: EnumIntentClass = Field(
        ...,
        description="The intent class this config applies to",
    )
    model_hint: str = Field(
        ...,
        description="Recommended model for this intent class (e.g., 'sonnet', 'opus', 'haiku')",
    )
    temperature: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recommended LLM temperature for this intent class (0.0 to 1.0)",
    )
    validator_set: list[str] = Field(
        default_factory=list,
        description="List of validators to apply for this intent class",
    )
    sandbox: bool = Field(
        default=False,
        description="Whether this intent class requires sandbox enforcement",
    )


# =============================================================================
# Intent Class Config Table
# =============================================================================
# Config table is the single source of truth for per-class behavior.
# No hardcoded class conditionals — downstream consumers look up by enum value.
# Values are configurable at runtime by overriding INTENT_CLASS_CONFIG_TABLE.
# =============================================================================

INTENT_CLASS_CONFIG_TABLE: dict[EnumIntentClass, ModelTypedIntentConfig] = {
    EnumIntentClass.REFACTOR: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.REFACTOR,
        model_hint="sonnet",
        temperature=0.3,
        validator_set=["code_quality", "test_coverage"],
        sandbox=False,
    ),
    EnumIntentClass.BUGFIX: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.BUGFIX,
        model_hint="sonnet",
        temperature=0.2,
        validator_set=["correctness", "regression"],
        sandbox=False,
    ),
    EnumIntentClass.FEATURE: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.FEATURE,
        model_hint="opus",
        temperature=0.5,
        validator_set=["design_review", "test_coverage"],
        sandbox=False,
    ),
    EnumIntentClass.ANALYSIS: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.ANALYSIS,
        model_hint="haiku",
        temperature=0.4,
        validator_set=[],
        sandbox=False,
    ),
    EnumIntentClass.CONFIGURATION: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.CONFIGURATION,
        model_hint="haiku",
        temperature=0.1,
        validator_set=["schema_validation"],
        sandbox=True,
    ),
    EnumIntentClass.DOCUMENTATION: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.DOCUMENTATION,
        model_hint="haiku",
        temperature=0.6,
        validator_set=["completeness"],
        sandbox=False,
    ),
    EnumIntentClass.MIGRATION: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.MIGRATION,
        model_hint="opus",
        temperature=0.2,
        validator_set=["reversibility", "schema_validation"],
        sandbox=True,
    ),
    EnumIntentClass.SECURITY: ModelTypedIntentConfig(
        intent_class=EnumIntentClass.SECURITY,
        model_hint="opus",
        temperature=0.1,
        validator_set=["security_audit", "least_privilege"],
        sandbox=True,
    ),
}


def get_intent_class_config(
    intent_class: EnumIntentClass,
    *,
    config_table: dict[EnumIntentClass, ModelTypedIntentConfig] | None = None,
) -> ModelTypedIntentConfig:
    """Look up per-class config from the config table.

    Args:
        intent_class: The intent class to look up.
        config_table: Optional config table override. If None, uses
            INTENT_CLASS_CONFIG_TABLE.

    Returns:
        ModelTypedIntentConfig for the given intent class.

    Raises:
        KeyError: If the intent class is not found in the config table.
    """
    table = config_table if config_table is not None else INTENT_CLASS_CONFIG_TABLE
    return table[intent_class]


__all__ = [
    "INTENT_CLASS_CONFIG_TABLE",
    "ModelTypedIntentConfig",
    "get_intent_class_config",
]
