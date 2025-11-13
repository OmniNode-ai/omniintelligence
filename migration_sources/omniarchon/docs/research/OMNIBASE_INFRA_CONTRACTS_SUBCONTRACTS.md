# Omnibase Infrastructure Contracts & Subcontracts - Comprehensive Analysis

**Date:** 2025-10-01
**Repository:** `/Volumes/PRO-G40/Code/omnibase_infra`
**Analysis Scope:** Complete contract definitions, subcontract implementations, usage patterns, and best examples

---

## Table of Contents

1. [Overview](#overview)
2. [Contract Architecture](#contract-architecture)
3. [Main Contract Structure](#main-contract-structure)
4. [Subcontract System](#subcontract-system)
5. [Complete Contract Examples](#complete-contract-examples)
6. [Complete Subcontract Examples](#complete-subcontract-examples)
7. [Python Model Implementations](#python-model-implementations)
8. [Usage Patterns](#usage-patterns)
9. [File Organization](#file-organization)
10. [Best Practices](#best-practices)

---

## Overview

The omnibase_infra project implements a sophisticated **contract-based architecture** where:

- **Contracts** define the complete specification for infrastructure nodes (Effect, Compute, Reducer, Orchestrator)
- **Subcontracts** provide reusable, composable patterns that can be mixed into main contracts
- **Models** represent structured data following Pydantic-based validation patterns
- **Nodes** implement the contracts via concrete Python classes

### Key Statistics

- **Total Subcontract Files:** 9 YAML subcontracts identified
- **Main Contracts:** 10+ node contracts across different types
- **Integration Pattern:** Mixin-based composition for subcontracts
- **Node Types:** Effect (PostgreSQL, Kafka), Compute, Orchestrator, Reducer patterns

---

## Contract Architecture

### ONEX Contract Principles

```yaml
# Every contract follows this structure:
contract_version: {major: 1, minor: 0, patch: 0}
node_name: "name"
node_type: "EFFECT" | "COMPUTE" | "REDUCER" | "ORCHESTRATOR"
input_model: "ModelInputClass"
output_model: "ModelOutputClass"

# Core sections:
- node_specification    # Node metadata and configuration
- dependencies          # Protocol and service dependencies
- shared_model_dependencies  # Shared Pydantic models
- event_type           # Event bus configuration
- input_state          # Input schema definition
- output_state         # Output schema definition
- io_operations        # Effect node I/O operations
- subcontracts         # Reusable pattern compositions
- definitions          # Model definitions
- shared_models        # Shared model references
```

### Contract Hierarchy

```
Main Contract (contract.yaml)
├── Node Specification
├── Dependencies (Protocols)
├── Shared Model Dependencies
├── Event Configuration
├── I/O Definitions
└── Subcontracts (Compositions)
    ├── Configuration Subcontract
    ├── Event Processing Subcontract
    ├── Connection Management Subcontract
    ├── Health Check Mixin Subcontract
    ├── Node Service Mixin Subcontract
    └── Node ID Contract Mixin Subcontract
```

---

## Main Contract Structure

### Complete PostgreSQL Adapter Contract

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contract.yaml`

```yaml
# Infrastructure PostgreSQL Adapter - ONEX Contract
# Effect node for PostgreSQL database operations via message bus integration

# === REQUIRED ROOT FIELDS ===
contract_version: {major: 1, minor: 0, patch: 0}
node_name: "postgres_adapter"
node_version: {major: 1, minor: 0, patch: 0}
contract_name: "postgres_adapter_contract"
description: "Infrastructure PostgreSQL Adapter - Message Bus to PostgreSQL Database Bridge"
node_type: "EFFECT"
name: "postgres_adapter"
version: {major: 1, minor: 0, patch: 0}
input_model: "ModelPostgresAdapterInput"
output_model: "ModelPostgresAdapterOutput"

# === REQUIRED METADATA FIELDS ===
uuid: "550e8400-e29b-41d4-a716-446655440000"
created_at: "2025-09-12T15:00:00Z"
last_modified_at: "2025-09-12T15:05:00Z"
hash: "sha256:abcd1234567890fedcba"
entrypoint: "omnibase_infra.nodes.node_postgres_adapter_effect.v1_0_0.node:NodePostgresAdapterEffect"
namespace: "omnibase_infra.infrastructure"
author: "ONEX"

# === NODE SPECIFICATION ===
node_specification:
  node_name: "postgres_adapter"
  version: {major: 1, minor: 0, patch: 0}
  description: "Infrastructure PostgreSQL Adapter - Message Bus to PostgreSQL Database Bridge"
  main_node_class: "Node"
  container_injection: "ONEXContainer"
  business_logic_pattern: "effect"

# === DEPENDENCIES ===
dependencies:
  - name: "protocol_database_client"
    type: "protocol"
    class_name: "ProtocolDatabaseClient"
    module: "omnibase_spi.protocols.core"
  - name: "protocol_event_bus"
    type: "protocol"
    class_name: "ProtocolEventBus"
    module: "omnibase_spi.protocols.event_bus"
  - name: "protocol_connection_pool"
    type: "protocol"
    class_name: "ProtocolConnectionPool"
    module: "omnibase_spi.protocols.core"
  - name: "postgres_connection_manager"
    type: "protocol"
    class_name: "PostgresConnectionManager"
    module: "omnibase_infra.infrastructure.postgres_connection_manager"

# === SHARED MODEL DEPENDENCIES ===
shared_model_dependencies:
  - name: "model_postgres_query_request"
    type: "model"
    class_name: "ModelPostgresQueryRequest"
    module: "omnibase_infra.models.postgres.model_postgres_query_request"
    description: "Shared PostgreSQL query request model"

  - name: "model_postgres_query_response"
    type: "model"
    class_name: "ModelPostgresQueryResponse"
    module: "omnibase_infra.models.postgres.model_postgres_query_response"
    description: "Shared PostgreSQL query response model"

  - name: "model_configuration_subcontract"
    type: "model"
    class_name: "ModelConfigurationSubcontract"
    module: "omnibase_infra.models.infrastructure.model_configuration_subcontract"
    description: "Shared configuration management subcontract model"

# === EVENT TYPE CONFIGURATION ===
event_type:
  primary_events: ["postgres_query_operation", "postgres_transaction_operation", "postgres_health_check"]
  event_categories: ["infrastructure", "database", "persistence"]
  publish_events: true
  subscribe_events: false
  event_routing: "infrastructure"

# === INPUT/OUTPUT STATE ===
input_state:
  object_type: "object"
  required:
    - "operation_type"
    - "correlation_id"
    - "timestamp"
  properties:
    operation_type:
      property_type: "string"
      enum: ["query", "health_check"]
      description: "Type of PostgreSQL operation to perform"

    query_request:
      property_type: "object"
      description: "Query request payload"
      reference: "ModelPostgresQueryRequest"

    correlation_id:
      property_type: "string"
      description: "Request correlation ID for tracing"
      format: "uuid"

output_state:
  object_type: "object"
  properties:
    operation_type:
      property_type: "string"
      description: "Type of operation that was executed"

    query_response:
      property_type: "object"
      description: "Query response payload"
      reference: "ModelPostgresQueryResponse"

    success:
      property_type: "boolean"
      description: "Whether the operation was successful"

# === IO OPERATIONS (Required for EFFECT nodes) ===
io_operations:
  - operation_type: "postgres_query_execution"
    atomic: true
    backup_enabled: false
    permissions: null
    recursive: false
    buffer_size: 8192
    timeout_seconds: 30
    validation_enabled: true

  - operation_type: "postgres_transaction_execution"
    atomic: true
    backup_enabled: true
    permissions: null
    recursive: false
    buffer_size: 16384
    timeout_seconds: 60
    validation_enabled: true

# === SUBCONTRACTS ===
subcontracts:
  - name: "configuration_subcontract"
    path: "./contracts/configuration_subcontract.yaml"
    description: "Standardized configuration management for infrastructure nodes"
    integration_type: "mixin"

  - name: "postgres_event_processing_subcontract"
    path: "./contracts/postgres_event_processing_subcontract.yaml"
    description: "Event bus integration patterns for PostgreSQL operations"
    integration_type: "mixin"

  - name: "postgres_connection_management_subcontract"
    path: "./contracts/postgres_connection_management_subcontract.yaml"
    description: "Connection pool and database management patterns"
    integration_type: "mixin"

# === DEFINITIONS ===
definitions:
  models:
    ModelPostgresAdapterInput:
      type: "object"
      description: "Input envelope for PostgreSQL adapter operations"
      properties:
        operation_type:
          type: "string"
          enum: ["query", "health_check"]
        query_request:
          $ref: "#/shared_models/ModelPostgresQueryRequest"
        correlation_id:
          type: "string"
          format: "uuid"
      required: ["operation_type", "correlation_id", "timestamp"]

    ModelPostgresAdapterOutput:
      type: "object"
      description: "Output envelope for PostgreSQL adapter operations"
      properties:
        operation_type:
          type: "string"
        query_response:
          $ref: "#/shared_models/ModelPostgresQueryResponse"
        success:
          type: "boolean"
      required: ["operation_type", "success", "correlation_id", "timestamp"]
```

### Key Contract Features

1. **Version Management:** Semantic versioning at contract and node level
2. **Dependency Injection:** Protocol-based dependency specification
3. **Model References:** Shared model dependencies for type safety
4. **Event Integration:** Event bus configuration for message routing
5. **I/O Operations:** Effect node I/O operation specifications
6. **Subcontract Composition:** Mixin-based reusable pattern inclusion

---

## Subcontract System

### Subcontract Types Identified

1. **Configuration Subcontract** - Configuration management patterns
2. **Event Processing Subcontract** - Event bus integration patterns
3. **Connection Management Subcontract** - Connection pool and resource management
4. **Health Check Mixin Subcontract** - Standardized health monitoring
5. **Node Service Mixin Subcontract** - Service lifecycle management
6. **Node ID Contract Mixin Subcontract** - Contract-based node identification

### Subcontract Integration Pattern

```yaml
# In Main Contract:
subcontracts:
  - name: "configuration_subcontract"
    path: "./contracts/configuration_subcontract.yaml"
    description: "Standardized configuration management"
    integration_type: "mixin"  # Mixin composition pattern
```

### Benefits of Subcontracts

- **Reusability:** Same subcontract used across multiple nodes
- **Consistency:** Standardized patterns across infrastructure
- **Maintainability:** Update pattern once, applies to all nodes
- **Composition:** Mix multiple subcontracts as needed
- **Validation:** Type-safe composition via model validation

---

## Complete Subcontract Examples

### 1. Configuration Subcontract (Most Complete)

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/configuration_subcontract.yaml`

```yaml
# Configuration Management Subcontract - ONEX Infrastructure Standards
# Provides standardized configuration loading, validation, and environment management

# === SUBCONTRACT METADATA ===
subcontract_version: {major: 1, minor: 0, patch: 0}
subcontract_name: "configuration_subcontract"
description: "Configuration management patterns for ONEX infrastructure nodes"
integration_type: "mixin"

# === CONFIGURATION STRATEGY ===
configuration_strategy:
  loading_order: ["container", "environment", "defaults"]
  validation_enabled: true
  environment_prefix_required: true
  secret_detection_enabled: true
  hot_reload_supported: false

# === ENVIRONMENT CONFIGURATION ===
environment_configuration:
  prefix_pattern: "ONEX_INFRA_{NODE_NAME}_"
  required_variables: []
  optional_variables: []
  validation_rules:
    - type: "format"
      pattern: "^[A-Z_][A-Z0-9_]*$"
    - type: "length"
      min_length: 1
      max_length: 256

# === CONTAINER CONFIGURATION ===
container_configuration:
  service_resolution_enabled: true
  fallback_to_environment: true
  configuration_service_key: "configuration_service"
  cache_configuration: true

# === VALIDATION PATTERNS ===
validation_patterns:
  database_connection_string:
    pattern: "^postgresql://[^:]+:[^@]+@[^:]+:[0-9]+/[^/]+$"
    required: true
    sensitive: true

  port_number:
    pattern: "^[1-9][0-9]{0,4}$"
    range: [1, 65535]
    required: true

  boolean_flag:
    pattern: "^(true|false|0|1|yes|no)$"
    required: false

  timeout_seconds:
    pattern: "^[1-9][0-9]*$"
    range: [1, 3600]
    required: false

# === SECURITY CONFIGURATION ===
security_configuration:
  sanitize_logs: true
  mask_sensitive_values: true
  sensitive_patterns:
    - "password"
    - "secret"
    - "key"
    - "token"
    - "credential"
  redaction_replacement: "[REDACTED]"

# === ERROR HANDLING ===
error_handling:
  fail_on_missing_required: true
  fail_on_invalid_format: true
  log_configuration_errors: true
  provide_detailed_validation_messages: true

# === MODELS DEFINITION ===
models:
  ModelConfigurationSource:
    type: "object"
    description: "Configuration source with priority and validation"
    properties:
      source_type:
        type: "string"
        enum: ["container", "environment", "defaults", "file"]
      priority:
        type: "integer"
        minimum: 1
        maximum: 100
      validation_enabled:
        type: "boolean"
        default: true
    required: ["source_type", "priority"]

  ModelEnvironmentConfiguration:
    type: "object"
    description: "Environment-based configuration loading"
    properties:
      prefix:
        type: "string"
        pattern: "^[A-Z_][A-Z0-9_]*_$"
        description: "Environment variable prefix"
      required_variables:
        type: "array"
        items:
          type: "string"
      optional_variables:
        type: "array"
        items:
          type: "string"
    required: ["prefix"]

  ModelConfigurationValidation:
    type: "object"
    description: "Configuration validation rules and patterns"
    properties:
      validation_rules:
        type: "array"
        items:
          $ref: "#/models/ModelValidationRule"
      sensitive_field_patterns:
        type: "array"
        items:
          type: "string"
    required: ["validation_rules"]

  ModelValidationRule:
    type: "object"
    description: "Individual validation rule for configuration values"
    properties:
      field_name:
        type: "string"
      rule_type:
        type: "string"
        enum: ["format", "range", "enum", "required"]
      pattern:
        type: "string"
      range_min:
        type: "number"
      range_max:
        type: "number"
      allowed_values:
        type: "array"
        items:
          type: "string"
      error_message:
        type: "string"
    required: ["field_name", "rule_type"]

# === INTEGRATION PATTERNS ===
integration_patterns:
  container_service_resolution:
    enabled: true
    service_key: "configuration_service"
    fallback_enabled: true

  environment_variable_loading:
    enabled: true
    prefix_required: true
    validation_enabled: true

  default_value_fallback:
    enabled: true
    log_fallback_usage: true

  configuration_caching:
    enabled: true
    cache_duration_seconds: 300
    invalidation_on_error: true

# === MIXIN CAPABILITIES ===
mixin_capabilities:
  - "load_configuration_from_container"
  - "load_configuration_from_environment"
  - "validate_configuration_values"
  - "sanitize_sensitive_configuration"
  - "provide_configuration_defaults"
  - "cache_configuration_results"
  - "handle_configuration_errors"
```

### 2. Event Processing Subcontract (PostgreSQL)

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/postgres_event_processing_subcontract.yaml`

```yaml
# PostgreSQL Event Processing Subcontract - Event Bus Integration Pattern
# Defines event handling patterns for PostgreSQL adapter integration with ONEX event bus

contract_type: "postgres_event_processing_subcontract"
contract_version:
  major: 1
  minor: 0
  patch: 0

metadata:
  name: "PostgresEventProcessingSubcontract"
  description: "Event bus integration for PostgreSQL adapter with ONEX message envelope handling"
  author: "ONEX Framework Team"
  created: "2025-09-11"
  purpose: "Define event processing patterns for bi-directional PostgreSQL-ONEX event communication"

business_logic:
  pattern: "event_bus_integration"
  ai_agent:
    capabilities: ["event_envelope_processing", "postgres_event_translation", "async_event_handling"]
    coordination_patterns: ["event_bus_subscriber", "event_bus_publisher"]
    performance_targets:
      event_processing_latency: "<10ms"
      event_throughput: "1000 events/sec"
      envelope_parsing_time: "<1ms"

# Event Bus Integration Strategy
event_bus_integration:
  name: "PostgresEventBusIntegration"
  description: "Bi-directional event processing between ONEX event bus and PostgreSQL operations"

  # Event subscription patterns
  subscription_patterns:
    inbound_events:
      - event_type: "postgres_query_request"
        handler: "handle_query_event"
        envelope_validation: true
        async_processing: true

      - event_type: "postgres_transaction_request"
        handler: "handle_transaction_event"
        envelope_validation: true
        async_processing: true

      - event_type: "postgres_health_check_request"
        handler: "handle_health_check_event"
        envelope_validation: true
        async_processing: false

  # Event publishing patterns
  publishing_patterns:
    outbound_events:
      - event_type: "postgres_query_completed"
        trigger: "query_execution_complete"
        envelope_format: "standard_onex_envelope"
        metadata_inclusion: ["query_hash", "execution_time", "rows_affected", "timestamp"]

      - event_type: "postgres_transaction_completed"
        trigger: "transaction_success"
        envelope_format: "standard_onex_envelope"
        metadata_inclusion: ["transaction_id", "isolation_level", "timestamp"]

      - event_type: "postgres_operation_failed"
        trigger: "operation_error"
        envelope_format: "error_onex_envelope"
        metadata_inclusion: ["operation_type", "error_code", "error_message", "timestamp"]

# Event Envelope Handling
envelope_processing:
  inbound_envelope_handling:
    validation_steps:
      - "validate_envelope_structure"
      - "verify_message_signature"
      - "check_correlation_id"
      - "validate_payload_schema"

    parsing_steps:
      - "extract_operation_type"
      - "parse_postgres_parameters"
      - "resolve_connection_pool"
      - "prepare_database_operation"

    error_handling:
      - "malformed_envelope": "reject_with_error_response"
      - "invalid_signature": "reject_with_security_alert"
      - "schema_validation_failed": "reject_with_validation_error"
      - "missing_correlation_id": "assign_new_correlation_id"

  outbound_envelope_creation:
    envelope_structure:
      - "correlation_id": "preserve_from_inbound_or_generate"
      - "source_service": "postgres_adapter"
      - "target_service": "extracted_from_routing_info"
      - "event_type": "determined_by_operation_result"
      - "payload": "postgres_operation_result_or_error"
      - "metadata": "operation_context_and_timing"

# Async Processing Patterns
async_processing:
  async_handlers:
    query_operations:
      pattern: "request_response_async"
      timeout_ms: 5000
      retry_attempts: 3
      error_strategy: "emit_failure_event"

    transaction_operations:
      pattern: "fire_and_forget_with_callback"
      timeout_ms: 10000
      retry_attempts: 2
      error_strategy: "emit_failure_event_with_rollback"

  # Synchronous processing for health checks
  sync_processing:
    health_checks:
      pattern: "immediate_response"
      timeout_ms: 1000
      retry_attempts: 0
      error_strategy: "return_error_status"

# Event Routing and Filtering
event_routing:
  routing_strategy: "content_based_routing"

  routing_rules:
    - condition: "event_type.startswith('postgres_query_')"
      target_handler: "query_management_handler"
      priority: "high"

    - condition: "event_type.startswith('postgres_transaction_')"
      target_handler: "transaction_management_handler"
      priority: "critical"

    - condition: "event_type.startswith('postgres_health_')"
      target_handler: "health_management_handler"
      priority: "medium"

  filtering_rules:
    - filter: "validate_database_permissions"
      action: "reject_if_unauthorized_schema"

    - filter: "check_connection_pool_limits"
      action: "defer_if_pool_exhausted"

    - filter: "validate_query_safety"
      action: "reject_if_dangerous_operation"

# Performance Optimization
performance_optimization:
  event_batching:
    enabled: true
    batch_size: 25
    batch_timeout_ms: 50
    applicable_operations: ["query_operations", "health_checks"]

  connection_pooling:
    postgres_connections: 10
    connection_reuse: true
    keepalive_interval: 30000

  caching:
    event_handler_cache: true
    query_plan_cache: true
    envelope_validation_cache: true

# Observability and Monitoring
observability:
  metrics:
    - "postgres.events_processed"
    - "postgres.events_published"
    - "postgres.envelope_validation_failures"
    - "postgres.async_processing_latency"
    - "postgres.database_error_rate"

  events_for_monitoring:
    - "event_processing_started"
    - "event_processing_completed"
    - "envelope_validation_failed"
    - "database_error_occurred"

# Integration with Main Contract
integration:
  main_contract_field: "event_processing_configuration"
  mapping_strategy: "event_handler_embedding"
  backward_compatibility: true
```

### 3. Connection Management Subcontract (PostgreSQL)

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/postgres_connection_management_subcontract.yaml`

```yaml
# PostgreSQL Connection Management Subcontract - Connection Pool Integration Pattern
# Defines connection pooling and database management patterns for PostgreSQL adapter

contract_type: "postgres_connection_management_subcontract"
contract_version:
  major: 1
  minor: 0
  patch: 0

metadata:
  name: "PostgresConnectionManagementSubcontract"
  description: "Connection pool management and database operations integration pattern"
  author: "ONEX Framework Team"
  created: "2025-09-11"
  purpose: "Define consistent connection management and database operation patterns"

business_logic:
  pattern: "connection_management"
  ai_agent:
    capabilities: ["connection_pooling", "transaction_management", "health_monitoring"]
    coordination_patterns: ["pool_management", "connection_lifecycle"]
    performance_targets:
      connection_acquisition_latency: "<50ms"
      query_execution_latency: "<100ms"
      pool_efficiency: ">90%"

# Connection Management Strategy
connection_strategy:
  name: "PostgresConnectionStrategy"
  description: "Enterprise-grade PostgreSQL connection management with pooling and monitoring"

  # Connection pool configuration
  pool_configuration:
    connection_pool_settings:
      min_connections: 5
      max_connections: 50
      connection_timeout: "10s"
      idle_timeout: "300s"
      max_connection_lifetime: "3600s"

    pool_health_monitoring:
      health_check_interval: "30s"
      connection_validation_query: "SELECT 1"
      failed_connection_threshold: 3
      pool_recovery_strategy: "gradual_replenishment"

  # Transaction management patterns
  transaction_patterns:
    isolation_levels:
      - "read_uncommitted"
      - "read_committed" # default
      - "repeatable_read"
      - "serializable"

    transaction_strategies:
      short_transactions:
        max_duration: "30s"
        retry_attempts: 3
        rollback_on_timeout: true

      long_transactions:
        max_duration: "300s"
        retry_attempts: 1
        rollback_on_timeout: true
        monitoring_enabled: true

      batch_transactions:
        batch_size: 100
        commit_interval: "10s"
        rollback_on_partial_failure: true

# Database Operation Patterns
operation_patterns:
  query_execution:
    read_operations:
      - pattern: "single_row_fetch"
        timeout: "5s"
        caching_enabled: false

      - pattern: "bulk_data_fetch"
        timeout: "30s"
        streaming_enabled: true
        batch_size: 1000

    write_operations:
      - pattern: "single_insert"
        timeout: "10s"
        return_generated_keys: true

      - pattern: "bulk_insert"
        timeout: "60s"
        batch_size: 500
        transaction_required: true

      - pattern: "update_operations"
        timeout: "30s"
        optimistic_locking: true
        affected_rows_validation: true

  # Prepared statement management
  prepared_statements:
    caching_strategy: "lru_cache"
    max_cached_statements: 100
    statement_timeout: "300s"
    auto_prepare_threshold: 5

# Connection Lifecycle Management
lifecycle_management:
  connection_acquisition:
    acquisition_strategy: "fair_queuing"
    max_wait_time: "30s"
    connection_validation: true

  connection_release:
    cleanup_strategy: "automatic"
    resource_validation: true
    connection_reset: true

  connection_monitoring:
    active_connection_tracking: true
    idle_connection_cleanup: true
    connection_leak_detection: true

# Health Check Integration
health_integration:
  database_health:
    connectivity_check:
      query: "SELECT version()"
      timeout: "5s"
      frequency: "60s"

    performance_check:
      slow_query_threshold: "1s"
      connection_pool_utilization_threshold: "80%"
      active_connection_limit: "90%"

  health_status_reporting:
    status_levels:
      - "healthy": "all_checks_passing"
      - "degraded": "some_checks_failing"
      - "unhealthy": "critical_checks_failing"

    health_metrics:
      - "connection_pool_size"
      - "active_connections"
      - "idle_connections"
      - "failed_connection_attempts"
      - "average_query_time"

# Error Handling and Recovery
error_handling:
  connection_errors:
    network_failures:
      retry_strategy: "exponential_backoff"
      max_retries: 3
      backoff_multiplier: 2
      recovery_action: "connection_pool_refresh"

    authentication_failures:
      retry_strategy: "none"
      alert_strategy: "immediate_security_alert"
      recovery_action: "credential_validation"

  transaction_errors:
    deadlock_handling:
      detection: "database_error_code_analysis"
      retry_strategy: "random_delay_retry"
      max_retries: 3

    constraint_violations:
      handling: "immediate_rollback"
      reporting: "detailed_error_response"
      recovery: "data_validation_enhancement"

# Performance Optimization
performance_optimization:
  query_optimization:
    query_plan_caching: true
    parameter_binding: true
    batch_execution: true

  connection_optimization:
    connection_warm_up: true
    connection_preallocation: true
    connection_affinity: true

  monitoring_optimization:
    metrics_aggregation: true
    performance_baseline_tracking: true
    auto_scaling_triggers: true

# Observability
observability:
  metrics:
    - "postgres.connection_pool_size"
    - "postgres.active_connections"
    - "postgres.connection_acquisition_time"
    - "postgres.query_execution_time"
    - "postgres.transaction_duration"
    - "postgres.connection_errors"

  events:
    - "connection_acquired"
    - "connection_released"
    - "transaction_started"
    - "transaction_committed"
    - "transaction_rolled_back"
    - "connection_pool_exhausted"

# Integration with Main Contract
integration:
  main_contract_field: "connection_management_configuration"
  mapping_strategy: "dependency_injection"
  backward_compatibility: true
```

### 4. Health Check Mixin Subcontract

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/health_check_mixin_subcontract.yaml`

```yaml
# Health Check Mixin Subcontract - Standardized Health Monitoring Pattern
# Defines health check patterns for MixinHealthCheck integration

contract_type: "health_check_mixin_subcontract"
contract_version:
  major: 1
  minor: 0
  patch: 0

metadata:
  name: "HealthCheckMixinSubcontract"
  description: "Standardized health monitoring for MixinHealthCheck integration with ONEX nodes"
  author: "ONEX Framework Team"
  created: "2025-01-15"
  purpose: "Define health check patterns for comprehensive node health monitoring"

business_logic:
  pattern: "standardized_health_monitoring"
  ai_agent:
    capabilities: ["health_assessment", "dependency_monitoring", "performance_tracking"]
    coordination_patterns: ["health_aggregator", "status_publisher", "monitoring_agent"]
    performance_targets:
      health_check_duration: "<100ms"
      status_reporting_frequency: "30s"
      dependency_check_timeout: "<500ms"

# Health Check Architecture
health_check_architecture:
  name: "StandardizedHealthMonitoring"
  description: "Comprehensive health monitoring system for ONEX infrastructure nodes"

  # Health check execution patterns
  execution_patterns:
    synchronous_checks:
      - check_type: "basic_operational_status"
        description: "Verify node is operational and responsive"
        timeout_ms: 50
        required: true

      - check_type: "immediate_dependency_status"
        description: "Check critical dependencies immediately available"
        timeout_ms: 100
        required: true

    asynchronous_checks:
      - check_type: "comprehensive_dependency_analysis"
        description: "Deep analysis of all service dependencies"
        timeout_ms: 2000
        required: false

      - check_type: "performance_metrics_collection"
        description: "Collect detailed performance metrics"
        timeout_ms: 1000
        required: false

  # Health status aggregation
  status_aggregation:
    aggregation_strategy: "worst_case_wins"
    status_hierarchy:
      - status: "CRITICAL"
        priority: 1
        escalation: "immediate_alert"

      - status: "UNHEALTHY"
        priority: 2
        escalation: "urgent_notification"

      - status: "DEGRADED"
        priority: 3
        escalation: "monitoring_alert"

      - status: "HEALTHY"
        priority: 4
        escalation: "none"

# PostgreSQL-Specific Health Checks
postgresql_health_checks:
  database_connectivity:
    check_name: "database_connectivity"
    description: "Verify PostgreSQL database connection is established and responsive"
    implementation: "_check_database_connectivity"
    timeout_ms: 2000
    retry_attempts: 2
    critical: true

  connection_pool_health:
    check_name: "connection_pool_health"
    description: "Validate PostgreSQL connection pool status and capacity"
    implementation: "_check_connection_pool_health"
    timeout_ms: 500
    retry_attempts: 1
    critical: false

  query_execution_capability:
    check_name: "query_execution_capability"
    description: "Test basic query execution against PostgreSQL database"
    implementation: "_check_query_execution_capability"
    timeout_ms: 1000
    retry_attempts: 1
    critical: true

# Health Status Models
health_status_models:
  model_health_status:
    fields:
      - name: "status"
        type: "EnumHealthStatus"
        required: true
        description: "Overall health status using ONEX standard enum"

      - name: "message"
        type: "Optional[str]"
        required: false
        description: "Human-readable status description"

      - name: "timestamp"
        type: "Optional[str]"
        required: false
        description: "ISO format timestamp of health check execution"

  enum_health_status:
    values:
      - "HEALTHY": "Service is fully operational"
      - "DEGRADED": "Service is operational but experiencing issues"
      - "UNHEALTHY": "Service has significant issues affecting functionality"
      - "CRITICAL": "Service is failing or non-responsive"

# Dependency Health Monitoring
dependency_monitoring:
  dependency_categories:
    critical_dependencies:
      - dependency: "postgresql_database"
        check_method: "database_connectivity_check"
        failure_impact: "service_unavailable"

      - dependency: "connection_manager"
        check_method: "connection_manager_health_check"
        failure_impact: "degraded_performance"

# Monitoring Integration
monitoring_integration:
  metrics_emission:
    health_check_metrics:
      - "health_check.execution_time_ms"
      - "health_check.success_rate"
      - "health_check.failure_count"
      - "health_check.dependency_health_score"

  alerting_rules:
    critical_alerts:
      - condition: "status == CRITICAL"
        action: "immediate_page"

      - condition: "consecutive_unhealthy > 3"
        action: "escalate_to_oncall"

# Integration with Main Contract
integration:
  main_contract_field: "health_monitoring_configuration"
  mapping_strategy: "health_check_embedding"
  backward_compatibility: true
```

### 5. Node Service Mixin Subcontract

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/node_service_mixin_subcontract.yaml`

```yaml
# Node Service Mixin Subcontract - Service Lifecycle Management Pattern
# Defines service lifecycle patterns for MixinNodeService integration

contract_type: "node_service_mixin_subcontract"
contract_version:
  major: 1
  minor: 0
  patch: 0

metadata:
  name: "NodeServiceMixinSubcontract"
  description: "Service lifecycle management for MixinNodeService integration"
  author: "ONEX Framework Team"
  created: "2025-01-15"
  purpose: "Define service lifecycle patterns for node service management"

business_logic:
  pattern: "node_service_lifecycle"
  ai_agent:
    capabilities: ["service_startup", "service_shutdown", "service_monitoring"]
    coordination_patterns: ["service_registry", "event_subscriber", "lifecycle_manager"]
    performance_targets:
      service_startup_time: "<500ms"
      service_shutdown_time: "<200ms"
      heartbeat_frequency: "30s"

# Service Lifecycle Management
service_lifecycle:
  name: "NodeServiceLifecycle"
  description: "Standardized service lifecycle management for ONEX infrastructure nodes"

  # Service initialization patterns
  initialization_patterns:
    startup_sequence:
      - step: "container_injection"
        description: "Inject ONEXContainer with dependencies"
        required: true
        timeout_ms: 1000

      - step: "event_bus_connection"
        description: "Connect to ONEX event bus for service coordination"
        required: true
        timeout_ms: 2000

      - step: "service_registration"
        description: "Register service with ONEX service registry"
        required: true
        timeout_ms: 1000

  # Service shutdown patterns
  shutdown_patterns:
    graceful_shutdown:
      - step: "stop_accepting_requests"
        description: "Stop accepting new service requests"
        timeout_ms: 100

      - step: "complete_active_operations"
        description: "Allow active operations to complete"
        timeout_ms: 5000

      - step: "disconnect_event_bus"
        description: "Gracefully disconnect from event bus"
        timeout_ms: 1000

# Event Bus Integration
event_bus_integration:
  service_coordination:
    heartbeat_events:
      event_type: "service_heartbeat"
      frequency_seconds: 30
      payload_fields: ["service_id", "status", "timestamp", "health_status"]

    lifecycle_events:
      service_started:
        event_type: "service_lifecycle_started"
        payload: ["service_id", "node_type", "domain", "capabilities"]

      service_stopped:
        event_type: "service_lifecycle_stopped"
        payload: ["service_id", "final_status", "shutdown_duration_ms"]

# Integration with Main Contract
integration:
  main_contract_field: "service_lifecycle_configuration"
  mapping_strategy: "mixin_embedding"
  backward_compatibility: true
```

### 6. Node ID Contract Mixin Subcontract

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contracts/node_id_contract_mixin_subcontract.yaml`

```yaml
# Node ID from Contract Mixin Subcontract - Contract-Based Node Identification
# Defines node ID loading patterns for MixinNodeIdFromContract integration

contract_type: "node_id_contract_mixin_subcontract"
contract_version:
  major: 1
  minor: 0
  patch: 0

metadata:
  name: "NodeIdContractMixinSubcontract"
  description: "Contract-based node ID loading for MixinNodeIdFromContract"
  author: "ONEX Framework Team"
  created: "2025-01-15"
  purpose: "Define contract-driven node identification patterns"

business_logic:
  pattern: "contract_based_node_identification"
  ai_agent:
    capabilities: ["contract_parsing", "node_id_extraction", "contract_validation"]
    coordination_patterns: ["contract_loader", "id_resolver", "validation_engine"]
    performance_targets:
      contract_load_time: "<50ms"
      id_resolution_time: "<10ms"

# Contract-Based Node ID Management
node_id_management:
  name: "ContractBasedNodeIdentification"
  description: "Standardized node ID loading from contract.yaml"

  # Contract loading patterns
  contract_loading:
    contract_discovery:
      - location: "contract.yaml"
        relative_to: "node_directory"
        priority: "primary"
        required: true

    contract_parsing:
      - field: "node_name"
        path: "metadata.node_name"
        fallback_path: "name"
        required: true

      - field: "version"
        path: "metadata.version"
        fallback_path: "version"
        required: true

  # Node ID generation patterns
  id_generation:
    primary_strategy:
      pattern: "contract_name_based"
      source_fields: ["contract_name", "node_name"]
      format: "{contract_name}_{version_major}_{version_minor}_{version_patch}"
      validation: "alphanumeric_underscore_only"

    fallback_strategies:
      - pattern: "node_name_based"
        source_fields: ["node_name"]
        format: "{node_name}_{version_major}_{version_minor}_{version_patch}"
        condition: "contract_name_missing"

# Integration with Main Contract
integration:
  main_contract_field: "node_identification_configuration"
  mapping_strategy: "metadata_extraction"
  backward_compatibility: true
```

---

## Python Model Implementations

### ModelConfigurationSubcontract - Complete Implementation

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/models/infrastructure/model_configuration_subcontract.py`

```python
#!/usr/bin/env python3
"""
Configuration Subcontract Model - ONEX Infrastructure Standards Compliant.

Dedicated subcontract model for configuration functionality providing:
- Configuration source priority and validation
- Environment variable loading with prefix patterns
- Container service resolution with fallback
- Configuration validation and sanitization
- Sensitive data detection and masking
- Error handling and logging

ZERO TOLERANCE: No Any types allowed in implementation.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ConfigurationSourceType(str, Enum):
    """Configuration source types in priority order."""
    CONTAINER = "container"
    ENVIRONMENT = "environment"
    DEFAULTS = "defaults"
    FILE = "file"


class ValidationRuleType(str, Enum):
    """Configuration validation rule types."""
    FORMAT = "format"
    RANGE = "range"
    ENUM = "enum"
    REQUIRED = "required"


class ModelConfigurationSource(BaseModel):
    """
    Configuration source with priority and validation.

    Defines where configuration values are loaded from
    and in what order, with validation capabilities.
    """

    source_type: ConfigurationSourceType = Field(
        ...,
        description="Type of configuration source",
    )

    priority: int = Field(
        ...,
        description="Priority for configuration loading (1-100)",
        ge=1,
        le=100,
    )

    validation_enabled: bool = Field(
        default=True,
        description="Whether validation is enabled for this source",
    )


class ModelEnvironmentConfiguration(BaseModel):
    """
    Environment-based configuration loading.

    Manages environment variable loading with proper
    prefixing, validation, and fallback values.
    """

    prefix: str = Field(
        ...,
        description="Environment variable prefix pattern",
        min_length=1,
        max_length=64,
    )

    required_variables: list[str] = Field(
        default_factory=list,
        description="Required environment variables",
    )

    optional_variables: list[str] = Field(
        default_factory=list,
        description="Optional environment variables",
    )

    fallback_values: dict[str, str] = Field(
        default_factory=dict,
        description="Fallback values for missing variables",
    )

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, v: str) -> str:
        """Validate environment prefix follows ONEX patterns."""
        if not v.endswith("_"):
            v = f"{v}_"
        if not v.isupper():
            v = v.upper()
        return v


class ModelValidationRule(BaseModel):
    """
    Individual validation rule for configuration values.

    Defines specific validation logic for configuration
    fields including format, range, and enum constraints.
    """

    field_name: str = Field(
        ...,
        description="Name of the field to validate",
        min_length=1,
    )

    rule_type: ValidationRuleType = Field(
        ...,
        description="Type of validation rule to apply",
    )

    pattern: str | None = Field(
        default=None,
        description="Regex pattern for format validation",
    )

    range_min: float | None = Field(
        default=None,
        description="Minimum value for range validation",
    )

    range_max: float | None = Field(
        default=None,
        description="Maximum value for range validation",
    )

    allowed_values: list[str] | None = Field(
        default=None,
        description="Allowed values for enum validation",
    )

    error_message: str | None = Field(
        default=None,
        description="Custom error message for validation failure",
    )


class ModelConfigurationValidation(BaseModel):
    """
    Configuration validation rules and patterns.

    Manages validation rules, sensitive field detection,
    and required field enforcement for configuration.
    """

    validation_rules: list[ModelValidationRule] = Field(
        ...,
        description="List of validation rules to apply",
    )

    sensitive_field_patterns: list[str] = Field(
        default_factory=lambda: ["password", "secret", "key", "token", "credential"],
        description="Patterns to identify sensitive fields",
    )

    required_fields: list[str] = Field(
        default_factory=list,
        description="List of required configuration fields",
    )


class ModelConfigurationIntegration(BaseModel):
    """
    Configuration integration patterns.

    Defines how configuration integrates with container
    services, environment loading, and caching systems.
    """

    container_service_resolution_enabled: bool = Field(
        default=True,
        description="Enable container service resolution",
    )

    container_service_key: str = Field(
        default="configuration_service",
        description="Service key for container resolution",
    )

    environment_loading_enabled: bool = Field(
        default=True,
        description="Enable environment variable loading",
    )

    prefix_required: bool = Field(
        default=True,
        description="Require environment variable prefix",
    )

    fallback_enabled: bool = Field(
        default=True,
        description="Enable fallback to defaults",
    )

    caching_enabled: bool = Field(
        default=True,
        description="Enable configuration caching",
    )

    cache_duration_seconds: int = Field(
        default=300,
        description="Cache duration in seconds",
        ge=1,
        le=3600,
    )


class ModelConfigurationSecurity(BaseModel):
    """
    Configuration security settings.

    Manages sensitive data detection, sanitization,
    and secure logging for configuration values.
    """

    sanitize_logs: bool = Field(
        default=True,
        description="Sanitize sensitive values in logs",
    )

    mask_sensitive_values: bool = Field(
        default=True,
        description="Mask sensitive configuration values",
    )

    sensitive_patterns: list[str] = Field(
        default_factory=lambda: ["password", "secret", "key", "token", "credential"],
        description="Patterns that identify sensitive fields",
    )

    redaction_replacement: str = Field(
        default="[REDACTED]",
        description="Replacement text for sensitive values",
    )


class ModelConfigurationSubcontract(BaseModel):
    """
    Main configuration subcontract model.

    Comprehensive configuration management system that provides
    standardized loading, validation, and security patterns
    for ONEX infrastructure nodes.
    """

    subcontract_version: str = Field(
        default="1.0.0",
        description="Configuration subcontract version",
    )

    sources: list[ModelConfigurationSource] = Field(
        default_factory=lambda: [
            ModelConfigurationSource(source_type=ConfigurationSourceType.CONTAINER, priority=1),
            ModelConfigurationSource(source_type=ConfigurationSourceType.ENVIRONMENT, priority=2),
            ModelConfigurationSource(source_type=ConfigurationSourceType.DEFAULTS, priority=3),
        ],
        description="Configuration sources in priority order",
    )

    environment_config: ModelEnvironmentConfiguration | None = Field(
        default=None,
        description="Environment variable configuration",
    )

    validation_config: ModelConfigurationValidation | None = Field(
        default=None,
        description="Configuration validation settings",
    )

    integration_config: ModelConfigurationIntegration = Field(
        default_factory=ModelConfigurationIntegration,
        description="Integration pattern configuration",
    )

    security_config: ModelConfigurationSecurity = Field(
        default_factory=ModelConfigurationSecurity,
        description="Security and sanitization configuration",
    )

    fail_on_missing_required: bool = Field(
        default=True,
        description="Fail when required configuration is missing",
    )

    fail_on_invalid_format: bool = Field(
        default=True,
        description="Fail when configuration format is invalid",
    )

    log_configuration_errors: bool = Field(
        default=True,
        description="Log configuration loading errors",
    )

    provide_detailed_validation_messages: bool = Field(
        default=True,
        description="Provide detailed validation error messages",
    )
```

### Key Model Features

1. **Pydantic-Based:** Full type safety and validation
2. **Enum Types:** Strongly typed configuration sources and rule types
3. **Field Validators:** Custom validation logic with `@field_validator`
4. **Default Factories:** Intelligent default value generation
5. **Nested Models:** Composition of configuration models
6. **Security:** Built-in sensitive data patterns and masking

---

## Usage Patterns

### How Nodes Use Contracts and Subcontracts

**File:** `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/node.py`

#### 1. Contract Reference in Node Implementation

```python
class NodePostgresAdapterEffect(NodeEffectService):
    """
    Infrastructure PostgreSQL Adapter Node - Message Bus Bridge.

    Integrates with:
    - postgres_event_processing_subcontract: Event bus integration patterns
    - postgres_connection_management_subcontract: Connection pool management
    """

    # Configuration will be loaded from environment or container
    config: ModelPostgresAdapterConfig

    def __init__(self, container: ModelONEXContainer):
        """Initialize PostgreSQL adapter tool with container injection."""
        super().__init__(container)
        self.node_type = "effect"
        self.domain = "infrastructure"

        # Initialize configuration from environment or container
        self.config = self._load_configuration(container)

        # Initialize event bus for OmniNode event publishing (REQUIRED)
        self._event_bus = self.container.get_service("ProtocolEventBus")
```

#### 2. Configuration Loading (from Configuration Subcontract)

```python
def _load_configuration(self, container: ModelONEXContainer) -> ModelPostgresAdapterConfig:
    """
    Load PostgreSQL adapter configuration from container or environment.

    Follows patterns from configuration_subcontract.yaml:
    - Container service resolution (priority 1)
    - Environment variable loading (priority 2)
    - Defaults (priority 3)
    """
    try:
        # Try to get configuration from container first (ONEX pattern)
        config = container.get_service("postgres_adapter_config")
        if config and hasattr(config, "postgres_host"):
            return config
    except Exception:
        pass  # Fall back to environment configuration

    # Fall back to environment-based configuration
    environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "development")
    return ModelPostgresAdapterConfig.for_environment(environment)
```

#### 3. Event Processing (from Event Processing Subcontract)

```python
async def _publish_event_to_redpanda(self, envelope: "ModelEventEnvelope") -> None:
    """
    Publish event envelope to RedPanda via proper ProtocolEventBus interface.

    Follows patterns from postgres_event_processing_subcontract.yaml:
    - Standard ONEX envelope format
    - Metadata inclusion
    - Error handling with OnexError propagation
    """
    if not self._event_bus or not self._event_publisher:
        raise OnexError(
            code=CoreErrorCode.DEPENDENCY_RESOLUTION_ERROR,
            message="Event bus not initialized - CRITICAL infrastructure failure",
        )

    try:
        # Extract the OnexEvent from the envelope payload
        onex_event = envelope.payload

        # Publish OnexEvent via proper ProtocolEventBus interface
        await self._event_bus.publish_async(onex_event)

    except Exception as e:
        # Event publishing is CRITICAL - failures MUST propagate
        raise OnexError(
            code=CoreErrorCode.SERVICE_UNAVAILABLE_ERROR,
            message=f"Critical infrastructure failure: Event publishing failed",
        ) from e
```

#### 4. Health Checks (from Health Check Mixin Subcontract)

```python
def get_health_checks(self) -> list[Callable]:
    """
    Override MixinHealthCheck to provide PostgreSQL-specific health checks.

    Follows patterns from health_check_mixin_subcontract.yaml:
    - Database connectivity check
    - Connection pool health check
    - Circuit breaker health check
    - RedPanda connectivity check
    """
    return [
        self._check_database_connectivity,
        self._check_connection_pool_health,
        self._check_circuit_breaker_health,
        self._check_redpanda_connectivity,
        self._check_event_publishing_health,
    ]

def _check_database_connectivity(self) -> ModelHealthStatus:
    """
    Check basic PostgreSQL database connectivity.

    Implements database_connectivity check from subcontract.
    """
    try:
        if self._connection_manager is None:
            return ModelHealthStatus(
                status=EnumHealthStatus.DEGRADED,
                message="Connection manager not initialized",
                timestamp=datetime.utcnow().isoformat(),
            )

        return ModelHealthStatus(
            status=EnumHealthStatus.HEALTHY,
            message="Database connection manager operational",
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        return ModelHealthStatus(
            status=EnumHealthStatus.UNHEALTHY,
            message=f"Database connectivity check failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
        )
```

#### 5. Connection Management (from Connection Management Subcontract)

```python
@property
def connection_manager(self) -> PostgresConnectionManager:
    """
    Get PostgreSQL connection manager instance via registry injection.

    Follows patterns from postgres_connection_management_subcontract.yaml:
    - Container injection per ONEX standards
    - Connection pool management
    - Thread-safe access
    """
    with self._connection_manager_sync_lock:
        if self._connection_manager is None:
            # Use container injection per ONEX standards
            self._connection_manager = self.container.get_service("postgres_connection_manager")

            if self._connection_manager is None:
                raise OnexError(
                    code=CoreErrorCode.DEPENDENCY_RESOLUTION_ERROR,
                    message="PostgreSQL connection manager service not available",
                )

        return self._connection_manager
```

---

## File Organization

### Directory Structure

```
/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/
├── nodes/
│   ├── node_postgres_adapter_effect/
│   │   └── v1_0_0/
│   │       ├── contract.yaml                    # Main contract
│   │       ├── contracts/                       # Subcontracts directory
│   │       │   ├── configuration_subcontract.yaml
│   │       │   ├── postgres_event_processing_subcontract.yaml
│   │       │   ├── postgres_connection_management_subcontract.yaml
│   │       │   ├── health_check_mixin_subcontract.yaml
│   │       │   ├── node_service_mixin_subcontract.yaml
│   │       │   └── node_id_contract_mixin_subcontract.yaml
│   │       └── node.py                          # Node implementation
│   ├── kafka_adapter/
│   │   └── v1_0_0/
│   │       ├── contract.yaml
│   │       ├── contracts/
│   │       │   ├── configuration_subcontract.yaml
│   │       │   ├── kafka_event_processing_subcontract.yaml
│   │       │   └── kafka_connection_management_subcontract.yaml
│   │       └── node.py
│   └── [other nodes]/
│
└── models/
    └── infrastructure/
        └── model_configuration_subcontract.py   # Python model implementation
```

### File Path Summary

**Main Contracts:**
- `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/contract.yaml`
- `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/kafka_adapter/v1_0_0/contract.yaml`

**Subcontracts (PostgreSQL Adapter - Most Complete):**
- Configuration: `contracts/configuration_subcontract.yaml`
- Event Processing: `contracts/postgres_event_processing_subcontract.yaml`
- Connection Management: `contracts/postgres_connection_management_subcontract.yaml`
- Health Check Mixin: `contracts/health_check_mixin_subcontract.yaml`
- Node Service Mixin: `contracts/node_service_mixin_subcontract.yaml`
- Node ID Mixin: `contracts/node_id_contract_mixin_subcontract.yaml`

**Subcontracts (Kafka Adapter):**
- Configuration: `contracts/configuration_subcontract.yaml`
- Event Processing: `contracts/kafka_event_processing_subcontract.yaml`
- Connection Management: `contracts/kafka_connection_management_subcontract.yaml`

**Python Models:**
- `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/models/infrastructure/model_configuration_subcontract.py`

**Node Implementations:**
- `/Volumes/PRO-G40/Code/omnibase_infra/src/omnibase_infra/nodes/node_postgres_adapter_effect/v1_0_0/node.py`

---

## Best Practices

### 1. Contract Design

✅ **DO:**
- Use semantic versioning for contracts and subcontracts
- Define clear input/output models with Pydantic references
- Specify all required dependencies explicitly
- Include comprehensive metadata (uuid, created_at, author)
- Document integration patterns in subcontracts

❌ **DON'T:**
- Skip version fields in contracts
- Use generic "object" types without model references
- Omit dependency specifications
- Mix concerns in single subcontract

### 2. Subcontract Composition

✅ **DO:**
- Use mixin integration type for reusable patterns
- Keep subcontracts focused on single concern
- Provide clear integration field mappings
- Document backward compatibility requirements
- Include performance targets and SLAs

❌ **DON'T:**
- Create god subcontracts with multiple responsibilities
- Hardcode integration patterns
- Skip backward compatibility considerations
- Omit performance expectations

### 3. Model Implementation

✅ **DO:**
- Use Pydantic BaseModel for all models
- Implement field validators for complex rules
- Use Enum for fixed value sets
- Provide sensible defaults with default_factory
- Document model purpose and usage

❌ **DON'T:**
- Use `Any` types (ZERO TOLERANCE policy)
- Skip validation on critical fields
- Use mutable default values
- Omit type hints

### 4. Node Implementation

✅ **DO:**
- Reference subcontract patterns in docstrings
- Follow container injection patterns
- Implement all health checks from subcontract
- Use structured logging with correlation IDs
- Validate configuration on startup

❌ **DON'T:**
- Hardcode configuration values
- Skip health check implementations
- Ignore subcontract patterns
- Use global state
- Skip error sanitization

### 5. Testing Patterns

✅ **DO:**
- Test contract schema validation
- Test subcontract model instantiation
- Test integration patterns end-to-end
- Mock container dependencies properly
- Verify health check implementations

❌ **DON'T:**
- Skip contract validation tests
- Test only happy paths
- Use real infrastructure in unit tests
- Skip edge case validation

---

## Summary

### Most Complete Examples Found

1. **Best Main Contract:** `node_postgres_adapter_effect/v1_0_0/contract.yaml`
   - Most comprehensive contract structure
   - Complete metadata and versioning
   - Well-defined subcontract composition
   - Clear I/O operation specifications

2. **Best Configuration Subcontract:** `configuration_subcontract.yaml`
   - Complete model definitions
   - Comprehensive validation patterns
   - Security configuration
   - Integration patterns clearly defined

3. **Best Event Processing Subcontract:** `postgres_event_processing_subcontract.yaml`
   - Comprehensive event patterns
   - Async processing configuration
   - Error handling strategies
   - Performance optimization settings

4. **Best Connection Management Subcontract:** `postgres_connection_management_subcontract.yaml`
   - Detailed pool configuration
   - Transaction management patterns
   - Complete lifecycle management
   - Observability metrics

5. **Best Python Model:** `model_configuration_subcontract.py`
   - Complete type safety with Pydantic
   - Field validators for complex logic
   - Nested model composition
   - Zero `Any` types (ONEX standard)

6. **Best Node Implementation:** `node_postgres_adapter_effect/v1_0_0/node.py`
   - Complete subcontract pattern implementation
   - Structured logging throughout
   - Health check comprehensive coverage
   - Event publishing integration

### Key Takeaways

1. **Contracts are living specifications** - They define both structure and behavior
2. **Subcontracts enable reuse** - Same patterns across multiple nodes
3. **Python models enforce contracts** - Pydantic validation ensures compliance
4. **Nodes implement contracts** - Concrete Python classes follow specifications
5. **Integration is explicit** - All dependencies and patterns clearly documented

---

**End of Report**
