"""
Knowledge Graph Service

Handles querying Memgraph for graph structure and pattern relationships.
Formats data for dashboard visualization (D3.js, Cytoscape, etc.).

ONEX Pattern: Orchestrator (coordinates queries across graph database)
Performance Target: <2s for 1000 nodes
"""

import logging
import os
from typing import Any, Dict, List, Optional

from constants.memgraph_labels import MemgraphLabels, MemgraphRelationships
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """
    Service for querying knowledge graph data from Memgraph.

    Responsibilities:
    - Connect to Memgraph via Neo4j driver
    - Execute Cypher queries for nodes and edges
    - Format results for visualization libraries
    - Apply filters (node type, quality, project)
    - Handle connection errors gracefully

    ONEX Compliance:
    - Orchestrator pattern: Coordinates multiple queries
    - Observable: Logs all operations and metrics
    - Resilient: Graceful degradation on connection errors
    """

    def __init__(
        self,
        memgraph_uri: Optional[str] = None,
        memgraph_user: Optional[str] = None,
        memgraph_password: Optional[str] = None,
    ):
        """
        Initialize KnowledgeGraphService.

        Args:
            memgraph_uri: Memgraph connection URI (default: from env MEMGRAPH_URI)
            memgraph_user: Username (default: from env MEMGRAPH_USER or empty)
            memgraph_password: Password (default: from env MEMGRAPH_PASSWORD or empty)
        """
        self.memgraph_uri = memgraph_uri or os.getenv(
            "MEMGRAPH_URI", "bolt://localhost:7687"
        )
        self.memgraph_user = memgraph_user or os.getenv("MEMGRAPH_USER", "")
        self.memgraph_password = memgraph_password or os.getenv("MEMGRAPH_PASSWORD", "")

        # Initialize driver (lazy connection)
        self._driver = None

    async def _get_driver(self):
        """Get or create Neo4j driver for Memgraph."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.memgraph_uri,
                auth=(
                    (self.memgraph_user, self.memgraph_password)
                    if self.memgraph_user
                    else None
                ),
            )
        return self._driver

    async def close(self):
        """Close Memgraph connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def get_graph_data(
        self,
        limit: int = 100,
        node_types: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query Memgraph for graph structure (nodes and edges).

        Args:
            limit: Maximum number of nodes to return
            node_types: Filter by node types (e.g., ['File', 'Concept'])
            min_quality_score: Minimum quality score for File nodes
            project_name: Filter by project name

        Returns:
            Dictionary with 'nodes' and 'edges' lists

        Raises:
            ConnectionError: If Memgraph is unavailable
            ValueError: If query parameters are invalid

        Example:
            >>> service = KnowledgeGraphService()
            >>> graph = await service.get_graph_data(limit=50, node_types=['File'])
            >>> print(f"Found {len(graph['nodes'])} nodes")
        """
        try:
            driver = await self._get_driver()

            # Build Cypher query dynamically based on filters
            query, parameters = self._build_graph_query(
                limit=limit,
                node_types=node_types,
                min_quality_score=min_quality_score,
                project_name=project_name,
            )

            logger.info(
                f"Executing Memgraph query: limit={limit}, "
                f"node_types={node_types}, min_quality_score={min_quality_score}"
            )

            # Execute query
            async with driver.session() as session:
                result = await session.run(query, parameters)
                records = await result.data()

            # Format results
            nodes, edges = self._format_graph_data(records)

            logger.info(
                f"Graph query completed: {len(nodes)} nodes, {len(edges)} edges"
            )

            return {"nodes": nodes, "edges": edges}

        except ServiceUnavailable as e:
            logger.error(f"Memgraph service unavailable: {str(e)}")
            raise ConnectionError(f"Cannot connect to Memgraph: {str(e)}")

        except Exception as e:
            logger.error(f"Graph query failed: {str(e)}", exc_info=True)
            raise

    def _build_graph_query(
        self,
        limit: int,
        node_types: Optional[List[str]],
        min_quality_score: float,
        project_name: Optional[str],
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build Cypher query with filters.

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        # Base query: Match all nodes and their relationships
        query_parts = []
        where_conditions = []
        parameters = {"limit": limit, "min_quality_score": min_quality_score}

        # Build base MATCH clause
        if node_types:
            labels = "|".join(node_types)
            query_parts.append(f"MATCH (n:{labels})")
        else:
            query_parts.append("MATCH (n)")

        # Add project filter using OPTIONAL MATCH
        # Memgraph requires bound variables for pattern matching in WHERE
        # So we use OPTIONAL MATCH + path variable to check containment
        if project_name:
            parameters["project_name"] = project_name
            query_parts.append(
                f"OPTIONAL MATCH project_path = (:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:{MemgraphRelationships.CONTAINS}*]->(n)"
            )
            # Include node if: (1) it's not a File, or (2) project_path exists
            where_conditions.append(
                f"(NOT n:{MemgraphLabels.FILE} OR project_path IS NOT NULL)"
            )

        # Add quality filter for File nodes
        if min_quality_score > 0:
            where_conditions.append(
                f"(NOT n:{MemgraphLabels.FILE} OR n.quality_score >= $min_quality_score)"
            )

        # Add WHERE clause if any conditions
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))

        # Limit nodes first
        query_parts.append("WITH n LIMIT $limit")

        # Get relationships for these nodes
        query_parts.append("OPTIONAL MATCH (n)-[r]->(m)")

        # Return nodes and relationships
        query_parts.append(
            """
            RETURN
                collect(DISTINCT {
                    id: id(n),
                    labels: labels(n),
                    properties: properties(n)
                }) as nodes,
                collect(DISTINCT {
                    id: id(r),
                    type: type(r),
                    start_node: id(startNode(r)),
                    end_node: id(endNode(r)),
                    properties: properties(r)
                }) as relationships
            """
        )

        query = "\n".join(query_parts)

        logger.debug(f"Built Cypher query: {query}")
        logger.debug(f"Query parameters: {parameters}")

        return query, parameters

    def _format_graph_data(self, records: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """
        Format Memgraph query results for visualization.

        Args:
            records: Raw Memgraph query results

        Returns:
            Tuple of (nodes_list, edges_list)
        """
        nodes = []
        edges = []

        if not records:
            return nodes, edges

        # Extract first record (aggregated data)
        record = records[0]

        # Process nodes
        for node_data in record.get("nodes", []):
            if node_data and node_data.get("id") is not None:
                # Determine primary label (first label)
                labels = node_data.get("labels", [])
                primary_label = labels[0] if labels else "Unknown"

                # Get display label from properties
                props = node_data.get("properties", {})
                display_label = (
                    props.get("name")
                    or props.get("path")
                    or props.get("absolute_path")
                    or f"{primary_label}_{node_data['id']}"
                )

                nodes.append(
                    {
                        "id": str(node_data["id"]),
                        "label": display_label,
                        "type": primary_label.lower(),
                        "properties": props,
                    }
                )

        # Process relationships
        for rel_data in record.get("relationships", []):
            if rel_data and rel_data.get("id") is not None:
                edges.append(
                    {
                        "source": str(rel_data["start_node"]),
                        "target": str(rel_data["end_node"]),
                        "relationship": rel_data.get("type", "RELATED_TO"),
                        "properties": rel_data.get("properties", {}),
                    }
                )

        return nodes, edges

    async def check_health(self) -> Dict[str, Any]:
        """
        Check Memgraph connectivity and service health.

        Returns:
            Dictionary with health status and details
        """
        try:
            driver = await self._get_driver()

            # Simple connectivity test
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.single()

            return {
                "status": "healthy",
                "memgraph_uri": self.memgraph_uri,
                "connection": "established",
            }

        except ServiceUnavailable:
            return {
                "status": "unhealthy",
                "memgraph_uri": self.memgraph_uri,
                "connection": "failed",
                "error": "Memgraph service unavailable",
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "memgraph_uri": self.memgraph_uri,
                "connection": "error",
                "error": str(e),
            }

    def __del__(self):
        """Cleanup on destruction."""
        if self._driver:
            # Note: Can't await in __del__, connection will be closed by Python
            logger.debug("KnowledgeGraphService driver cleanup on destruction")
