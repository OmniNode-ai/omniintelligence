"""
Models for Haystack Adapter Effect Node
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


class ModelHaystackAdapterInput(BaseModel):
    """Input model for Haystack adapter operations."""

    operation: str = Field(..., description="Operation type")
    query: Optional[str] = Field(None, description="Query text for RAG retrieval")
    document_content: Optional[str] = Field(None, description="Document content to index")
    document_id: Optional[str] = Field(None, description="Document ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document/query metadata")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters for search")
    top_k: int = Field(10, description="Number of documents to retrieve")
    generation_params: Optional[Dict[str, Any]] = Field(None, description="Generation parameters")
    correlation_id: str = Field(..., description="Correlation ID for tracing")


class ModelHaystackAdapterOutput(BaseModel):
    """Output model for Haystack adapter operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    operation: str = Field(..., description="Operation that was executed")
    query: Optional[str] = Field(None, description="Original query")
    answer: Optional[str] = Field(None, description="Generated answer")
    retrieved_documents: Optional[List[Dict[str, Any]]] = Field(
        None, description="Retrieved documents with content and metadata"
    )
    document_id: Optional[str] = Field(None, description="Document ID")
    indexed: Optional[bool] = Field(None, description="Whether document was indexed")
    deleted: Optional[bool] = Field(None, description="Whether document was deleted")
    latency_ms: float = Field(..., description="Total operation latency in milliseconds")
    retrieval_latency_ms: Optional[float] = Field(None, description="Retrieval step latency")
    generation_latency_ms: Optional[float] = Field(None, description="Generation step latency")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ModelHaystackAdapterConfig(BaseModel):
    """Configuration for Haystack adapter."""

    # Document store configuration
    qdrant_url: str = Field(..., description="Qdrant server URL")
    collection_name: str = Field("haystack_documents", description="Qdrant collection name")
    embedding_model: str = Field("text-embedding-3-small", description="Embedding model")

    # Generation configuration
    llm_model: str = Field("gpt-4", description="LLM model for answer generation")
    llm_temperature: float = Field(0.7, description="LLM temperature")
    llm_max_tokens: int = Field(2000, description="Maximum tokens for generation")

    # Retrieval configuration
    default_top_k: int = Field(10, description="Default number of documents to retrieve")
    similarity_threshold: float = Field(0.7, description="Minimum similarity score")

    # Feature flags
    enable_hybrid_search: bool = Field(True, description="Enable hybrid search")
    enable_caching: bool = Field(True, description="Enable result caching")
    cache_ttl_seconds: int = Field(3600, description="Cache TTL in seconds")


__all__ = [
    "ModelHaystackAdapterInput",
    "ModelHaystackAdapterOutput",
    "ModelHaystackAdapterConfig",
]
