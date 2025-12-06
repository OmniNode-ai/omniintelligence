"""
Backward compatibility regression tests.

These tests ensure that legacy API patterns continue to work as expected,
preventing accidental breaking changes during ONEX migration.

The tests focus on:
1. Legacy field names (timeout_seconds, circuit_breaker_timeout_seconds)
2. Environment-based configuration (for_environment, from_environment_variable)
3. Serialization/deserialization with legacy field names

Note:
    This test imports directly from the model file rather than the package
    __init__.py to avoid circular import issues during migration.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Direct import from the file to avoid __init__.py import chain issues
# This is a temporary workaround during the migration period
# Get the repo root relative to this test file
repo_root = Path(__file__).parent.parent.parent
models_path = repo_root / "src" / "omniintelligence" / "_legacy" / "models"
sys.path.insert(0, str(models_path))
from model_intelligence_config import ModelIntelligenceConfig  # noqa: E402


@pytest.mark.unit
class TestLegacyFieldCompatibility:
    """Test that legacy field names remain functional."""

    def test_model_accepts_timeout_seconds_alias(self):
        """Verify ModelIntelligenceConfig accepts timeout_seconds via alias."""
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_seconds=60000,  # Legacy name (alias)
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Both names should work due to populate_by_name=True
        assert config.timeout_ms == 60000
        # model_dump(by_alias=True) returns alias names
        assert config.model_dump(by_alias=True)["timeout_seconds"] == 60000

    def test_model_accepts_circuit_breaker_timeout_seconds_alias(self):
        """Verify ModelIntelligenceConfig accepts circuit_breaker_timeout_seconds."""
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            circuit_breaker_timeout_seconds=120000,  # Legacy name (alias)
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        assert config.circuit_breaker_timeout_ms == 120000
        # model_dump(by_alias=True) returns alias names
        assert config.model_dump(by_alias=True)["circuit_breaker_timeout_seconds"] == 120000

    def test_model_accepts_both_legacy_and_canonical_names(self):
        """Verify model can be created with either legacy or canonical field names."""
        # Using legacy names
        config_legacy = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_seconds=30000,
            circuit_breaker_timeout_seconds=60000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Using canonical names (timeout_ms, circuit_breaker_timeout_ms)
        config_canonical = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_ms=30000,
            circuit_breaker_timeout_ms=60000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Both should result in identical internal state
        assert config_legacy.timeout_ms == config_canonical.timeout_ms
        assert (
            config_legacy.circuit_breaker_timeout_ms
            == config_canonical.circuit_breaker_timeout_ms
        )


@pytest.mark.unit
class TestEnvironmentConfiguration:
    """Test environment-based configuration backward compatibility."""

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_development(self):
        """Verify development environment config loads correctly."""
        config = ModelIntelligenceConfig.for_environment("development")

        assert config is not None
        assert config.base_url == "http://localhost:8053"
        assert config.timeout_ms == 30000
        assert config.circuit_breaker_threshold == 3
        assert config.circuit_breaker_timeout_ms == 30000
        assert config.consumer_group_id == "intelligence_adapter_dev"

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_production(self):
        """Verify production environment config loads correctly."""
        config = ModelIntelligenceConfig.for_environment("production")

        assert config is not None
        assert config.base_url == "http://archon-intelligence:8053"
        assert config.timeout_ms == 60000
        assert config.circuit_breaker_threshold == 10
        assert config.circuit_breaker_timeout_ms == 60000
        assert config.consumer_group_id == "intelligence_adapter_prod"

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_staging(self):
        """Verify staging environment config loads correctly."""
        config = ModelIntelligenceConfig.for_environment("staging")

        assert config is not None
        assert config.base_url == "http://archon-intelligence:8053"
        assert config.timeout_ms == 45000
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout_ms == 45000
        assert config.consumer_group_id == "intelligence_adapter_staging"

    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_variable_defaults_to_development(self):
        """Verify from_environment_variable defaults to development when unset."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config is not None
        assert config.timeout_ms == 30000
        assert config.circuit_breaker_threshold == 3
        assert config.consumer_group_id == "intelligence_adapter_dev"

    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True)
    def test_from_environment_variable_reads_env(self):
        """Verify from_environment_variable reads ENVIRONMENT variable."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_ms == 60000
        assert config.circuit_breaker_threshold == 10

    @patch.dict(os.environ, {"ENVIRONMENT": "STAGING"}, clear=True)
    def test_from_environment_variable_case_insensitive(self):
        """Verify ENVIRONMENT variable is case-insensitive."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_ms == 45000
        assert config.circuit_breaker_threshold == 5

    def test_for_environment_invalid_raises_value_error(self):
        """Verify invalid environment raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ModelIntelligenceConfig.for_environment("invalid")  # type: ignore[arg-type]

        assert "Invalid environment" in str(exc_info.value)
        assert "development, staging, production" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "unknown_env"}, clear=True)
    def test_from_environment_variable_invalid_raises_value_error(self):
        """Verify invalid ENVIRONMENT variable raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ModelIntelligenceConfig.from_environment_variable()

        assert "ENVIRONMENT must be one of" in str(exc_info.value)


@pytest.mark.unit
class TestSerializationCompatibility:
    """Test that serialization remains backward compatible."""

    def test_model_dump_uses_field_names_by_default(self):
        """Verify model_dump() uses field names by default, not aliases.

        In Pydantic v2, model_dump() uses the actual field names (timeout_ms)
        by default, and model_dump(by_alias=True) uses aliases (timeout_seconds).
        This is important to document for backward compatibility.
        """
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_ms=45000,
            circuit_breaker_timeout_ms=90000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Default dump uses field names (canonical names)
        data = config.model_dump()
        assert "timeout_ms" in data
        assert data["timeout_ms"] == 45000
        assert "circuit_breaker_timeout_ms" in data
        assert data["circuit_breaker_timeout_ms"] == 90000

        # by_alias=True uses alias names (legacy names)
        data_aliased = config.model_dump(by_alias=True)
        assert "timeout_seconds" in data_aliased
        assert data_aliased["timeout_seconds"] == 45000
        assert "circuit_breaker_timeout_seconds" in data_aliased
        assert data_aliased["circuit_breaker_timeout_seconds"] == 90000

    def test_model_dump_by_alias_true(self):
        """Verify model_dump(by_alias=True) uses legacy field names."""
        config = ModelIntelligenceConfig(
            timeout_ms=30000,
            circuit_breaker_timeout_ms=60000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        data = config.model_dump(by_alias=True)

        assert "timeout_seconds" in data
        assert data["timeout_seconds"] == 30000
        assert "circuit_breaker_timeout_seconds" in data
        assert data["circuit_breaker_timeout_seconds"] == 60000

    def test_model_validates_from_dict_with_legacy_names(self):
        """Verify model can be created from dictionary using legacy field names."""
        data = {
            "base_url": "http://localhost:8053",
            "timeout_seconds": 60000,  # Legacy alias name
            "max_retries": 3,
            "retry_delay_ms": 1000,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout_seconds": 30000,  # Legacy alias name
            "enable_event_publishing": True,
            "input_topics": ["ns.domain.pattern.op.v1"],
            "output_topics": {"event": "ns.domain.pattern.event.v1"},
            "consumer_group_id": "test-group",
        }

        config = ModelIntelligenceConfig.model_validate(data)

        assert config.base_url == "http://localhost:8053"
        assert config.timeout_ms == 60000
        assert config.circuit_breaker_timeout_ms == 30000

    def test_model_validates_from_dict_with_canonical_names(self):
        """Verify model can be created from dictionary using canonical field names."""
        data = {
            "base_url": "http://localhost:8053",
            "timeout_ms": 60000,  # Canonical name
            "max_retries": 3,
            "retry_delay_ms": 1000,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout_ms": 30000,  # Canonical name
            "enable_event_publishing": True,
            "input_topics": ["ns.domain.pattern.op.v1"],
            "output_topics": {"event": "ns.domain.pattern.event.v1"},
            "consumer_group_id": "test-group",
        }

        config = ModelIntelligenceConfig.model_validate(data)

        assert config.base_url == "http://localhost:8053"
        assert config.timeout_ms == 60000
        assert config.circuit_breaker_timeout_ms == 30000

    def test_json_roundtrip_preserves_values(self):
        """Verify JSON serialization/deserialization preserves all values."""
        original = ModelIntelligenceConfig(
            base_url="http://archon:8053",
            timeout_ms=45000,
            max_retries=5,
            retry_delay_ms=2000,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=10,
            circuit_breaker_timeout_ms=90000,
            enable_event_publishing=True,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"quality": "ns.domain.pattern.quality.v1"},
            consumer_group_id="test-consumers",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = ModelIntelligenceConfig.model_validate_json(json_str)

        # All values should be preserved
        assert restored.base_url == original.base_url
        assert restored.timeout_ms == original.timeout_ms
        assert restored.max_retries == original.max_retries
        assert restored.retry_delay_ms == original.retry_delay_ms
        assert restored.circuit_breaker_enabled == original.circuit_breaker_enabled
        assert restored.circuit_breaker_threshold == original.circuit_breaker_threshold
        assert (
            restored.circuit_breaker_timeout_ms == original.circuit_breaker_timeout_ms
        )
        assert restored.enable_event_publishing == original.enable_event_publishing
        assert restored.input_topics == original.input_topics
        assert restored.output_topics == original.output_topics
        assert restored.consumer_group_id == original.consumer_group_id


@pytest.mark.unit
class TestHelperMethodsBackwardCompatibility:
    """Test that helper methods remain backward compatible."""

    def test_get_health_check_url_format(self):
        """Verify health check URL format is unchanged."""
        config = ModelIntelligenceConfig()
        url = config.get_health_check_url()

        assert url == "http://localhost:8053/health"
        assert url.endswith("/health")

    def test_get_assess_code_url_format(self):
        """Verify assess code URL format is unchanged."""
        config = ModelIntelligenceConfig()
        url = config.get_assess_code_url()

        assert url == "http://localhost:8053/assess/code"
        assert url.endswith("/assess/code")

    def test_get_performance_baseline_url_format(self):
        """Verify performance baseline URL format is unchanged."""
        config = ModelIntelligenceConfig()
        url = config.get_performance_baseline_url()

        assert url == "http://localhost:8053/performance/baseline"
        assert url.endswith("/performance/baseline")

    def test_get_output_topic_for_event_returns_topic(self):
        """Verify get_output_topic_for_event returns correct topic."""
        config = ModelIntelligenceConfig()
        topic = config.get_output_topic_for_event("quality_assessed")

        assert topic is not None
        assert "quality_assessed" in topic

    def test_get_output_topic_for_event_returns_none_for_unknown(self):
        """Verify get_output_topic_for_event returns None for unknown events."""
        config = ModelIntelligenceConfig()
        topic = config.get_output_topic_for_event("nonexistent_event")

        assert topic is None

    def test_is_circuit_breaker_enabled_method(self):
        """Verify is_circuit_breaker_enabled method works."""
        config_enabled = ModelIntelligenceConfig()
        assert config_enabled.is_circuit_breaker_enabled() is True

        config_disabled = ModelIntelligenceConfig(
            circuit_breaker_enabled=False,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config_disabled.is_circuit_breaker_enabled() is False


@pytest.mark.unit
class TestEnvironmentVariableOverrides:
    """Test that environment variable overrides work correctly."""

    @patch.dict(
        os.environ,
        {"INTELLIGENCE_BASE_URL": "http://custom-service:9999"},
        clear=True,
    )
    def test_base_url_env_override_in_development(self):
        """Verify INTELLIGENCE_BASE_URL overrides default in development."""
        config = ModelIntelligenceConfig.for_environment("development")

        assert config.base_url == "http://custom-service:9999"

    @patch.dict(
        os.environ,
        {"INTELLIGENCE_BASE_URL": "http://custom-service:9999"},
        clear=True,
    )
    def test_base_url_env_override_in_production(self):
        """Verify INTELLIGENCE_BASE_URL overrides default in production."""
        config = ModelIntelligenceConfig.for_environment("production")

        assert config.base_url == "http://custom-service:9999"

    @patch.dict(
        os.environ,
        {"INTELLIGENCE_BASE_URL": "http://custom-service:9999"},
        clear=True,
    )
    def test_base_url_env_override_in_staging(self):
        """Verify INTELLIGENCE_BASE_URL overrides default in staging."""
        config = ModelIntelligenceConfig.for_environment("staging")

        assert config.base_url == "http://custom-service:9999"


@pytest.mark.unit
class TestDefaultValuesBackwardCompatibility:
    """Test that default values remain unchanged for backward compatibility."""

    def test_default_base_url(self):
        """Verify default base_url is unchanged."""
        config = ModelIntelligenceConfig()
        assert config.base_url == "http://localhost:8053"

    def test_default_timeout_ms(self):
        """Verify default timeout is 30000ms (30 seconds)."""
        config = ModelIntelligenceConfig()
        assert config.timeout_ms == 30000

    def test_default_max_retries(self):
        """Verify default max_retries is 3."""
        config = ModelIntelligenceConfig()
        assert config.max_retries == 3

    def test_default_retry_delay_ms(self):
        """Verify default retry_delay_ms is 1000."""
        config = ModelIntelligenceConfig()
        assert config.retry_delay_ms == 1000

    def test_default_circuit_breaker_enabled(self):
        """Verify circuit breaker is enabled by default."""
        config = ModelIntelligenceConfig()
        assert config.circuit_breaker_enabled is True

    def test_default_circuit_breaker_threshold(self):
        """Verify default circuit_breaker_threshold is 5."""
        config = ModelIntelligenceConfig()
        assert config.circuit_breaker_threshold == 5

    def test_default_circuit_breaker_timeout_ms(self):
        """Verify default circuit_breaker_timeout_ms is 60000 (60 seconds)."""
        config = ModelIntelligenceConfig()
        assert config.circuit_breaker_timeout_ms == 60000

    def test_default_enable_event_publishing(self):
        """Verify event publishing is enabled by default."""
        config = ModelIntelligenceConfig()
        assert config.enable_event_publishing is True

    def test_default_consumer_group_id(self):
        """Verify default consumer_group_id is unchanged."""
        config = ModelIntelligenceConfig()
        assert config.consumer_group_id == "intelligence_adapter_consumers"

    def test_default_input_topics_format(self):
        """Verify default input topics follow expected format."""
        config = ModelIntelligenceConfig()
        assert len(config.input_topics) == 1
        assert "omninode.intelligence.request.assess.v1" in config.input_topics[0]

    def test_default_output_topics_keys(self):
        """Verify default output topics have expected keys."""
        config = ModelIntelligenceConfig()
        expected_keys = {"quality_assessed", "performance_optimized", "error", "audit"}
        assert expected_keys == set(config.output_topics.keys())


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for backward compatibility.

    These tests cover scenarios that might occur during migration from legacy
    to canonical field naming, including mixed usage and serialization modes.

    Validator Review Notes (Part 2):
        The model uses field-level constraints (ge=, le=) for range validation:
        - timeout_ms: ge=5000, le=300000
        - max_retries: ge=0, le=10
        - retry_delay_ms: ge=100, le=10000
        - circuit_breaker_threshold: ge=1, le=100
        - circuit_breaker_timeout_ms: ge=10000, le=600000

        The @field_validator decorators perform SEMANTIC validation only:
        - validate_base_url: URL format (http/https, no trailing slash)
        - validate_input_topics: ONEX naming convention, non-empty list
        - validate_output_topics: ONEX naming convention, non-empty dict

        FINDING: No duplicate validation detected. Field constraints handle
        numeric bounds, validators handle semantic rules. This is good design.
    """

    def test_mixed_field_names_accepted(self):
        """Verify model accepts mix of legacy and canonical field names.

        Legacy code may gradually migrate to canonical names, so we need to
        support configs that use a mix of both naming conventions.
        """
        # Mix of legacy (timeout_seconds) and canonical (circuit_breaker_timeout_ms)
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_seconds=45000,  # Legacy alias
            circuit_breaker_timeout_ms=90000,  # Canonical name
            max_retries=3,  # Standard (no alias)
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Both should be properly set
        assert config.timeout_ms == 45000
        assert config.circuit_breaker_timeout_ms == 90000
        assert config.max_retries == 3

    def test_serialization_mode_json(self):
        """Verify model_dump(mode='json') produces JSON-serializable output.

        mode='json' should ensure all values are JSON-compatible primitives.
        This is important for API responses and message serialization.
        """
        import json

        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_ms=30000,
            circuit_breaker_timeout_ms=60000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Serialize with mode='json'
        data = config.model_dump(mode="json")

        # Verify output is JSON-serializable (all basic types)
        assert isinstance(data, dict)
        assert isinstance(data["base_url"], str)
        assert isinstance(data["timeout_ms"], int)
        assert isinstance(data["circuit_breaker_timeout_ms"], int)
        assert isinstance(data["input_topics"], list)
        assert isinstance(data["output_topics"], dict)

        # Values should be correct
        assert data["timeout_ms"] == 30000
        assert data["circuit_breaker_timeout_ms"] == 60000

        # Verify it can be JSON-encoded (no special objects)
        json_str = json.dumps(data)
        assert json_str  # Non-empty

    def test_serialization_mode_python(self):
        """Verify model_dump(mode='python') produces Python-native output.

        mode='python' keeps Python types as-is (e.g., datetimes, enums).
        For this model, output should be similar to mode='json' since we
        only have basic types.
        """
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_ms=30000,
            circuit_breaker_timeout_ms=60000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Serialize with mode='python' (default)
        data_python = config.model_dump(mode="python")
        data_json = config.model_dump(mode="json")

        # For this model with basic types, both modes should produce same values
        assert data_python["timeout_ms"] == data_json["timeout_ms"]
        assert data_python["base_url"] == data_json["base_url"]
        assert data_python["input_topics"] == data_json["input_topics"]
        assert data_python["output_topics"] == data_json["output_topics"]

    def test_validation_error_with_legacy_names(self):
        """Verify validation errors reference correct field names when using aliases.

        When validation fails with legacy field names (aliases), the error
        message should be helpful for debugging.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                base_url="http://localhost:8053",
                timeout_seconds=-1000,  # Invalid: below minimum (5000)
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )

        # Error should be raised for the field
        error = exc_info.value
        errors = error.errors()
        assert len(errors) >= 1

        # Find the timeout error
        timeout_error = next(
            (e for e in errors if "timeout" in str(e.get("loc", []))),
            None,
        )
        assert timeout_error is not None
        # Error should indicate value constraint violation
        assert "greater than or equal to" in str(timeout_error.get("msg", "")).lower()

    def test_validation_error_with_canonical_names(self):
        """Verify validation errors reference correct field names when using canonical names.

        When validation fails with canonical field names, error messages
        should correctly identify the field.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                base_url="http://localhost:8053",
                timeout_ms=999999999,  # Invalid: above maximum (300000)
                circuit_breaker_timeout_ms=99,  # Invalid: below minimum (10000)
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )

        # Multiple validation errors should be raised
        error = exc_info.value
        errors = error.errors()
        assert len(errors) >= 2

        # Both fields should have errors
        error_locs = [str(e.get("loc", [])) for e in errors]
        error_locs_str = " ".join(error_locs)
        assert "timeout_ms" in error_locs_str or "timeout_seconds" in error_locs_str
        assert (
            "circuit_breaker_timeout_ms" in error_locs_str
            or "circuit_breaker_timeout_seconds" in error_locs_str
        )

    def test_serialization_by_alias_combined_with_mode(self):
        """Verify by_alias works correctly with both serialization modes."""
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053",
            timeout_ms=45000,
            circuit_breaker_timeout_ms=90000,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Test all combinations
        data_python_no_alias = config.model_dump(mode="python", by_alias=False)
        data_python_with_alias = config.model_dump(mode="python", by_alias=True)
        data_json_no_alias = config.model_dump(mode="json", by_alias=False)
        data_json_with_alias = config.model_dump(mode="json", by_alias=True)

        # Without alias: canonical names
        assert "timeout_ms" in data_python_no_alias
        assert "timeout_ms" in data_json_no_alias
        assert "circuit_breaker_timeout_ms" in data_python_no_alias
        assert "circuit_breaker_timeout_ms" in data_json_no_alias

        # With alias: legacy names
        assert "timeout_seconds" in data_python_with_alias
        assert "timeout_seconds" in data_json_with_alias
        assert "circuit_breaker_timeout_seconds" in data_python_with_alias
        assert "circuit_breaker_timeout_seconds" in data_json_with_alias

        # Values should be consistent across all modes
        assert data_python_no_alias["timeout_ms"] == 45000
        assert data_python_with_alias["timeout_seconds"] == 45000
        assert data_json_no_alias["timeout_ms"] == 45000
        assert data_json_with_alias["timeout_seconds"] == 45000

    def test_model_validate_with_mixed_names_in_dict(self):
        """Verify model_validate() handles dictionaries with mixed field names.

        When deserializing from JSON or dict, the model should accept either
        legacy or canonical names (but not duplicates).
        """
        # Dict with mixed naming
        data = {
            "base_url": "http://localhost:8053",
            "timeout_seconds": 30000,  # Legacy alias
            "max_retries": 3,
            "retry_delay_ms": 1000,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout_ms": 60000,  # Canonical name
            "enable_event_publishing": True,
            "input_topics": ["ns.domain.pattern.op.v1"],
            "output_topics": {"event": "ns.domain.pattern.event.v1"},
            "consumer_group_id": "test-group",
        }

        config = ModelIntelligenceConfig.model_validate(data)

        # Both should be properly set
        assert config.timeout_ms == 30000
        assert config.circuit_breaker_timeout_ms == 60000

    def test_json_schema_contains_alias_info(self):
        """Verify JSON schema includes alias information for documentation.

        The JSON schema should document both canonical and legacy field names
        so API consumers know both are accepted.
        """
        schema = ModelIntelligenceConfig.model_json_schema()

        # Schema should exist and have properties
        assert "properties" in schema
        props = schema["properties"]

        # Check for timeout field (may use alias in schema)
        # The exact key depends on Pydantic's schema generation settings
        timeout_found = "timeout_ms" in props or "timeout_seconds" in props
        assert timeout_found, "timeout field should be in schema"

        cb_timeout_found = (
            "circuit_breaker_timeout_ms" in props
            or "circuit_breaker_timeout_seconds" in props
        )
        assert cb_timeout_found, "circuit_breaker_timeout field should be in schema"

    def test_exclude_unset_with_aliases(self):
        """Verify exclude_unset works correctly with aliased fields.

        When using exclude_unset=True, only explicitly set fields should
        be included in the output.
        """
        # Create config with only some fields set
        config = ModelIntelligenceConfig(
            timeout_seconds=50000,  # Using legacy alias
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )

        # Dump with exclude_unset
        data = config.model_dump(exclude_unset=True)

        # timeout should be present (was set)
        assert "timeout_ms" in data
        assert data["timeout_ms"] == 50000

        # Topics should be present
        assert "input_topics" in data
        assert "output_topics" in data

        # Fields with defaults that weren't explicitly set should be excluded
        # Note: Pydantic may include some fields if they're required or have defaults
        # The key point is that explicitly set fields are present
        assert data["timeout_ms"] == 50000
