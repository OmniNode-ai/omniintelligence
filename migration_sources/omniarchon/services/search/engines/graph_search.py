"""
Graph Search Engine for Relationship Discovery

Handles graph traversal queries and entity relationship analysis using Memgraph.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from models.search_models import (
    EntityRelationship,
    EntityType,
    RelationshipSearchRequest,
    RelationshipSearchResponse,
    SearchRequest,
    SearchResult,
)
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class GraphSearchEngine:
    """
    Graph search engine for relationship discovery and traversal.

    Provides graph-based search capabilities by:
    1. Traversing entity relationships in Memgraph
    2. Finding paths between entities
    3. Analyzing entity connections and patterns
    4. Ranking results by graph-based relevance
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://memgraph:7687",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize graph search engine.

        Args:
            memgraph_uri: Memgraph connection URI
            username: Authentication username (optional)
            password: Authentication password (optional)
        """
        self.memgraph_uri = memgraph_uri
        self.username = username
        self.password = password
        self.driver = None

    async def initialize(self):
        """Initialize async driver and verify connectivity"""
        try:
            auth = (
                (self.username, self.password)
                if self.username and self.password
                else None
            )
            self.driver = AsyncGraphDatabase.driver(
                self.memgraph_uri,
                auth=auth,
                max_connection_pool_size=10,
                connection_timeout=30.0,
            )

            await self.driver.verify_connectivity()
            logger.info(f"Graph search engine initialized: {self.memgraph_uri}")

        except Exception as e:
            logger.error(f"Failed to initialize graph search engine: {e}")
            raise

    async def close(self):
        """Close driver and cleanup connections"""
        if self.driver:
            await self.driver.close()
            logger.info("Graph search engine closed")

    async def health_check(self) -> bool:
        """Check Memgraph connectivity"""
        try:
            if not self.driver:
                return False

            async with self.driver.session() as session:
                result = await session.run("RETURN 'graph_search_health' as status")
                record = await result.single()
                return record and record["status"] == "graph_search_health"

        except Exception as e:
            logger.error(f"Graph search health check failed: {e}")
            return False

    async def structural_search(
        self, query: str, request: SearchRequest
    ) -> List[SearchResult]:
        """
        Perform structural/graph-based search.

        Args:
            query: Search query text
            request: Search request with parameters

        Returns:
            List of structurally relevant search results
        """
        start_time = time.time()

        try:
            # Extract search terms for graph matching
            search_terms = self._extract_search_terms(query)

            # Build graph query based on search terms and filters
            cypher_query, params = self._build_search_query(search_terms, request)

            # Execute graph query
            async with self.driver.session() as session:
                result = await session.run(cypher_query, params)
                records = await result.data()

            # Convert to SearchResult objects
            results = []
            for record in records:
                entity = record.get("entity", {})
                relationships = record.get("relationships", [])
                path = record.get("path", [])
                structural_score = record.get("score", 0.5)

                search_result = SearchResult(
                    entity_id=entity.get("entity_id", entity.get("id", "")),
                    entity_type=self._map_graph_label_to_entity_type(
                        entity.get("labels", ["Entity"])[0]
                    ),
                    title=entity.get("title", entity.get("name", "Untitled")),
                    content=entity.get("content") if request.include_content else None,
                    url=entity.get("url"),
                    relevance_score=structural_score,
                    structural_score=structural_score,
                    source_id=entity.get("source_id"),
                    project_id=entity.get("project_id"),
                    relationships=(
                        relationships if request.include_relationships else None
                    ),
                    path_to_query=path,
                )
                results.append(search_result)

            search_time = (time.time() - start_time) * 1000
            logger.info(
                f"Structural search completed in {search_time:.2f}ms, found {len(results)} results"
            )

            return results[: request.limit]

        except Exception as e:
            logger.error(f"Structural search failed: {e}")
            return []

    async def find_related_entities(
        self,
        entity_id: str,
        max_depth: int = 3,
        relationship_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find entities related to a given entity through graph traversal.

        Args:
            entity_id: Starting entity ID
            max_depth: Maximum traversal depth
            relationship_types: Filter by relationship types

        Returns:
            List of related entities with relationship info
        """
        try:
            # Build relationship traversal query
            relationship_filter = ""
            if relationship_types:
                types_str = "|".join(relationship_types)
                relationship_filter = f"[r:{types_str}*1..{max_depth}]"
            else:
                relationship_filter = f"[r*1..{max_depth}]"

            query = f"""
            MATCH (start {{entity_id: $entity_id}})
            MATCH (start)-{relationship_filter}-(related)
            WHERE start <> related
            RETURN DISTINCT related,
                   length((start)-{relationship_filter}-(related)) as distance,
                   [(start)-[rel*1..{max_depth}]-(related) | {{
                       type: type(rel[0]),
                       properties: properties(rel[0])
                   }}] as relationship_path
            ORDER BY distance ASC
            LIMIT 100
            """

            async with self.driver.session() as session:
                result = await session.run(query, {"entity_id": entity_id})
                records = await result.data()

            related_entities = []
            for record in records:
                related = dict(record["related"])
                distance = record["distance"]
                relationship_path = record["relationship_path"]

                related_entities.append(
                    {
                        "entity": related,
                        "distance": distance,
                        "relationship_path": relationship_path,
                    }
                )

            logger.debug(
                f"Found {len(related_entities)} related entities for {entity_id}"
            )
            return related_entities

        except Exception as e:
            logger.error(f"Failed to find related entities for {entity_id}: {e}")
            return []

    async def find_shortest_path(
        self, source_entity_id: str, target_entity_id: str, max_depth: int = 5
    ) -> Optional[List[str]]:
        """
        Find shortest path between two entities.

        Args:
            source_entity_id: Source entity ID
            target_entity_id: Target entity ID
            max_depth: Maximum path length to search

        Returns:
            List of entity IDs forming the shortest path, or None if no path found
        """
        try:
            query = (
                """
            MATCH (start {entity_id: $source_id}), (end {entity_id: $target_id})
            MATCH path = shortestPath((start)-[*1..%d]-(end))
            RETURN [node in nodes(path) | node.entity_id] as entity_path
            """
                % max_depth
            )

            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    {"source_id": source_entity_id, "target_id": target_entity_id},
                )
                record = await result.single()

                if record:
                    return record["entity_path"]
                return None

        except Exception as e:
            logger.error(
                f"Failed to find path between {source_entity_id} and {target_entity_id}: {e}"
            )
            return None

    async def relationship_search(
        self, request: RelationshipSearchRequest
    ) -> RelationshipSearchResponse:
        """
        Search for entity relationships based on criteria.

        Args:
            request: Relationship search request

        Returns:
            Relationship search response with found relationships
        """
        start_time = time.time()

        try:
            relationships = []
            paths = []

            # Build relationship query
            rel_filter = ""
            if request.relationship_types:
                types_str = "|".join(request.relationship_types)
                rel_filter = f"[r:{types_str}]"
            else:
                rel_filter = "[r]"

            # Find direct relationships
            query = f"""
            MATCH (source {{entity_id: $source_id}})-{rel_filter}-(target)
            RETURN source, target, r, type(r) as rel_type
            ORDER BY r.confidence_score DESC
            LIMIT 50
            """

            async with self.driver.session() as session:
                result = await session.run(query, {"source_id": request.entity_id})
                records = await result.data()

                for record in records:
                    rel = record["r"]
                    rel_type = record["rel_type"]
                    target = record["target"]

                    relationship = EntityRelationship(
                        source_entity_id=request.entity_id,
                        target_entity_id=target.get("entity_id", ""),
                        relationship_type=rel_type,
                        relationship_properties=dict(rel),
                        confidence_score=rel.get("confidence_score"),
                    )
                    relationships.append(relationship)

            # Find paths to specific targets if requested
            if request.target_entity_ids and request.include_paths:
                for target_id in request.target_entity_ids:
                    path = await self.find_shortest_path(
                        request.entity_id, target_id, request.max_depth
                    )
                    if path:
                        paths.append(path)

            search_time = (time.time() - start_time) * 1000

            return RelationshipSearchResponse(
                source_entity_id=request.entity_id,
                relationships=relationships,
                paths=paths if paths else None,
                search_time_ms=search_time,
            )

        except Exception as e:
            logger.error(f"Relationship search failed: {e}")
            return RelationshipSearchResponse(
                source_entity_id=request.entity_id,
                relationships=[],
                paths=None,
                search_time_ms=(time.time() - start_time) * 1000,
            )

    async def analyze_entity_centrality(
        self, entity_types: Optional[List[str]] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Analyze entity centrality to find important/connected entities.

        Args:
            entity_types: Filter by entity types
            limit: Maximum entities to return

        Returns:
            List of entities with centrality metrics
        """
        try:
            # Build entity type filter
            type_filter = ""
            if entity_types:
                labels = "|".join(entity_types)
                type_filter = f":{labels}"

            query = f"""
            MATCH (n{type_filter})
            OPTIONAL MATCH (n)-[r]-(connected)
            WITH n, count(DISTINCT connected) as degree
            WHERE degree > 0
            RETURN n, degree,
                   degree as centrality_score
            ORDER BY centrality_score DESC
            LIMIT $limit
            """

            async with self.driver.session() as session:
                result = await session.run(query, {"limit": limit})
                records = await result.data()

            central_entities = []
            for record in records:
                entity = dict(record["n"])
                degree = record["degree"]
                centrality = record["centrality_score"]

                central_entities.append(
                    {"entity": entity, "degree": degree, "centrality_score": centrality}
                )

            logger.info(f"Found {len(central_entities)} central entities")
            return central_entities

        except Exception as e:
            logger.error(f"Centrality analysis failed: {e}")
            return []

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query"""
        # Simple term extraction - could be enhanced with NLP
        terms = [
            term.strip().lower() for term in query.split() if len(term.strip()) > 2
        ]
        return terms

    def _build_search_query(
        self, search_terms: List[str], request: SearchRequest
    ) -> Tuple[str, Dict[str, Any]]:
        """Build Cypher query for structural search"""
        # Build label filter
        label_filter = ""
        if request.entity_types:
            labels = [
                self._map_entity_type_to_graph_label(et) for et in request.entity_types
            ]
            label_filter = ":" + "|".join(labels)

        # Build property search conditions
        search_conditions = []
        params = {"limit": request.limit}

        for i, term in enumerate(search_terms):
            term_key = f"term_{i}"
            params[term_key] = f".*{term}.*"
            search_conditions.append(
                f"(n.title =~ ${term_key} OR n.content =~ ${term_key} OR n.name =~ ${term_key})"
            )

        where_clause = ""
        if search_conditions:
            where_clause = f"WHERE {' OR '.join(search_conditions)}"

        query = f"""
        MATCH (n{label_filter})
        {where_clause}
        OPTIONAL MATCH (n)-[r]-(related)
        WITH n, collect(DISTINCT {{
            entity_id: related.entity_id,
            type: labels(related)[0],
            relationship_type: type(r)
        }}) as relationships
        RETURN n as entity,
               relationships,
               [] as path,
               0.7 as score
        ORDER BY score DESC
        LIMIT $limit
        """

        return query, params

    def _map_entity_type_to_graph_label(self, entity_type: EntityType) -> str:
        """Map EntityType to graph node label"""
        mapping = {
            EntityType.SOURCE: "Source",
            EntityType.PROJECT: "Project",
            EntityType.PAGE: "Page",
            EntityType.CODE_EXAMPLE: "CodeExample",
            EntityType.ENTITY: "Entity",
        }
        return mapping.get(entity_type, "Entity")

    def _map_graph_label_to_entity_type(self, label: str) -> EntityType:
        """Map graph node label to EntityType"""
        mapping = {
            "Source": EntityType.SOURCE,
            "Project": EntityType.PROJECT,
            "Page": EntityType.PAGE,
            "CodeExample": EntityType.CODE_EXAMPLE,
            "Entity": EntityType.ENTITY,
        }
        return mapping.get(label, EntityType.ENTITY)
