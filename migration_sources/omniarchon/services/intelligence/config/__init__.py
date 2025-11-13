"""
Configuration Module for Intelligence Service

Centralized configuration management for intelligence service components.
"""

import os

from pydantic_settings import BaseSettings

from .timeout_config import (
    TimeoutConfig,
    get_async_timeout,
    get_cache_timeout,
    get_db_timeout,
    get_http_timeout,
    get_retry_config,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "production")

    # Service Configuration
    service_name: str = "archon-intelligence"
    service_port: int = int(os.getenv("INTELLIGENCE_SERVICE_PORT", "8053"))

    # Kafka Configuration
    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "omninode-bridge-redpanda:9092"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra environment variables without validation errors


# Global settings instance
settings = Settings()

__all__ = [
    "settings",
    "Settings",
    "TimeoutConfig",
    "get_http_timeout",
    "get_db_timeout",
    "get_cache_timeout",
    "get_async_timeout",
    "get_retry_config",
]
