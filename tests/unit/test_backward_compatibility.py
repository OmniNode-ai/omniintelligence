"""
Backward compatibility regression tests.

These tests ensure that API patterns continue to work as expected,
preventing accidental breaking changes during ONEX migration.

The tests focus on:
1. Environment-based configuration (for_environment, from_environment_variable)
2. Helper methods (get_health_check_url, get_assess_code_url, etc.)
3. Default values and their stability
4. Serialization/deserialization behavior

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

    These tests cover serialization modes and validation behavior.

    Validator Review Notes:
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

    def test_validation_error_with_canonical_names(self):
        """Verify validation errors reference correct field names.

        When validation fails, error messages should correctly identify the field.
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
        assert "timeout_ms" in error_locs_str
        assert "circuit_breaker_timeout_ms" in error_locs_str

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

    def test_model_validates_from_dict_with_canonical_names(self):
        """Verify model can be created from dictionary using canonical field names."""
        data = {
            "base_url": "http://localhost:8053",
            "timeout_ms": 60000,
            "max_retries": 3,
            "retry_delay_ms": 1000,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout_ms": 30000,
            "enable_event_publishing": True,
            "input_topics": ["ns.domain.pattern.op.v1"],
            "output_topics": {"event": "ns.domain.pattern.event.v1"},
            "consumer_group_id": "test-group",
        }

        config = ModelIntelligenceConfig.model_validate(data)

        assert config.base_url == "http://localhost:8053"
        assert config.timeout_ms == 60000
        assert config.circuit_breaker_timeout_ms == 30000

    def test_json_schema_contains_required_fields(self):
        """Verify JSON schema includes required field information."""
        schema = ModelIntelligenceConfig.model_json_schema()

        # Schema should exist and have properties
        assert "properties" in schema
        props = schema["properties"]

        # Check for timeout field in schema
        assert "timeout_ms" in props, "timeout_ms field should be in schema"

        # Check for circuit_breaker_timeout field in schema
        assert (
            "circuit_breaker_timeout_ms" in props
        ), "circuit_breaker_timeout_ms field should be in schema"
