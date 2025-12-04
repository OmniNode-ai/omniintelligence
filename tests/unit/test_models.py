"""
Unit tests for shared models.

Tests Pydantic model validation and serialization.
"""

import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from omniintelligence.enums import (
    EnumFSMAction,
    EnumFSMType,
    EnumIntentType,
)
from omniintelligence.models import (
    ModelFSMState,
    ModelIntelligenceConfig,
    ModelIntent,
    ModelReducerInput,
    ModelReducerOutput,
)


def test_model_intent_creation():
    """Test ModelIntent creation and validation."""
    intent = ModelIntent(
        intent_type=EnumIntentType.WORKFLOW_TRIGGER,
        target="intelligence_orchestrator",
        payload={"test": "data"},
        correlation_id="corr_123",
    )

    assert intent.intent_type == EnumIntentType.WORKFLOW_TRIGGER
    assert intent.target == "intelligence_orchestrator"
    assert intent.payload["test"] == "data"
    assert intent.correlation_id == "corr_123"
    assert isinstance(intent.timestamp, datetime)


def test_reducer_input_validation():
    """Test ModelReducerInput validation."""
    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
    )

    assert input_data.fsm_type == EnumFSMType.INGESTION
    assert input_data.entity_id == "doc_123"
    assert input_data.action == EnumFSMAction.START_PROCESSING
    assert input_data.payload is None


def test_reducer_output_with_intents():
    """Test ModelReducerOutput with intents."""
    intent = ModelIntent(
        intent_type=EnumIntentType.EVENT_PUBLISH,
        target="kafka_event_effect",
        payload={},
        correlation_id="corr_789",
    )

    output = ModelReducerOutput(
        success=True,
        previous_state="RECEIVED",
        current_state="PROCESSING",
        intents=[intent],
    )

    assert output.success is True
    assert output.previous_state == "RECEIVED"
    assert output.current_state == "PROCESSING"
    assert len(output.intents) == 1
    assert output.intents[0].intent_type == EnumIntentType.EVENT_PUBLISH


def test_fsm_state_model():
    """Test ModelFSMState creation."""
    state = ModelFSMState(
        fsm_type=EnumFSMType.PATTERN_LEARNING,
        entity_id="pattern_123",
        current_state="FOUNDATION",
        previous_state=None,
        transition_timestamp=datetime.now(UTC),
    )

    assert state.fsm_type == EnumFSMType.PATTERN_LEARNING
    assert state.entity_id == "pattern_123"
    assert state.current_state == "FOUNDATION"
    assert state.previous_state is None


def test_model_serialization():
    """Test model JSON serialization."""
    intent = ModelIntent(
        intent_type=EnumIntentType.CACHE_INVALIDATE,
        target="cache_service",
        payload={"key": "test"},
        correlation_id="corr_101",
    )

    # Serialize to JSON
    json_str = intent.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialize from JSON
    intent_copy = ModelIntent.model_validate_json(json_str)
    assert intent_copy.intent_type == intent.intent_type
    assert intent_copy.target == intent.target
    assert intent_copy.correlation_id == intent.correlation_id


# =============================================================================
# ModelIntelligenceConfig Tests
# =============================================================================


class TestModelIntelligenceConfigDefaults:
    """Test ModelIntelligenceConfig default values."""

    def test_instantiation_with_defaults(self):
        """Test that ModelIntelligenceConfig can be instantiated with defaults."""
        config = ModelIntelligenceConfig()

        assert config.base_url == "http://localhost:8053"
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.retry_delay_ms == 1000
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout_seconds == 60.0
        assert config.enable_event_publishing is True
        assert config.consumer_group_id == "intelligence_adapter_consumers"

    def test_default_input_topics(self):
        """Test default input topics."""
        config = ModelIntelligenceConfig()
        assert len(config.input_topics) == 1
        assert config.input_topics[0] == "omninode.intelligence.request.assess.v1"

    def test_default_output_topics(self):
        """Test default output topics."""
        config = ModelIntelligenceConfig()
        assert "quality_assessed" in config.output_topics
        assert "performance_optimized" in config.output_topics
        assert "error" in config.output_topics
        assert "audit" in config.output_topics


class TestModelIntelligenceConfigCustomValues:
    """Test ModelIntelligenceConfig with custom values."""

    def test_instantiation_with_custom_values(self):
        """Test instantiation with all custom values."""
        config = ModelIntelligenceConfig(
            base_url="http://archon-intelligence:8053",
            timeout_seconds=60.0,
            max_retries=5,
            retry_delay_ms=2000,
            circuit_breaker_enabled=False,
            circuit_breaker_threshold=10,
            circuit_breaker_timeout_seconds=120.0,
            enable_event_publishing=False,
            input_topics=["custom.namespace.domain.pattern.op.v1"],
            output_topics={
                "custom_event": "custom.namespace.domain.pattern.event.v1"
            },
            consumer_group_id="custom_consumer_group",
        )

        assert config.base_url == "http://archon-intelligence:8053"
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 5
        assert config.retry_delay_ms == 2000
        assert config.circuit_breaker_enabled is False
        assert config.circuit_breaker_threshold == 10
        assert config.circuit_breaker_timeout_seconds == 120.0
        assert config.enable_event_publishing is False
        assert config.input_topics == ["custom.namespace.domain.pattern.op.v1"]
        assert config.output_topics == {
            "custom_event": "custom.namespace.domain.pattern.event.v1"
        }
        assert config.consumer_group_id == "custom_consumer_group"


class TestModelIntelligenceConfigBaseUrlValidation:
    """Test base_url field validation."""

    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL."""
        config = ModelIntelligenceConfig(
            base_url="http://localhost:8053/",
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.base_url == "http://localhost:8053"

    def test_base_url_empty_raises_error(self):
        """Test that empty base URL raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                base_url="",
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Base URL cannot be empty" in str(exc_info.value)

    def test_base_url_whitespace_only_raises_error(self):
        """Test that whitespace-only base URL raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                base_url="   ",
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Base URL cannot be empty" in str(exc_info.value)

    def test_base_url_invalid_protocol_raises_error(self):
        """Test that non-http/https base URL raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                base_url="ftp://localhost:8053",
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "must start with http:// or https://" in str(exc_info.value)

    def test_base_url_https_valid(self):
        """Test that https base URL is valid."""
        config = ModelIntelligenceConfig(
            base_url="https://secure.example.com:8053",
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.base_url == "https://secure.example.com:8053"


class TestModelIntelligenceConfigInputTopicsValidation:
    """Test input_topics field validation."""

    def test_input_topics_empty_list_raises_error(self):
        """Test that empty input topics list raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=[],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Input topics list cannot be empty" in str(exc_info.value)

    def test_input_topics_empty_string_raises_error(self):
        """Test that empty topic name raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=[""],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Topic name cannot be empty" in str(exc_info.value)

    def test_input_topics_whitespace_only_raises_error(self):
        """Test that whitespace-only topic name raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["   "],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Topic name cannot be empty" in str(exc_info.value)

    def test_input_topics_invalid_onex_convention_raises_error(self):
        """Test that topic not following ONEX convention raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["invalid.topic"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "does not follow ONEX convention" in str(exc_info.value)

    def test_input_topics_four_parts_invalid(self):
        """Test that topic with only 4 parts raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "does not follow ONEX convention" in str(exc_info.value)

    def test_input_topics_valid_onex_convention(self):
        """Test that valid ONEX topic convention is accepted."""
        config = ModelIntelligenceConfig(
            input_topics=["ns.domain.pattern.operation.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.input_topics == ["ns.domain.pattern.operation.v1"]

    def test_input_topics_multiple_valid(self):
        """Test multiple valid input topics."""
        config = ModelIntelligenceConfig(
            input_topics=[
                "ns.domain.pattern.op1.v1",
                "ns.domain.pattern.op2.v2",
            ],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert len(config.input_topics) == 2


class TestModelIntelligenceConfigOutputTopicsValidation:
    """Test output_topics field validation."""

    def test_output_topics_empty_dict_raises_error(self):
        """Test that empty output topics dict raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={},
            )
        assert "Output topics mapping cannot be empty" in str(exc_info.value)

    def test_output_topics_empty_event_type_raises_error(self):
        """Test that empty event type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"": "ns.domain.pattern.event.v1"},
            )
        assert "Event type cannot be empty" in str(exc_info.value)

    def test_output_topics_whitespace_event_type_raises_error(self):
        """Test that whitespace-only event type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"   ": "ns.domain.pattern.event.v1"},
            )
        assert "Event type cannot be empty" in str(exc_info.value)

    def test_output_topics_empty_topic_name_raises_error(self):
        """Test that empty topic name raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": ""},
            )
        assert "Topic name for 'event' cannot be empty" in str(exc_info.value)

    def test_output_topics_whitespace_topic_name_raises_error(self):
        """Test that whitespace-only topic name raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "   "},
            )
        assert "Topic name for 'event' cannot be empty" in str(exc_info.value)

    def test_output_topics_invalid_onex_convention_raises_error(self):
        """Test that topic not following ONEX convention raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "invalid.topic"},
            )
        assert "does not follow ONEX convention" in str(exc_info.value)

    def test_output_topics_multiple_valid(self):
        """Test multiple valid output topics."""
        config = ModelIntelligenceConfig(
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={
                "event1": "ns.domain.pattern.event1.v1",
                "event2": "ns.domain.pattern.event2.v1",
            },
        )
        assert len(config.output_topics) == 2


class TestModelIntelligenceConfigForEnvironment:
    """Test for_environment() class method."""

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_development(self):
        """Test development environment configuration."""
        config = ModelIntelligenceConfig.for_environment("development")

        assert config.base_url == "http://localhost:8053"
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.retry_delay_ms == 1000
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_threshold == 3
        assert config.circuit_breaker_timeout_seconds == 30.0
        assert config.enable_event_publishing is True
        assert config.consumer_group_id == "intelligence_adapter_dev"
        assert len(config.input_topics) == 1
        assert "dev.omninode" in config.input_topics[0]

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_staging(self):
        """Test staging environment configuration."""
        config = ModelIntelligenceConfig.for_environment("staging")

        assert config.base_url == "http://archon-intelligence:8053"
        assert config.timeout_seconds == 45.0
        assert config.max_retries == 4
        assert config.retry_delay_ms == 1500
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout_seconds == 45.0
        assert config.enable_event_publishing is True
        assert config.consumer_group_id == "intelligence_adapter_staging"
        assert len(config.input_topics) == 2
        assert "staging.omninode" in config.input_topics[0]

    @patch.dict(os.environ, {}, clear=True)
    def test_for_environment_production(self):
        """Test production environment configuration."""
        config = ModelIntelligenceConfig.for_environment("production")

        assert config.base_url == "http://archon-intelligence:8053"
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 5
        assert config.retry_delay_ms == 2000
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_threshold == 10
        assert config.circuit_breaker_timeout_seconds == 60.0
        assert config.enable_event_publishing is True
        assert config.consumer_group_id == "intelligence_adapter_prod"
        assert len(config.input_topics) == 3
        assert "prod.omninode" in config.input_topics[0]
        # Production has more output topics
        assert "pattern_learned" in config.output_topics

    def test_for_environment_invalid_raises_error(self):
        """Test that invalid environment raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ModelIntelligenceConfig.for_environment("invalid")  # type: ignore
        assert "Invalid environment: invalid" in str(exc_info.value)
        assert "development, staging, production" in str(exc_info.value)

    @patch.dict(os.environ, {"INTELLIGENCE_BASE_URL": "http://custom:9999"})
    def test_for_environment_respects_env_override(self):
        """Test that INTELLIGENCE_BASE_URL env var overrides default."""
        config = ModelIntelligenceConfig.for_environment("development")
        assert config.base_url == "http://custom:9999"


class TestModelIntelligenceConfigFromEnvironmentVariable:
    """Test from_environment_variable() class method."""

    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_variable_defaults_to_development(self):
        """Test that missing ENVIRONMENT defaults to development."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_seconds == 30.0
        assert config.circuit_breaker_threshold == 3
        assert config.consumer_group_id == "intelligence_adapter_dev"

    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True)
    def test_from_environment_variable_development(self):
        """Test development environment from ENVIRONMENT variable."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_seconds == 30.0
        assert config.circuit_breaker_threshold == 3

    @patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=True)
    def test_from_environment_variable_staging(self):
        """Test staging environment from ENVIRONMENT variable."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_seconds == 45.0
        assert config.circuit_breaker_threshold == 5

    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True)
    def test_from_environment_variable_production(self):
        """Test production environment from ENVIRONMENT variable."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_seconds == 60.0
        assert config.circuit_breaker_threshold == 10

    @patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}, clear=True)
    def test_from_environment_variable_case_insensitive(self):
        """Test that ENVIRONMENT value is case-insensitive."""
        config = ModelIntelligenceConfig.from_environment_variable()

        assert config.timeout_seconds == 60.0
        assert config.circuit_breaker_threshold == 10

    @patch.dict(os.environ, {"ENVIRONMENT": "invalid_env"}, clear=True)
    def test_from_environment_variable_invalid_raises_error(self):
        """Test that invalid ENVIRONMENT value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ModelIntelligenceConfig.from_environment_variable()
        assert "ENVIRONMENT must be one of" in str(exc_info.value)
        assert "invalid_env" in str(exc_info.value)


class TestModelIntelligenceConfigHelperMethods:
    """Test helper methods."""

    def test_get_health_check_url(self):
        """Test get_health_check_url() returns correct URL."""
        config = ModelIntelligenceConfig()
        assert config.get_health_check_url() == "http://localhost:8053/health"

    def test_get_health_check_url_custom_base(self):
        """Test get_health_check_url() with custom base URL."""
        config = ModelIntelligenceConfig(
            base_url="http://archon:9000",
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.get_health_check_url() == "http://archon:9000/health"

    def test_get_assess_code_url(self):
        """Test get_assess_code_url() returns correct URL."""
        config = ModelIntelligenceConfig()
        assert config.get_assess_code_url() == "http://localhost:8053/assess/code"

    def test_get_assess_code_url_custom_base(self):
        """Test get_assess_code_url() with custom base URL."""
        config = ModelIntelligenceConfig(
            base_url="http://archon:9000",
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.get_assess_code_url() == "http://archon:9000/assess/code"

    def test_get_performance_baseline_url(self):
        """Test get_performance_baseline_url() returns correct URL."""
        config = ModelIntelligenceConfig()
        assert (
            config.get_performance_baseline_url()
            == "http://localhost:8053/performance/baseline"
        )

    def test_get_performance_baseline_url_custom_base(self):
        """Test get_performance_baseline_url() with custom base URL."""
        config = ModelIntelligenceConfig(
            base_url="http://archon:9000",
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert (
            config.get_performance_baseline_url()
            == "http://archon:9000/performance/baseline"
        )

    def test_get_output_topic_for_event_existing(self):
        """Test get_output_topic_for_event() for existing event type."""
        config = ModelIntelligenceConfig()
        topic = config.get_output_topic_for_event("quality_assessed")
        assert topic == "omninode.intelligence.event.quality_assessed.v1"

    def test_get_output_topic_for_event_nonexistent(self):
        """Test get_output_topic_for_event() for non-existent event type."""
        config = ModelIntelligenceConfig()
        topic = config.get_output_topic_for_event("unknown_event")
        assert topic is None

    def test_is_circuit_breaker_enabled_true(self):
        """Test is_circuit_breaker_enabled() when enabled."""
        config = ModelIntelligenceConfig()
        assert config.is_circuit_breaker_enabled() is True

    def test_is_circuit_breaker_enabled_false(self):
        """Test is_circuit_breaker_enabled() when disabled."""
        config = ModelIntelligenceConfig(
            circuit_breaker_enabled=False,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.is_circuit_breaker_enabled() is False


class TestModelIntelligenceConfigFieldBoundaries:
    """Test field boundary validation."""

    def test_timeout_seconds_minimum(self):
        """Test minimum timeout_seconds value."""
        config = ModelIntelligenceConfig(
            timeout_seconds=5.0,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.timeout_seconds == 5.0

    def test_timeout_seconds_below_minimum_raises_error(self):
        """Test timeout_seconds below minimum raises error."""
        with pytest.raises(ValidationError):
            ModelIntelligenceConfig(
                timeout_seconds=4.9,
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )

    def test_timeout_seconds_maximum(self):
        """Test maximum timeout_seconds value."""
        config = ModelIntelligenceConfig(
            timeout_seconds=300.0,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.timeout_seconds == 300.0

    def test_timeout_seconds_above_maximum_raises_error(self):
        """Test timeout_seconds above maximum raises error."""
        with pytest.raises(ValidationError):
            ModelIntelligenceConfig(
                timeout_seconds=300.1,
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )

    def test_max_retries_minimum(self):
        """Test minimum max_retries value."""
        config = ModelIntelligenceConfig(
            max_retries=0,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.max_retries == 0

    def test_max_retries_maximum(self):
        """Test maximum max_retries value."""
        config = ModelIntelligenceConfig(
            max_retries=10,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.max_retries == 10

    def test_max_retries_above_maximum_raises_error(self):
        """Test max_retries above maximum raises error."""
        with pytest.raises(ValidationError):
            ModelIntelligenceConfig(
                max_retries=11,
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )

    def test_circuit_breaker_threshold_boundaries(self):
        """Test circuit_breaker_threshold boundary values."""
        # Minimum
        config = ModelIntelligenceConfig(
            circuit_breaker_threshold=1,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.circuit_breaker_threshold == 1

        # Maximum
        config = ModelIntelligenceConfig(
            circuit_breaker_threshold=100,
            input_topics=["ns.domain.pattern.op.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        assert config.circuit_breaker_threshold == 100

    def test_circuit_breaker_threshold_below_minimum_raises_error(self):
        """Test circuit_breaker_threshold below minimum raises error."""
        with pytest.raises(ValidationError):
            ModelIntelligenceConfig(
                circuit_breaker_threshold=0,
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )


class TestModelIntelligenceConfigSerialization:
    """Test model serialization and deserialization."""

    def test_json_serialization(self):
        """Test JSON serialization."""
        config = ModelIntelligenceConfig()
        json_str = config.model_dump_json()
        assert isinstance(json_str, str)
        assert "base_url" in json_str
        assert "localhost:8053" in json_str

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        # Use custom topics that pass ONEX convention (5+ parts)
        config = ModelIntelligenceConfig(
            input_topics=["ns.domain.pattern.operation.v1"],
            output_topics={"event": "ns.domain.pattern.event.v1"},
        )
        json_str = config.model_dump_json()
        config_copy = ModelIntelligenceConfig.model_validate_json(json_str)

        assert config_copy.base_url == config.base_url
        assert config_copy.timeout_seconds == config.timeout_seconds
        assert config_copy.circuit_breaker_threshold == config.circuit_breaker_threshold

    def test_dict_serialization(self):
        """Test dictionary serialization."""
        config = ModelIntelligenceConfig()
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert config_dict["base_url"] == "http://localhost:8053"
        assert config_dict["timeout_seconds"] == 30.0

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            ModelIntelligenceConfig(
                unknown_field="value",
                input_topics=["ns.domain.pattern.op.v1"],
                output_topics={"event": "ns.domain.pattern.event.v1"},
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)
