"""
Enhanced Memgraph Adapter for LangExtract Service

Advanced knowledge graph operations with language-aware entity management,
semantic relationship mapping, and intelligent graph enhancement.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models.extraction_models import (
    EnhancedEntity,
    EnhancedRelationship,
    EntityType,
)
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class EnhancedMemgraphAdapter:
    """
    Enhanced adapter for Memgraph knowledge graph operations.

    Provides advanced capabilities for language-aware entity storage,
    semantic relationship management, and graph analytics.
    """

    def __init__(
        self, uri: str = "bolt://localhost:7687", auth: Optional[Tuple[str, str]] = None
    ):
        """
        Initialize enhanced Memgraph adapter.

        Args:
            uri: Memgraph connection URI
            auth: Optional authentication tuple (username, password)
        """
        self.uri = uri
        self.auth = auth or ("", "")
        self.driver = None

        # Graph enhancement settings
        self.enhancement_config = {
            "auto_create_indexes": True,
            "enable_semantic_clustering": True,
            "relationship_inference": True,
            "quality_scoring": True,
            "duplicate_detection": True,
        }

        # Query optimization settings
        self.query_config = {
            "batch_size": 1000,
            "max_concurrent_transactions": 10,
            "query_timeout": 30,
            "enable_query_caching": True,
        }

        # Statistics tracking
        self.stats = {
            "entities_created": 0,
            "entities_updated": 0,
            "relationships_created": 0,
            "relationships_updated": 0,
            "queries_executed": 0,
            "transactions_committed": 0,
            "enhancement_operations": 0,
        }

        # Node labels and relationship types
        self.node_labels = {
            EntityType.CLASS: "CodeClass",
            EntityType.FUNCTION: "CodeFunction",
            EntityType.METHOD: "CodeMethod",
            EntityType.VARIABLE: "CodeVariable",
            EntityType.CONSTANT: "CodeConstant",
            EntityType.MODULE: "CodeModule",
            EntityType.CONCEPT: "Concept",
            EntityType.TOPIC: "Topic",
            EntityType.KEYWORD: "Keyword",
            EntityType.EXAMPLE: "Example",
            EntityType.DOCUMENT: "Document",
        }

    async def initialize(self):
        """Initialize connection and setup graph schema"""
        try:
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)

            # Verify connection
            await self._verify_connection()

            # Setup graph schema
            if self.enhancement_config["auto_create_indexes"]:
                await self._create_indexes()

            # Setup graph constraints
            await self._create_constraints()

            logger.info("Enhanced Memgraph adapter initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Memgraph adapter: {e}")
            raise

    async def close(self):
        """Close database connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Memgraph adapter connection closed")

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as health")
                record = await result.single()
                return record["health"] == 1
        except Exception as e:
            logger.error(f"Memgraph health check failed: {e}")
            return False

    async def upsert_entities(self, entities: List[EnhancedEntity]) -> Dict[str, int]:
        """
        Upsert entities with language-aware processing.

        Args:
            entities: List of entities to upsert

        Returns:
            Dictionary with operation counts
        """
        try:
            if not entities:
                return {"created": 0, "updated": 0}

            # Group entities by type for efficient processing
            entities_by_type = {}
            for entity in entities:
                entity_type = entity.entity_type
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = []
                entities_by_type[entity_type].append(entity)

            created_count = 0
            updated_count = 0

            # Process entities by type
            for entity_type, type_entities in entities_by_type.items():
                results = await self._upsert_entities_by_type(
                    entity_type, type_entities
                )
                created_count += results["created"]
                updated_count += results["updated"]

            # Update statistics
            self.stats["entities_created"] += created_count
            self.stats["entities_updated"] += updated_count

            logger.info(
                f"Upserted entities: {created_count} created, {updated_count} updated"
            )

            return {"created": created_count, "updated": updated_count}

        except Exception as e:
            logger.error(f"Entity upsert failed: {e}")
            return {"created": 0, "updated": 0}

    async def upsert_relationships(
        self, relationships: List[EnhancedRelationship]
    ) -> Dict[str, int]:
        """
        Upsert relationships with enhanced validation.

        Args:
            relationships: List of relationships to upsert

        Returns:
            Dictionary with operation counts
        """
        try:
            if not relationships:
                return {"created": 0, "updated": 0}

            # Filter and validate relationships
            valid_relationships = await self._validate_relationships(relationships)

            if not valid_relationships:
                logger.warning("No valid relationships to upsert")
                return {"created": 0, "updated": 0}

            # Batch process relationships
            batch_size = self.query_config["batch_size"]
            created_count = 0
            updated_count = 0

            for i in range(0, len(valid_relationships), batch_size):
                batch = valid_relationships[i : i + batch_size]
                results = await self._upsert_relationship_batch(batch)
                created_count += results["created"]
                updated_count += results["updated"]

            # Update statistics
            self.stats["relationships_created"] += created_count
            self.stats["relationships_updated"] += updated_count

            logger.info(
                f"Upserted relationships: {created_count} created, {updated_count} updated"
            )

            return {"created": created_count, "updated": updated_count}

        except Exception as e:
            logger.error(f"Relationship upsert failed: {e}")
            return {"created": 0, "updated": 0}

    async def enhance_graph_with_semantic_clustering(self) -> Dict[str, Any]:
        """
        Enhance graph with semantic clustering and relationship inference.

        Returns:
            Enhancement results
        """
        try:
            if not self.enhancement_config["enable_semantic_clustering"]:
                return {"clusters_created": 0, "relationships_inferred": 0}

            logger.info("Starting semantic clustering enhancement")

            # Create semantic clusters based on entity similarities
            clusters_created = await self._create_semantic_clusters()

            # Infer missing relationships
            relationships_inferred = 0
            if self.enhancement_config["relationship_inference"]:
                relationships_inferred = await self._infer_relationships()

            # Update graph quality scores
            quality_updates = 0
            if self.enhancement_config["quality_scoring"]:
                quality_updates = await self._update_quality_scores()

            # Detect and merge duplicates
            duplicates_merged = 0
            if self.enhancement_config["duplicate_detection"]:
                duplicates_merged = await self._detect_and_merge_duplicates()

            enhancement_results = {
                "clusters_created": clusters_created,
                "relationships_inferred": relationships_inferred,
                "quality_updates": quality_updates,
                "duplicates_merged": duplicates_merged,
                "enhancement_timestamp": datetime.utcnow().isoformat(),
            }

            self.stats["enhancement_operations"] += 1

            logger.info(f"Graph enhancement completed: {enhancement_results}")
            return enhancement_results

        except Exception as e:
            logger.error(f"Graph enhancement failed: {e}")
            return {"error": str(e)}

    async def query_entities_by_language(
        self,
        language: str,
        entity_types: Optional[List[EntityType]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query entities by detected language.

        Args:
            language: Language code to filter by
            entity_types: Optional entity types to filter
            limit: Maximum number of results

        Returns:
            List of matching entities
        """
        try:
            # Build query based on filters
            where_clauses = [f"n.language = '{language}'"]

            if entity_types:
                type_labels = [
                    self.node_labels.get(et, "Entity") for et in entity_types
                ]
                label_filter = " OR ".join([f"n:{label}" for label in type_labels])
                where_clauses.append(f"({label_filter})")

            where_clause = " AND ".join(where_clauses)

            query = f"""
            MATCH (n)
            WHERE {where_clause}
            RETURN n.entity_id as entity_id, n.name as name, n.entity_type as entity_type,
                   n.language as language, n.confidence_score as confidence_score,
                   n.source_path as source_path, n.properties as properties
            ORDER BY n.confidence_score DESC
            LIMIT {limit}
            """

            async with self.driver.session() as session:
                result = await session.run(query)
                entities = []

                async for record in result:
                    entities.append(
                        {
                            "entity_id": record["entity_id"],
                            "name": record["name"],
                            "entity_type": record["entity_type"],
                            "language": record["language"],
                            "confidence_score": record["confidence_score"],
                            "source_path": record["source_path"],
                            "properties": record["properties"] or {},
                        }
                    )

                self.stats["queries_executed"] += 1
                return entities

        except Exception as e:
            logger.error(f"Language-based entity query failed: {e}")
            return []

    async def find_semantic_neighbors(
        self,
        entity_id: str,
        similarity_threshold: float = 0.7,
        max_neighbors: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar entities.

        Args:
            entity_id: Source entity ID
            similarity_threshold: Minimum similarity score
            max_neighbors: Maximum number of neighbors to return

        Returns:
            List of similar entities with similarity scores
        """
        try:
            query = """
            MATCH (source {entity_id: $entity_id})
            MATCH (target)
            WHERE source <> target
            AND target.semantic_embedding IS NOT NULL
            AND source.semantic_embedding IS NOT NULL
            WITH source, target,
                 gds.similarity.cosine(source.semantic_embedding, target.semantic_embedding) as similarity
            WHERE similarity >= $threshold
            RETURN target.entity_id as entity_id, target.name as name,
                   target.entity_type as entity_type, similarity
            ORDER BY similarity DESC
            LIMIT $max_neighbors
            """

            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=entity_id,
                    threshold=similarity_threshold,
                    max_neighbors=max_neighbors,
                )

                neighbors = []
                async for record in result:
                    neighbors.append(
                        {
                            "entity_id": record["entity_id"],
                            "name": record["name"],
                            "entity_type": record["entity_type"],
                            "similarity_score": record["similarity"],
                        }
                    )

                return neighbors

        except Exception as e:
            logger.error(f"Semantic neighbor search failed: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get adapter and graph statistics"""
        try:
            # Get graph statistics
            graph_stats = await self._get_graph_statistics()

            # Combine with adapter statistics
            return {
                "adapter_statistics": self.stats,
                "graph_statistics": graph_stats,
                "configuration": {
                    "enhancement_config": self.enhancement_config,
                    "query_config": self.query_config,
                },
                "connection_info": {
                    "uri": self.uri,
                    "connected": self.driver is not None,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}

    async def _upsert_entities_by_type(
        self,
        entity_type: EntityType,
        entities: List[EnhancedEntity],
    ) -> Dict[str, int]:
        """Upsert entities of a specific type"""
        try:
            node_label = self.node_labels.get(entity_type, "Entity")
            created_count = 0
            updated_count = 0

            batch_size = self.query_config["batch_size"]

            for i in range(0, len(entities), batch_size):
                batch = entities[i : i + batch_size]

                async with self.driver.session() as session:
                    async with session.begin_transaction() as tx:
                        for entity in batch:
                            # Prepare entity properties
                            properties = {
                                "entity_id": entity.entity_id,
                                "name": entity.name,
                                "entity_type": entity.entity_type.value,
                                "description": entity.description or "",
                                "confidence_score": entity.confidence_score,
                                "source_path": entity.source_path,
                                "language": (
                                    entity.language.value if entity.language else "en"
                                ),
                                "content": entity.content or "",
                                "properties": entity.properties,
                                "created_at": datetime.utcnow().isoformat(),
                                "updated_at": datetime.utcnow().isoformat(),
                            }

                            # Add semantic information if available
                            if entity.semantic_embedding:
                                properties["semantic_embedding"] = (
                                    entity.semantic_embedding
                                )

                            if entity.semantic_concepts:
                                properties["semantic_concepts"] = (
                                    entity.semantic_concepts
                                )

                            if entity.quality_score is not None:
                                properties["quality_score"] = entity.quality_score

                            # Upsert query
                            query = f"""
                            MERGE (n:{node_label} {{entity_id: $entity_id}})
                            ON CREATE SET n += $properties, n.created_count = 1
                            ON MATCH SET n += $properties, n.updated_at = $timestamp,
                                         n.updated_count = COALESCE(n.updated_count, 0) + 1
                            RETURN n.created_count as created_count
                            """

                            result = await tx.run(
                                query,
                                entity_id=entity.entity_id,
                                properties=properties,
                                timestamp=datetime.utcnow().isoformat(),
                            )

                            record = await result.single()
                            if record and record["created_count"] == 1:
                                created_count += 1
                            else:
                                updated_count += 1

                        await tx.commit()
                        self.stats["transactions_committed"] += 1

            return {"created": created_count, "updated": updated_count}

        except Exception as e:
            logger.error(f"Entity type upsert failed for {entity_type}: {e}")
            return {"created": 0, "updated": 0}

    async def _upsert_relationship_batch(
        self, relationships: List[EnhancedRelationship]
    ) -> Dict[str, int]:
        """Upsert a batch of relationships"""
        try:
            created_count = 0
            updated_count = 0

            async with self.driver.session() as session:
                async with session.begin_transaction() as tx:
                    for rel in relationships:
                        # Prepare relationship properties
                        properties = {
                            "relationship_id": rel.relationship_id,
                            "confidence_score": rel.confidence_score,
                            "description": rel.description or "",
                            "properties": rel.properties,
                            "created_at": rel.created_at.isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                        }

                        if rel.strength is not None:
                            properties["strength"] = rel.strength

                        if rel.semantic_weight is not None:
                            properties["semantic_weight"] = rel.semantic_weight

                        # Upsert relationship query
                        query = f"""
                        MATCH (source {{entity_id: $source_id}})
                        MATCH (target {{entity_id: $target_id}})
                        MERGE (source)-[r:{rel.relationship_type.value.upper()} {{relationship_id: $rel_id}}]->(target)
                        ON CREATE SET r += $properties, r.created_count = 1
                        ON MATCH SET r += $properties, r.updated_at = $timestamp,
                                     r.updated_count = COALESCE(r.updated_count, 0) + 1
                        RETURN r.created_count as created_count
                        """

                        result = await tx.run(
                            query,
                            source_id=rel.source_entity_id,
                            target_id=rel.target_entity_id,
                            rel_id=rel.relationship_id,
                            properties=properties,
                            timestamp=datetime.utcnow().isoformat(),
                        )

                        record = await result.single()
                        if record and record["created_count"] == 1:
                            created_count += 1
                        else:
                            updated_count += 1

                    await tx.commit()
                    self.stats["transactions_committed"] += 1

            return {"created": created_count, "updated": updated_count}

        except Exception as e:
            logger.error(f"Relationship batch upsert failed: {e}")
            return {"created": 0, "updated": 0}

    async def _validate_relationships(
        self, relationships: List[EnhancedRelationship]
    ) -> List[EnhancedRelationship]:
        """Validate relationships before upsert"""
        valid_relationships = []

        for rel in relationships:
            # Check if source and target entities exist
            if await self._entity_exists(
                rel.source_entity_id
            ) and await self._entity_exists(rel.target_entity_id):
                valid_relationships.append(rel)
            else:
                logger.warning(
                    f"Skipping relationship {rel.relationship_id}: entities not found"
                )

        return valid_relationships

    async def _entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in graph"""
        try:
            async with self.driver.session() as session:
                result = await session.run(
                    "MATCH (n {entity_id: $entity_id}) RETURN count(n) as count",
                    entity_id=entity_id,
                )
                record = await result.single()
                return record["count"] > 0
        except Exception:
            return False

    async def _verify_connection(self):
        """Verify database connection"""
        try:
            async with self.driver.session() as session:
                await session.run("RETURN 1")
            logger.info("Memgraph connection verified")
        except Exception as e:
            logger.error(f"Memgraph connection verification failed: {e}")
            raise

    async def _create_indexes(self):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX ON :Entity(entity_id);",
            "CREATE INDEX ON :Entity(name);",
            "CREATE INDEX ON :Entity(entity_type);",
            "CREATE INDEX ON :Entity(language);",
            "CREATE INDEX ON :Entity(source_path);",
            "CREATE INDEX ON :CodeClass(name);",
            "CREATE INDEX ON :CodeFunction(name);",
            "CREATE INDEX ON :Concept(name);",
        ]

        try:
            async with self.driver.session() as session:
                for index_query in indexes:
                    try:
                        await session.run(index_query)
                    except Neo4jError as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Index creation failed: {e}")

            logger.info("Database indexes created/verified")

        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    async def _create_constraints(self):
        """Create database constraints"""
        constraints = [
            "CREATE CONSTRAINT ON (n:Entity) ASSERT n.entity_id IS UNIQUE;",
        ]

        try:
            async with self.driver.session() as session:
                for constraint_query in constraints:
                    try:
                        await session.run(constraint_query)
                    except Neo4jError as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Constraint creation failed: {e}")

            logger.info("Database constraints created/verified")

        except Exception as e:
            logger.error(f"Failed to create constraints: {e}")

    async def _create_semantic_clusters(self) -> int:
        """Create semantic clusters based on entity similarities"""
        # Placeholder implementation - would use graph algorithms
        return 0

    async def _infer_relationships(self) -> int:
        """Infer missing relationships based on patterns"""
        # Placeholder implementation - would analyze patterns
        return 0

    async def _update_quality_scores(self) -> int:
        """Update quality scores for entities and relationships"""
        # Placeholder implementation - would calculate quality metrics
        return 0

    async def _detect_and_merge_duplicates(self) -> int:
        """Detect and merge duplicate entities"""
        # Placeholder implementation - would find and merge duplicates
        return 0

    async def _get_graph_statistics(self) -> Dict[str, Any]:
        """Get graph-level statistics"""
        try:
            async with self.driver.session() as session:
                # Count nodes by type
                node_counts = {}
                for entity_type, label in self.node_labels.items():
                    result = await session.run(
                        f"MATCH (n:{label}) RETURN count(n) as count"
                    )
                    record = await result.single()
                    node_counts[entity_type.value] = record["count"] if record else 0

                # Count relationships
                result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
                record = await result.single()
                relationship_count = record["count"] if record else 0

                # Count total nodes
                result = await session.run("MATCH (n) RETURN count(n) as count")
                record = await result.single()
                total_nodes = record["count"] if record else 0

                return {
                    "total_nodes": total_nodes,
                    "total_relationships": relationship_count,
                    "nodes_by_type": node_counts,
                    "last_updated": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get graph statistics: {e}")
            return {}
