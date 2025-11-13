"""
ONEX Qdrant Vector Indexing Module

Provides ONEX-compliant effect nodes for Qdrant vector operations with
high-performance semantic similarity search and pattern indexing.
"""

from .config import ONEXQdrantConfig, get_config, reset_config
from .service import ONEXQdrantService

__version__ = "1.0.0"
__all__ = [
    "ONEXQdrantService",
    "ONEXQdrantConfig",
    "get_config",
    "reset_config",
]
