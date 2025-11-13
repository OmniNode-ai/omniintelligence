"""
Configuration for ONEX Qdrant Vector Operations

Manages configuration from environment variables and provides
validated configuration models.
"""

import os
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator


class QdrantConfig(BaseModel):
    """Configuration for Qdrant vector database connection."""

    url: str = Field(default="http://qdrant:6333", description="Qdrant service URL")
    api_key: Optional[str] = Field(
        default=None, description="Qdrant API key (optional)"
    )
    collection_name: str = Field(
        default="intelligence_patterns", description="Default collection name"
    )

    @validator("url")
    def validate_url(cls, v):
        """Validate URL format using comprehensive parsing."""
        if v:
            # Parse URL and validate components
            parsed = urlparse(v)

            # Validate scheme
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(
                    f"Qdrant URL must use http or https scheme, got: {parsed.scheme or 'none'}"
                )

            # Validate netloc (host:port)
            if not parsed.netloc:
                raise ValueError(f"Qdrant URL must include a valid host, got: {v}")

            # Check for suspicious patterns
            if any(char in v for char in [" ", "\t", "\n", "\r"]):
                raise ValueError(
                    f"Qdrant URL contains invalid whitespace characters: {v!r}"
                )

            # Remove trailing slash for consistency
            return v.rstrip("/")
        return v


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI API connection."""

    api_key: str = Field(..., description="OpenAI API key (required)")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    max_retries: int = Field(
        default=3, description="Maximum retry attempts for API calls"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")

    @validator("api_key")
    def validate_api_key(cls, v):
        """Ensure API key is provided."""
        if not v or not v.strip():
            raise ValueError("OpenAI API key is required")
        return v


class PerformanceConfig(BaseModel):
    """Performance tuning configuration."""

    max_batch_size: int = Field(
        default=100, ge=1, le=1000, description="Maximum batch size for indexing"
    )
    default_search_limit: int = Field(
        default=10, ge=1, le=1000, description="Default search result limit"
    )
    default_hnsw_ef: int = Field(
        default=128, ge=16, le=512, description="Default HNSW search parameter (ef)"
    )
    target_search_latency_ms: float = Field(
        default=100.0, description="Target search latency in milliseconds"
    )
    target_batch_latency_ms: float = Field(
        default=2000.0, description="Target batch indexing latency in milliseconds"
    )


class ONEXQdrantConfig(BaseModel):
    """Complete configuration for ONEX Qdrant operations."""

    qdrant: QdrantConfig
    openai: OpenAIConfig
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    @classmethod
    def from_env(cls) -> "ONEXQdrantConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            QDRANT_URL: Qdrant service URL
            QDRANT_API_KEY: Optional Qdrant API key
            QDRANT_COLLECTION_NAME: Default collection name
            OPENAI_API_KEY: OpenAI API key (required)
            OPENAI_EMBEDDING_MODEL: OpenAI embedding model
            MAX_BATCH_SIZE: Maximum batch size for indexing
            DEFAULT_SEARCH_LIMIT: Default search result limit
            DEFAULT_HNSW_EF: Default HNSW search parameter

        Returns:
            Complete ONEX Qdrant configuration

        Raises:
            ValueError: If required environment variables are missing
        """
        return cls(
            qdrant=QdrantConfig(
                url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
                collection_name=os.getenv(
                    "QDRANT_COLLECTION_NAME", "intelligence_patterns"
                ),
            ),
            openai=OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                embedding_model=os.getenv(
                    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
                ),
                max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
                timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
            ),
            performance=PerformanceConfig(
                max_batch_size=int(os.getenv("MAX_BATCH_SIZE", "100")),
                default_search_limit=int(os.getenv("DEFAULT_SEARCH_LIMIT", "10")),
                default_hnsw_ef=int(os.getenv("DEFAULT_HNSW_EF", "128")),
                target_search_latency_ms=float(
                    os.getenv("TARGET_SEARCH_LATENCY_MS", "100.0")
                ),
                target_batch_latency_ms=float(
                    os.getenv("TARGET_BATCH_LATENCY_MS", "2000.0")
                ),
            ),
        )


# Global config instance (lazy loaded)
_config: Optional[ONEXQdrantConfig] = None


def get_config() -> ONEXQdrantConfig:
    """
    Get the global ONEX Qdrant configuration instance.

    Returns:
        Global configuration instance

    Raises:
        ValueError: If configuration cannot be loaded
    """
    global _config
    if _config is None:
        _config = ONEXQdrantConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration instance (primarily for testing)."""
    global _config
    _config = None
