"""
Input model for Vectorization Compute Node
"""

from pydantic import BaseModel, Field
from typing import Dict, Any
from uuid import UUID, uuid4


class ModelVectorizationComputeInput(BaseModel):
    """Input model for vectorization operations."""

    content: str = Field(..., description="Content to vectorize", min_length=1)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (language, file_path, etc.)"
    )
    model_name: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use"
    )
    batch_mode: bool = Field(
        default=False,
        description="Whether to process in batch mode"
    )
    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for request tracing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Sample code to vectorize",
                "metadata": {"language": "python", "file_path": "src/main.py"},
                "model_name": "text-embedding-3-small",
                "batch_mode": False
            }
        }
