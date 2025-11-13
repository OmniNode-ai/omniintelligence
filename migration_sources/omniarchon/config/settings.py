"""
Centralized configuration for Archon Intelligence Platform.

Pattern: Pydantic Settings with type validation, singleton, and auto-loading.
Based on omniclaude's settings module pattern.
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# Auto-load .env files on module import (before Settings class instantiation)
def find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git"""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return current


def load_env_files(project_root: Path, environment: Optional[str] = None):
    """Load .env files in priority order"""
    from dotenv import load_dotenv

    # Load base .env
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger.debug(f"Loaded {env_file}")

    # Load environment-specific .env (overrides base)
    if environment:
        env_specific = project_root / f".env.{environment}"
        if env_specific.exists():
            load_dotenv(env_specific, override=True)
            logger.debug(f"Loaded {env_specific}")


# Auto-load on module import
try:
    _project_root = find_project_root()
    _environment = os.getenv("ENVIRONMENT")
    load_env_files(_project_root, _environment)
    logger.debug(f"Auto-loaded .env from: {_project_root}")
except Exception as e:
    logger.warning(f"Failed to auto-load .env: {e}")


class Settings(BaseSettings):
    """
    Centralized Archon configuration with type validation.

    Configuration Priority (highest to lowest):
    1. System environment variables
    2. .env.{ENVIRONMENT} file
    3. .env file
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="allow"
    )

    # ========================================================================
    # SECTION 1: Core Intelligence Services (LOCAL)
    # ========================================================================

    intelligence_service_port: int = Field(
        default=8053, ge=1, le=65535, description="Archon Intelligence service port"
    )

    bridge_service_port: int = Field(
        default=8054, ge=1, le=65535, description="Archon Bridge service port"
    )

    search_service_port: int = Field(
        default=8055, ge=1, le=65535, description="Archon Search service port"
    )

    langextract_service_port: int = Field(
        default=8156, ge=1, le=65535, description="LangExtract service port"
    )

    langextract_service_url: str = Field(
        default="http://archon-langextract:8156",
        description="LangExtract service URL (Docker: archon-langextract:8156)",
    )

    # ========================================================================
    # SECTION 2: Event Bus - Kafka/Redpanda (REMOTE at 192.168.86.200)
    # ========================================================================

    kafka_bootstrap_servers: str = Field(
        default="omninode-bridge-redpanda:9092",
        description=(
            "Kafka broker addresses. "
            "Use omninode-bridge-redpanda:9092 for Docker services, "
            "192.168.86.200:29092 for host scripts"
        ),
    )

    kafka_enable_intelligence: bool = Field(
        default=True, description="Enable intelligence event publishing"
    )

    kafka_request_timeout_ms: int = Field(
        default=5000,
        ge=1000,
        le=60000,
        description="Kafka request timeout in milliseconds",
    )

    kafka_topic_prefix: str = Field(
        default="dev.archon-intelligence",
        description="Kafka topic prefix for all Archon topics",
    )

    # ========================================================================
    # SECTION 3: Databases
    # ========================================================================

    # PostgreSQL (REMOTE at 192.168.86.200)
    postgres_host: str = Field(
        default="192.168.86.200", description="PostgreSQL host (remote server)"
    )

    postgres_port: int = Field(
        default=5436,
        ge=1,
        le=65535,
        description="PostgreSQL port (5436 for external access)",
    )

    postgres_database: str = Field(
        default="omninode_bridge", description="PostgreSQL database name"
    )

    postgres_user: str = Field(default="postgres", description="PostgreSQL username")

    postgres_password: str = Field(
        default="", description="PostgreSQL password (REQUIRED - set in .env)"
    )

    postgres_pool_min_size: int = Field(
        default=2, ge=1, le=100, description="Minimum PostgreSQL connection pool size"
    )

    postgres_pool_max_size: int = Field(
        default=10, ge=1, le=100, description="Maximum PostgreSQL connection pool size"
    )

    # Memgraph (LOCAL)
    memgraph_uri: str = Field(
        default="bolt://memgraph:7687", description="Memgraph connection URI"
    )

    # Qdrant (LOCAL)
    qdrant_host: str = Field(default="localhost", description="Qdrant host")

    qdrant_port: int = Field(default=6333, ge=1, le=65535, description="Qdrant port")

    qdrant_url: str = Field(
        default="http://localhost:6333", description="Qdrant connection URL"
    )

    # ========================================================================
    # SECTION 4: Performance & Caching
    # ========================================================================

    valkey_url: str = Field(
        default="redis://archon-valkey:6379/0",
        description="Valkey (Redis) connection URL",
    )

    enable_cache: bool = Field(
        default=True, description="Enable distributed caching with Valkey"
    )

    cache_ttl_patterns: int = Field(
        default=300, ge=0, description="Cache TTL for patterns in seconds"
    )

    # ========================================================================
    # SECTION 5: AI/ML Services
    # ========================================================================

    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key for embeddings and LLM"
    )

    embedding_service_url: str = Field(
        default="http://192.168.86.201:8002",
        description="Embedding service URL (vLLM or OpenAI-compatible endpoint)",
    )

    embedding_model: str = Field(
        default="Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        description="Embedding model name",
    )

    embedding_dimensions: int = Field(
        default=1536, ge=1, description="Embedding vector dimensions"
    )

    # ========================================================================
    # SECTION 6: Feature Flags & Timeouts
    # ========================================================================

    enable_real_time_events: bool = Field(
        default=True, description="Enable real-time event publishing"
    )

    # HTTP Timeouts (milliseconds)
    http_timeout_intelligence: int = Field(
        default=60000,
        ge=1000,
        le=300000,
        description="HTTP timeout for intelligence service",
    )

    http_timeout_search: int = Field(
        default=60000, ge=1000, le=300000, description="HTTP timeout for search service"
    )

    # Database Timeouts (milliseconds)
    db_timeout_connection: int = Field(
        default=30000, ge=1000, le=120000, description="Database connection timeout"
    )

    db_timeout_query: int = Field(
        default=60000, ge=1000, le=300000, description="Database query timeout"
    )

    # Cache Timeouts (milliseconds)
    cache_timeout_operation: int = Field(
        default=2000, ge=100, le=30000, description="Cache operation timeout"
    )

    # ========================================================================
    # Field Validators
    # ========================================================================

    @field_validator(
        "postgres_port",
        "qdrant_port",
        "intelligence_service_port",
        "bridge_service_port",
        "search_service_port",
    )
    @classmethod
    def validate_port_range(cls, v: int) -> int:
        """Validate port is in valid range (1-65535)"""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator(
        "kafka_request_timeout_ms", "http_timeout_intelligence", "db_timeout_connection"
    )
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable"""
        if v < 1000:
            raise ValueError(f"Timeout must be at least 1000ms, got {v}")
        return v

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def get_postgres_dsn(self, async_driver: bool = True) -> str:
        """Generate PostgreSQL connection string"""
        scheme = "postgresql+asyncpg" if async_driver else "postgresql"
        password = self.get_effective_postgres_password()
        return (
            f"{scheme}://{self.postgres_user}:{password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    def get_effective_postgres_password(self) -> str:
        """Get PostgreSQL password with validation"""
        if not self.postgres_password:
            raise ValueError(
                "PostgreSQL password not configured. " "Set POSTGRES_PASSWORD in .env"
            )
        return self.postgres_password

    def get_effective_kafka_bootstrap_servers(self) -> str:
        """Get Kafka bootstrap servers"""
        return self.kafka_bootstrap_servers

    def validate_required_services(self) -> List[str]:
        """Validate that required services are configured"""
        errors = []

        # Check PostgreSQL password
        try:
            self.get_effective_postgres_password()
        except ValueError as e:
            errors.append(str(e))

        return errors

    def to_dict_sanitized(self) -> dict:
        """Export config with sensitive values sanitized"""
        data = self.model_dump()

        # Sanitize sensitive fields
        sensitive_fields = [
            "postgres_password",
            "openai_api_key",
        ]

        for field in sensitive_fields:
            if data.get(field):
                data[field] = "***REDACTED***"

        return data

    def log_configuration(
        self, logger_instance: Optional[logging.Logger] = None
    ) -> None:
        """Log configuration with sanitized sensitive values"""
        log = logger_instance or logger

        log.info("=" * 80)
        log.info("Archon Configuration")
        log.info(f"  Kafka: {self.kafka_bootstrap_servers}")
        log.info(f"  PostgreSQL: {self.postgres_host}:{self.postgres_port}")
        log.info(f"  Memgraph: {self.memgraph_uri}")
        log.info(f"  Qdrant: {self.qdrant_url}")
        log.info(f"  Embedding Service: {self.embedding_service_url}")
        log.info(f"  Cache Enabled: {self.enable_cache}")
        log.info(f"  Real-time Events: {self.enable_real_time_events}")
        log.info("=" * 80)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Thread-safe singleton using lru_cache"""
    settings_instance = Settings()

    # Validate on first load
    errors = settings_instance.validate_required_services()
    if errors:
        logger.error(f"Configuration validation failed:\n" + "\n".join(errors))

    return settings_instance


# Export singleton instance
settings = get_settings()
