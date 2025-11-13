"""
Ollama API Response Models

Pydantic models for validating Ollama API responses (embeddings, generation).

API Documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
Performance: Validation overhead <1ms for typical responses
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OllamaEmbeddingResponse(BaseModel):
    """
    Response model for Ollama /api/embeddings endpoint.

    Validates the embedding vector response to ensure correct dimensions
    and data types.

    Example:
        {
            "embedding": [0.123, -0.456, 0.789, ...],  # 768 dimensions for nomic-embed-text
            "model": "nomic-embed-text",
            "prompt": "sample text"
        }
    """

    embedding: List[float] = Field(
        ...,
        description="Embedding vector (768 dimensions for nomic-embed-text)",
        min_length=1,
    )
    model: Optional[str] = Field(
        default=None, description="Model name used for embedding"
    )
    prompt: Optional[str] = Field(default=None, description="Original prompt text")

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: List[float]) -> List[float]:
        """
        Validate embedding vector dimensions.

        Accepts any non-empty embedding vector. Logs a warning for dimensions
        outside common ranges, but does not fail validation to support custom models.
        """
        if not v:
            raise ValueError("Embedding vector cannot be empty")

        # Common embedding dimensions for reference
        # But we accept ANY dimension to support custom/future models
        common_dimensions = [384, 512, 768, 1024, 1536, 3072]
        if len(v) not in common_dimensions:
            # Log info but don't fail - allow any dimension for flexibility
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"Embedding dimension {len(v)} detected. "
                f"Common dimensions include {common_dimensions}, but custom dimensions are supported."
            )

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embedding": [0.123, -0.456, 0.789],  # Truncated for readability
                "model": "nomic-embed-text",
                "prompt": "sample text for embedding",
            }
        }
    )


class OllamaGenerateResponse(BaseModel):
    """
    Response model for Ollama /api/generate endpoint.

    Validates text generation responses for streaming and non-streaming modes.

    Example:
        {
            "model": "llama2",
            "created_at": "2024-01-01T00:00:00Z",
            "response": "Generated text response",
            "done": true,
            "context": [1, 2, 3],
            "total_duration": 1000000000,
            "load_duration": 100000000,
            "prompt_eval_count": 10,
            "prompt_eval_duration": 200000000,
            "eval_count": 50,
            "eval_duration": 700000000
        }
    """

    model: str = Field(..., description="Model name used for generation")
    created_at: str = Field(..., description="Timestamp of generation")
    response: str = Field(..., description="Generated text response")
    done: bool = Field(..., description="Whether generation is complete")

    # Optional fields for detailed metrics
    context: Optional[List[int]] = Field(
        default=None, description="Context encoding for continuing conversation"
    )
    total_duration: Optional[int] = Field(
        default=None, description="Total duration in nanoseconds"
    )
    load_duration: Optional[int] = Field(
        default=None, description="Model load duration in nanoseconds"
    )
    prompt_eval_count: Optional[int] = Field(
        default=None, description="Number of tokens in prompt"
    )
    prompt_eval_duration: Optional[int] = Field(
        default=None, description="Prompt evaluation duration in nanoseconds"
    )
    eval_count: Optional[int] = Field(
        default=None, description="Number of tokens generated"
    )
    eval_duration: Optional[int] = Field(
        default=None, description="Generation duration in nanoseconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "llama2",
                "created_at": "2024-01-01T00:00:00Z",
                "response": "This is a generated response.",
                "done": True,
                "total_duration": 1000000000,
                "eval_count": 50,
            }
        }
    )
