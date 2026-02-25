"""Handler for typed 8-class intent classification.

Maps legacy TF-IDF intent categories to the typed 8-class system
(REFACTOR, BUGFIX, FEATURE, ANALYSIS, CONFIGURATION, DOCUMENTATION,
MIGRATION, SECURITY) using a config-table-driven lookup.

Design:
    - Config-table-driven: no hardcoded class conditionals
    - ANALYSIS used as fallback when confidence is below threshold
    - Pure functional design (no side effects, no I/O)
    - Deterministic: same input always produces same output

ONEX Compliance:
    - No try/except at this level — errors propagate to the orchestrating handler
    - Pure computation, no logging
"""

from __future__ import annotations

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_typed_intent import (
    ModelTypedIntent,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_typed_intent_config import (
    INTENT_CLASS_CONFIG_TABLE,
    ModelTypedIntentConfig,
    get_intent_class_config,
)

# =============================================================================
# TF-IDF Category → Typed Intent Class Mapping
# =============================================================================
# Maps from legacy string-keyed TF-IDF categories to the typed 8-class enum.
# Categories not in this map fall through to the ANALYSIS fallback.
# =============================================================================

_CATEGORY_TO_TYPED_CLASS: dict[str, EnumIntentClass] = {
    # Refactoring maps to REFACTOR
    "refactoring": EnumIntentClass.REFACTOR,
    # Debugging / bug fixing maps to BUGFIX
    "debugging": EnumIntentClass.BUGFIX,
    # Code generation / new features maps to FEATURE
    "code_generation": EnumIntentClass.FEATURE,
    # Analysis / review maps to ANALYSIS
    "analysis": EnumIntentClass.ANALYSIS,
    # Quality assessment also maps to ANALYSIS (read-only evaluation)
    "quality_assessment": EnumIntentClass.ANALYSIS,
    # Semantic analysis maps to ANALYSIS
    "semantic_analysis": EnumIntentClass.ANALYSIS,
    # Documentation maps to DOCUMENTATION
    "documentation": EnumIntentClass.DOCUMENTATION,
    # Testing maps to FEATURE (production: test coverage is a feature deliverable)
    "testing": EnumIntentClass.FEATURE,
    # Database / schema changes map to MIGRATION
    "database": EnumIntentClass.MIGRATION,
    # Security maps to SECURITY
    "security": EnumIntentClass.SECURITY,
    # Architecture / design maps to FEATURE
    "architecture": EnumIntentClass.FEATURE,
    # API design maps to FEATURE
    "api_design": EnumIntentClass.FEATURE,
    # DevOps / deployment maps to CONFIGURATION
    "devops": EnumIntentClass.CONFIGURATION,
    # Pattern learning maps to ANALYSIS
    "pattern_learning": EnumIntentClass.ANALYSIS,
}

# Default fallback class when confidence is below threshold or category is unknown
_FALLBACK_CLASS: EnumIntentClass = EnumIntentClass.ANALYSIS

# Default confidence threshold for typed classification
# (uses config table's implied minimum; configurable via parameter)
DEFAULT_TYPED_CONFIDENCE_THRESHOLD: float = 0.3


def resolve_typed_intent(
    intent_category: str,
    confidence: float,
    *,
    confidence_threshold: float = DEFAULT_TYPED_CONFIDENCE_THRESHOLD,
    config_table: dict[EnumIntentClass, ModelTypedIntentConfig] | None = None,
) -> ModelTypedIntent:
    """Resolve a TF-IDF intent category to a typed 8-class intent result.

    Maps the raw TF-IDF category string to the typed EnumIntentClass,
    resolves per-class config from the config table, and applies the
    ANALYSIS fallback when confidence is below the threshold.

    Args:
        intent_category: Primary intent category string from TF-IDF classifier
            (e.g., "refactoring", "debugging", "code_generation").
        confidence: Classification confidence score (0.0 to 1.0).
        confidence_threshold: Minimum confidence to use the mapped class.
            Below this threshold, falls back to ANALYSIS. Defaults to
            DEFAULT_TYPED_CONFIDENCE_THRESHOLD (0.3).
        config_table: Optional config table override. If None, uses
            INTENT_CLASS_CONFIG_TABLE.

    Returns:
        ModelTypedIntent with resolved intent class, confidence, and config.
        If confidence is below threshold or category is unmapped, returns
        ANALYSIS class with fallback=True.
    """
    table = config_table if config_table is not None else INTENT_CLASS_CONFIG_TABLE

    # Determine whether to use the mapped class or fall back
    use_fallback = confidence < confidence_threshold

    if use_fallback:
        # Fallback: use ANALYSIS regardless of category
        resolved_class = _FALLBACK_CLASS
    else:
        # Look up from mapping; fall back to ANALYSIS if category is unknown
        resolved_class = _CATEGORY_TO_TYPED_CLASS.get(intent_category, _FALLBACK_CLASS)
        if (
            resolved_class is _FALLBACK_CLASS
            and intent_category not in _CATEGORY_TO_TYPED_CLASS
        ):
            # Category was genuinely unmapped — mark as fallback
            use_fallback = True

    config = get_intent_class_config(resolved_class, config_table=table)

    return ModelTypedIntent(
        intent_class=resolved_class,
        confidence=confidence,
        config=config,
        fallback=use_fallback,
    )


def get_category_to_typed_class_mapping() -> dict[str, EnumIntentClass]:
    """Return a copy of the TF-IDF category to typed class mapping.

    Useful for inspection, testing, and config-table overrides.

    Returns:
        Copy of _CATEGORY_TO_TYPED_CLASS mapping dict.
    """
    return dict(_CATEGORY_TO_TYPED_CLASS)


__all__ = [
    "DEFAULT_TYPED_CONFIDENCE_THRESHOLD",
    "get_category_to_typed_class_mapping",
    "resolve_typed_intent",
]
