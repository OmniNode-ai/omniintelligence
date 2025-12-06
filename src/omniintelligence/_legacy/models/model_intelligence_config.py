"""
Intelligence Adapter Effect Node Configuration Model.

This module provides configuration for the Intelligence Adapter Effect Node,
enabling integration with the Archon intelligence service for code quality
assessment, performance optimization, and ONEX compliance validation.

Reference Architecture:
    - OmniNode Bridge configuration patterns (circuit breaker, environment-based)
    - ONEX Effect Node patterns (event-driven, circuit-protected)
    - Event Bus integration (Kafka topics, consumer groups)

Created: 2025-10-21
Pattern: ONEX Configuration Contract
"""

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelIntelligenceConfig(BaseModel):
    """
    Configuration contract for Intelligence Adapter Effect Node.

    Provides comprehensive configuration for integrating with the Archon
    intelligence service, including service connection settings, circuit
    breaker fault tolerance, and event bus integration.

    Configuration Sections:
        1. Service Configuration: Connection and timeout settings
        2. Circuit Breaker: Fault tolerance and resilience
        3. Event Bus: Kafka integration for event-driven workflows
        4. Environment: Environment-specific defaults

    All settings support environment variable overrides with INTELLIGENCE_ prefix.
    For example, INTELLIGENCE_BASE_URL overrides base_url setting.

    Circuit Breaker Behavior:
        - CLOSED: Normal operation, requests flow through to intelligence service
        - OPEN: Service is failing, requests fail fast with circuit breaker error
        - HALF_OPEN: Testing recovery, limited requests allowed to check health

    Event Bus Integration:
        - Input Topics: Subscribe to quality assessment requests
        - Output Topics: Publish results, errors, and audit events
        - Consumer Groups: Load balancing across multiple adapter instances

    Example:
        Development environment configuration:
            config = ModelIntelligenceConfig.for_environment("development")
            print(f"Base URL: {config.base_url}")
            print(f"Timeout: {config.timeout_ms}ms")
            print(f"Circuit breaker: {config.circuit_breaker_enabled}")

        Production environment configuration:
            config = ModelIntelligenceConfig.for_environment("production")
            # Higher thresholds, stricter circuit breaker, multiple topics

        Custom configuration:
            config = ModelIntelligenceConfig(
                base_url="http://archon-intelligence:8053",
                timeout_ms=60000,
                circuit_breaker_threshold=10,
                input_topics=["quality.requests", "performance.requests"],
                output_topics={
                    "quality_assessed": "quality.results",
                    "error": "intelligence.errors",
                }
            )

    Attributes:
        # Service Configuration
        base_url: Intelligence service base URL (default: http://localhost:8053)
        timeout_ms: API request timeout in milliseconds (5000-300000)
        max_retries: Number of retry attempts for failed requests (0-10)
        retry_delay_ms: Delay between retry attempts in milliseconds (100-10000)

        # Circuit Breaker Settings
        circuit_breaker_enabled: Enable circuit breaker pattern (default: True)
        circuit_breaker_threshold: Failures before opening circuit (1-100)
        circuit_breaker_timeout_ms: Recovery timeout in milliseconds (10000-600000)

        # Event Bus Settings
        enable_event_publishing: Enable Kafka event publishing (default: True)
        input_topics: Kafka topics to subscribe for incoming requests
        output_topics: Event type to Kafka topic mapping for publishing
        consumer_group_id: Kafka consumer group identifier

    Environment Defaults:
        Development:
            - Base URL: http://localhost:8053
            - Timeout: 30.0s
            - Circuit breaker threshold: 3 failures
            - Recovery timeout: 30.0s
            - Single input/output topics

        Staging:
            - Base URL: http://archon-intelligence:8053
            - Timeout: 45.0s
            - Circuit breaker threshold: 5 failures
            - Recovery timeout: 45.0s
            - Multiple input/output topics

        Production:
            - Base URL: http://archon-intelligence:8053
            - Timeout: 60.0s
            - Circuit breaker threshold: 10 failures
            - Recovery timeout: 60.0s
            - Multiple input/output topics with versioning
    """

    # ==========================================
    # Service Configuration
    # ==========================================

    base_url: str = Field(
        default="http://localhost:8053",
        description="Intelligence service base URL",
        examples=[
            "http://localhost:8053",
            "http://archon-intelligence:8053",
            "http://192.168.86.101:8053",
        ],
    )

    timeout_ms: int = Field(
        default=30000,
        ge=5000,
        le=300000,
        description="API request timeout in milliseconds (5000-300000)",
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests (0-10)",
    )

    retry_delay_ms: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Delay between retry attempts in milliseconds (100-10000)",
    )

    # ==========================================
    # Circuit Breaker Settings
    # ==========================================

    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker for fault tolerance",
    )

    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of consecutive failures before opening circuit (1-100)",
    )

    circuit_breaker_timeout_ms: int = Field(
        default=60000,
        ge=10000,
        le=600000,
        description="Circuit breaker recovery timeout in milliseconds (10000-600000)",
    )

    # ==========================================
    # Event Bus Settings
    # ==========================================

    enable_event_publishing: bool = Field(
        default=True,
        description="Enable Kafka event publishing for event-driven workflows",
    )

    input_topics: list[str] = Field(
        default_factory=lambda: ["omninode.intelligence.request.assess.v1"],
        description="Kafka topics to subscribe for incoming intelligence requests",
        examples=[
            ["omninode.intelligence.request.assess.v1"],
            [
                "omninode.intelligence.request.quality.v1",
                "omninode.intelligence.request.performance.v1",
            ],
        ],
    )

    output_topics: dict[str, str] = Field(
        default_factory=lambda: {
            "quality_assessed": "omninode.intelligence.event.quality_assessed.v1",
            "performance_optimized": "omninode.intelligence.event.performance_optimized.v1",
            "error": "omninode.intelligence.event.error.v1",
            "audit": "omninode.intelligence.audit.v1",
        },
        description="Mapping of event types to Kafka output topics",
        examples=[
            {
                "quality_assessed": "omninode.intelligence.event.quality_assessed.v1",
                "error": "omninode.intelligence.event.error.v1",
            }
        ],
    )

    consumer_group_id: str = Field(
        default="intelligence_adapter_consumers",
        description="Kafka consumer group identifier for load balancing",
        examples=[
            "intelligence_adapter_consumers",
            "intelligence_adapter_dev",
            "intelligence_adapter_prod",
        ],
    )

    # ==========================================
    # Validators
    # ==========================================

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """
        Validate and normalize base URL format.

        Args:
            v: Base URL string to validate

        Returns:
            Normalized base URL without trailing slash

        Raises:
            ValueError: If URL is invalid or empty

        Examples:
            Input: "http://localhost:8053/"
            Output: "http://localhost:8053"

            Input: "http://archon-intelligence:8053"
            Output: "http://archon-intelligence:8053"
        """
        if not v or not v.strip():
            raise ValueError("Base URL cannot be empty")

        v = v.strip()

        # Remove trailing slash for consistency
        if v.endswith("/"):
            v = v[:-1]

        # Validate URL format (basic check)
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Base URL must start with http:// or https://, got: {v}")

        return v

    @field_validator("input_topics")
    @classmethod
    def validate_input_topics(cls, v: list[str]) -> list[str]:
        """
        Validate input topics are non-empty and follow ONEX naming convention.

        Args:
            v: List of input topic names

        Returns:
            Validated list of topic names

        Raises:
            ValueError: If topics list is empty or contains invalid topic names

        ONEX Topic Convention:
            {namespace}.{domain}.{pattern}.{operation}.{version}
            Example: omninode.intelligence.request.assess.v1
        """
        if not v:
            raise ValueError("Input topics list cannot be empty")

        for topic in v:
            if not topic or not topic.strip():
                raise ValueError("Topic name cannot be empty")

            # Basic ONEX naming convention check
            parts = topic.split(".")
            if len(parts) < 5:
                raise ValueError(
                    f"Topic '{topic}' does not follow ONEX convention: "
                    f"namespace.domain.pattern.operation.version"
                )

        return v

    @field_validator("output_topics")
    @classmethod
    def validate_output_topics(cls, v: dict[str, str]) -> dict[str, str]:
        """
        Validate output topic mapping is non-empty and topics follow ONEX convention.

        Args:
            v: Dictionary mapping event types to topic names

        Returns:
            Validated output topic mapping

        Raises:
            ValueError: If mapping is empty or contains invalid topics
        """
        if not v:
            raise ValueError("Output topics mapping cannot be empty")

        for event_type, topic in v.items():
            if not event_type or not event_type.strip():
                raise ValueError("Event type cannot be empty")

            if not topic or not topic.strip():
                raise ValueError(f"Topic name for '{event_type}' cannot be empty")

            # Basic ONEX naming convention check
            parts = topic.split(".")
            if len(parts) < 5:
                raise ValueError(
                    f"Topic '{topic}' does not follow ONEX convention: "
                    f"namespace.domain.pattern.operation.version"
                )

        return v

    # ==========================================
    # Environment Factory Methods
    # ==========================================

    @classmethod
    def for_environment(
        cls, env: Literal["development", "staging", "production"]
    ) -> "ModelIntelligenceConfig":
        """
        Create configuration for specific environment with optimized defaults.

        This factory method provides environment-specific configurations that
        balance performance, reliability, and cost for each deployment stage:

        Development:
            - Local service URL for fast iteration
            - Short timeouts for quick feedback
            - Aggressive circuit breaker for early failure detection
            - Single topic for simplicity
            - Optimized for developer productivity

        Staging:
            - Container service URL for realistic testing
            - Moderate timeouts for load testing
            - Balanced circuit breaker settings
            - Multiple topics for integration testing
            - Mirrors production topology

        Production:
            - Container service URL for high availability
            - Extended timeouts for reliability
            - Lenient circuit breaker to avoid false positives
            - Multiple versioned topics for flexibility
            - Optimized for uptime and resilience

        Args:
            env: Environment name (development, staging, production)

        Returns:
            ModelIntelligenceConfig instance with environment-specific defaults

        Raises:
            ValueError: If environment name is invalid

        Examples:
            Development configuration:
                >>> config = ModelIntelligenceConfig.for_environment("development")
                >>> config.base_url
                'http://localhost:8053'
                >>> config.timeout_ms
                30000
                >>> config.circuit_breaker_threshold
                3

            Staging configuration:
                >>> config = ModelIntelligenceConfig.for_environment("staging")
                >>> config.base_url
                'http://archon-intelligence:8053'
                >>> config.timeout_ms
                45000
                >>> config.circuit_breaker_threshold
                5

            Production configuration:
                >>> config = ModelIntelligenceConfig.for_environment("production")
                >>> config.base_url
                'http://archon-intelligence:8053'
                >>> config.timeout_ms
                60000
                >>> config.circuit_breaker_threshold
                10
        """
        # Environment-specific configurations
        configs: dict[str, dict[str, Any]] = {
            "development": {
                "base_url": os.getenv("INTELLIGENCE_BASE_URL", "http://localhost:8053"),
                "timeout_ms": 30000,  # 30 seconds in ms
                "max_retries": 3,
                "retry_delay_ms": 1000,
                "circuit_breaker_enabled": True,
                "circuit_breaker_threshold": 3,
                "circuit_breaker_timeout_ms": 30000,  # 30 seconds in ms
                "enable_event_publishing": True,
                "input_topics": [
                    "dev.omninode.intelligence.request.assess.v1",
                ],
                "output_topics": {
                    "quality_assessed": "dev.omninode.intelligence.event.quality_assessed.v1",
                    "performance_optimized": "dev.omninode.intelligence.event.performance_optimized.v1",
                    "error": "dev.omninode.intelligence.event.error.v1",
                    "audit": "dev.omninode.intelligence.audit.v1",
                },
                "consumer_group_id": "intelligence_adapter_dev",
            },
            "staging": {
                "base_url": os.getenv(
                    "INTELLIGENCE_BASE_URL", "http://archon-intelligence:8053"
                ),
                "timeout_ms": 45000,  # 45 seconds in ms
                "max_retries": 4,
                "retry_delay_ms": 1500,
                "circuit_breaker_enabled": True,
                "circuit_breaker_threshold": 5,
                "circuit_breaker_timeout_ms": 45000,  # 45 seconds in ms
                "enable_event_publishing": True,
                "input_topics": [
                    "staging.omninode.intelligence.request.quality.v1",
                    "staging.omninode.intelligence.request.performance.v1",
                ],
                "output_topics": {
                    "quality_assessed": "staging.omninode.intelligence.event.quality_assessed.v1",
                    "performance_optimized": "staging.omninode.intelligence.event.performance_optimized.v1",
                    "compliance_checked": "staging.omninode.intelligence.event.compliance_checked.v1",
                    "error": "staging.omninode.intelligence.event.error.v1",
                    "audit": "staging.omninode.intelligence.audit.v1",
                },
                "consumer_group_id": "intelligence_adapter_staging",
            },
            "production": {
                "base_url": os.getenv(
                    "INTELLIGENCE_BASE_URL", "http://archon-intelligence:8053"
                ),
                "timeout_ms": 60000,  # 60 seconds in ms
                "max_retries": 5,
                "retry_delay_ms": 2000,
                "circuit_breaker_enabled": True,
                "circuit_breaker_threshold": 10,
                "circuit_breaker_timeout_ms": 60000,  # 60 seconds in ms
                "enable_event_publishing": True,
                "input_topics": [
                    "prod.omninode.intelligence.request.quality.v1",
                    "prod.omninode.intelligence.request.performance.v1",
                    "prod.omninode.intelligence.request.compliance.v1",
                ],
                "output_topics": {
                    "quality_assessed": "prod.omninode.intelligence.event.quality_assessed.v1",
                    "performance_optimized": "prod.omninode.intelligence.event.performance_optimized.v1",
                    "compliance_checked": "prod.omninode.intelligence.event.compliance_checked.v1",
                    "pattern_learned": "prod.omninode.intelligence.event.pattern_learned.v1",
                    "error": "prod.omninode.intelligence.event.error.v1",
                    "audit": "prod.omninode.intelligence.audit.v1",
                },
                "consumer_group_id": "intelligence_adapter_prod",
            },
        }

        if env not in configs:
            raise ValueError(
                f"Invalid environment: {env}. "
                f"Must be one of: development, staging, production"
            )

        return cls(**configs[env])

    @classmethod
    def from_environment_variable(cls) -> "ModelIntelligenceConfig":
        """
        Create configuration from ENVIRONMENT variable with fallback to development.

        This method reads the ENVIRONMENT variable and creates the appropriate
        configuration. If ENVIRONMENT is not set, defaults to development.

        Environment Variable:
            ENVIRONMENT: One of development, staging, production (default: development)

        Returns:
            ModelIntelligenceConfig instance for the current environment

        Examples:
            Using environment variable:
                >>> import os
                >>> os.environ["ENVIRONMENT"] = "production"
                >>> config = ModelIntelligenceConfig.from_environment_variable()
                >>> config.circuit_breaker_threshold
                10

            With fallback to development:
                >>> os.environ.pop("ENVIRONMENT", None)  # Remove if exists
                >>> config = ModelIntelligenceConfig.from_environment_variable()
                >>> config.circuit_breaker_threshold
                3
        """
        env = os.getenv("ENVIRONMENT", "development").lower()

        # Validate environment name (fail-closed approach for production safety)
        valid_environments = {"development", "staging", "production"}
        if env not in valid_environments:
            raise ValueError(
                f"ENVIRONMENT must be one of {sorted(valid_environments)}, got: {env!r}"
            )

        return cls.for_environment(env)  # type: ignore

    # ==========================================
    # Configuration Helpers
    # ==========================================

    def get_health_check_url(self) -> str:
        """
        Get full URL for intelligence service health check endpoint.

        Returns:
            Complete health check URL

        Example:
            >>> config = ModelIntelligenceConfig()
            >>> config.get_health_check_url()
            'http://localhost:8053/health'
        """
        return f"{self.base_url}/health"

    def get_assess_code_url(self) -> str:
        """
        Get full URL for code quality assessment endpoint.

        Returns:
            Complete code assessment URL

        Example:
            >>> config = ModelIntelligenceConfig()
            >>> config.get_assess_code_url()
            'http://localhost:8053/assess/code'
        """
        return f"{self.base_url}/assess/code"

    def get_performance_baseline_url(self) -> str:
        """
        Get full URL for performance baseline establishment endpoint.

        Returns:
            Complete performance baseline URL

        Example:
            >>> config = ModelIntelligenceConfig()
            >>> config.get_performance_baseline_url()
            'http://localhost:8053/performance/baseline'
        """
        return f"{self.base_url}/performance/baseline"

    def get_output_topic_for_event(self, event_type: str) -> str | None:
        """
        Get Kafka output topic for specific event type.

        Args:
            event_type: Event type identifier

        Returns:
            Topic name if configured, None otherwise

        Example:
            >>> config = ModelIntelligenceConfig()
            >>> config.get_output_topic_for_event("quality_assessed")
            'omninode.intelligence.event.quality_assessed.v1'
            >>> config.get_output_topic_for_event("unknown")
            None
        """
        return self.output_topics.get(event_type)

    def is_circuit_breaker_enabled(self) -> bool:
        """
        Check if circuit breaker is enabled.

        Returns:
            True if circuit breaker is enabled

        Example:
            >>> config = ModelIntelligenceConfig()
            >>> config.is_circuit_breaker_enabled()
            True
        """
        return self.circuit_breaker_enabled

    # Pydantic v2 configuration
    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields for safety
        json_schema_extra={
            "examples": [
                # Development example
                {
                    "base_url": "http://localhost:8053",
                    "timeout_ms": 30000,
                    "max_retries": 3,
                    "retry_delay_ms": 1000,
                    "circuit_breaker_enabled": True,
                    "circuit_breaker_threshold": 3,
                    "circuit_breaker_timeout_ms": 30000,
                    "enable_event_publishing": True,
                    "input_topics": ["dev.omninode.intelligence.request.assess.v1"],
                    "output_topics": {
                        "quality_assessed": "dev.omninode.intelligence.event.quality_assessed.v1",
                        "error": "dev.omninode.intelligence.event.error.v1",
                    },
                    "consumer_group_id": "intelligence_adapter_dev",
                },
                # Production example
                {
                    "base_url": "http://archon-intelligence:8053",
                    "timeout_ms": 60000,
                    "max_retries": 5,
                    "retry_delay_ms": 2000,
                    "circuit_breaker_enabled": True,
                    "circuit_breaker_threshold": 10,
                    "circuit_breaker_timeout_ms": 60000,
                    "enable_event_publishing": True,
                    "input_topics": [
                        "prod.omninode.intelligence.request.quality.v1",
                        "prod.omninode.intelligence.request.performance.v1",
                    ],
                    "output_topics": {
                        "quality_assessed": "prod.omninode.intelligence.event.quality_assessed.v1",
                        "performance_optimized": "prod.omninode.intelligence.event.performance_optimized.v1",
                        "error": "prod.omninode.intelligence.event.error.v1",
                        "audit": "prod.omninode.intelligence.audit.v1",
                    },
                    "consumer_group_id": "intelligence_adapter_prod",
                },
            ]
        },
    )
