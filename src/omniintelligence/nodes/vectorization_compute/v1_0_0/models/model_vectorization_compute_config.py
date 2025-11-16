"""
Configuration model for Vectorization Compute Node
"""

from pydantic import BaseModel, Field
from typing import Literal


class ModelVectorizationComputeConfig(BaseModel):
    """Configuration for vectorization compute operations."""

    default_model: str = Field(
        default="text-embedding-3-small",
        description="Default embedding model to use"
    )
    max_batch_size: int = Field(
        default=100,
        description="Maximum batch size for vectorization",
        gt=0,
        le=1000
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable caching of embeddings"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds",
        gt=0
    )
    timeout_ms: int = Field(
        default=30000,
        description="Operation timeout in milliseconds",
        gt=0
    )
    max_content_length: int = Field(
        default=8000,
        description="Maximum content length in characters",
        gt=0
    )

    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        """Factory method for environment-specific configurations."""
        if env == "production":
            return cls(
                default_model="text-embedding-3-small",
                max_batch_size=100,
                enable_caching=True,
                cache_ttl_seconds=3600,
                timeout_ms=30000,
            )
        elif env == "staging":
            return cls(
                default_model="text-embedding-3-small",
                max_batch_size=50,
                enable_caching=True,
                cache_ttl_seconds=1800,
                timeout_ms=60000,
            )
        else:  # development
            return cls(
                default_model="text-embedding-3-small",
                max_batch_size=10,
                enable_caching=False,
                cache_ttl_seconds=300,
                timeout_ms=120000,
            )

    class Config:
        json_schema_extra = {
            "example": {
                "default_model": "text-embedding-3-small",
                "max_batch_size": 100,
                "enable_caching": True,
                "cache_ttl_seconds": 3600
            }
        }
