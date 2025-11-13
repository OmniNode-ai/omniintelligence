"""
Centralized Timeout Configuration Module

This module provides configuration-driven timeout values for all services,
replacing hardcoded timeout values throughout the codebase.

Environment variables can override any default value.
All timeout values are in seconds unless otherwise specified.
"""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPTimeoutConfig(BaseSettings):
    """HTTP client timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="HTTP_TIMEOUT_", env_file=".env", extra="ignore"
    )

    # Default HTTP client timeout
    default: float = Field(
        default=30.0,
        description="Default HTTP client timeout in seconds",
        ge=1.0,
        le=300.0,
    )

    # Health check timeout (should be fast)
    health_check: float = Field(
        default=5.0, description="Timeout for health check requests", ge=1.0, le=30.0
    )

    # Service-specific timeouts
    intelligence: float = Field(
        default=60.0,
        description="Timeout for intelligence service operations",
        ge=10.0,
        le=300.0,
    )

    search: float = Field(
        default=45.0,
        description="Timeout for search service operations",
        ge=10.0,
        le=300.0,
    )

    langextract: float = Field(
        default=90.0,
        description="Timeout for langextract operations (can be slow)",
        ge=10.0,
        le=300.0,
    )

    bridge: float = Field(
        default=30.0,
        description="Timeout for bridge service operations",
        ge=10.0,
        le=300.0,
    )

    mcp: float = Field(
        default=30.0,
        description="Timeout for MCP service operations",
        ge=10.0,
        le=300.0,
    )

    # Long-running operation timeouts
    optimization: float = Field(
        default=120.0,
        description="Timeout for optimization operations",
        ge=30.0,
        le=600.0,
    )

    baseline_collection: float = Field(
        default=60.0,
        description="Timeout for performance baseline collection",
        ge=30.0,
        le=300.0,
    )

    # Connection timeouts (typically shorter)
    connect: float = Field(
        default=10.0, description="HTTP connection timeout", ge=1.0, le=60.0
    )

    read: float = Field(default=30.0, description="HTTP read timeout", ge=5.0, le=300.0)

    write: float = Field(default=5.0, description="HTTP write timeout", ge=1.0, le=60.0)


class DatabaseTimeoutConfig(BaseSettings):
    """Database connection and query timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DB_TIMEOUT_", env_file=".env", extra="ignore"
    )

    connection: float = Field(
        default=30.0, description="Database connection timeout", ge=5.0, le=120.0
    )

    socket_connect: float = Field(
        default=5.0, description="Database socket connection timeout", ge=1.0, le=30.0
    )

    socket: float = Field(
        default=5.0, description="Database socket operation timeout", ge=1.0, le=60.0
    )

    query: float = Field(
        default=60.0, description="Database query execution timeout", ge=5.0, le=300.0
    )

    acquire: float = Field(
        default=2.0, description="Connection pool acquire timeout", ge=0.5, le=30.0
    )

    # Memgraph-specific
    memgraph_connection: float = Field(
        default=30.0, description="Memgraph connection timeout", ge=5.0, le=120.0
    )

    memgraph_command: float = Field(
        default=60.0, description="Memgraph command execution timeout", ge=5.0, le=300.0
    )


class CacheTimeoutConfig(BaseSettings):
    """Cache (Redis/Valkey) timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_TIMEOUT_", env_file=".env", extra="ignore"
    )

    socket_connect: float = Field(
        default=5.0, description="Cache socket connection timeout", ge=1.0, le=30.0
    )

    socket: float = Field(
        default=5.0, description="Cache socket operation timeout", ge=1.0, le=30.0
    )

    operation: float = Field(
        default=2.0, description="Cache operation timeout", ge=0.5, le=30.0
    )


class AsyncOperationTimeoutConfig(BaseSettings):
    """Async operation timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ASYNC_TIMEOUT_", env_file=".env", extra="ignore"
    )

    # Wait for timeouts
    quick_operation: float = Field(
        default=2.0, description="Timeout for quick async operations", ge=0.5, le=30.0
    )

    standard_operation: float = Field(
        default=10.0,
        description="Timeout for standard async operations",
        ge=1.0,
        le=300.0,
    )

    long_operation: float = Field(
        default=30.0,
        description="Timeout for long-running async operations",
        ge=5.0,
        le=600.0,
    )

    # Consumer shutdown timeouts
    consumer_shutdown: float = Field(
        default=10.0, description="Timeout for Kafka consumer shutdown", ge=5.0, le=60.0
    )

    event_consumption: float = Field(
        default=30.0,
        description="Timeout for event consumption task shutdown",
        ge=10.0,
        le=120.0,
    )

    # Subprocess timeouts
    git_operation: float = Field(
        default=5.0, description="Timeout for git operations", ge=1.0, le=60.0
    )

    git_log_operation: float = Field(
        default=10.0,
        description="Timeout for git log operations (can be slower)",
        ge=5.0,
        le=120.0,
    )


class BackgroundTaskTimeoutConfig(BaseSettings):
    """Background task and periodic job timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BACKGROUND_TIMEOUT_", env_file=".env", extra="ignore"
    )

    # Sleep intervals for periodic tasks
    health_check_interval: float = Field(
        default=30.0,
        description="Interval for periodic health checks",
        ge=5.0,
        le=300.0,
    )

    cache_cleanup_interval: float = Field(
        default=3600.0,
        description="Interval for cache cleanup (1 hour)",
        ge=60.0,
        le=86400.0,
    )

    metrics_collection_interval: float = Field(
        default=300.0,
        description="Interval for metrics collection (5 minutes)",
        ge=30.0,
        le=3600.0,
    )

    # Retry delays
    retry_base_delay: float = Field(
        default=1.0,
        description="Base delay for exponential backoff retries",
        ge=0.1,
        le=10.0,
    )

    retry_short_delay: float = Field(
        default=5.0, description="Short retry delay", ge=1.0, le=60.0
    )

    retry_long_delay: float = Field(
        default=10.0, description="Long retry delay", ge=5.0, le=120.0
    )

    # Processing delays
    processing_delay_short: float = Field(
        default=0.1,
        description="Short processing delay (rate limiting)",
        ge=0.01,
        le=5.0,
    )

    processing_delay_medium: float = Field(
        default=0.5, description="Medium processing delay", ge=0.1, le=10.0
    )

    processing_delay_long: float = Field(
        default=1.0, description="Long processing delay", ge=0.5, le=30.0
    )


class TestTimeoutConfig(BaseSettings):
    """Test execution timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="TEST_TIMEOUT_", env_file=".env", extra="ignore"
    )

    unit: float = Field(
        default=60.0, description="Timeout for unit tests", ge=10.0, le=300.0
    )

    integration: float = Field(
        default=300.0,
        description="Timeout for integration tests (5 minutes)",
        ge=60.0,
        le=1800.0,
    )

    e2e: float = Field(
        default=600.0,
        description="Timeout for end-to-end tests (10 minutes)",
        ge=120.0,
        le=3600.0,
    )

    performance: float = Field(
        default=900.0,
        description="Timeout for performance tests (15 minutes)",
        ge=300.0,
        le=3600.0,
    )

    pytest_total: float = Field(
        default=1800.0,
        description="Total pytest timeout (30 minutes)",
        ge=300.0,
        le=7200.0,
    )


class ServiceRestartTimeoutConfig(BaseSettings):
    """Service restart and recovery timeout configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SERVICE_RESTART_TIMEOUT_", env_file=".env", extra="ignore"
    )

    default: float = Field(
        default=60.0, description="Default service restart timeout", ge=10.0, le=300.0
    )

    database: float = Field(
        default=90.0, description="Database service restart timeout", ge=30.0, le=300.0
    )

    intelligence: float = Field(
        default=120.0,
        description="Intelligence service restart timeout",
        ge=30.0,
        le=300.0,
    )

    search: float = Field(
        default=120.0, description="Search service restart timeout", ge=30.0, le=300.0
    )

    langextract: float = Field(
        default=180.0,
        description="Langextract service restart timeout",
        ge=60.0,
        le=300.0,
    )

    # Container operations
    container_stop: float = Field(
        default=30.0, description="Docker container stop timeout", ge=10.0, le=120.0
    )

    container_wait: float = Field(
        default=60.0, description="Docker container wait timeout", ge=30.0, le=300.0
    )


class RetryConfig(BaseSettings):
    """Retry behavior configuration."""

    model_config = SettingsConfigDict(
        env_prefix="RETRY_", env_file=".env", extra="ignore"
    )

    max_attempts: int = Field(
        default=3, description="Maximum retry attempts", ge=1, le=10
    )

    backoff_multiplier: float = Field(
        default=2.0, description="Exponential backoff multiplier", ge=1.0, le=5.0
    )

    max_delay: float = Field(
        default=60.0, description="Maximum retry delay in seconds", ge=10.0, le=300.0
    )


class TimeoutConfig(BaseSettings):
    """Master timeout configuration aggregating all timeout categories."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sub-configurations
    http: HTTPTimeoutConfig = Field(default_factory=HTTPTimeoutConfig)
    database: DatabaseTimeoutConfig = Field(default_factory=DatabaseTimeoutConfig)
    cache: CacheTimeoutConfig = Field(default_factory=CacheTimeoutConfig)
    async_operation: AsyncOperationTimeoutConfig = Field(
        default_factory=AsyncOperationTimeoutConfig
    )
    background_task: BackgroundTaskTimeoutConfig = Field(
        default_factory=BackgroundTaskTimeoutConfig
    )
    test: TestTimeoutConfig = Field(default_factory=TestTimeoutConfig)
    service_restart: ServiceRestartTimeoutConfig = Field(
        default_factory=ServiceRestartTimeoutConfig
    )
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @classmethod
    def get_instance(cls) -> "TimeoutConfig":
        """Get singleton instance of timeout configuration."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance


# Global singleton instance
timeout_config = TimeoutConfig.get_instance()


# Convenience functions for common timeout scenarios
def get_http_timeout(service: str = "default") -> float:
    """
    Get HTTP timeout for a specific service.

    Args:
        service: Service name (default, intelligence, search, bridge, mcp, langextract)

    Returns:
        Timeout value in seconds
    """
    service_map = {
        "default": timeout_config.http.default,
        "intelligence": timeout_config.http.intelligence,
        "search": timeout_config.http.search,
        "bridge": timeout_config.http.bridge,
        "mcp": timeout_config.http.mcp,
        "langextract": timeout_config.http.langextract,
        "health": timeout_config.http.health_check,
        "optimization": timeout_config.http.optimization,
    }
    return service_map.get(service, timeout_config.http.default)


def get_db_timeout(operation: str = "connection") -> float:
    """
    Get database timeout for a specific operation.

    Args:
        operation: Operation type (connection, query, socket, acquire, memgraph_connection, memgraph_command)

    Returns:
        Timeout value in seconds
    """
    operation_map = {
        "connection": timeout_config.database.connection,
        "query": timeout_config.database.query,
        "socket": timeout_config.database.socket,
        "socket_connect": timeout_config.database.socket_connect,
        "acquire": timeout_config.database.acquire,
        "memgraph_connection": timeout_config.database.memgraph_connection,
        "memgraph_command": timeout_config.database.memgraph_command,
    }
    return operation_map.get(operation, timeout_config.database.connection)


def get_cache_timeout(operation: str = "operation") -> float:
    """
    Get cache timeout for a specific operation.

    Args:
        operation: Operation type (operation, socket, socket_connect)

    Returns:
        Timeout value in seconds
    """
    operation_map = {
        "operation": timeout_config.cache.operation,
        "socket": timeout_config.cache.socket,
        "socket_connect": timeout_config.cache.socket_connect,
    }
    return operation_map.get(operation, timeout_config.cache.operation)


def get_async_timeout(operation: str = "standard") -> float:
    """
    Get async operation timeout.

    Args:
        operation: Operation type (quick, standard, long, consumer_shutdown, event_consumption, git)

    Returns:
        Timeout value in seconds
    """
    operation_map = {
        "quick": timeout_config.async_operation.quick_operation,
        "standard": timeout_config.async_operation.standard_operation,
        "long": timeout_config.async_operation.long_operation,
        "consumer_shutdown": timeout_config.async_operation.consumer_shutdown,
        "event_consumption": timeout_config.async_operation.event_consumption,
        "git": timeout_config.async_operation.git_operation,
        "git_log": timeout_config.async_operation.git_log_operation,
    }
    return operation_map.get(
        operation, timeout_config.async_operation.standard_operation
    )


def get_retry_config() -> dict:
    """
    Get retry configuration as a dictionary.

    Returns:
        Dictionary with max_attempts, backoff_multiplier, max_delay
    """
    return {
        "max_attempts": timeout_config.retry.max_attempts,
        "backoff_multiplier": timeout_config.retry.backoff_multiplier,
        "max_delay": timeout_config.retry.max_delay,
    }


# Export all for easy importing
__all__ = [
    "TimeoutConfig",
    "HTTPTimeoutConfig",
    "DatabaseTimeoutConfig",
    "CacheTimeoutConfig",
    "AsyncOperationTimeoutConfig",
    "BackgroundTaskTimeoutConfig",
    "TestTimeoutConfig",
    "ServiceRestartTimeoutConfig",
    "RetryConfig",
    "timeout_config",
    "get_http_timeout",
    "get_db_timeout",
    "get_cache_timeout",
    "get_async_timeout",
    "get_retry_config",
]
