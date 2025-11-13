"""
Service Resolution Subcontract Example - ONEX Documentation.

Demonstrates service discovery and dependency injection patterns for ONEX nodes.
Based on: omnibase_3/src/omnibase/model/subcontracts/model_service_resolution_subcontract.py

This example shows how Effect and Orchestrator nodes can use service resolution
for dependency injection and dynamic service discovery.
"""

from enum import Enum

from pydantic import BaseModel, Field

# === ENUMS ===


class ServiceProtocol(str, Enum):
    """Supported service communication protocols."""

    HTTP = "HTTP"
    HTTPS = "HTTPS"
    GRPC = "GRPC"
    TCP = "TCP"
    UDP = "UDP"
    WEBSOCKET = "WEBSOCKET"


class ServiceHealthStatus(str, Enum):
    """Health status levels for discovered services."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class DiscoveryMethod(str, Enum):
    """Service discovery mechanisms."""

    DNS = "DNS"  # DNS-based service discovery
    CONSUL = "CONSUL"  # HashiCorp Consul
    ETCD = "ETCD"  # etcd key-value store
    KUBERNETES = "KUBERNETES"  # Kubernetes service discovery
    STATIC = "STATIC"  # Static configuration
    ENVIRONMENT = "ENVIRONMENT"  # Environment variables


# === MODELS ===


class ModelServiceEndpoint(BaseModel):
    """Service endpoint specification."""

    host: str = Field(
        ...,
        description="Service host address (hostname or IP)",
        examples=["api.example.com", "10.0.1.5"],
    )

    port: int = Field(
        ...,
        description="Service port number",
        ge=1,
        le=65535,
        examples=[8080, 443, 5432],
    )

    protocol: ServiceProtocol = Field(
        default=ServiceProtocol.HTTPS,
        description="Communication protocol",
    )

    path: str = Field(
        default="/",
        description="Base path for service endpoints",
        examples=["/", "/api/v1", "/graphql"],
    )

    weight: int = Field(
        default=100,
        description="Load balancing weight (higher = more traffic)",
        ge=0,
        le=1000,
    )

    health_status: ServiceHealthStatus = Field(
        default=ServiceHealthStatus.UNKNOWN,
        description="Current health status of this endpoint",
    )


class ModelServiceDependency(BaseModel):
    """External service dependency specification."""

    service_name: str = Field(
        ...,
        description="Unique name for this service dependency",
        examples=["user_database", "auth_api", "message_queue"],
    )

    discovery_method: DiscoveryMethod = Field(
        default=DiscoveryMethod.ENVIRONMENT,
        description="How to discover this service",
    )

    required: bool = Field(
        default=True,
        description="Whether this service is required for node operation",
    )

    fallback_endpoints: list[ModelServiceEndpoint] = Field(
        default_factory=list,
        description="Fallback endpoints if discovery fails",
    )

    timeout_seconds: float = Field(
        default=5.0,
        description="Connection timeout for this service",
        gt=0,
    )

    retry_attempts: int = Field(
        default=3,
        description="Number of connection retry attempts",
        ge=0,
    )

    circuit_breaker_threshold: int = Field(
        default=5,
        description="Failures before circuit breaker opens",
        ge=1,
    )


class ModelServiceResolutionSubcontract(BaseModel):
    """
    Service Resolution Subcontract for ONEX nodes.

    Provides service discovery, dependency injection, and service registry
    integration patterns. Applicable to Effect and Orchestrator nodes that
    need to interact with external services.

    Features:
    - Service discovery via multiple methods (DNS, Consul, k8s, etc.)
    - Health-aware endpoint selection
    - Circuit breaker pattern integration
    - Load balancing support
    - Fallback endpoint configuration
    """

    subcontract_name: str = Field(
        default="service_resolution_subcontract",
        description="Subcontract identifier",
    )

    subcontract_version: str = Field(
        default="1.0.0",
        description="Subcontract version",
    )

    applicable_node_types: list[str] = Field(
        default=["EFFECT", "ORCHESTRATOR"],
        description="Node types this subcontract applies to",
    )

    # === SERVICE DEPENDENCIES ===

    service_dependencies: list[ModelServiceDependency] = Field(
        default_factory=list,
        description="List of external service dependencies",
    )

    # === DISCOVERY CONFIGURATION ===

    discovery_refresh_interval_seconds: int = Field(
        default=60,
        description="How often to refresh service discovery (seconds)",
        ge=1,
    )

    health_check_interval_seconds: int = Field(
        default=30,
        description="How often to check endpoint health (seconds)",
        ge=1,
    )

    # === LOAD BALANCING ===

    enable_load_balancing: bool = Field(
        default=True,
        description="Enable load balancing across multiple endpoints",
    )

    load_balancing_strategy: str = Field(
        default="weighted_round_robin",
        description="Load balancing strategy",
        pattern="^(round_robin|weighted_round_robin|least_connections|random)$",
    )

    # === FAILURE HANDLING ===

    enable_circuit_breaker: bool = Field(
        default=True,
        description="Enable circuit breaker pattern for failing services",
    )

    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        description="How long circuit stays open before retry (seconds)",
        ge=1,
    )

    fail_fast_on_missing_required: bool = Field(
        default=True,
        description="Fail immediately if required service not found",
    )


# === USAGE EXAMPLES ===

# Example 1: Effect node with database dependency
effect_with_db = ModelServiceResolutionSubcontract(
    service_dependencies=[
        ModelServiceDependency(
            service_name="postgres_primary",
            discovery_method=DiscoveryMethod.KUBERNETES,
            required=True,
            timeout_seconds=5.0,
            retry_attempts=3,
        ),
        ModelServiceDependency(
            service_name="redis_cache",
            discovery_method=DiscoveryMethod.DNS,
            required=False,
            fallback_endpoints=[
                ModelServiceEndpoint(
                    host="cache.local",
                    port=6379,
                    protocol=ServiceProtocol.TCP,
                )
            ],
        ),
    ]
)

# Example 2: Orchestrator with multiple service dependencies
orchestrator_multi_service = ModelServiceResolutionSubcontract(
    service_dependencies=[
        ModelServiceDependency(
            service_name="auth_service",
            discovery_method=DiscoveryMethod.CONSUL,
            required=True,
            timeout_seconds=2.0,
        ),
        ModelServiceDependency(
            service_name="user_service",
            discovery_method=DiscoveryMethod.CONSUL,
            required=True,
            timeout_seconds=3.0,
        ),
        ModelServiceDependency(
            service_name="notification_service",
            discovery_method=DiscoveryMethod.CONSUL,
            required=False,
            timeout_seconds=5.0,
        ),
    ],
    enable_load_balancing=True,
    load_balancing_strategy="least_connections",
    health_check_interval_seconds=15,
)

# Example 3: Static service configuration (no dynamic discovery)
static_service_config = ModelServiceResolutionSubcontract(
    service_dependencies=[
        ModelServiceDependency(
            service_name="external_api",
            discovery_method=DiscoveryMethod.STATIC,
            required=True,
            fallback_endpoints=[
                ModelServiceEndpoint(
                    host="api.external.com",
                    port=443,
                    protocol=ServiceProtocol.HTTPS,
                    path="/api/v2",
                    weight=100,
                )
            ],
            timeout_seconds=10.0,
            retry_attempts=3,
            circuit_breaker_threshold=5,
        )
    ],
    enable_circuit_breaker=True,
    circuit_breaker_timeout_seconds=120,
)
