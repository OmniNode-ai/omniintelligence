"""
Memgraph Connector for Bridge Service

Handles connections and operations with Memgraph knowledge graph.
Focused on bridge-specific graph operations and entity management.
"""

import logging
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class MemgraphConnector:
    """
    Memgraph connector for bridge service.

    Provides graph database operations specifically for bridge
    synchronization and entity relationship management.
    """

    def __init__(
        self,
        uri: str = "bolt://memgraph:7687",
        username: str = None,
        password: str = None,
    ):
        """
        Initialize Memgraph connector.

        Args:
            uri: Memgraph connection URI
            username: Authentication username (optional)
            password: Authentication password (optional)
        """
        self.uri = uri
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
                self.uri,
                auth=auth,
                max_connection_pool_size=50,  # Increased from 10 to handle burst traffic
                connection_timeout=120.0,  # Increased from 30.0 for heavy load
            )

            # Verify connectivity
            await self.driver.verify_connectivity()

            # Initialize bridge-specific schema
            await self._initialize_bridge_schema()

            logger.info(f"Memgraph bridge connector initialized: {self.uri}")

        except Exception as e:
            logger.error(f"Failed to initialize Memgraph connector: {e}")
            raise

    async def close(self):
        """Close driver and cleanup connections"""
        if self.driver:
            await self.driver.close()
            logger.info("Memgraph bridge connector closed")

    async def health_check(self) -> bool:
        """Check Memgraph connectivity"""
        try:
            if not self.driver:
                return False

            async with self.driver.session() as session:
                result = await session.run("RETURN 'bridge_health_check' as status")
                record = await result.single()
                return record and record["status"] == "bridge_health_check"

        except Exception as e:
            logger.error(f"Memgraph health check failed: {e}")
            return False

    async def create_source_entity(self, source_data: Dict[str, Any]) -> str:
        """Create or update source entity in graph"""
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (s:Source {source_id: $source_id})
                ON CREATE SET
                    s.source_url = $source_url,
                    s.source_display_name = $source_display_name,
                    s.source_type = $source_type,
                    s.status = $status,
                    s.created_at = $created_at,
                    s.bridge_synced_at = datetime(),
                    s.entity_origin = 'supabase'
                ON MATCH SET
                    s.source_url = $source_url,
                    s.source_display_name = $source_display_name,
                    s.source_type = $source_type,
                    s.status = $status,
                    s.updated_at = $updated_at,
                    s.bridge_synced_at = datetime()
                RETURN s.source_id as id
                """

                params = {
                    "source_id": source_data["source_id"],
                    "source_url": source_data["source_url"],
                    "source_display_name": source_data["source_display_name"],
                    "source_type": source_data.get("source_type", "web"),
                    "status": source_data.get("status", "unknown"),
                    "created_at": source_data["created_at"],
                    "updated_at": source_data.get("updated_at"),
                }

                result = await session.run(query, params)
                record = await result.single()
                return record["id"] if record else None

        except Exception as e:
            logger.error(f"Failed to create source entity: {e}")
            return None

    async def create_project_entity(self, project_data: Dict[str, Any]) -> str:
        """Create or update project entity in graph"""
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (p:Project {project_id: $project_id})
                ON CREATE SET
                    p.title = $title,
                    p.description = $description,
                    p.github_repo = $github_repo,
                    p.features = $features,
                    p.created_at = $created_at,
                    p.bridge_synced_at = datetime(),
                    p.entity_origin = 'supabase'
                ON MATCH SET
                    p.title = $title,
                    p.description = $description,
                    p.github_repo = $github_repo,
                    p.features = $features,
                    p.updated_at = $updated_at,
                    p.bridge_synced_at = datetime()
                RETURN p.project_id as id
                """

                params = {
                    "project_id": project_data["project_id"],
                    "title": project_data["title"],
                    "description": project_data.get("description"),
                    "github_repo": project_data.get("github_repo"),
                    "features": project_data.get("features", {}),
                    "created_at": project_data["created_at"],
                    "updated_at": project_data.get("updated_at"),
                }

                result = await session.run(query, params)
                record = await result.single()
                return record["id"] if record else None

        except Exception as e:
            logger.error(f"Failed to create project entity: {e}")
            return None

    async def create_page_entity(self, page_data: Dict[str, Any]) -> str:
        """Create or update page entity in graph"""
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (page:Page {page_id: $page_id})
                ON CREATE SET
                    page.url = $url,
                    page.title = $title,
                    page.page_type = $page_type,
                    page.content_hash = $content_hash,
                    page.created_at = $created_at,
                    page.bridge_synced_at = datetime(),
                    page.entity_origin = 'supabase'
                ON MATCH SET
                    page.url = $url,
                    page.title = $title,
                    page.page_type = $page_type,
                    page.content_hash = $content_hash,
                    page.updated_at = $updated_at,
                    page.bridge_synced_at = datetime()
                RETURN page.page_id as id
                """

                params = {
                    "page_id": page_data["page_id"],
                    "url": page_data["url"],
                    "title": page_data.get("title"),
                    "page_type": page_data.get("page_type"),
                    "content_hash": page_data.get("content_hash"),
                    "created_at": page_data["created_at"],
                    "updated_at": page_data.get("updated_at"),
                }

                result = await session.run(query, params)
                record = await result.single()
                return record["id"] if record else None

        except Exception as e:
            logger.error(f"Failed to create page entity: {e}")
            return None

    async def create_relationship(
        self,
        source_id: str = None,
        target_id: str = None,
        relationship_type: str = None,
        source_label: str = "Entity",
        target_label: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
        from_entity_id: str = None,
        to_entity_id: str = None,
    ) -> bool:
        """Create relationship between entities (supports both call patterns)"""
        try:
            # Support both calling patterns
            if from_entity_id is not None and to_entity_id is not None:
                # New pattern: use entity_id directly
                source_id_val = from_entity_id
                target_id_val = to_entity_id
                query = """
                MATCH (source {entity_id: $source_id}), (target {entity_id: $target_id})
                MERGE (source)-[r:BRIDGE_RELATION {type: $rel_type}]->(target)
                ON CREATE SET
                    r.created_at = datetime(),
                    r.bridge_synced_at = datetime(),
                    r.properties = $properties
                ON MATCH SET
                    r.updated_at = datetime(),
                    r.bridge_synced_at = datetime(),
                    r.properties = $properties
                RETURN r.type as relationship_type
                """
            else:
                # Original pattern: use labels and specific ID fields
                source_id_val = source_id
                target_id_val = target_id
                query = f"""
                MATCH (source:{source_label}), (target:{target_label})
                WHERE source.{self._get_id_field(source_label)} = $source_id
                  AND target.{self._get_id_field(target_label)} = $target_id
                MERGE (source)-[r:BRIDGE_RELATION {{type: $rel_type}}]->(target)
                ON CREATE SET
                    r.created_at = datetime(),
                    r.bridge_synced_at = datetime(),
                    r.properties = $properties
                ON MATCH SET
                    r.updated_at = datetime(),
                    r.bridge_synced_at = datetime(),
                    r.properties = $properties
                RETURN r.type as relationship_type
                """

            async with self.driver.session() as session:
                params = {
                    "source_id": source_id_val,
                    "target_id": target_id_val,
                    "rel_type": relationship_type,
                    "properties": properties or {},
                }

                result = await session.run(query, params)
                record = await result.single()
                return record is not None

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    async def link_page_to_source(self, page_id: str, source_id: str) -> bool:
        """Link page to its source"""
        return await self.create_relationship(
            source_id=source_id,
            target_id=page_id,
            relationship_type="CONTAINS_PAGE",
            source_label="Source",
            target_label="Page",
            properties={"relationship_type": "containment"},
        )

    async def link_code_to_page(self, code_example_id: str, page_id: str) -> bool:
        """Link code example to its page"""
        return await self.create_relationship(
            source_id=page_id,
            target_id=code_example_id,
            relationship_type="CONTAINS_CODE",
            source_label="Page",
            target_label="CodeExample",
            properties={"relationship_type": "containment"},
        )

    async def get_bridge_entities_by_origin(
        self,
        origin: str = "supabase",
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get entities created by bridge from specific origin"""
        try:
            async with self.driver.session() as session:
                if entity_type:
                    query = f"""
                    MATCH (e:{entity_type} {{entity_origin: $origin}})
                    RETURN e, labels(e) as labels
                    ORDER BY e.bridge_synced_at DESC
                    LIMIT $limit
                    """
                else:
                    query = """
                    MATCH (e {entity_origin: $origin})
                    RETURN e, labels(e) as labels
                    ORDER BY e.bridge_synced_at DESC
                    LIMIT $limit
                    """

                params = {"origin": origin, "limit": limit}
                result = await session.run(query, params)
                records = await result.data()

                entities = []
                for record in records:
                    entity_data = dict(record["e"])
                    entity_data["labels"] = record["labels"]
                    entities.append(entity_data)

                return entities

        except Exception as e:
            logger.error(f"Failed to get bridge entities: {e}")
            return []

    async def get_bridge_statistics(self) -> Dict[str, Any]:
        """Get bridge synchronization statistics"""
        try:
            async with self.driver.session() as session:
                # Count entities by origin
                origin_stats = await session.run(
                    """
                    MATCH (e {entity_origin: 'supabase'})
                    RETURN labels(e)[0] as entity_type, count(*) as count
                    ORDER BY count DESC
                """
                )
                origin_data = await origin_stats.data()

                # Count relationships created by bridge
                rel_stats = await session.run(
                    """
                    MATCH ()-[r:BRIDGE_RELATION]->()
                    RETURN r.type as relationship_type, count(*) as count
                    ORDER BY count DESC
                """
                )
                rel_data = await rel_stats.data()

                # Get last sync times
                last_sync = await session.run(
                    """
                    MATCH (e {entity_origin: 'supabase'})
                    RETURN max(e.bridge_synced_at) as last_sync_time
                """
                )
                last_sync_record = await last_sync.single()

                return {
                    "entities_by_type": {
                        item["entity_type"]: item["count"] for item in origin_data
                    },
                    "relationships_by_type": {
                        item["relationship_type"]: item["count"] for item in rel_data
                    },
                    "last_sync_time": (
                        last_sync_record["last_sync_time"] if last_sync_record else None
                    ),
                    "total_bridge_entities": sum(item["count"] for item in origin_data),
                    "total_bridge_relationships": sum(
                        item["count"] for item in rel_data
                    ),
                }

        except Exception as e:
            logger.error(f"Failed to get bridge statistics: {e}")
            return {}

    async def cleanup_orphaned_entities(self) -> int:
        """Clean up entities that no longer exist in source system"""
        try:
            async with self.driver.session() as session:
                # This would require implementing a mechanism to track deleted entities
                # For now, we'll implement a basic cleanup of entities without relationships
                query = """
                MATCH (e {entity_origin: 'supabase'})
                WHERE NOT EXISTS((e)-[:BRIDGE_RELATION]-()) AND NOT EXISTS(()-[:BRIDGE_RELATION]-(e))
                AND NOT EXISTS((e)-[:CONTAINS]->()) AND NOT EXISTS((e)<-[:CONTAINS]-())
                DELETE e
                RETURN count(*) as deleted_count
                """

                result = await session.run(query)
                record = await result.single()
                return record["deleted_count"] if record else 0

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned entities: {e}")
            return 0

    async def _initialize_bridge_schema(self):
        """Initialize bridge-specific schema and indexes"""
        try:
            async with self.driver.session() as session:
                # Create indexes for bridge entities
                indexes = [
                    "CREATE INDEX ON :Source(source_id);",
                    "CREATE INDEX ON :Project(project_id);",
                    "CREATE INDEX ON :Page(page_id);",
                    "CREATE INDEX ON :CodeExample(example_id);",
                    "CREATE INDEX ON :Source(entity_origin);",
                    "CREATE INDEX ON :Project(entity_origin);",
                    "CREATE INDEX ON :Page(entity_origin);",
                    "CREATE INDEX ON :CodeExample(entity_origin);",
                ]

                for index_query in indexes:
                    try:
                        await session.run(index_query)
                    except Exception as e:
                        # Index might already exist
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to create index: {e}")

                logger.info("Bridge schema initialization completed")

        except Exception as e:
            logger.error(f"Bridge schema initialization failed: {e}")

    def _get_id_field(self, label: str) -> str:
        """Get the ID field name for a given entity label"""
        id_fields = {
            "Source": "source_id",
            "Project": "project_id",
            "Page": "page_id",
            "CodeExample": "example_id",
            "Entity": "entity_id",
        }
        return id_fields.get(label, "id")

    async def store_entities(self, entities: List[Dict[str, Any]]) -> bool:
        """Store multiple entities in the knowledge graph"""
        try:
            success_count = 0
            for entity in entities:
                entity_id = entity.get("entity_id")
                entity_type = entity.get("entity_type", "Entity")
                name = entity.get("name", "")
                properties = entity.get("properties", {})
                confidence_score = entity.get("confidence_score", 1.0)

                async with self.driver.session() as session:
                    # Create entity with dynamic label
                    query = f"""
                    MERGE (e:{entity_type} {{entity_id: $entity_id}})
                    ON CREATE SET
                        e.name = $name,
                        e.entity_type = $entity_type,
                        e.confidence_score = $confidence_score,
                        e.properties = $properties,
                        e.created_at = datetime(),
                        e.bridge_synced_at = datetime(),
                        e.entity_origin = 'bridge_intelligence'
                    ON MATCH SET
                        e.name = $name,
                        e.entity_type = $entity_type,
                        e.confidence_score = $confidence_score,
                        e.properties = $properties,
                        e.updated_at = datetime(),
                        e.bridge_synced_at = datetime()
                    RETURN e.entity_id as id
                    """

                    params = {
                        "entity_id": entity_id,
                        "name": name,
                        "entity_type": entity_type,
                        "confidence_score": confidence_score,
                        "properties": properties,
                    }

                    result = await session.run(query, params)
                    record = await result.single()
                    if record:
                        success_count += 1

            logger.info(f"Stored {success_count}/{len(entities)} entities successfully")
            return success_count > 0

        except Exception as e:
            logger.error(f"Failed to store entities: {e}")
            return False

    async def find_entity_relationships(
        self,
        entity_id: str,
        entity_label: str,
        relationship_types: Optional[List[str]] = None,
        direction: str = "both",
    ) -> List[Dict[str, Any]]:
        """Find relationships for an entity"""
        try:
            async with self.driver.session() as session:
                id_field = self._get_id_field(entity_label)

                if direction == "outgoing":
                    rel_pattern = "-[r:BRIDGE_RELATION]->(target)"
                    target_return = "target"
                elif direction == "incoming":
                    rel_pattern = "<-[r:BRIDGE_RELATION]-(source)"
                    target_return = "source"
                else:  # both
                    rel_pattern = "-[r:BRIDGE_RELATION]-(connected)"
                    target_return = "connected"

                query = f"""
                MATCH (entity:{entity_label} {{{id_field}: $entity_id}}){rel_pattern}
                WHERE $rel_types IS NULL OR r.type IN $rel_types
                RETURN r, {target_return}, labels({target_return}) as target_labels
                """

                params = {"entity_id": entity_id, "rel_types": relationship_types}

                result = await session.run(query, params)
                records = await result.data()

                relationships = []
                for record in records:
                    relationships.append(
                        {
                            "relationship": dict(record["r"]),
                            "connected_entity": dict(record[target_return]),
                            "connected_labels": record["target_labels"],
                        }
                    )

                return relationships

        except Exception as e:
            logger.error(f"Failed to find entity relationships: {e}")
            return []
