"""
Search Services

Consolidated search and RAG functionality with strategy pattern support.
"""

# Main RAG service
from server.services.search.agentic_rag_strategy import AgenticRAGStrategy

# Strategy implementations
from server.services.search.base_search_strategy import BaseSearchStrategy
from server.services.search.hybrid_search_strategy import HybridSearchStrategy
from server.services.search.rag_service import RAGService
from server.services.search.reranking_strategy import RerankingStrategy

__all__ = [
    # Main service classes
    "RAGService",
    # Strategy classes
    "BaseSearchStrategy",
    "HybridSearchStrategy",
    "RerankingStrategy",
    "AgenticRAGStrategy",
]
