"""
External API Response Models

Pydantic models for validating responses from external services (Ollama, Qdrant, Memgraph, etc.).
All external API responses MUST be validated using these models to ensure data integrity.

Performance Target: <5ms validation overhead per response
"""

from .memgraph import (
    MemgraphNode,
    MemgraphQueryResponse,
    MemgraphRecord,
    MemgraphRelationship,
)
from .ollama import OllamaEmbeddingResponse, OllamaGenerateResponse
from .qdrant import (
    QdrantCollectionInfo,
    QdrantDeleteResponse,
    QdrantSearchHit,
    QdrantSearchResponse,
    QdrantUpsertResponse,
)
from .rag_search import (
    RAGSearchMetadata,
    RAGSearchResponse,
    RAGSearchResult,
)

__all__ = [
    # Ollama
    "OllamaEmbeddingResponse",
    "OllamaGenerateResponse",
    # Qdrant
    "QdrantSearchResponse",
    "QdrantSearchHit",
    "QdrantUpsertResponse",
    "QdrantCollectionInfo",
    "QdrantDeleteResponse",
    # Memgraph
    "MemgraphQueryResponse",
    "MemgraphRecord",
    "MemgraphNode",
    "MemgraphRelationship",
    # RAG Search
    "RAGSearchResponse",
    "RAGSearchResult",
    "RAGSearchMetadata",
]
