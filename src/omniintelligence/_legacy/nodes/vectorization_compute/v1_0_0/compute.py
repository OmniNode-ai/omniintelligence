"""
Vectorization Compute Node

Generates embeddings from code and documents using:
- OpenAI API (highest quality, requires API key)
- SentenceTransformers (high quality, offline, no API key)
- TF-IDF fallback (basic quality, always available)
"""

import logging
import os
from enum import Enum
from typing import Any

import httpx
from omnibase_core.nodes import NodeCompute
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    TFIDF = "tfidf"
    AUTO = "auto"  # Automatic fallback chain


# Lazy-loaded SentenceTransformer model cache
_sentence_transformer_model: Any = None


def _get_sentence_transformer_model(model_name: str) -> Any:
    """Lazy-load SentenceTransformer model to avoid import overhead.

    Args:
        model_name: Name of the SentenceTransformers model to load

    Returns:
        Loaded SentenceTransformer model instance

    Raises:
        ImportError: If sentence-transformers package is not installed
    """
    global _sentence_transformer_model
    if _sentence_transformer_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading SentenceTransformer model: {model_name}")
            _sentence_transformer_model = SentenceTransformer(model_name)
            logger.info("SentenceTransformer model loaded successfully")
        except ImportError as e:
            raise ImportError(
                "sentence-transformers package not installed. "
                "Install with: pip install sentence-transformers"
            ) from e
    return _sentence_transformer_model


class ModelVectorizationInput(BaseModel):
    """Input model for vectorization."""

    content: str = Field(..., description="Content to vectorize")
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_name: str = Field(default="text-embedding-3-small")
    batch_mode: bool = Field(default=False)


class ModelVectorizationOutput(BaseModel):
    """Output model for vectorization."""

    success: bool
    embeddings: list[float]
    model_used: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelVectorizationConfig(BaseModel):
    """Configuration for vectorization."""

    default_model: str = "text-embedding-3-small"
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    embedding_provider: EmbeddingProvider = EmbeddingProvider.AUTO
    max_batch_size: int = 100
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    # Dimension varies by provider:
    # - OpenAI text-embedding-3-small: 1536
    # - SentenceTransformers all-MiniLM-L6-v2: 384
    # - TF-IDF fallback: configurable (default 1536)
    embedding_dimension: int = 1536
    sentence_transformer_dimension: int = 384


class VectorizationCompute(NodeCompute):
    """Compute node for generating embeddings.

    Supports multiple embedding providers with automatic fallback:
    - OpenAI API (highest quality, requires API key)
    - SentenceTransformers (high quality, offline, no API key required)
    - TF-IDF fallback (basic quality, always available)

    Configure via EMBEDDING_PROVIDER env var: 'openai', 'sentence-transformers', 'tfidf', 'auto'
    """

    def __init__(
        self,
        container: Any | None = None,
        config: ModelVectorizationConfig | None = None,
    ) -> None:
        """Initialize the vectorization compute node.

        Args:
            container: Optional ONEX container for dependency injection (not used in standalone mode)
            config: Optional configuration for the node
        """
        # Only initialize base class with proper container (has compute_cache_config)
        # In standalone/test mode, container is None or config, so we skip super().__init__
        if container is not None and hasattr(container, "compute_cache_config"):
            super().__init__(container)

        self.config = config or ModelVectorizationConfig()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", self.config.default_model
        )
        self.sentence_transformer_model = os.getenv(
            "SENTENCE_TRANSFORMER_MODEL", self.config.sentence_transformer_model
        )

        # Parse embedding provider from env or config
        provider_str = os.getenv("EMBEDDING_PROVIDER", self.config.embedding_provider.value)
        try:
            self.embedding_provider = EmbeddingProvider(provider_str.lower())
        except ValueError:
            logger.warning(
                f"Invalid EMBEDDING_PROVIDER '{provider_str}', using 'auto'"
            )
            self.embedding_provider = EmbeddingProvider.AUTO

        # Log provider configuration
        self._log_provider_status()

    def _log_provider_status(self) -> None:
        """Log the configured embedding provider and availability status."""
        if self.embedding_provider == EmbeddingProvider.AUTO:
            providers = []
            if self.openai_api_key:
                providers.append("OpenAI")
            providers.append("SentenceTransformers")
            providers.append("TF-IDF")
            logger.info(
                f"Embedding provider: AUTO (fallback chain: {' -> '.join(providers)})"
            )
        else:
            logger.info(f"Embedding provider: {self.embedding_provider.value}")

        if (
            self.embedding_provider in (EmbeddingProvider.OPENAI, EmbeddingProvider.AUTO)
            and not self.openai_api_key
        ):
            logger.warning(
                "OPENAI_API_KEY not found - OpenAI embeddings unavailable"
            )

    def _generate_sentence_transformer_embedding(self, content: str) -> list[float]:
        """Generate embedding using SentenceTransformers.

        Uses the configured model (default: all-MiniLM-L6-v2) for offline
        high-quality embeddings without requiring an API key.

        Args:
            content: Text content to embed

        Returns:
            List of float values representing the embedding (384 dimensions for MiniLM)

        Raises:
            ImportError: If sentence-transformers is not installed
            Exception: If embedding generation fails
        """
        model = _get_sentence_transformer_model(self.sentence_transformer_model)

        # Generate embedding - returns numpy array
        embedding_array = model.encode(content, convert_to_numpy=True)

        # Convert numpy array to list of floats
        embedding = embedding_array.tolist()

        logger.debug(
            f"Generated SentenceTransformer embedding: {len(embedding)} dimensions "
            f"for {len(content)} chars using {self.sentence_transformer_model}"
        )
        return embedding

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _generate_openai_embedding(self, content: str) -> list[float]:
        """Generate embedding using OpenAI API.

        Args:
            content: Text content to embed

        Returns:
            List of float values representing the embedding

        Raises:
            httpx.HTTPStatusError: If API request fails
            httpx.TimeoutException: If request times out
        """
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": content, "model": self.embedding_model}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract embedding from response
            embedding = data["data"][0]["embedding"]
            logger.debug(
                f"Generated OpenAI embedding: {len(embedding)} dimensions for {len(content)} chars"
            )
            return embedding

    def _generate_tfidf_embedding(self, content: str) -> list[float]:
        """Generate simple TF-IDF-like embedding as fallback.

        This is a basic fallback that creates a fixed-size vector based on
        word frequencies and character distributions. Not as sophisticated
        as real embeddings but provides consistent dimensionality.

        Args:
            content: Text content to embed

        Returns:
            List of float values representing the embedding
        """
        import hashlib
        import math

        # Normalize content
        content_lower = content.lower()
        words = content_lower.split()

        # Initialize embedding vector
        embedding = [0.0] * self.config.embedding_dimension

        # Simple word frequency-based features
        word_freq: dict[str, int] = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Map words to embedding dimensions using hash
        for word, freq in word_freq.items():
            # Use hash to deterministically map word to dimensions
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            # Use multiple dimensions per word for better distribution
            for i in range(5):
                idx = (hash_val + i) % self.config.embedding_dimension
                # TF-IDF-like weighting: log(1 + freq) / sqrt(len(words))
                weight = math.log(1 + freq) / math.sqrt(len(words))
                embedding[idx] += weight

        # Normalize embedding to unit length
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        logger.debug(
            f"Generated TF-IDF embedding: {len(embedding)} dimensions for {len(content)} chars"
        )
        return embedding

    async def process(
        self, input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Generate embeddings for content.

        Uses the configured provider or automatic fallback chain:
        OpenAI -> SentenceTransformers -> TF-IDF

        Args:
            input_data: Input containing content and configuration

        Returns:
            Output containing embeddings and metadata
        """
        try:
            if not input_data.content.strip():
                logger.warning("Empty content provided for vectorization")
                return ModelVectorizationOutput(
                    success=False,
                    embeddings=[0.0] * self.config.embedding_dimension,
                    model_used="none",
                    metadata={
                        "error": "Empty content",
                        "content_length": 0,
                    },
                )

            # Direct provider selection (non-AUTO mode)
            if self.embedding_provider == EmbeddingProvider.OPENAI:
                return await self._try_openai_embedding(input_data)
            elif self.embedding_provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                return self._try_sentence_transformer_embedding(input_data)
            elif self.embedding_provider == EmbeddingProvider.TFIDF:
                return self._try_tfidf_embedding(input_data)

            # AUTO mode: fallback chain OpenAI -> SentenceTransformers -> TF-IDF
            return await self._try_auto_fallback_chain(input_data)

        except Exception as e:
            logger.error(f"Vectorization failed: {e}", exc_info=True)
            return ModelVectorizationOutput(
                success=False,
                embeddings=[0.0] * self.config.embedding_dimension,
                model_used="error",
                metadata={
                    "error": str(e),
                    "content_length": len(input_data.content),
                },
            )

    async def _try_openai_embedding(
        self, input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Try to generate embedding using OpenAI API."""
        if not self.openai_api_key:
            return ModelVectorizationOutput(
                success=False,
                embeddings=[0.0] * self.config.embedding_dimension,
                model_used="error",
                metadata={
                    "error": "OPENAI_API_KEY not configured",
                    "content_length": len(input_data.content),
                },
            )
        embeddings = await self._generate_openai_embedding(input_data.content)
        return ModelVectorizationOutput(
            success=True,
            embeddings=embeddings,
            model_used=self.embedding_model,
            metadata={
                "content_length": len(input_data.content),
                "method": "openai_api",
                "provider": "openai",
                **input_data.metadata,
            },
        )

    def _try_sentence_transformer_embedding(
        self, input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Try to generate embedding using SentenceTransformers."""
        embeddings = self._generate_sentence_transformer_embedding(input_data.content)
        return ModelVectorizationOutput(
            success=True,
            embeddings=embeddings,
            model_used=self.sentence_transformer_model,
            metadata={
                "content_length": len(input_data.content),
                "method": "sentence_transformers",
                "provider": "sentence-transformers",
                "dimensions": len(embeddings),
                **input_data.metadata,
            },
        )

    def _try_tfidf_embedding(
        self, input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Generate embedding using TF-IDF fallback."""
        embeddings = self._generate_tfidf_embedding(input_data.content)
        return ModelVectorizationOutput(
            success=True,
            embeddings=embeddings,
            model_used="tfidf-fallback",
            metadata={
                "content_length": len(input_data.content),
                "method": "tfidf_fallback",
                "provider": "tfidf",
                "note": "Using TF-IDF fallback - consider using sentence-transformers for better quality",
                **input_data.metadata,
            },
        )

    async def _try_auto_fallback_chain(
        self, input_data: ModelVectorizationInput
    ) -> ModelVectorizationOutput:
        """Try embedding providers in fallback chain: OpenAI -> SentenceTransformers -> TF-IDF."""
        # Try OpenAI first if API key available
        if self.openai_api_key:
            try:
                return await self._try_openai_embedding(input_data)
            except Exception as e:
                logger.warning(
                    f"OpenAI API failed, falling back to SentenceTransformers: {e}"
                )

        # Try SentenceTransformers
        try:
            return self._try_sentence_transformer_embedding(input_data)
        except ImportError as e:
            logger.warning(
                f"SentenceTransformers not available, falling back to TF-IDF: {e}"
            )
        except Exception as e:
            logger.warning(
                f"SentenceTransformers failed, falling back to TF-IDF: {e}"
            )

        # Final fallback to TF-IDF
        return self._try_tfidf_embedding(input_data)
