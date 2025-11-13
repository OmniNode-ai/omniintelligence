# ONEX Manifest Types - Complete Guide

**Purpose**: Understand the 3 types of YAML manifest files that configure ONEX nodes
**Source**: Extracted from canary tool implementations
**Last Updated**: 2025-10-01

---

## Overview

ONEX nodes are configured through **3 distinct manifest types**, each serving a different purpose in the node's lifecycle:

1. **Contract Manifest** (`contract.yaml`) - Defines the node's interface and behavior
2. **Node Config Manifest** (`node_config.yaml`) - Runtime configuration and resource limits
3. **Deployment Manifest** (`deployment_config.yaml`) - Infrastructure and deployment settings

---

## Manifest Type 1: Contract (`contract.yaml`)

###  Purpose

The **ONEX Contract** is the MOST IMPORTANT manifest - it defines:
- Node identity and classification
- Input/output models (interface)
- Available actions (what the node can do)
- Subcontract references (FSM, Events, Caching, etc.)
- Performance constraints
- Infrastructure requirements

### Source Example

```bash
/Volumes/PRO-G40/Code/omnibase_3/src/omnibase/tools/canary/canary_pure_tool/v1_0_0/contract.yaml
```

### Structure

```yaml
# === CONTRACT METADATA ===
contract_metadata:
  template_version: "2.0"
  last_validated: "2025-08-16"
  compliance_level: "gold_standard"
  canonical_reference: true

# === CORE NODE IDENTITY ===
contract_version: {major: 1, minor: 0, patch: 0}
node_name: "canary_pure_tool"
node_version: {major: 1, minor: 0, patch: 0}
description: "Canary tool demonstrating perfect pure functional node patterns"
author: "ONEX Framework Team"
node_tier: 1
node_classification: "pure_functional"

# === NODEBASE SPECIFICATION (REQUIRED) ===
tool_specification:
  main_tool_class: "ToolCanaryPureProcessor"
  container_injection: "ONEXContainer"
  business_logic_pattern: "pure_functional"

# === DEPENDENCIES ===
dependencies:
  - name: "contract_loader"
    type: "utility"
    class: "UtilityContractLoader"
    module: "omnibase.utils.contract.utility_contract_loader"

# === INFRASTRUCTURE ===
infrastructure:
  event_bus:
    strategy: "auto"
    fallback: "in_memory"
    connection_timeout_ms: 5000

# === INPUT/OUTPUT MODELS (AI QUICK REFERENCE) ===
input_state:
  required: ["action", "input_text", "transformation_type"]
  optional: ["output_format", "strict_mode"]
  full_schema: {$ref: "...contracts/contract_models.yaml#/input_state"}

output_state:
  returns: ["transformed_text", "transformation_metadata"]
  full_schema: {$ref: "...contracts/contract_models.yaml#/output_state"}

# === PRIMARY ACTIONS ===
primary_actions: ["transform_text", "analyze_text", "validate_input"]
action_details: {$ref: "...contracts/contract_actions.yaml"}

# === SUBCONTRACT REFERENCES ===
cli_interface: {$ref: "...contracts/contract_cli.yaml"}
validation_rules: {$ref: "...contracts/contract_validation.yaml"}

# === EXECUTION CAPABILITIES ===
execution_capabilities:
  supported_node_types: ["full", "lightweight"]
  performance_constraints:
    max_concurrent_executions: 100
    timeout_ms: 5000
    memory_limit_mb: 128
```

### Key Sections Explained

#### 1. Contract Metadata
- **template_version**: ONEX template version (2.0 is current)
- **compliance_level**: Quality designation (gold_standard, compliant, experimental)
- **canonical_reference**: Whether this is a reference implementation

#### 2. Core Node Identity
- **node_name**: Unique identifier (snake_case)
- **node_version**: SemVer versioning
- **node_tier**: 1 (Compute), 2 (Effect), 3 (Reducer), 4 (Orchestrator)
- **node_classification**: pure_functional | stateful | coordination

#### 3. NodeBase Specification (REQUIRED)
- **main_tool_class**: Python class name that NodeBase will instantiate
- **container_injection**: Dependency injection pattern (always "ONEXContainer")
- **business_logic_pattern**: Guides AI code generation

#### 4. Dependencies
List of components to inject via DI container:
- **name**: Dependency identifier
- **type**: utility | protocol | service
- **class**: Python class name
- **module**: Import path

#### 5. Infrastructure
Configuration for infrastructure services:
- **event_bus**: Event emission strategy
- **logger**: Logging configuration
- **metrics**: Metrics collection settings

#### 6. Input/Output Models
Quick reference for AI and developers:
- **required**: Mandatory fields
- **optional**: Optional fields
- **full_schema**: Reference to detailed Pydantic model definition

#### 7. Primary Actions
List of operations this node can perform:
- **primary_actions**: Action names (e.g., "transform_text")
- **action_details**: Reference to detailed action specifications

#### 8. Subcontract References
Links to detailed configuration files:
- **cli_interface**: CLI argument specifications
- **validation_rules**: Input validation rules
- **examples**: Usage examples
- **testing**: Test specifications

### How It's Used

1. **NodeBase Loading**: NodeBase reads `contract.yaml` on initialization
2. **Contract Instantiation**: Creates Pydantic `ModelContractCompute/Effect/Reducer/Orchestrator`
3. **Validation**: Validates node implementation against contract
4. **Runtime Checks**: Ensures compliance during execution

### Critical Requirements

- **✅ MUST have**: `tool_specification` section for NodeBase
- **✅ MUST define**: `input_state` and `output_state` for interface
- **✅ MUST specify**: `node_tier` and `node_classification` for routing
- **✅ MUST provide**: Subcontract refs for complex features (FSM, Events, etc.)

---

## Manifest Type 2: Node Config (`node_config.yaml`)

### Purpose

The **Node Configuration** manifest defines **runtime behavior**:
- Performance limits and thresholds
- Resource requirements (CPU, memory, disk)
- Concurrency settings
- Caching configuration
- Environment variables

### Source Example

```bash
/Volumes/PRO-G40/Code/omnibase_3/src/omnibase/tools/canary/canary_pure_tool/v1_0_0/node_config.yaml
```

### Structure

```yaml
# === BASIC NODE INFORMATION ===
node_name: canary_pure_tool
node_version: {"major": 1, "minor": 0, "patch": 0}
node_tier: 1
node_classification: pure_functional

# === PERFORMANCE CONFIGURATION ===
performance:
  # Execution constraints
  max_execution_time_ms: 5000
  max_memory_usage_mb: 128
  max_cpu_usage_percent: 25

  # Concurrency settings
  max_concurrent_executions: 50
  execution_pool_size: 10

  # Caching configuration
  enable_result_caching: true
  cache_ttl_seconds: 300
  max_cache_entries: 1000

# === RESOURCE REQUIREMENTS ===
resource_requirements:
  # Minimum requirements
  min_memory_mb: 32
  min_cpu_cores: 1
  min_disk_space_mb: 10

  # Recommended requirements
  recommended_memory_mb: 64
  recommended_cpu_cores: 2
  recommended_disk_space_mb: 50

  # Network requirements
  requires_network_access: false
  requires_external_apis: false

  # Storage requirements
  requires_persistent_storage: false
  requires_temp_storage: true
  temp_storage_mb: 10

# === RUNTIME CONFIGURATION ===
runtime:
  # Environment variables
  environment_variables:
    ONEX_LOG_LEVEL: "INFO"
    ONEX_ENABLE_METRICS: "true"
    ONEX_CORRELATION_TRACKING: "true"

  # Startup configuration
  startup_timeout_ms: 2000
  graceful_shutdown_timeout_ms: 3000
  health_check_interval_ms: 30000

  # Feature flags
  enable_telemetry: true
  enable_profiling: false
  enable_debug_mode: false

# === LOGGING CONFIGURATION ===
logging:
  log_level: "INFO"
  log_format: "json"
  enable_correlation_ids: true
  log_rotation_size_mb: 100
  max_log_files: 10

# === MONITORING CONFIGURATION ===
monitoring:
  enable_metrics: true
  metrics_port: 9090
  metrics_path: "/metrics"
  enable_health_checks: true
  health_check_port: 8080
  health_check_path: "/health"
```

### Key Sections Explained

#### 1. Performance Configuration
- **max_execution_time_ms**: Hard limit for single operation
- **max_memory_usage_mb**: Memory limit enforcement
- **max_cpu_usage_percent**: CPU throttling threshold
- **max_concurrent_executions**: Parallel execution limit
- **enable_result_caching**: Whether to cache results

#### 2. Resource Requirements
- **Minimum**: Required to start node
- **Recommended**: For optimal performance
- **Network**: External connectivity needs
- **Storage**: Disk space requirements

#### 3. Runtime Configuration
- **environment_variables**: Environment setup
- **startup_timeout_ms**: Max startup time
- **graceful_shutdown_timeout_ms**: Cleanup time allowed
- **Feature flags**: Enable/disable features

### How It's Used

1. **Node Initialization**: Node reads config on startup
2. **Resource Allocation**: System allocates based on requirements
3. **Runtime Enforcement**: Monitors and enforces limits
4. **Dynamic Configuration**: Can be updated without code changes

### Critical Requirements

- **✅ MUST specify**: Performance constraints for safety
- **✅ MUST define**: Resource requirements for scheduling
- **✅ SHOULD provide**: Environment variables for configuration
- **✅ SHOULD enable**: Monitoring and health checks

---

## Manifest Type 3: Deployment (`deployment_config.yaml`)

### Purpose

The **Deployment Configuration** manifest defines **infrastructure deployment**:
- Container configuration (Docker/K8s)
- Resource limits (CPU, memory)
- Health and readiness checks
- Auto-scaling rules
- Environment-specific settings

### Source Example

```bash
/Volumes/PRO-G40/Code/omnibase_3/src/omnibase/tools/canary/canary_pure_tool/v1_0_0/deployment_config.yaml
```

### Structure

```yaml
# === DEPLOYMENT METADATA ===
deployment_name: canary_pure_tool_deployment
deployment_version: {"major": 1, "minor": 0, "patch": 0}
target_environments: ["development", "staging", "production"]
deployment_strategy: blue_green

# === CONTAINER CONFIGURATION ===
container:
  # Base image settings
  base_image: "python:3.11-slim"
  working_directory: "/app/canary_pure_tool"

  # Resource limits
  cpu_limit: "500m"
  memory_limit: "256Mi"
  cpu_request: "100m"
  memory_request: "128Mi"

  # Environment variables
  environment_variables:
    ONEX_NODE_NAME: "canary_pure_tool"
    ONEX_NODE_VERSION: "1.0.0"
    ONEX_LOG_LEVEL: "INFO"

  # Health check configuration
  health_check:
    http_get:
      path: "/health"
      port: 8080
    initial_delay_seconds: 10
    period_seconds: 30
    timeout_seconds: 5
    failure_threshold: 3

  # Readiness check configuration
  readiness_check:
    http_get:
      path: "/ready"
      port: 8080
    initial_delay_seconds: 5
    period_seconds: 10
    timeout_seconds: 3
    failure_threshold: 2

# === KUBERNETES CONFIGURATION ===
kubernetes:
  # Deployment settings
  deployment:
    replicas: 3
    max_surge: 1
    max_unavailable: 1
    revision_history_limit: 5

  # Auto-scaling settings
  autoscaling:
    enabled: true
    min_replicas: 2
    max_replicas: 10
    target_cpu_utilization: 70
    target_memory_utilization: 80

  # Service settings
  service:
    type: "ClusterIP"
    port: 8080
    target_port: 8080

# === NETWORK CONFIGURATION ===
network:
  ingress:
    enabled: false
  egress:
    allowed_hosts: []
    allowed_ports: []

# === SECURITY CONFIGURATION ===
security:
  run_as_non_root: true
  read_only_root_filesystem: true
  allow_privilege_escalation: false

  # Resource quotas
  resource_quotas:
    cpu_limit: "1000m"
    memory_limit: "512Mi"
    persistent_volume_claims: 0

# === MONITORING & OBSERVABILITY ===
observability:
  # Prometheus metrics
  prometheus:
    enabled: true
    port: 9090
    path: "/metrics"

  # Logging
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"

  # Tracing
  tracing:
    enabled: false
    sampling_rate: 0.1
```

### Key Sections Explained

#### 1. Deployment Metadata
- **deployment_name**: Unique deployment identifier
- **target_environments**: Where to deploy (dev, staging, prod)
- **deployment_strategy**: blue_green | rolling | recreate

#### 2. Container Configuration
- **base_image**: Docker base image
- **resource_limits**: K8s resource constraints
- **health_check**: Liveness probe configuration
- **readiness_check**: Readiness probe configuration

#### 3. Kubernetes Configuration
- **replicas**: Number of pod instances
- **autoscaling**: HPA configuration
- **service**: K8s service configuration

#### 4. Security Configuration
- **run_as_non_root**: Security constraint
- **read_only_root_filesystem**: Immutable filesystem
- **resource_quotas**: Hard limits

### How It's Used

1. **CI/CD Pipeline**: Reads deployment config for build/deploy
2. **Container Build**: Creates Docker image with specified settings
3. **K8s Deployment**: Applies configuration to cluster
4. **Monitoring Setup**: Configures observability tools

### Critical Requirements

- **✅ MUST define**: Health and readiness checks
- **✅ MUST specify**: Resource limits for safety
- **✅ MUST enable**: Security constraints (non-root, read-only)
- **✅ SHOULD configure**: Auto-scaling for production

---

## Manifest Relationships

```
contract.yaml (INTERFACE)
    ↓ defines interface and behavior
    ↓
node_config.yaml (RUNTIME)
    ↓ specifies runtime constraints
    ↓
deployment_config.yaml (INFRASTRUCTURE)
    ↓ configures deployment
    ↓
RUNNING NODE INSTANCE
```

### Loading Order

1. **contract.yaml** loaded by NodeBase
2. **node_config.yaml** loaded by node implementation
3. **deployment_config.yaml** loaded by deployment system (K8s, Docker)

### Separation of Concerns

| Manifest | Audience | When Changed |
|----------|----------|--------------|
| **contract.yaml** | Developers | When interface changes |
| **node_config.yaml** | Operators | When tuning performance |
| **deployment_config.yaml** | DevOps | When changing infrastructure |

---

## Best Practices

###  Contract Manifest (`contract.yaml`)
1. **Keep interface stable** - Avoid breaking changes
2. **Document thoroughly** - Include descriptions for all fields
3. **Version properly** - Use semantic versioning
4. **Reference subcontracts** - Don't inline complex configurations
5. **Validate rigorously** - Use contract validation tools

### Node Config Manifest (`node_config.yaml`)
1. **Set realistic limits** - Test under load
2. **Enable monitoring** - Always include health checks
3. **Configure caching** - For performance optimization
4. **Document variables** - Explain all environment variables
5. **Environment-specific** - Different configs for dev/prod

### Deployment Manifest (`deployment_config.yaml`)
1. **Security first** - Always enable security constraints
2. **Resource limits** - Prevent resource exhaustion
3. **Health checks** - Enable both liveness and readiness
4. **Auto-scaling** - For production workloads
5. **Observability** - Enable metrics and logging

---

## Common Patterns

### Pattern 1: Feature Flags in Contract

```yaml
# contract.yaml
feature_flags:
  enable_advanced_caching: true
  enable_batch_processing: false
  enable_async_execution: true
```

### Pattern 2: Environment-Specific Config

```yaml
# node_config.yaml
environments:
  development:
    log_level: "DEBUG"
    enable_profiling: true
  production:
    log_level: "INFO"
    enable_profiling: false
```

### Pattern 3: Multi-Environment Deployment

```yaml
# deployment_config.yaml
environments:
  staging:
    replicas: 1
    resources:
      cpu_limit: "200m"
      memory_limit: "128Mi"
  production:
    replicas: 3
    resources:
      cpu_limit: "1000m"
      memory_limit: "512Mi"
```

---

## Validation & Testing

### Contract Validation

```bash
# Validate contract against schema
onex validate contract contract.yaml

# Test contract compliance
onex test compliance --contract contract.yaml --implementation node.py
```

### Config Validation

```bash
# Validate node config
onex validate config node_config.yaml

# Test with config
onex test run --config node_config.yaml
```

### Deployment Validation

```bash
# Validate deployment manifest
kubectl apply --dry-run=client -f deployment_config.yaml

# Validate security
kubectl auth can-i --as=system:serviceaccount:default:node-sa create pods
```

---

## Troubleshooting

### Common Issues

#### Issue: Contract not loading
**Symptom**: "Contract file not found" error
**Solution**: Ensure `contract.yaml` is in same directory as `node.py`

#### Issue: Resource limits exceeded
**Symptom**: Pod OOMKilled or CPU throttled
**Solution**: Increase limits in `deployment_config.yaml`

#### Issue: Health check failing
**Symptom**: Pod restarting constantly
**Solution**: Adjust `initial_delay_seconds` in deployment config

---

## References

- **ONEX Architecture**: `docs/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md`
- **Contract System**: `CONTRACTS_REFERENCE.md`
- **Node Development**: `README.md`

---

**Last Updated**: 2025-10-01
**Version**: 1.0.0
