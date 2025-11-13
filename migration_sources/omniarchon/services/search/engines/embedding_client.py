"""
Polymorphic Embedding Client

Provides a clean abstraction for different embedding backends (vLLM, OpenAI-compatible APIs).
Uses Protocol pattern for type safety and dependency injection.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Protocol

import httpx
import numpy as np
from models.external_validation import ValidationStatus
from utils.response_validator import validate_ollama_embedding, validate_ollama_health

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    """Protocol for embedding client implementations"""

    async def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        ...

    async def health_check(self) -> bool:
        """Check if embedding service is healthy"""
        ...


class OllamaEmbeddingClient:
    """
    DEPRECATED: Ollama-specific embedding client.

    This client is deprecated as we've migrated to vLLM with OpenAI-compatible API.
    Kept for backward compatibility only. Use OpenAIEmbeddingClient instead.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        http_client: httpx.AsyncClient,
        timeout: float,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_client = http_client
        self.timeout = timeout
        logger.warning(
            "OllamaEmbeddingClient is deprecated. Use OpenAIEmbeddingClient (vLLM) instead."
        )

    async def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using Ollama API (DEPRECATED)"""
        try:
            response = await self.http_client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"Ollama embedding failed: {response.status_code} - {response.text}"
                )
                return None

            result = response.json()

            # Validate Ollama response
            validation_result = validate_ollama_embedding(result, allow_partial=True)

            if validation_result.status == ValidationStatus.FAILED:
                logger.error(
                    f"Ollama response validation failed: {validation_result.errors}"
                )
                return None

            # Extract validated embedding
            validated_response = validation_result.validated_data
            if not validated_response or not validated_response.embedding:
                logger.error("No embedding in validated Ollama response")
                return None

            return np.array(validated_response.embedding, dtype=np.float32)

        except Exception as e:
            logger.error(f"Ollama embedding generation failed: {e}")
            return None

    async def health_check(self) -> bool:
        """Check Ollama service health (DEPRECATED)"""
        try:
            response = await self.http_client.get(
                f"{self.base_url}/api/tags", timeout=self.timeout
            )
            if response.status_code == 200:
                result = response.json()
                validation_result = validate_ollama_health(result, allow_partial=True)
                return validation_result.status in [
                    ValidationStatus.VALID,
                    ValidationStatus.PARTIAL,
                ]
            return False
        except Exception as e:
            logger.debug(f"Ollama health check failed: {e}")
            return False


class OpenAIEmbeddingClient:
    """OpenAI-compatible embedding client (vLLM, OpenAI)"""

    def __init__(
        self,
        base_url: str,
        model: str,
        http_client: httpx.AsyncClient,
        timeout: float,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_client = http_client
        self.timeout = timeout

    async def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding using OpenAI-compatible API"""
        try:
            response = await self.http_client.post(
                f"{self.base_url}/v1/embeddings",
                json={"model": self.model, "input": text},
                timeout=self.timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"OpenAI embedding failed: {response.status_code} - {response.text}"
                )
                return None

            result = response.json()

            # OpenAI format: {"data": [{"embedding": [...]}]}
            if "data" not in result or len(result["data"]) == 0:
                logger.error("Invalid OpenAI embedding response format")
                return None

            embedding = result["data"][0]["embedding"]
            return np.array(embedding, dtype=np.float32)

        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            return None

    async def health_check(self) -> bool:
        """Check OpenAI-compatible service health"""
        try:
            response = await self.http_client.get(
                f"{self.base_url}/v1/models", timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"OpenAI health check failed: {e}")
            return False


def create_embedding_client(
    base_url: str,
    model: str,
    http_client: httpx.AsyncClient,
    timeout: float,
    client_type: str = "auto",
) -> EmbeddingClient:
    """
    Factory to create the appropriate embedding client.

    Args:
        base_url: Embedding service URL
        model: Model name
        http_client: HTTP client instance
        timeout: Request timeout
        client_type: "ollama" (deprecated), "openai", or "auto" (default: OpenAI-compatible)

    Returns:
        Embedding client instance
    """
    if client_type == "auto":
        # Auto-detect based on URL
        # Default to OpenAI-compatible (vLLM) for all URLs
        if "/api/" in base_url and "/v1/" not in base_url:
            # Legacy Ollama-style URL detected
            logger.warning(
                f"Detected Ollama-style URL ({base_url}). "
                "Consider migrating to OpenAI-compatible API (vLLM)."
            )
            client_type = "ollama"
        else:
            # Default to OpenAI-compatible (vLLM)
            client_type = "openai"

    if client_type == "openai":
        logger.info(f"Creating OpenAI-compatible embedding client for {base_url}")
        return OpenAIEmbeddingClient(base_url, model, http_client, timeout)
    else:
        logger.warning(
            f"Creating deprecated Ollama embedding client for {base_url}. "
            "Please migrate to vLLM with OpenAI-compatible API."
        )
        return OllamaEmbeddingClient(base_url, model, http_client, timeout)
