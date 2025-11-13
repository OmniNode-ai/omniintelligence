"""
Pattern Relationships Service

Business logic for pattern relationship management.
"""

import logging
import os
from typing import Dict, List, Optional

from relationship_engine import GraphBuilder, RelationshipDetector
from src.api.pattern_relationships.models import (
    CircularDependency,
    CreateRelationshipRequest,
    GraphEdge,
    GraphNode,
    RelationshipInfo,
)

logger = logging.getLogger(__name__)


class PatternRelationshipsService:
    """Service for managing pattern relationships."""

    def __init__(self):
        """Initialize service with GraphBuilder."""
        # Get database configuration from environment
        db_config = {
            "db_host": os.getenv("POSTGRES_HOST", "192.168.86.200"),
            "db_port": int(os.getenv("POSTGRES_PORT", "5436")),
            "db_name": os.getenv("POSTGRES_DATABASE", "omninode_bridge"),
            "db_user": os.getenv("POSTGRES_USER", "postgres"),
            "db_password": os.getenv(
                "POSTGRES_PASSWORD", "omninode-bridge-postgres-dev-2024"
            ),
        }

        self.graph_builder = GraphBuilder(**db_config)
        self.relationship_detector = RelationshipDetector()

    async def get_pattern_relationships(self, pattern_id: str) -> Dict:
        """
        Get all relationships for a pattern.

        Args:
            pattern_id: Pattern UUID

        Returns:
            Dictionary with relationship groups
        """
        try:
            relationships = await self.graph_builder.get_pattern_relationships(
                pattern_id
            )

            # Convert to response format
            result = {
                "pattern_id": pattern_id,
                "uses": [RelationshipInfo(**rel) for rel in relationships["uses"]],
                "used_by": [
                    RelationshipInfo(**rel) for rel in relationships["used_by"]
                ],
                "extends": [
                    RelationshipInfo(**rel) for rel in relationships["extends"]
                ],
                "extended_by": [
                    RelationshipInfo(**rel) for rel in relationships["extended_by"]
                ],
                "similar_to": [
                    RelationshipInfo(**rel) for rel in relationships["similar_to"]
                ],
                "composed_of": [
                    RelationshipInfo(**rel) for rel in relationships["composed_of"]
                ],
            }

            logger.info(
                f"Retrieved relationships for pattern {pattern_id} | "
                f"uses={len(result['uses'])} used_by={len(result['used_by'])} "
                f"extends={len(result['extends'])} extended_by={len(result['extended_by'])} "
                f"similar_to={len(result['similar_to'])} composed_of={len(result['composed_of'])}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get relationships for pattern {pattern_id}: {e}")
            raise

    async def build_pattern_graph(
        self,
        root_pattern_id: str,
        depth: int = 2,
        relationship_types: Optional[List[str]] = None,
    ) -> Dict:
        """
        Build pattern graph starting from root pattern.

        Args:
            root_pattern_id: Starting pattern UUID
            depth: Maximum graph depth
            relationship_types: Filter by relationship types

        Returns:
            Dictionary with graph data
        """
        try:
            graph = await self.graph_builder.build_graph(
                root_pattern_id=root_pattern_id,
                depth=depth,
                relationship_types=relationship_types,
            )

            # Convert to response format
            result = {
                "root_pattern_id": root_pattern_id,
                "depth": depth,
                "nodes": [
                    GraphNode(
                        id=node.pattern_id,
                        name=node.pattern_name,
                        metadata=node.metadata,
                    )
                    for node in graph.nodes.values()
                ],
                "edges": [
                    GraphEdge(
                        source=edge.source_id,
                        target=edge.target_id,
                        type=edge.relationship_type,
                        strength=edge.strength,
                        metadata=edge.metadata,
                    )
                    for edge in graph.edges
                ],
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
            }

            logger.info(
                f"Built graph for pattern {root_pattern_id} | "
                f"depth={depth} nodes={result['node_count']} edges={result['edge_count']}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to build graph for pattern {root_pattern_id}: {e}")
            raise

    async def find_dependency_chain(
        self, source_pattern_id: str, target_pattern_id: str
    ) -> Dict:
        """
        Find dependency chain between two patterns.

        Args:
            source_pattern_id: Source pattern UUID
            target_pattern_id: Target pattern UUID

        Returns:
            Dictionary with chain information
        """
        try:
            chain = await self.graph_builder.find_dependency_chain(
                source_pattern_id, target_pattern_id
            )

            result = {
                "source_pattern_id": source_pattern_id,
                "target_pattern_id": target_pattern_id,
                "chain": chain,
                "chain_length": len(chain) if chain else None,
            }

            if chain:
                logger.info(
                    f"Found dependency chain from {source_pattern_id} to {target_pattern_id} | "
                    f"length={len(chain)}"
                )
            else:
                logger.info(
                    f"No dependency chain found from {source_pattern_id} to {target_pattern_id}"
                )

            return result

        except Exception as e:
            logger.error(
                f"Failed to find dependency chain from {source_pattern_id} to {target_pattern_id}: {e}"
            )
            raise

    async def detect_circular_dependencies(self, pattern_id: str) -> Dict:
        """
        Detect circular dependencies for a pattern.

        Args:
            pattern_id: Pattern UUID

        Returns:
            Dictionary with circular dependency information
        """
        try:
            cycles = await self.graph_builder.detect_circular_dependencies(pattern_id)

            result = {
                "pattern_id": pattern_id,
                "has_circular_dependencies": len(cycles) > 0,
                "circular_dependencies": [
                    CircularDependency(cycle=cycle, cycle_length=len(cycle))
                    for cycle in cycles
                ],
                "cycle_count": len(cycles),
            }

            if cycles:
                logger.warning(
                    f"Found {len(cycles)} circular dependencies for pattern {pattern_id}"
                )
            else:
                logger.info(f"No circular dependencies found for pattern {pattern_id}")

            return result

        except Exception as e:
            logger.error(
                f"Failed to detect circular dependencies for pattern {pattern_id}: {e}"
            )
            raise

    async def create_relationship(self, request: CreateRelationshipRequest) -> Dict:
        """
        Create a relationship between two patterns.

        Args:
            request: Relationship creation request

        Returns:
            Dictionary with created relationship info
        """
        try:
            relationship_id = await self.graph_builder.store_relationship(
                source_pattern_id=request.source_pattern_id,
                target_pattern_id=request.target_pattern_id,
                relationship_type=request.relationship_type,
                strength=request.strength,
                description=request.description,
                context=request.context,
            )

            result = {
                "relationship_id": relationship_id,
                "source_pattern_id": request.source_pattern_id,
                "target_pattern_id": request.target_pattern_id,
                "relationship_type": request.relationship_type,
                "strength": request.strength,
            }

            logger.info(
                f"Created relationship {relationship_id} | "
                f"{request.relationship_type}: {request.source_pattern_id} -> {request.target_pattern_id} "
                f"(strength={request.strength})"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise

    async def detect_relationships_for_pattern(
        self,
        pattern_id: str,
        source_code: str,
        pattern_name: str,
        detect_types: Optional[List[str]] = None,
    ) -> Dict:
        """
        Automatically detect relationships from source code.

        Args:
            pattern_id: Pattern UUID
            source_code: Pattern source code
            pattern_name: Pattern name
            detect_types: Relationship types to detect (default: all)

        Returns:
            Dictionary with detected relationships
        """
        try:
            # Detect relationships using RelationshipDetector
            relationships = self.relationship_detector.detect_all_relationships(
                source_code=source_code,
                source_pattern_name=pattern_name,
                source_pattern_id=pattern_id,
            )

            # Filter by detect_types if specified
            if detect_types:
                relationships = [
                    rel
                    for rel in relationships
                    if rel.relationship_type.value in detect_types
                ]

            # Convert to CreateRelationshipRequest format
            detected = []
            for rel in relationships:
                # Note: We need to resolve target_pattern_name to target_pattern_id
                # For now, we'll return the name and let the caller resolve it
                detected.append(
                    CreateRelationshipRequest(
                        source_pattern_id=pattern_id,
                        target_pattern_id=rel.target_pattern_name,  # Will need resolution
                        relationship_type=rel.relationship_type.value,
                        strength=rel.confidence,
                        description=f"Auto-detected {rel.relationship_type.value} relationship",
                        context=rel.context,
                    )
                )

            result = {
                "pattern_id": pattern_id,
                "detected_relationships": detected,
                "detection_count": len(detected),
            }

            logger.info(
                f"Detected {len(detected)} relationships for pattern {pattern_id}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Failed to detect relationships for pattern {pattern_id}: {e}"
            )
            raise
