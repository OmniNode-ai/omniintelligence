"""
Embedding Services

Handles all embedding-related operations.
"""

from server.services.embeddings.contextual_embedding_service import (
    generate_contextual_embedding,
    generate_contextual_embeddings_batch,
    process_chunk_with_context,
)
from server.services.embeddings.embedding_service import (
    create_embedding,
    create_embeddings_batch,
    get_openai_client,
)

__all__ = [
    # Embedding functions
    "create_embedding",
    "create_embeddings_batch",
    "get_openai_client",
    # Contextual embedding functions
    "generate_contextual_embedding",
    "generate_contextual_embeddings_batch",
    "process_chunk_with_context",
]
