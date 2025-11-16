"""
Configuration for Vectorization Compute Node
"""

from typing import Literal
from .models import ModelVectorizationComputeConfig


class VectorizationComputeConfig:
    """
    Configuration wrapper for vectorization compute operations.

    Provides environment-specific configurations and validation.
    """

    def __init__(self, config: ModelVectorizationComputeConfig):
        """
        Initialize configuration.

        Args:
            config: Pydantic configuration model
        """
        self.config = config
        self._validate_config()

    @classmethod
    def for_environment(
        cls,
        env: Literal["production", "staging", "development"]
    ) -> "VectorizationComputeConfig":
        """
        Create environment-specific configuration.

        Args:
            env: Environment name

        Returns:
            Configuration instance
        """
        config = ModelVectorizationComputeConfig.for_environment(env)
        return cls(config)

    @classmethod
    def default(cls) -> "VectorizationComputeConfig":
        """Create default configuration for production."""
        return cls.for_environment("production")

    def _validate_config(self) -> None:
        """Validate configuration constraints."""
        # Ensure timeout is reasonable
        if self.config.timeout_ms < 1000:
            raise ValueError("Timeout must be at least 1000ms")

        # Ensure cache TTL is reasonable
        if self.config.enable_caching and self.config.cache_ttl_seconds < 60:
            raise ValueError("Cache TTL must be at least 60 seconds when caching is enabled")

        # Ensure batch size is reasonable
        if self.config.max_batch_size > 1000:
            raise ValueError("Batch size cannot exceed 1000")

    def get_timeout_seconds(self) -> float:
        """Get timeout in seconds."""
        return self.config.timeout_ms / 1000.0

    def should_cache(self) -> bool:
        """Check if caching is enabled."""
        return self.config.enable_caching

    def get_model_name(self) -> str:
        """Get default model name."""
        return self.config.default_model
