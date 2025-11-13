"""
Knowledge Graph API module.

Provides endpoints for querying and visualizing the knowledge graph
built from pattern relationships in Qdrant and Memgraph.
"""

__all__ = ["router"]

from src.api.knowledge_graph.routes import router
