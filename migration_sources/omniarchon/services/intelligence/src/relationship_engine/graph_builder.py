"""
Graph Builder Module
====================

Builds and queries pattern knowledge graph using PostgreSQL and optionally Memgraph.

Provides:
- Store relationships in pattern_relationships table
- Query relationships by pattern ID
- Build dependency graphs with configurable depth
- Graph traversal algorithms
- Optional Memgraph integration for advanced graph queries
"""

import json
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

import asyncpg

try:
    from neo4j import GraphDatabase

    MEMGRAPH_AVAILABLE = True
except ImportError:
    MEMGRAPH_AVAILABLE = False


class GraphNode:
    """Represents a node in the pattern graph."""

    def __init__(
        self, pattern_id: str, pattern_name: str, metadata: Optional[Dict] = None
    ):
        self.pattern_id = pattern_id
        self.pattern_name = pattern_name
        self.metadata = metadata or {}


class GraphEdge:
    """Represents an edge in the pattern graph."""

    def __init__(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        strength: float,
        metadata: Optional[Dict] = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.strength = strength
        self.metadata = metadata or {}


class PatternGraph:
    """Represents a pattern knowledge graph."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []

    def add_node(self, node: GraphNode):
        """Add node to graph."""
        self.nodes[node.pattern_id] = node

    def add_edge(self, edge: GraphEdge):
        """Add edge to graph."""
        self.edges.append(edge)

    def to_dict(self) -> Dict:
        """Convert graph to dictionary format for JSON serialization."""
        return {
            "nodes": [
                {
                    "id": node.pattern_id,
                    "name": node.pattern_name,
                    "metadata": node.metadata,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.relationship_type,
                    "strength": edge.strength,
                    "metadata": edge.metadata,
                }
                for edge in self.edges
            ],
        }


class GraphBuilder:
    """
    Builds and queries pattern knowledge graph.

    Uses PostgreSQL pattern_relationships table as primary storage.
    Optionally uses Memgraph for advanced graph queries.
    """

    def __init__(
        self,
        db_host: str = "192.168.86.200",
        db_port: int = 5436,
        db_name: str = "omninode_bridge",
        db_user: str = "postgres",
        db_password: str = "omninode-bridge-postgres-dev-2024",
        use_memgraph: bool = False,
        memgraph_uri: str = "bolt://localhost:7687",
    ):
        """
        Initialize graph builder.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            use_memgraph: Whether to use Memgraph for graph queries
            memgraph_uri: Memgraph connection URI
        """
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password

        self.use_memgraph = use_memgraph and MEMGRAPH_AVAILABLE
        self.memgraph_uri = memgraph_uri
        self.memgraph_driver = None

        if self.use_memgraph:
            try:
                self.memgraph_driver = GraphDatabase.driver(memgraph_uri)
            except Exception as e:
                print(f"Warning: Failed to connect to Memgraph: {e}")
                self.use_memgraph = False

    async def _get_connection(self) -> asyncpg.Connection:
        """Get database connection."""
        return await asyncpg.connect(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )

    async def store_relationship(
        self,
        source_pattern_id: str,
        target_pattern_id: str,
        relationship_type: str,
        strength: float,
        description: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Store a single relationship in the database.

        Args:
            source_pattern_id: Source pattern UUID
            target_pattern_id: Target pattern UUID
            relationship_type: Type of relationship (uses, extends, composed_of, similar_to)
            strength: Relationship strength (0.0-1.0)
            description: Optional description
            context: Optional context metadata

        Returns:
            Relationship ID (UUID)

        Raises:
            ValueError: If strength not in range [0, 1]
            asyncpg.PostgresError: If database operation fails
        """
        if not 0.0 <= strength <= 1.0:
            raise ValueError(f"Strength must be between 0 and 1, got {strength}")

        conn = await self._get_connection()
        try:
            # Insert relationship (ON CONFLICT UPDATE)
            query = """
                INSERT INTO pattern_relationships (
                    source_pattern_id,
                    target_pattern_id,
                    relationship_type,
                    strength,
                    description,
                    context
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (source_pattern_id, target_pattern_id, relationship_type)
                DO UPDATE SET
                    strength = EXCLUDED.strength,
                    description = EXCLUDED.description,
                    context = EXCLUDED.context,
                    updated_at = NOW()
                RETURNING id
            """

            context_json = json.dumps(context) if context else None

            relationship_id = await conn.fetchval(
                query,
                UUID(source_pattern_id),
                UUID(target_pattern_id),
                relationship_type,
                strength,
                description,
                context_json,
            )

            return str(relationship_id)

        finally:
            await conn.close()

    async def store_relationships_batch(self, relationships: List[Dict]) -> List[str]:
        """
        Store multiple relationships in a batch.

        Args:
            relationships: List of relationship dictionaries with keys:
                - source_pattern_id
                - target_pattern_id
                - relationship_type
                - strength
                - description (optional)
                - context (optional)

        Returns:
            List of relationship IDs

        Raises:
            ValueError: If any relationship is invalid
        """
        conn = await self._get_connection()
        try:
            relationship_ids = []

            async with conn.transaction():
                for rel in relationships:
                    rel_id = await self.store_relationship(
                        source_pattern_id=rel["source_pattern_id"],
                        target_pattern_id=rel["target_pattern_id"],
                        relationship_type=rel["relationship_type"],
                        strength=rel["strength"],
                        description=rel.get("description"),
                        context=rel.get("context"),
                    )
                    relationship_ids.append(rel_id)

            return relationship_ids

        finally:
            await conn.close()

    async def get_pattern_relationships(self, pattern_id: str) -> Dict[str, List[Dict]]:
        """
        Get all relationships for a pattern.

        Returns relationships grouped by type:
        - uses: Patterns this pattern imports/uses
        - used_by: Patterns that import/use this pattern
        - extends: Patterns this pattern extends
        - extended_by: Patterns that extend this pattern
        - similar_to: Semantically similar patterns
        - composed_of: Patterns this is composed of

        Args:
            pattern_id: Pattern UUID

        Returns:
            Dictionary with relationship groups
        """
        conn = await self._get_connection()
        try:
            # Query outgoing relationships
            outgoing_query = """
                SELECT
                    pr.target_pattern_id,
                    pt.pattern_name,
                    pr.relationship_type,
                    pr.strength,
                    pr.description,
                    pr.context
                FROM pattern_relationships pr
                JOIN pattern_templates pt ON pr.target_pattern_id = pt.id
                WHERE pr.source_pattern_id = $1
                ORDER BY pr.strength DESC
            """

            outgoing = await conn.fetch(outgoing_query, UUID(pattern_id))

            # Query incoming relationships
            incoming_query = """
                SELECT
                    pr.source_pattern_id,
                    pt.pattern_name,
                    pr.relationship_type,
                    pr.strength,
                    pr.description,
                    pr.context
                FROM pattern_relationships pr
                JOIN pattern_templates pt ON pr.source_pattern_id = pt.id
                WHERE pr.target_pattern_id = $1
                ORDER BY pr.strength DESC
            """

            incoming = await conn.fetch(incoming_query, UUID(pattern_id))

            # Group by relationship type
            result = {
                "uses": [],
                "used_by": [],
                "extends": [],
                "extended_by": [],
                "similar_to": [],
                "composed_of": [],
            }

            # Process outgoing relationships
            for row in outgoing:
                rel_type = row["relationship_type"]
                rel_data = {
                    "pattern_id": str(row["target_pattern_id"]),
                    "pattern_name": row["pattern_name"],
                    "strength": float(row["strength"]),
                    "description": row["description"],
                    "context": row["context"],
                }

                if rel_type == "uses":
                    result["uses"].append(rel_data)
                elif rel_type == "extends":
                    result["extends"].append(rel_data)
                elif rel_type == "similar_to":
                    result["similar_to"].append(rel_data)
                elif rel_type == "composed_of":
                    result["composed_of"].append(rel_data)

            # Process incoming relationships
            for row in incoming:
                rel_type = row["relationship_type"]
                rel_data = {
                    "pattern_id": str(row["source_pattern_id"]),
                    "pattern_name": row["pattern_name"],
                    "strength": float(row["strength"]),
                    "description": row["description"],
                    "context": row["context"],
                }

                if rel_type == "uses":
                    result["used_by"].append(rel_data)
                elif rel_type == "extends":
                    result["extended_by"].append(rel_data)

            return result

        finally:
            await conn.close()

    async def build_graph(
        self,
        root_pattern_id: str,
        depth: int = 2,
        relationship_types: Optional[List[str]] = None,
    ) -> PatternGraph:
        """
        Build pattern graph starting from root pattern.

        Args:
            root_pattern_id: Starting pattern UUID
            depth: Maximum graph depth (default: 2)
            relationship_types: Filter by relationship types (default: all)

        Returns:
            PatternGraph object

        Raises:
            ValueError: If depth < 1
        """
        if depth < 1:
            raise ValueError("Depth must be at least 1")

        graph = PatternGraph()
        visited: Set[str] = set()
        to_visit: List[Tuple[str, int]] = [(root_pattern_id, 0)]

        conn = await self._get_connection()
        try:
            while to_visit:
                current_id, current_depth = to_visit.pop(0)

                if current_id in visited or current_depth > depth:
                    continue

                visited.add(current_id)

                # Get pattern info
                pattern_query = """
                    SELECT pattern_name, pattern_type, language
                    FROM pattern_templates
                    WHERE id = $1
                """
                pattern = await conn.fetchrow(pattern_query, UUID(current_id))

                if pattern:
                    node = GraphNode(
                        pattern_id=current_id,
                        pattern_name=pattern["pattern_name"],
                        metadata={
                            "pattern_type": pattern["pattern_type"],
                            "language": pattern["language"],
                        },
                    )
                    graph.add_node(node)

                # Get relationships
                rel_query = """
                    SELECT
                        target_pattern_id,
                        relationship_type,
                        strength,
                        context
                    FROM pattern_relationships
                    WHERE source_pattern_id = $1
                """

                if relationship_types:
                    rel_query += " AND relationship_type = ANY($2::text[])"
                    relationships = await conn.fetch(
                        rel_query, UUID(current_id), relationship_types
                    )
                else:
                    relationships = await conn.fetch(rel_query, UUID(current_id))

                for rel in relationships:
                    target_id = str(rel["target_pattern_id"])

                    edge = GraphEdge(
                        source_id=current_id,
                        target_id=target_id,
                        relationship_type=rel["relationship_type"],
                        strength=float(rel["strength"]),
                        metadata=rel["context"],
                    )
                    graph.add_edge(edge)

                    # Add target to visit queue if not at max depth
                    if current_depth < depth:
                        to_visit.append((target_id, current_depth + 1))

            return graph

        finally:
            await conn.close()

    async def find_dependency_chain(
        self, source_pattern_id: str, target_pattern_id: str
    ) -> Optional[List[str]]:
        """
        Find dependency chain from source to target pattern.

        Uses breadth-first search to find shortest path.

        Args:
            source_pattern_id: Starting pattern UUID
            target_pattern_id: Target pattern UUID

        Returns:
            List of pattern IDs forming the chain, or None if no path exists
        """
        conn = await self._get_connection()
        try:
            # BFS to find shortest path
            queue: List[List[str]] = [[source_pattern_id]]
            visited: Set[str] = {source_pattern_id}

            while queue:
                path = queue.pop(0)
                current_id = path[-1]

                if current_id == target_pattern_id:
                    return path

                # Get neighbors
                query = """
                    SELECT target_pattern_id
                    FROM pattern_relationships
                    WHERE source_pattern_id = $1
                """
                neighbors = await conn.fetch(query, UUID(current_id))

                for row in neighbors:
                    neighbor_id = str(row["target_pattern_id"])
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(path + [neighbor_id])

            return None

        finally:
            await conn.close()

    async def detect_circular_dependencies(self, pattern_id: str) -> List[List[str]]:
        """
        Detect circular dependencies involving a pattern.

        Args:
            pattern_id: Pattern UUID to check

        Returns:
            List of circular dependency chains
        """
        # Use DFS to detect cycles
        cycles = []
        visited = set()
        rec_stack = []

        async def dfs(current_id: str):
            visited.add(current_id)
            rec_stack.append(current_id)

            conn = await self._get_connection()
            try:
                query = """
                    SELECT target_pattern_id
                    FROM pattern_relationships
                    WHERE source_pattern_id = $1
                """
                neighbors = await conn.fetch(query, UUID(current_id))

                for row in neighbors:
                    neighbor_id = str(row["target_pattern_id"])

                    if neighbor_id not in visited:
                        await dfs(neighbor_id)
                    elif neighbor_id in rec_stack:
                        # Found cycle
                        cycle_start = rec_stack.index(neighbor_id)
                        cycle = rec_stack[cycle_start:] + [neighbor_id]
                        cycles.append(cycle)

            finally:
                await conn.close()

            rec_stack.pop()

        await dfs(pattern_id)

        return cycles

    def close(self):
        """Close Memgraph connection if active."""
        if self.memgraph_driver:
            self.memgraph_driver.close()


# Example usage
if __name__ == "__main__":
    import asyncio

    async def main():
        builder = GraphBuilder()

        # Example: Build graph for a pattern
        pattern_id = "12345678-1234-1234-1234-123456789012"

        try:
            # Get relationships
            relationships = await builder.get_pattern_relationships(pattern_id)
            print(f"Relationships for {pattern_id}:")
            for rel_type, rels in relationships.items():
                print(f"  {rel_type}: {len(rels)}")

            # Build graph
            graph = await builder.build_graph(pattern_id, depth=2)
            print(f"\nGraph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())
