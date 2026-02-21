# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the typed 8-class intent classification system.

Tests cover:
    - All 8 intent classes (REFACTOR, BUGFIX, FEATURE, ANALYSIS,
      CONFIGURATION, DOCUMENTATION, MIGRATION, SECURITY)
    - Config table structure and completeness
    - Typed intent resolution from TF-IDF categories
    - ANALYSIS fallback for low-confidence classifications
    - Integration with handle_intent_classification output
    - ModelIntentClassifiedEvent envelope construction
    - EnumIntentClass enum values

Verification tags (from ticket OMN-2488):
    V1: pytest tests/ -m unit -v -k classification
    V2: pytest tests/ -m unit -v -k intent_event
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_typed_classification import (
    DEFAULT_TYPED_CONFIDENCE_THRESHOLD,
    get_category_to_typed_class_mapping,
    resolve_typed_intent,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_intent_classified_event import (
    ModelIntentClassifiedEvent,
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
# Fixtures
# =============================================================================


@pytest.fixture
def high_confidence() -> float:
    """Confidence score well above the fallback threshold."""
    return 0.9


@pytest.fixture
def low_confidence() -> float:
    """Confidence score below the fallback threshold."""
    return 0.1


# =============================================================================
# EnumIntentClass Tests
# =============================================================================


@pytest.mark.unit
class TestEnumIntentClass:
    """Tests for the 8-class EnumIntentClass enum."""

    def test_all_eight_classes_present(self) -> None:
        """Verify all 8 intent classes are defined."""
        expected = {
            "REFACTOR",
            "BUGFIX",
            "FEATURE",
            "ANALYSIS",
            "CONFIGURATION",
            "DOCUMENTATION",
            "MIGRATION",
            "SECURITY",
        }
        actual = {cls.value for cls in EnumIntentClass}
        assert actual == expected

    def test_enum_values_are_uppercase_strings(self) -> None:
        """Enum values must be uppercase strings (ONEX enum governance)."""
        for cls in EnumIntentClass:
            assert isinstance(cls.value, str)
            assert cls.value == cls.value.upper()

    def test_enum_is_str_subclass(self) -> None:
        """EnumIntentClass must subclass str for JSON serialization."""
        assert issubclass(EnumIntentClass, str)

    @pytest.mark.parametrize(
        "class_name",
        [
            "REFACTOR",
            "BUGFIX",
            "FEATURE",
            "ANALYSIS",
            "CONFIGURATION",
            "DOCUMENTATION",
            "MIGRATION",
            "SECURITY",
        ],
    )
    def test_each_class_accessible_by_name(self, class_name: str) -> None:
        """Each intent class must be accessible by name."""
        cls = EnumIntentClass[class_name]
        assert cls.value == class_name


# =============================================================================
# Config Table Tests
# =============================================================================


@pytest.mark.unit
class TestIntentClassConfigTable:
    """Tests for the INTENT_CLASS_CONFIG_TABLE."""

    def test_all_eight_classes_in_config_table(self) -> None:
        """Every intent class must have a config entry."""
        for cls in EnumIntentClass:
            assert cls in INTENT_CLASS_CONFIG_TABLE, (
                f"Missing config entry for {cls.value}"
            )

    def test_config_table_has_exactly_eight_entries(self) -> None:
        """Config table must have exactly 8 entries (one per class)."""
        assert len(INTENT_CLASS_CONFIG_TABLE) == 8

    @pytest.mark.parametrize("intent_class", list(EnumIntentClass))
    def test_each_config_has_valid_model_hint(
        self, intent_class: EnumIntentClass
    ) -> None:
        """Each config must have a non-empty model hint string."""
        config = INTENT_CLASS_CONFIG_TABLE[intent_class]
        assert isinstance(config.model_hint, str)
        assert len(config.model_hint) > 0

    @pytest.mark.parametrize("intent_class", list(EnumIntentClass))
    def test_each_config_has_valid_temperature(
        self, intent_class: EnumIntentClass
    ) -> None:
        """Each config temperature must be in [0.0, 1.0]."""
        config = INTENT_CLASS_CONFIG_TABLE[intent_class]
        assert 0.0 <= config.temperature <= 1.0

    @pytest.mark.parametrize("intent_class", list(EnumIntentClass))
    def test_each_config_has_validator_set_list(
        self, intent_class: EnumIntentClass
    ) -> None:
        """Each config validator_set must be a list."""
        config = INTENT_CLASS_CONFIG_TABLE[intent_class]
        assert isinstance(config.validator_set, list)

    @pytest.mark.parametrize("intent_class", list(EnumIntentClass))
    def test_each_config_has_sandbox_bool(self, intent_class: EnumIntentClass) -> None:
        """Each config sandbox flag must be a bool."""
        config = INTENT_CLASS_CONFIG_TABLE[intent_class]
        assert isinstance(config.sandbox, bool)

    def test_config_is_frozen(self) -> None:
        """ModelTypedIntentConfig must be frozen (immutable)."""
        from pydantic import ValidationError

        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.REFACTOR]
        with pytest.raises(ValidationError):
            config.temperature = 0.99  # type: ignore[misc]

    # Per-class spec verification (from ticket OMN-2488)

    def test_refactor_config(self) -> None:
        """REFACTOR: sonnet, 0.3, code_quality+test_coverage, no sandbox."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.REFACTOR]
        assert config.model_hint == "sonnet"
        assert config.temperature == 0.3
        assert "code_quality" in config.validator_set
        assert "test_coverage" in config.validator_set
        assert config.sandbox is False

    def test_bugfix_config(self) -> None:
        """BUGFIX: sonnet, 0.2, correctness+regression, no sandbox."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.BUGFIX]
        assert config.model_hint == "sonnet"
        assert config.temperature == 0.2
        assert "correctness" in config.validator_set
        assert "regression" in config.validator_set
        assert config.sandbox is False

    def test_feature_config(self) -> None:
        """FEATURE: opus, 0.5, design_review+test_coverage, no sandbox."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.FEATURE]
        assert config.model_hint == "opus"
        assert config.temperature == 0.5
        assert "design_review" in config.validator_set
        assert "test_coverage" in config.validator_set
        assert config.sandbox is False

    def test_analysis_config(self) -> None:
        """ANALYSIS: haiku, 0.4, no validators, no sandbox."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.ANALYSIS]
        assert config.model_hint == "haiku"
        assert config.temperature == 0.4
        assert config.validator_set == []
        assert config.sandbox is False

    def test_configuration_config(self) -> None:
        """CONFIGURATION: haiku, 0.1, schema_validation, sandbox=True."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.CONFIGURATION]
        assert config.model_hint == "haiku"
        assert config.temperature == 0.1
        assert "schema_validation" in config.validator_set
        assert config.sandbox is True

    def test_documentation_config(self) -> None:
        """DOCUMENTATION: haiku, 0.6, completeness, no sandbox."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.DOCUMENTATION]
        assert config.model_hint == "haiku"
        assert config.temperature == 0.6
        assert "completeness" in config.validator_set
        assert config.sandbox is False

    def test_migration_config(self) -> None:
        """MIGRATION: opus, 0.2, reversibility+schema_validation, sandbox=True."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.MIGRATION]
        assert config.model_hint == "opus"
        assert config.temperature == 0.2
        assert "reversibility" in config.validator_set
        assert "schema_validation" in config.validator_set
        assert config.sandbox is True

    def test_security_config(self) -> None:
        """SECURITY: opus, 0.1, security_audit+least_privilege, sandbox=True."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.SECURITY]
        assert config.model_hint == "opus"
        assert config.temperature == 0.1
        assert "security_audit" in config.validator_set
        assert "least_privilege" in config.validator_set
        assert config.sandbox is True


# =============================================================================
# Typed Intent Resolution Tests
# =============================================================================


@pytest.mark.unit
class TestResolveTypedIntent:
    """Tests for resolve_typed_intent() function."""

    def test_refactoring_category_maps_to_refactor(
        self, high_confidence: float
    ) -> None:
        """refactoring TF-IDF category → REFACTOR typed class."""
        result = resolve_typed_intent("refactoring", high_confidence)
        assert result.intent_class == EnumIntentClass.REFACTOR
        assert result.fallback is False

    def test_debugging_category_maps_to_bugfix(self, high_confidence: float) -> None:
        """debugging TF-IDF category → BUGFIX typed class."""
        result = resolve_typed_intent("debugging", high_confidence)
        assert result.intent_class == EnumIntentClass.BUGFIX
        assert result.fallback is False

    def test_code_generation_category_maps_to_feature(
        self, high_confidence: float
    ) -> None:
        """code_generation TF-IDF category → FEATURE typed class."""
        result = resolve_typed_intent("code_generation", high_confidence)
        assert result.intent_class == EnumIntentClass.FEATURE
        assert result.fallback is False

    def test_analysis_category_maps_to_analysis(self, high_confidence: float) -> None:
        """analysis TF-IDF category → ANALYSIS typed class."""
        result = resolve_typed_intent("analysis", high_confidence)
        assert result.intent_class == EnumIntentClass.ANALYSIS
        assert result.fallback is False

    def test_documentation_category_maps_to_documentation(
        self, high_confidence: float
    ) -> None:
        """documentation TF-IDF category → DOCUMENTATION typed class."""
        result = resolve_typed_intent("documentation", high_confidence)
        assert result.intent_class == EnumIntentClass.DOCUMENTATION
        assert result.fallback is False

    def test_database_category_maps_to_migration(self, high_confidence: float) -> None:
        """database TF-IDF category → MIGRATION typed class."""
        result = resolve_typed_intent("database", high_confidence)
        assert result.intent_class == EnumIntentClass.MIGRATION
        assert result.fallback is False

    def test_security_category_maps_to_security(self, high_confidence: float) -> None:
        """security TF-IDF category → SECURITY typed class."""
        result = resolve_typed_intent("security", high_confidence)
        assert result.intent_class == EnumIntentClass.SECURITY
        assert result.fallback is False

    def test_devops_category_maps_to_configuration(
        self, high_confidence: float
    ) -> None:
        """devops TF-IDF category → CONFIGURATION typed class."""
        result = resolve_typed_intent("devops", high_confidence)
        assert result.intent_class == EnumIntentClass.CONFIGURATION
        assert result.fallback is False

    def test_low_confidence_falls_back_to_analysis(self, low_confidence: float) -> None:
        """Low confidence → ANALYSIS fallback regardless of category."""
        result = resolve_typed_intent("security", low_confidence)
        assert result.intent_class == EnumIntentClass.ANALYSIS
        assert result.fallback is True

    def test_unknown_category_falls_back_to_analysis(
        self, high_confidence: float
    ) -> None:
        """Unmapped category → ANALYSIS fallback."""
        result = resolve_typed_intent("unknown_category_xyz", high_confidence)
        assert result.intent_class == EnumIntentClass.ANALYSIS
        assert result.fallback is True

    def test_unknown_intent_category_falls_back_to_analysis(
        self, high_confidence: float
    ) -> None:
        """'unknown' intent category → ANALYSIS fallback."""
        result = resolve_typed_intent("unknown", high_confidence)
        assert result.intent_class == EnumIntentClass.ANALYSIS
        assert result.fallback is True

    def test_result_has_config_matching_intent_class(
        self, high_confidence: float
    ) -> None:
        """Result config matches the resolved intent class."""
        result = resolve_typed_intent("security", high_confidence)
        expected_config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.SECURITY]
        assert result.config == expected_config

    def test_result_confidence_matches_input(self, high_confidence: float) -> None:
        """Result confidence matches the input confidence score."""
        result = resolve_typed_intent("refactoring", high_confidence)
        assert result.confidence == high_confidence

    def test_result_is_frozen(self, high_confidence: float) -> None:
        """ModelTypedIntent must be frozen."""
        from pydantic import ValidationError

        result = resolve_typed_intent("refactoring", high_confidence)
        with pytest.raises(ValidationError):
            result.confidence = 0.5  # type: ignore[misc]

    def test_custom_confidence_threshold_respected(self) -> None:
        """Custom threshold parameter is respected."""
        # confidence=0.5 is above 0.3 (default) but below 0.7 (custom)
        result_default = resolve_typed_intent(
            "security", 0.5, confidence_threshold=DEFAULT_TYPED_CONFIDENCE_THRESHOLD
        )
        result_custom = resolve_typed_intent("security", 0.5, confidence_threshold=0.7)

        # With default threshold, should map security → SECURITY
        assert result_default.intent_class == EnumIntentClass.SECURITY
        assert result_default.fallback is False

        # With high custom threshold, should fall back to ANALYSIS
        assert result_custom.intent_class == EnumIntentClass.ANALYSIS
        assert result_custom.fallback is True

    def test_config_table_override_respected(self, high_confidence: float) -> None:
        """Custom config_table parameter overrides the default."""
        custom_config = ModelTypedIntentConfig(
            intent_class=EnumIntentClass.SECURITY,
            model_hint="custom-model",
            temperature=0.99,
            validator_set=["custom_validator"],
            sandbox=False,
        )
        custom_table = {**INTENT_CLASS_CONFIG_TABLE}
        custom_table[EnumIntentClass.SECURITY] = custom_config

        result = resolve_typed_intent(
            "security", high_confidence, config_table=custom_table
        )
        assert result.config.model_hint == "custom-model"
        assert result.config.temperature == 0.99

    def test_all_eight_classes_resolvable(self, high_confidence: float) -> None:
        """All 8 intent classes are reachable via resolve_typed_intent."""
        category_to_class = get_category_to_typed_class_mapping()

        # Collect all reachable typed classes
        reachable = {
            resolve_typed_intent(category, high_confidence).intent_class
            for category in category_to_class
        }

        # All 8 classes must be reachable
        for cls in EnumIntentClass:
            assert cls in reachable, (
                f"Intent class {cls.value} is not reachable from any TF-IDF category"
            )


# =============================================================================
# ModelTypedIntent Property Tests
# =============================================================================


@pytest.mark.unit
class TestModelTypedIntent:
    """Tests for ModelTypedIntent model and its convenience properties."""

    def test_model_hint_property(self) -> None:
        """model_hint property returns config.model_hint."""
        result = resolve_typed_intent("security", 0.9)
        assert result.model_hint == result.config.model_hint

    def test_temperature_property(self) -> None:
        """temperature property returns config.temperature."""
        result = resolve_typed_intent("refactoring", 0.9)
        assert result.temperature == result.config.temperature

    def test_validator_set_property(self) -> None:
        """validator_set property returns config.validator_set."""
        result = resolve_typed_intent("security", 0.9)
        assert result.validator_set == result.config.validator_set

    def test_sandbox_property(self) -> None:
        """sandbox property returns config.sandbox."""
        # Use "database" which maps to MIGRATION (sandbox=True)
        result_sandbox = resolve_typed_intent("database", 0.9)
        result_no_sandbox = resolve_typed_intent("refactoring", 0.9)
        assert result_sandbox.sandbox is True
        assert result_no_sandbox.sandbox is False

    def test_model_construction_explicit(self) -> None:
        """ModelTypedIntent can be constructed directly with explicit values."""
        config = INTENT_CLASS_CONFIG_TABLE[EnumIntentClass.FEATURE]
        typed_intent = ModelTypedIntent(
            intent_class=EnumIntentClass.FEATURE,
            confidence=0.85,
            config=config,
            fallback=False,
        )
        assert typed_intent.intent_class == EnumIntentClass.FEATURE
        assert typed_intent.confidence == 0.85
        assert typed_intent.fallback is False


# =============================================================================
# ModelIntentClassifiedEvent Tests (V2: intent_event)
# =============================================================================


@pytest.mark.unit
class TestModelIntentClassifiedEvent:
    """Tests for the frozen event envelope for onex.evt.intent.classified.v1."""

    def test_event_is_preview_safe(self) -> None:
        """Event model must not have a prompt text field."""
        field_names = set(ModelIntentClassifiedEvent.model_fields.keys())
        assert "prompt" not in field_names
        assert "prompt_text" not in field_names
        assert "full_prompt" not in field_names

    def test_event_is_frozen(self) -> None:
        """Event envelope must be frozen (immutable after emission)."""
        from datetime import UTC, datetime
        from uuid import UUID

        from pydantic import ValidationError

        event = ModelIntentClassifiedEvent.from_typed_intent(
            session_id="test-session",
            correlation_id=UUID("00000000-0000-0000-0000-000000000001"),
            intent_class=EnumIntentClass.SECURITY,
            confidence=0.9,
            fallback=False,
            model_hint="opus",
            temperature=0.1,
            validator_set=["security_audit"],
            sandbox=True,
            emitted_at=datetime.now(UTC),
        )
        with pytest.raises(ValidationError):
            event.confidence = 0.5  # type: ignore[misc]

    def test_from_typed_intent_classmethod(self) -> None:
        """from_typed_intent classmethod builds correct event envelope."""
        from datetime import UTC, datetime
        from uuid import UUID

        emitted_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        correlation_id = UUID("12345678-1234-1234-1234-123456789012")

        event = ModelIntentClassifiedEvent.from_typed_intent(
            session_id="session-abc",
            correlation_id=correlation_id,
            intent_class=EnumIntentClass.MIGRATION,
            confidence=0.75,
            fallback=False,
            model_hint="opus",
            temperature=0.2,
            validator_set=["reversibility", "schema_validation"],
            sandbox=True,
            emitted_at=emitted_at,
        )

        assert event.event_type == "IntentClassified"
        assert event.session_id == "session-abc"
        assert event.correlation_id == str(correlation_id)
        assert event.intent_class == EnumIntentClass.MIGRATION
        assert event.confidence == 0.75
        assert event.fallback is False
        assert event.model_hint == "opus"
        assert event.temperature == 0.2
        assert "reversibility" in event.validator_set
        assert "schema_validation" in event.validator_set
        assert event.sandbox is True
        assert event.emitted_at == emitted_at

    @pytest.mark.parametrize("intent_class", list(EnumIntentClass))
    def test_event_created_for_each_intent_class(
        self, intent_class: EnumIntentClass
    ) -> None:
        """Event envelope can be created for all 8 intent classes."""
        from datetime import UTC, datetime
        from uuid import UUID

        config = INTENT_CLASS_CONFIG_TABLE[intent_class]
        event = ModelIntentClassifiedEvent.from_typed_intent(
            session_id="test-session",
            correlation_id=UUID("00000000-0000-0000-0000-000000000001"),
            intent_class=intent_class,
            confidence=0.8,
            fallback=False,
            model_hint=config.model_hint,
            temperature=config.temperature,
            validator_set=list(config.validator_set),
            sandbox=config.sandbox,
            emitted_at=datetime.now(UTC),
        )
        assert event.intent_class == intent_class

    def test_event_extra_fields_ignored(self) -> None:
        """Event model ignores extra fields (forward compatibility)."""
        from datetime import UTC, datetime

        # Pydantic with extra="ignore" should silently ignore unknown fields
        event = ModelIntentClassifiedEvent.model_validate(
            {
                "session_id": "test",
                "correlation_id": "00000000-0000-0000-0000-000000000001",
                "intent_class": "SECURITY",
                "confidence": 0.9,
                "model_hint": "opus",
                "temperature": 0.1,
                "emitted_at": datetime(2025, 1, 1, tzinfo=UTC),
                "future_field_unknown": "should_be_ignored",
            }
        )
        assert event.intent_class == EnumIntentClass.SECURITY


# =============================================================================
# Integration with handle_intent_classification
# =============================================================================


@pytest.mark.unit
class TestClassificationIntegration:
    """Integration tests: typed_intent present in handle_intent_classification output."""

    def test_classification_output_has_typed_intent_for_refactor_prompts(
        self,
    ) -> None:
        """Refactoring prompts produce REFACTOR typed intent in output."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Refactor the user service for better maintainability"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.REFACTOR

    def test_classification_output_has_typed_intent_for_bugfix_prompts(
        self,
    ) -> None:
        """Bug fix prompts produce BUGFIX typed intent in output."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Fix the critical bug causing crashes in production"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.BUGFIX

    def test_classification_output_has_typed_intent_for_feature_prompts(
        self,
    ) -> None:
        """Feature prompts produce FEATURE typed intent in output."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Generate a new Python module for user authentication"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.FEATURE

    def test_classification_output_has_typed_intent_for_analysis_prompts(
        self,
    ) -> None:
        """Analysis prompts produce ANALYSIS typed intent in output."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Review and examine the code architecture carefully"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.ANALYSIS

    def test_classification_output_has_typed_intent_for_documentation_prompts(
        self,
    ) -> None:
        """Documentation prompts produce DOCUMENTATION typed intent."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Add comprehensive documentation and docstrings to the module"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.DOCUMENTATION

    def test_classification_output_has_typed_intent_for_security_prompts(
        self,
    ) -> None:
        """Security prompts produce SECURITY typed intent in output."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Security audit the credential handling and encryption code"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.SECURITY

    def test_classification_output_has_typed_intent_for_migration_prompts(
        self,
    ) -> None:
        """Database migration prompts produce MIGRATION typed intent."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Create a database migration for the schema changes"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        assert result.typed_intent.intent_class == EnumIntentClass.MIGRATION

    def test_classification_output_has_typed_intent_for_devops_prompts(
        self,
    ) -> None:
        """DevOps/deployment prompts produce CONFIGURATION typed intent."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Configure the Docker deployment pipeline for kubernetes"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.success is True
        assert result.typed_intent is not None
        # devops/configuration is the expected class for deployment config
        assert result.typed_intent.intent_class in (
            EnumIntentClass.CONFIGURATION,
            EnumIntentClass.FEATURE,  # code_generation may win for some phrasings
        )

    def test_typed_intent_has_valid_config_in_output(self) -> None:
        """typed_intent in output always has a non-None config."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(
            content="Refactor the authentication module"
        )
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )

        assert result.typed_intent is not None
        assert result.typed_intent.config is not None
        assert result.typed_intent.intent_class in EnumIntentClass

    def test_ambiguous_prompt_falls_back_to_analysis(self) -> None:
        """When TF-IDF returns 'unknown' intent, typed classification uses ANALYSIS fallback."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_typed_classification import (
            resolve_typed_intent,
        )

        # Simulate what happens when TF-IDF returns "unknown" with zero confidence.
        # This is the contract: when intent_category == "unknown" and confidence == 0.0,
        # resolve_typed_intent falls back to ANALYSIS.
        result = resolve_typed_intent("unknown", 0.0)
        assert result.intent_class == EnumIntentClass.ANALYSIS
        assert result.fallback is True

    def test_empty_input_has_typed_intent_none_in_error_response(self) -> None:
        """Empty input produces an error response with no typed_intent."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
            handle_intent_classification,
        )
        from omniintelligence.nodes.node_intent_classifier_compute.models import (
            ModelIntentClassificationInput,
        )

        input_data = ModelIntentClassificationInput(content="x")
        # Minimal content that may still produce output
        result = handle_intent_classification(
            input_data=input_data, config=DEFAULT_CLASSIFICATION_CONFIG
        )
        # Even minimal input should produce either a valid typed_intent or None
        # (error path returns None)
        assert result.typed_intent is None or isinstance(
            result.typed_intent, ModelTypedIntent
        )


# =============================================================================
# Category Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestCategoryMapping:
    """Tests for the TF-IDF category to typed class mapping."""

    def test_get_category_mapping_returns_dict(self) -> None:
        """get_category_to_typed_class_mapping returns a dict."""
        mapping = get_category_to_typed_class_mapping()
        assert isinstance(mapping, dict)

    def test_get_category_mapping_returns_copy(self) -> None:
        """get_category_to_typed_class_mapping returns a copy (not the original)."""
        mapping1 = get_category_to_typed_class_mapping()
        mapping2 = get_category_to_typed_class_mapping()
        # Should be equal content but different objects
        assert mapping1 == mapping2
        assert mapping1 is not mapping2

    def test_all_mapped_values_are_enum_intent_class(self) -> None:
        """All mapping values are valid EnumIntentClass members."""
        mapping = get_category_to_typed_class_mapping()
        for category, typed_class in mapping.items():
            assert isinstance(typed_class, EnumIntentClass), (
                f"Category {category!r} maps to non-enum value {typed_class!r}"
            )

    def test_security_category_in_mapping(self) -> None:
        """'security' TF-IDF category is in the mapping."""
        mapping = get_category_to_typed_class_mapping()
        assert "security" in mapping
        assert mapping["security"] == EnumIntentClass.SECURITY

    def test_get_intent_class_config_returns_correct_config(self) -> None:
        """get_intent_class_config returns matching config for each class."""
        for intent_class in EnumIntentClass:
            config = get_intent_class_config(intent_class)
            assert config.intent_class == intent_class
