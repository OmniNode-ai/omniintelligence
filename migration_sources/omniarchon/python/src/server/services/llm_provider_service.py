"""
LLM Provider Service

Provides a unified interface for creating OpenAI-compatible clients for different LLM providers.
Supports OpenAI, Ollama, and Google Gemini.
"""

import os
import time
from contextlib import asynccontextmanager
from typing import Any

import openai
from server.config.logfire_config import get_logger
from server.services.credential_service import credential_service

logger = get_logger(__name__)

# Settings cache with TTL
_settings_cache: dict[str, tuple[Any, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_settings(key: str) -> Any | None:
    """Get cached settings if not expired."""
    if key in _settings_cache:
        value, timestamp = _settings_cache[key]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            return value
        else:
            # Expired, remove from cache
            del _settings_cache[key]
    return None


def _set_cached_settings(key: str, value: Any) -> None:
    """Cache settings with current timestamp."""
    _settings_cache[key] = (value, time.time())


@asynccontextmanager
async def get_llm_client(
    provider: str | None = None, use_embedding_provider: bool = False
):
    """
    Create an async OpenAI-compatible client based on the configured provider.

    This context manager handles client creation for different LLM providers
    that support the OpenAI API format.

    Args:
        provider: Override provider selection
        use_embedding_provider: Use the embedding-specific provider if different

    Yields:
        openai.AsyncOpenAI: An OpenAI-compatible client configured for the selected provider
    """
    client = None

    try:
        # Get provider configuration from database settings
        if provider:
            # Explicit provider requested - get minimal config
            provider_name = provider
            api_key = await credential_service._get_provider_api_key(provider)

            # Check cache for rag_settings
            cache_key = "rag_strategy_settings"
            rag_settings = _get_cached_settings(cache_key)
            if rag_settings is None:
                rag_settings = await credential_service.get_credentials_by_category(
                    "rag_strategy"
                )
                _set_cached_settings(cache_key, rag_settings)
                logger.debug("Fetched and cached rag_strategy settings")
            else:
                logger.debug("Using cached rag_strategy settings")

            base_url = credential_service._get_provider_base_url(provider, rag_settings)
        else:
            # Get configured provider from database
            service_type = "embedding" if use_embedding_provider else "llm"

            # Check cache for provider config
            cache_key = f"provider_config_{service_type}"
            provider_config = _get_cached_settings(cache_key)
            if provider_config is None:
                provider_config = await credential_service.get_active_provider(
                    service_type
                )
                _set_cached_settings(cache_key, provider_config)
                logger.debug(f"Fetched and cached {service_type} provider config")
            else:
                logger.debug(f"Using cached {service_type} provider config")

            provider_name = provider_config["provider"]
            api_key = provider_config["api_key"]
            base_url = provider_config["base_url"]

        logger.info(f"Creating LLM client for provider: {provider_name}")

        if provider_name == "openai":
            if not api_key:
                raise ValueError("OpenAI API key not found")

            client = openai.AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client created successfully")

        elif provider_name == "ollama":
            # Ollama requires an API key in the client but doesn't actually use it
            client = openai.AsyncOpenAI(
                api_key="ollama",  # Required but unused by Ollama
                base_url=base_url or "http://localhost:11434/v1",
            )
            logger.info(f"Ollama client created successfully with base URL: {base_url}")

        elif provider_name == "google":
            if not api_key:
                raise ValueError("Google API key not found")

            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
                or "https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            logger.info("Google Gemini client created successfully")

        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

        yield client

    except Exception as e:
        logger.error(
            f"Error creating LLM client for provider {provider_name if 'provider_name' in locals() else 'unknown'}: {e}"
        )
        raise
    finally:
        # Cleanup if needed
        pass


async def get_embedding_model(provider: str | None = None) -> str:
    """
    Get the configured embedding model from environment variables ONLY.

    NO hardcoded fallbacks - ensures vector dimensions match configuration.

    Args:
        provider: Ignored (kept for backward compatibility)

    Returns:
        str: The embedding model from EMBEDDING_MODEL env var

    Raises:
        ValueError: If EMBEDDING_MODEL not set in .env file
    """
    try:
        # Get embedding model from environment ONLY
        embedding_model = os.getenv("EMBEDDING_MODEL")

        if not embedding_model:
            error_msg = (
                "EMBEDDING_MODEL not set in .env file. "
                "This is required to ensure correct vector dimensions. "
                "Add to .env: EMBEDDING_MODEL=text-embedding-3-small (or your model)"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Using embedding model from .env: {embedding_model}")
        return embedding_model

    except Exception as e:
        logger.error(f"Error getting embedding model: {e}")
        # Don't fallback - fail fast to prevent dimension mismatches
        raise
