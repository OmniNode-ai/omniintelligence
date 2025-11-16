"""
Utility functions for vectorization operations
"""

import hashlib
from typing import List, Dict, Any


def generate_cache_key(content: str, model_name: str, metadata: Dict[str, Any]) -> str:
    """
    Generate deterministic cache key for vectorization.

    Args:
        content: Content to vectorize
        model_name: Embedding model name
        metadata: Additional metadata

    Returns:
        Hex digest cache key
    """
    # Deterministic key generation
    key_data = f"{content}:{model_name}:{sorted(metadata.items())}"
    return hashlib.sha256(key_data.encode()).hexdigest()


def validate_embeddings(embeddings: List[float], expected_dim: int = 1536) -> bool:
    """
    Validate embedding dimensions and values.

    Args:
        embeddings: Generated embeddings
        expected_dim: Expected embedding dimension

    Returns:
        True if valid, False otherwise
    """
    if not embeddings:
        return False

    if len(embeddings) != expected_dim:
        return False

    # Check for NaN or infinite values
    return all(isinstance(val, (int, float)) and -1e10 < val < 1e10 for val in embeddings)


def truncate_content(content: str, max_length: int) -> str:
    """
    Truncate content to maximum length if needed.

    Args:
        content: Content to truncate
        max_length: Maximum allowed length

    Returns:
        Truncated content
    """
    if len(content) <= max_length:
        return content

    return content[:max_length]


def batch_content(contents: List[str], batch_size: int) -> List[List[str]]:
    """
    Split contents into batches.

    Args:
        contents: List of content strings
        batch_size: Maximum batch size

    Returns:
        List of batches
    """
    batches = []
    for i in range(0, len(contents), batch_size):
        batches.append(contents[i:i + batch_size])
    return batches
