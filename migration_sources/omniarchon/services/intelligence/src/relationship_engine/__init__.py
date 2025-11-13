"""
Relationship Engine Module
===========================

Pattern relationship detection and graph building for intelligence system.

This module provides:
- RelationshipDetector: Detect relationships between patterns (USES, EXTENDS, COMPOSED_OF, SIMILAR_TO)
- GraphBuilder: Build knowledge graph from detected relationships
- SimilarityAnalyzer: Calculate semantic similarity between patterns

Relationship Types:
- USES: Pattern A imports/uses pattern B
- EXTENDS: Pattern A inherits from pattern B
- COMPOSED_OF: Pattern A calls functions from pattern B
- SIMILAR_TO: Patterns are semantically similar

Example:
    from relationship_engine import RelationshipDetector, GraphBuilder

    # Detect relationships
    detector = RelationshipDetector()
    relationships = detector.detect_all_relationships(pattern_a, pattern_b)

    # Build graph
    builder = GraphBuilder(db_connection)
    await builder.store_relationships(relationships)
    graph = await builder.build_graph(pattern_id, depth=2)
"""

from relationship_engine.graph_builder import GraphBuilder
from relationship_engine.relationship_detector import (
    RelationshipDetector,
    RelationshipType,
)
from relationship_engine.similarity_analyzer import SimilarityAnalyzer

__all__ = [
    "RelationshipDetector",
    "RelationshipType",
    "GraphBuilder",
    "SimilarityAnalyzer",
]
