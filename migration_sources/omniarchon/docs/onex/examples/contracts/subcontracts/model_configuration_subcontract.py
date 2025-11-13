"""
Configuration Management Subcontract Example - ONEX Documentation.

Demonstrates configuration loading, validation, and runtime management patterns.
Based on: omnibase_core/src/omnibase_core/models/contracts/subcontracts/model_configuration_subcontract.py

This example shows how nodes can manage configuration from multiple sources
with validation, environment-specific variants, and runtime updates.
"""

from enum import Enum

from pydantic import BaseModel, Field

# === ENUMS ===


class ConfigurationSourceType(str, Enum):
    """Configuration source types."""

    FILE = "FILE"  # Configuration file (YAML/JSON)
    ENVIRONMENT = "ENVIRONMENT"  # Environment variables
    CONSUL = "CONSUL"  # HashiCorp Consul
    ETCD = "ETCD"  # etcd key-value store
    DATABASE = "DATABASE"  # Database-backed config
    SECRETS_MANAGER = "SECRETS_MANAGER"  # AWS Secrets Manager, Vault, etc.
    COMMAND_LINE = "COMMAND_LINE"  # CLI arguments


class ConfigurationFormat(str, Enum):
    """Configuration file formats."""

    YAML = "YAML"
    JSON = "JSON"
    TOML = "TOML"
    ENV = "ENV"  # .env file format
    INI = "INI"


class ValidationLevel(str, Enum):
    """Configuration validation strictness levels."""

    STRICT = "STRICT"  # Fail on any validation error
    PERMISSIVE = "PERMISSIVE"  # Warn on validation errors
    NONE = "NONE"  # No validation


# === MODELS ===


class ModelConfigurationSource(BaseModel):
    """Configuration source specification."""

    source_name: str = Field(
        ...,
        description="Unique name for this configuration source",
        examples=["app_config", "secrets", "runtime_overrides"],
    )

    source_type: ConfigurationSourceType = Field(
        ...,
        description="Type of configuration source",
    )

    source_path: str | None = Field(
        default=None,
        description="Path to configuration source (file path, URL, key prefix)",
        examples=["config/app.yaml", "/consul/app/config", "APP_"],
    )

    format: ConfigurationFormat = Field(
        default=ConfigurationFormat.YAML,
        description="Configuration format",
    )

    priority: int = Field(
        default=100,
        description="Source priority (higher = takes precedence)",
        ge=0,
        le=1000,
    )

    required: bool = Field(
        default=True,
        description="Whether this source must be available",
    )

    watch_for_changes: bool = Field(
        default=False,
        description="Monitor source for runtime changes",
    )

    reload_on_change: bool = Field(
        default=False,
        description="Automatically reload configuration on change",
    )


class ModelConfigurationValidation(BaseModel):
    """Configuration validation rules."""

    validation_level: ValidationLevel = Field(
        default=ValidationLevel.STRICT,
        description="Validation strictness level",
    )

    schema_path: str | None = Field(
        default=None,
        description="Path to validation schema (JSON Schema, Pydantic model)",
        examples=["schemas/config.schema.json"],
    )

    required_fields: list[str] = Field(
        default_factory=list,
        description="List of required configuration fields",
        examples=[["database.host", "database.port", "api.key"]],
    )

    allowed_environments: list[str] = Field(
        default_factory=lambda: ["development", "staging", "production"],
        description="Allowed environment values",
    )

    validate_on_load: bool = Field(
        default=True,
        description="Validate configuration when loading",
    )

    validate_on_update: bool = Field(
        default=True,
        description="Validate configuration before runtime updates",
    )


class ModelSensitiveDataHandling(BaseModel):
    """Sensitive data handling configuration."""

    mask_sensitive_fields: bool = Field(
        default=True,
        description="Mask sensitive values in logs",
    )

    sensitive_field_patterns: list[str] = Field(
        default_factory=lambda: ["*password*", "*secret*", "*token*", "*key*"],
        description="Patterns to identify sensitive fields (glob patterns)",
    )

    encrypt_at_rest: bool = Field(
        default=False,
        description="Encrypt configuration at rest",
    )

    encryption_key_source: str | None = Field(
        default=None,
        description="Source for encryption key",
        examples=["env:ENCRYPTION_KEY", "file:/secrets/key.pem"],
    )


class ModelConfigurationSubcontract(BaseModel):
    """
    Configuration Management Subcontract for ONEX nodes.

    Provides standardized configuration loading, validation, merging,
    and runtime reconfiguration capabilities. Applicable to all node types
    that need configuration management.

    Features:
    - Multi-source configuration (files, env vars, remote stores)
    - Priority-based configuration merging
    - Environment-specific configuration variants
    - Runtime configuration updates with validation
    - Sensitive data handling and encryption
    - Configuration change monitoring
    """

    subcontract_name: str = Field(
        default="configuration_subcontract",
        description="Subcontract identifier",
    )

    subcontract_version: str = Field(
        default="1.0.0",
        description="Subcontract version",
    )

    applicable_node_types: list[str] = Field(
        default=["EFFECT", "COMPUTE", "REDUCER", "ORCHESTRATOR"],
        description="Applicable to all node types",
    )

    # === CONFIGURATION SOURCES ===

    configuration_sources: list[ModelConfigurationSource] = Field(
        default_factory=list,
        description="Ordered list of configuration sources (merged by priority)",
    )

    # === VALIDATION ===

    validation: ModelConfigurationValidation = Field(
        default_factory=ModelConfigurationValidation,
        description="Configuration validation rules",
    )

    # === SENSITIVE DATA ===

    sensitive_data_handling: ModelSensitiveDataHandling = Field(
        default_factory=ModelSensitiveDataHandling,
        description="Sensitive data handling configuration",
    )

    # === RUNTIME BEHAVIOR ===

    allow_runtime_updates: bool = Field(
        default=False,
        description="Allow configuration updates while node is running",
    )

    update_grace_period_seconds: int = Field(
        default=30,
        description="Grace period before applying configuration updates",
        ge=0,
    )

    rollback_on_validation_failure: bool = Field(
        default=True,
        description="Rollback to previous config if validation fails",
    )

    # === ENVIRONMENT-SPECIFIC ===

    current_environment: str = Field(
        default="development",
        description="Current runtime environment",
        examples=["development", "staging", "production"],
    )

    environment_override_prefix: str = Field(
        default="ENV_OVERRIDE_",
        description="Prefix for environment-specific overrides",
    )


# === USAGE EXAMPLES ===

# Example 1: Standard multi-source configuration
standard_config = ModelConfigurationSubcontract(
    configuration_sources=[
        # Base configuration file (lowest priority)
        ModelConfigurationSource(
            source_name="base_config",
            source_type=ConfigurationSourceType.FILE,
            source_path="config/base.yaml",
            format=ConfigurationFormat.YAML,
            priority=100,
            required=True,
        ),
        # Environment-specific overrides (medium priority)
        ModelConfigurationSource(
            source_name="env_config",
            source_type=ConfigurationSourceType.FILE,
            source_path="config/production.yaml",
            format=ConfigurationFormat.YAML,
            priority=200,
            required=False,
        ),
        # Environment variables (highest priority)
        ModelConfigurationSource(
            source_name="env_vars",
            source_type=ConfigurationSourceType.ENVIRONMENT,
            source_path="APP_",  # Prefix for env vars
            priority=300,
            required=False,
        ),
    ],
    validation=ModelConfigurationValidation(
        validation_level=ValidationLevel.STRICT,
        required_fields=["database.host", "database.port", "api.base_url"],
    ),
    current_environment="production",
)

# Example 2: Configuration with secrets management
config_with_secrets = ModelConfigurationSubcontract(
    configuration_sources=[
        # Application config
        ModelConfigurationSource(
            source_name="app_config",
            source_type=ConfigurationSourceType.FILE,
            source_path="config/app.yaml",
            priority=100,
        ),
        # Secrets from external manager
        ModelConfigurationSource(
            source_name="secrets",
            source_type=ConfigurationSourceType.SECRETS_MANAGER,
            source_path="prod/app/secrets",  # Path in secrets manager
            priority=200,
            required=True,
        ),
    ],
    sensitive_data_handling=ModelSensitiveDataHandling(
        mask_sensitive_fields=True,
        sensitive_field_patterns=["*password*", "*secret*", "*api_key*"],
        encrypt_at_rest=True,
        encryption_key_source="env:CONFIG_ENCRYPTION_KEY",
    ),
)

# Example 3: Dynamic configuration with runtime updates
dynamic_config = ModelConfigurationSubcontract(
    configuration_sources=[
        # Base file config
        ModelConfigurationSource(
            source_name="base",
            source_type=ConfigurationSourceType.FILE,
            source_path="config/base.yaml",
            priority=100,
        ),
        # Consul for dynamic config
        ModelConfigurationSource(
            source_name="consul_config",
            source_type=ConfigurationSourceType.CONSUL,
            source_path="/app/runtime-config",
            priority=200,
            watch_for_changes=True,
            reload_on_change=True,
        ),
    ],
    allow_runtime_updates=True,
    update_grace_period_seconds=30,
    rollback_on_validation_failure=True,
    validation=ModelConfigurationValidation(
        validation_level=ValidationLevel.STRICT,
        validate_on_update=True,
    ),
)

# Example 4: Minimal configuration (environment variables only)
minimal_config = ModelConfigurationSubcontract(
    configuration_sources=[
        ModelConfigurationSource(
            source_name="env_only",
            source_type=ConfigurationSourceType.ENVIRONMENT,
            source_path="",  # All env vars
            priority=100,
        ),
    ],
    validation=ModelConfigurationValidation(
        validation_level=ValidationLevel.PERMISSIVE,
        required_fields=["PORT", "HOST"],
    ),
)
