"""
Memgraph Adapter for Archon Intelligence Service

Graph database operations for storing and querying knowledge entities and relationships.
Adapted from omnibase_3 patterns with Archon-specific enhancements.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from models.entity_models import (
    EntityType,
    KnowledgeEntity,
    KnowledgeRelationship,
)
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar("T")


def retry_on_transient_error(
    max_attempts: int = 3, initial_backoff: float = 0.1, backoff_multiplier: float = 2.0
) -> Callable:
    """
    Retry decorator for Memgraph TransientErrors caused by concurrent transactions.

    When multiple workers try to create the same nodes simultaneously, Memgraph
    raises TransientErrors. This decorator implements exponential backoff retry
    logic to handle these race conditions gracefully.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_backoff: Initial backoff delay in seconds (default: 0.1s)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)

    Example:
        @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
        async def store_entity(self, entity):
            # This will retry up to 3 times on TransientError
            # Delays: 0.1s → 0.2s → 0.4s
            pass

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            attempt = 0
            backoff = initial_backoff
            last_exception = None

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Check if it's a Memgraph TransientError
                    is_transient = (
                        "transienterror" in error_msg
                        or "transient" in error_msg
                        or "conflicting transactions" in error_msg
                        or "serialization" in error_msg
                        or "transaction conflict" in error_msg
                    )

                    if not is_transient:
                        # Not a transient error, raise immediately
                        logger.error(
                            f"❌ [MEMGRAPH] Non-transient error in {func.__name__} | "
                            f"error={str(e)[:200]}"
                        )
                        raise

                    attempt += 1

                    if attempt >= max_attempts:
                        # Out of retries, raise the last exception
                        logger.error(
                            f"❌ [MEMGRAPH RETRY] Exhausted all {max_attempts} attempts for {func.__name__} | "
                            f"final_error={str(e)[:200]}"
                        )
                        raise

                    # Log retry attempt
                    logger.warning(
                        f"🔄 [MEMGRAPH RETRY {attempt}/{max_attempts}] {func.__name__} "
                        f"failed with TransientError, retrying in {backoff:.2f}s | "
                        f"error={str(e)[:100]}"
                    )

                    # Wait before retry
                    await asyncio.sleep(backoff)
                    backoff *= backoff_multiplier

            # Should never reach here, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Failed after {max_attempts} attempts")

        return async_wrapper

    return decorator


class MemgraphKnowledgeAdapter:
    """
    Async adapter for Memgraph knowledge graph operations.

    Provides high-level interface for storing and querying entities,
    relationships, and performing graph analytics.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = None,
        password: str = None,
    ):
        """
        Initialize Memgraph adapter with connection parameters.

        Args:
            uri: Memgraph connection URI (bolt protocol)
            username: Authentication username (optional for dev)
            password: Authentication password (optional for dev)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self._connection_pool_size = (
            50  # Increased from 10 to handle concurrent bulk ingestion
        )
        self._max_retry_attempts = 3
        self._retry_delay = 1.0

        # Concurrency throttling via semaphore to prevent transaction conflicts
        # During bulk ingestion, limiting concurrent writes reduces Memgraph TransientErrors
        self._max_concurrent_writes = int(
            os.getenv("MEMGRAPH_MAX_CONCURRENT_WRITES", "10")
        )
        self._write_semaphore = asyncio.Semaphore(self._max_concurrent_writes)

        # Metrics tracking
        self._throttle_wait_count = 0
        self._total_writes = 0

        logger.info(
            f"🔧 [MEMGRAPH CONFIG] Initialized with concurrency throttling | "
            f"max_concurrent_writes={self._max_concurrent_writes} | "
            f"connection_pool_size={self._connection_pool_size}"
        )

    async def initialize(self):
        """Initialize async driver and verify connectivity"""
        try:
            # Create async driver with connection pooling
            auth = (
                (self.username, self.password)
                if self.username and self.password
                else None
            )
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=auth,
                max_connection_pool_size=self._connection_pool_size,
                connection_timeout=120.0,  # Increased from 30s to handle high concurrent load
            )

            # Verify connectivity
            await self.driver.verify_connectivity()

            # Initialize schema if needed
            await self._initialize_schema()

            logger.info(f"Memgraph adapter initialized successfully: {self.uri}")

        except Exception as e:
            logger.error(f"Failed to initialize Memgraph adapter: {e}")
            raise

    async def close(self):
        """Close driver and cleanup connections"""
        if self.driver:
            await self.driver.close()
            logger.info("Memgraph adapter closed")

    async def health_check(self) -> bool:
        """Check Memgraph connectivity and basic operations"""
        try:
            if not self.driver:
                return False

            async with self.driver.session() as session:
                result = await session.run("RETURN 'health_check' as status")
                record = await result.single()
                return record and record["status"] == "health_check"

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def create_file_node(self, file_data: dict) -> bool:
        """
        Create or update a FILE node in Memgraph with comprehensive metadata.

        Uses MERGE to ensure idempotent file node creation. If a file already
        exists (based on entity_id/path), it updates the metadata. This enables
        architectural queries, orphan detection, and dependency analysis.

        Args:
            file_data: Dictionary containing file metadata with keys:
                - entity_id: Unique file identifier (required)
                - name: Filename (required)
                - path: Full or relative file path (required)
                - relative_path: Project-relative path
                - project_name: Project identifier
                - file_size: Size in bytes
                - language: Programming language or file type
                - file_hash: Content hash for change detection
                - last_modified: Last modification timestamp
                - indexed_at: Indexing timestamp
                - content_type: "code" or "documentation"
                - line_count: Number of lines
                - entity_count: Number of extracted entities
                - import_count: Number of import statements

        Returns:
            bool: True if file node was successfully created/updated, False otherwise

        Example:
            file_data = {
                "entity_id": "file_abc123",
                "name": "app.py",
                "path": "services/intelligence/app.py",
                "language": "python",
                "file_size": 125000,
                "line_count": 2800,
                "entity_count": 45
            }
            success = await adapter.create_file_node(file_data)
        """
        if not file_data or not self.driver:
            logger.warning("create_file_node called with empty file_data or no driver")
            return False

        # Validate required fields
        required_fields = ["entity_id", "name", "path"]
        missing_fields = [field for field in required_fields if field not in file_data]
        if missing_fields:
            logger.error(f"Missing required fields for file node: {missing_fields}")
            return False

        try:
            async with self.driver.session() as session:
                # Use MERGE to create or update file node
                query = """
                MERGE (f:File {entity_id: $entity_id})
                ON CREATE SET
                    f.name = $name,
                    f.path = $path,
                    f.relative_path = $relative_path,
                    f.project_name = $project_name,
                    f.file_size = $file_size,
                    f.language = $language,
                    f.file_hash = $file_hash,
                    f.last_modified = $last_modified,
                    f.indexed_at = $indexed_at,
                    f.content_type = $content_type,
                    f.line_count = $line_count,
                    f.entity_count = $entity_count,
                    f.import_count = $import_count,
                    f.created_at = $indexed_at
                ON MATCH SET
                    f.project_name = $project_name,
                    f.name = $name,
                    f.file_size = $file_size,
                    f.file_hash = $file_hash,
                    f.last_modified = $last_modified,
                    f.indexed_at = $indexed_at,
                    f.line_count = $line_count,
                    f.entity_count = $entity_count,
                    f.import_count = $import_count,
                    f.updated_at = $indexed_at
                RETURN f.entity_id as file_id, f.name as name, f.language as language
                """

                params = {
                    "entity_id": file_data["entity_id"],
                    "name": file_data["name"],
                    "path": file_data["path"],
                    "relative_path": file_data.get("relative_path", file_data["path"]),
                    "project_name": file_data.get("project_name")
                    or file_data.get("project_id")
                    or "unknown",
                    "file_size": file_data.get("file_size", 0),
                    "language": file_data.get("language", "unknown"),
                    "file_hash": file_data.get("file_hash", ""),
                    "last_modified": file_data.get(
                        "last_modified", datetime.now(timezone.utc).isoformat()
                    ),
                    "indexed_at": file_data.get(
                        "indexed_at", datetime.now(timezone.utc).isoformat()
                    ),
                    "content_type": file_data.get("content_type", "code"),
                    "line_count": file_data.get("line_count", 0),
                    "entity_count": file_data.get("entity_count", 0),
                    "import_count": file_data.get("import_count", 0),
                }

                logger.debug(
                    f"📁 [FILE NODE] Creating/updating file node | "
                    f"file_id={params['entity_id']} | name={params['name']} | "
                    f"language={params['language']} | path={params['path']}"
                )

                result = await session.run(query, params)
                record = await result.single()

                if record:
                    logger.info(
                        f"✅ [FILE NODE] File node stored successfully | "
                        f"file_id={record['file_id']} | name={record['name']} | "
                        f"language={record['language']}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ [FILE NODE] MERGE returned no record | "
                        f"file_id={params['entity_id']} | path={params['path']}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"❌ [FILE NODE] Failed to create file node | "
                f"file_id={file_data.get('entity_id', 'unknown')} | "
                f"error={str(e)}",
                exc_info=True,
            )
            return False

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def create_file_import_relationship(
        self,
        source_id: str,
        target_id: str,
        import_type: str = "module",
        confidence: float = 1.0,
    ) -> bool:
        """
        Create IMPORTS relationship between FILE nodes.

        Uses MERGE to ensure idempotent relationship creation and handles
        missing target files gracefully by creating placeholder FILE nodes.

        Args:
            source_id: Source file entity_id (format: "file:{project_id}:{path}")
            target_id: Target file entity_id (format: "file:{project_id}:{path}")
            import_type: Type of import (module, class, function, from_import, direct)
            confidence: Confidence score (0.0-1.0)

        Returns:
            bool: True if relationship was successfully created, False otherwise

        Example:
            success = await adapter.create_file_import_relationship(
                source_id="file:myproject:src/main.py",
                target_id="file:myproject:src/utils.py",
                import_type="module",
                confidence=1.0
            )
        """
        if not source_id or not target_id or not self.driver:
            logger.warning(
                "create_file_import_relationship called with invalid parameters"
            )
            return False

        try:
            async with self.driver.session() as session:
                # Use MERGE to create file nodes if they don't exist, then create relationship
                query = """
                MERGE (source:File {entity_id: $source_id})
                ON CREATE SET
                    source.name = "unknown",
                    source.path = $source_id,
                    source.project_name = $source_project_name,
                    source.created_at = $timestamp
                ON MATCH SET
                    source.project_name = $source_project_name,
                    source.updated_at = $timestamp
                MERGE (target:File {entity_id: $target_id})
                ON CREATE SET
                    target.name = "unknown",
                    target.path = $target_id,
                    target.project_name = $target_project_name,
                    target.created_at = $timestamp
                ON MATCH SET
                    target.project_name = $target_project_name,
                    target.updated_at = $timestamp
                MERGE (source)-[r:IMPORTS]->(target)
                SET r.import_type = $import_type,
                    r.confidence = $confidence,
                    r.created_at = $timestamp,
                    r.updated_at = $timestamp
                RETURN r, source.entity_id as source, target.entity_id as target
                """

                # Extract project_name from entity_id (format: "file:project_name:path")
                def extract_project_name(entity_id: str) -> str:
                    parts = entity_id.split(":", 2)
                    return parts[1] if len(parts) > 1 else "unknown"

                params = {
                    "source_id": source_id,
                    "target_id": target_id,
                    "source_project_name": extract_project_name(source_id),
                    "target_project_name": extract_project_name(target_id),
                    "import_type": import_type,
                    "confidence": float(confidence),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                logger.debug(
                    f"📦 [IMPORT REL] Creating import relationship | "
                    f"source={source_id} | target={target_id} | type={import_type}"
                )

                result = await session.run(query, params)
                record = await result.single()

                if record:
                    logger.debug(
                        f"✅ [IMPORT REL] Import relationship created | "
                        f"source={record['source']} | target={record['target']}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ [IMPORT REL] MERGE returned no record | "
                        f"source={source_id} | target={target_id}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"❌ [IMPORT REL] Failed to create import relationship | "
                f"source={source_id} | target={target_id} | error={str(e)}",
                exc_info=True,
            )
            return False

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def _store_single_entity(
        self, session, entity: KnowledgeEntity
    ) -> Optional[str]:
        """
        Store a single entity with retry logic for TransientErrors.

        This is a helper method called by store_entities() to handle individual
        entity storage with proper retry logic for concurrent access.

        Args:
            session: Active Memgraph session
            entity: Entity to store

        Returns:
            Stored entity_id if successful, None otherwise
        """
        # Upsert entity node
        query = """
        MERGE (e:Entity {entity_id: $entity_id})
        ON CREATE SET
            e.name = $name,
            e.entity_type = $entity_type,
            e.description = $description,
            e.source_path = $source_path,
            e.confidence_score = $confidence_score,
            e.source_line_number = $source_line_number,
            e.properties = $properties,
            e.created_at = $created_at,
            e.file_hash = $file_hash,
            e.extraction_method = $extraction_method
        ON MATCH SET
            e.is_stub = false,
            e.entity_type = $entity_type,
            e.name = $name,
            e.description = $description,
            e.confidence_score = $confidence_score,
            e.properties = $properties,
            e.updated_at = $updated_at,
            e.file_hash = $file_hash
        RETURN e.entity_id as stored_id
        """

        params = {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "description": entity.description,
            "source_path": entity.source_path,
            "confidence_score": entity.confidence_score,
            "source_line_number": entity.source_line_number,
            "properties": entity.properties,
            "created_at": (
                entity.metadata.created_at.isoformat()
                if entity.metadata.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "file_hash": entity.metadata.file_hash,
            "extraction_method": entity.metadata.extraction_method,
        }

        result = await session.run(query, params)
        record = await result.single()

        if record:
            # Store embedding if available
            if entity.embedding:
                logger.debug(
                    f"📊 [MEMGRAPH STORAGE] Storing embedding | "
                    f"entity_id={entity.entity_id} | "
                    f"embedding_dim={len(entity.embedding)}"
                )
                await self._store_entity_embedding(
                    session, entity.entity_id, entity.embedding
                )
            return record["stored_id"]

        return None

    async def store_entities(self, entities: List[KnowledgeEntity]) -> int:
        """
        Store knowledge entities in Memgraph with upsert semantics.

        Args:
            entities: List of entities to store

        Returns:
            Number of entities successfully stored
        """
        if not entities:
            logger.debug("store_entities called with empty entity list")
            return 0

        # Log storage operation start
        logger.info(
            f"📝 [MEMGRAPH STORAGE] Starting entity storage | "
            f"entity_count={len(entities)} | "
            f"source_paths={list(set(e.source_path for e in entities))[:5]}"
        )

        stored_count = 0
        failed_count = 0
        start_time = datetime.now(timezone.utc)

        # Acquire semaphore to limit concurrent writes (prevents TransientErrors)
        async with self._write_semaphore:
            self._total_writes += 1
            semaphore_wait_start = time.time()

            try:
                async with self.driver.session() as session:
                    for idx, entity in enumerate(entities):
                        try:
                            # Log before each entity write
                            logger.debug(
                                f"📝 [MEMGRAPH STORAGE] Storing entity {idx+1}/{len(entities)} | "
                                f"entity_id={entity.entity_id} | "
                                f"type={entity.entity_type.value} | "
                                f"name={entity.name} | "
                                f"source_path={entity.source_path}"
                            )

                            # Use helper method with built-in retry logic
                            stored_id = await self._store_single_entity(session, entity)

                            if stored_id:
                                stored_count += 1
                                logger.debug(
                                    f"✅ [MEMGRAPH STORAGE] Entity stored successfully | "
                                    f"entity_id={entity.entity_id} | "
                                    f"stored_id={stored_id}"
                                )
                            else:
                                failed_count += 1
                                logger.warning(
                                    f"⚠️ [MEMGRAPH STORAGE] Entity storage returned no record | "
                                    f"entity_id={entity.entity_id}"
                                )

                        except Exception as e:
                            failed_count += 1
                            logger.error(
                                f"❌ [MEMGRAPH STORAGE] Failed to store entity | "
                                f"entity_id={entity.entity_id} | "
                                f"entity_type={entity.entity_type.value} | "
                                f"name={entity.name} | "
                                f"source_path={entity.source_path} | "
                                f"error={str(e)} | "
                                f"error_type={type(e).__name__}",
                                exc_info=True,
                            )
                            continue

                duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000

                # Log final storage results
                logger.info(
                    f"✅ [MEMGRAPH STORAGE] Entity storage completed | "
                    f"stored={stored_count} | "
                    f"failed={failed_count} | "
                    f"total={len(entities)} | "
                    f"success_rate={stored_count/len(entities)*100:.1f}% | "
                    f"duration_ms={duration_ms:.2f}"
                )

                return stored_count

            except Exception as e:
                duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                logger.error(
                    f"❌ [MEMGRAPH STORAGE] Batch entity storage failed catastrophically | "
                    f"total_entities={len(entities)} | "
                    f"stored_before_failure={stored_count} | "
                    f"failed={failed_count} | "
                    f"duration_ms={duration_ms:.2f} | "
                    f"error={str(e)} | "
                    f"error_type={type(e).__name__}",
                    exc_info=True,
                )
                raise

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def _store_single_relationship(
        self, session, rel: KnowledgeRelationship
    ) -> Optional[str]:
        """
        Store a single relationship with retry logic for TransientErrors.

        This is a helper method called by store_relationships() to handle individual
        relationship storage with proper retry logic for concurrent access.

        Args:
            session: Active Memgraph session
            rel: Relationship to store

        Returns:
            Stored relationship_id if successful, None otherwise
        """
        # Create relationship with properties
        # Use MERGE for entities to create stub nodes for external references
        query = """
        MERGE (source:Entity {entity_id: $source_id})
        ON CREATE SET source.name = $source_id, source.entity_type = 'reference', source.is_stub = true
        MERGE (target:Entity {entity_id: $target_id})
        ON CREATE SET target.name = $target_id, target.entity_type = 'reference', target.is_stub = true
        MERGE (source)-[r:RELATES {relationship_type: $rel_type, relationship_id: $rel_id}]->(target)
        ON CREATE SET
            r.confidence_score = $confidence_score,
            r.properties = $properties,
            r.created_at = $created_at
        ON MATCH SET
            r.confidence_score = $confidence_score,
            r.properties = $properties,
            r.updated_at = $updated_at
        RETURN r.relationship_id as stored_id
        """

        params = {
            "source_id": rel.source_entity_id,
            "target_id": rel.target_entity_id,
            "rel_type": rel.relationship_type.value,
            "rel_id": rel.relationship_id,
            "confidence_score": rel.confidence_score,
            "properties": rel.properties,
            "created_at": (
                rel.created_at.isoformat()
                if rel.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await session.run(query, params)
        record = await result.single()

        if record:
            return record["stored_id"]

        return None

    async def store_relationships(
        self, relationships: List[KnowledgeRelationship]
    ) -> int:
        """
        Store relationships between entities with comprehensive logging.

        Args:
            relationships: List of relationships to store

        Returns:
            Number of relationships successfully stored
        """
        if not relationships:
            logger.debug("store_relationships called with empty relationship list")
            return 0

        # Log storage operation start
        logger.info(
            f"🔗 [MEMGRAPH STORAGE] Starting relationship storage | "
            f"relationship_count={len(relationships)} | "
            f"types={list(set(r.relationship_type.value for r in relationships))[:5]}"
        )

        stored_count = 0
        failed_count = 0
        start_time = datetime.now(timezone.utc)

        # Acquire semaphore to limit concurrent writes (prevents TransientErrors)
        async with self._write_semaphore:
            self._total_writes += 1

            try:
                async with self.driver.session() as session:
                    for idx, rel in enumerate(relationships):
                        try:
                            # Log before each relationship write
                            logger.debug(
                                f"🔗 [MEMGRAPH STORAGE] Storing relationship {idx+1}/{len(relationships)} | "
                                f"relationship_id={rel.relationship_id} | "
                                f"type={rel.relationship_type.value} | "
                                f"source={rel.source_entity_id} | "
                                f"target={rel.target_entity_id} | "
                                f"confidence={rel.confidence_score:.2f}"
                            )

                            # Use helper method with built-in retry logic
                            stored_id = await self._store_single_relationship(
                                session, rel
                            )

                            if stored_id:
                                stored_count += 1
                                logger.debug(
                                    f"✅ [MEMGRAPH STORAGE] Relationship stored successfully | "
                                    f"relationship_id={rel.relationship_id} | "
                                    f"stored_id={stored_id}"
                                )
                            else:
                                failed_count += 1
                                logger.warning(
                                    f"⚠️ [MEMGRAPH STORAGE] Relationship storage returned no record | "
                                    f"relationship_id={rel.relationship_id} | "
                                    f"source={rel.source_entity_id} | "
                                    f"target={rel.target_entity_id}"
                                )

                        except Exception as e:
                            failed_count += 1
                            logger.error(
                                f"❌ [MEMGRAPH STORAGE] Failed to store relationship | "
                                f"relationship_id={rel.relationship_id} | "
                                f"type={rel.relationship_type.value} | "
                                f"source={rel.source_entity_id} | "
                                f"target={rel.target_entity_id} | "
                                f"error={str(e)} | "
                                f"error_type={type(e).__name__}",
                                exc_info=True,
                            )
                            continue

                duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000

                # Log final storage results
                logger.info(
                    f"✅ [MEMGRAPH STORAGE] Relationship storage completed | "
                    f"stored={stored_count} | "
                    f"failed={failed_count} | "
                    f"total={len(relationships)} | "
                    f"success_rate={stored_count/len(relationships)*100:.1f}% | "
                    f"duration_ms={duration_ms:.2f}"
                )

                return stored_count

            except Exception as e:
                duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                logger.error(
                    f"❌ [MEMGRAPH STORAGE] Batch relationship storage failed catastrophically | "
                    f"total_relationships={len(relationships)} | "
                    f"stored_before_failure={stored_count} | "
                    f"failed={failed_count} | "
                    f"duration_ms={duration_ms:.2f} | "
                    f"error={str(e)} | "
                    f"error_type={type(e).__name__}",
                    exc_info=True,
                )
                raise

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[KnowledgeEntity]:
        """
        Search entities by name, description, and properties.

        Args:
            query: Search query string
            entity_type: Filter by entity type
            limit: Maximum results to return
            min_confidence: Minimum confidence score

        Returns:
            List of matching entities
        """
        try:
            async with self.driver.session() as session:
                # Build dynamic query based on filters
                cypher_query = """
                MATCH (e:Entity)
                WHERE
                    e.confidence_score >= $min_confidence
                    AND (
                        toLower(e.name) CONTAINS toLower($query)
                        OR toLower(e.description) CONTAINS toLower($query)
                    )
                """

                params = {
                    "query": query,
                    "min_confidence": min_confidence,
                    "limit": limit,
                }

                if entity_type:
                    cypher_query += " AND e.entity_type = $entity_type"
                    params["entity_type"] = entity_type

                cypher_query += """
                RETURN e
                ORDER BY e.confidence_score DESC, e.name ASC
                LIMIT $limit
                """

                result = await session.run(cypher_query, params)
                records = await result.data()

                entities = []
                for record in records:
                    entity_data = record["e"]
                    entity = self._create_entity_from_node(entity_data)
                    entities.append(entity)

                return entities

        except Exception as e:
            logger.error(f"Entity search failed: {e}")
            return []

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def get_entity_relationships(
        self, entity_id: str, relationship_type: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get relationships for a specific entity.

        Args:
            entity_id: Entity ID to find relationships for
            relationship_type: Filter by relationship type
            limit: Maximum relationships to return

        Returns:
            List of relationship data with connected entities
        """
        try:
            async with self.driver.session() as session:
                cypher_query = """
                MATCH (source:Entity {entity_id: $entity_id})-[r:RELATES]-(target:Entity)
                """

                params = {"entity_id": entity_id, "limit": limit}

                if relationship_type:
                    cypher_query += " WHERE r.relationship_type = $relationship_type"
                    params["relationship_type"] = relationship_type

                cypher_query += """
                RETURN r, source, target
                LIMIT $limit
                """

                result = await session.run(cypher_query, params)
                records = await result.data()

                relationships = []
                for record in records:
                    rel_data = {
                        "relationship": record["r"],
                        "source_entity": self._create_entity_from_node(
                            record["source"]
                        ),
                        "target_entity": self._create_entity_from_node(
                            record["target"]
                        ),
                    }
                    relationships.append(rel_data)

                return relationships

        except Exception as e:
            logger.error(f"Failed to get relationships for entity {entity_id}: {e}")
            return []

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def find_similar_entities(
        self, embedding: List[float], similarity_threshold: float = 0.8, limit: int = 10
    ) -> List[KnowledgeEntity]:
        """
        Find entities similar to given embedding using cosine similarity.

        Args:
            embedding: Query embedding vector
            similarity_threshold: Minimum similarity score
            limit: Maximum results to return

        Returns:
            List of similar entities with similarity scores
        """
        # TODO: Implement vector similarity search
        # This requires Memgraph with vector indexing support
        logger.warning("Vector similarity search not yet implemented")
        return []

    @retry_on_transient_error(max_attempts=3, initial_backoff=0.1)
    async def get_entity_statistics(self) -> Dict[str, Any]:
        """Get statistics about entities and relationships in the graph"""
        try:
            async with self.driver.session() as session:
                # Entity counts by type
                entity_stats = await session.run(
                    """
                    MATCH (e:Entity)
                    RETURN e.entity_type as type, count(*) as count
                    ORDER BY count DESC
                """
                )
                entity_counts = await entity_stats.data()

                # Relationship counts by type
                rel_stats = await session.run(
                    """
                    MATCH ()-[r:RELATES]->()
                    RETURN r.relationship_type as type, count(*) as count
                    ORDER BY count DESC
                """
                )
                relationship_counts = await rel_stats.data()

                # Total counts
                total_entities = await session.run(
                    "MATCH (e:Entity) RETURN count(*) as total"
                )
                total_rels = await session.run(
                    "MATCH ()-[r:RELATES]->() RETURN count(*) as total"
                )

                total_entities_record = await total_entities.single()
                total_rels_record = await total_rels.single()

                return {
                    "total_entities": (
                        total_entities_record["total"] if total_entities_record else 0
                    ),
                    "total_relationships": (
                        total_rels_record["total"] if total_rels_record else 0
                    ),
                    "entity_counts_by_type": {
                        item["type"]: item["count"] for item in entity_counts
                    },
                    "relationship_counts_by_type": {
                        item["type"]: item["count"] for item in relationship_counts
                    },
                }

        except Exception as e:
            logger.error(f"Failed to get entity statistics: {e}")
            return {}

    async def _initialize_schema(self):
        """Initialize Memgraph schema with indexes and constraints"""
        try:
            async with self.driver.session() as session:
                # Create indexes for performance
                indexes = [
                    "CREATE INDEX ON :Entity(entity_id);",
                    "CREATE INDEX ON :Entity(entity_type);",
                    "CREATE INDEX ON :Entity(source_path);",
                    "CREATE INDEX ON :Entity(name);",
                    "CREATE INDEX ON :Entity(confidence_score);",
                ]

                for index_query in indexes:
                    try:
                        await session.run(index_query)
                    except Exception as e:
                        # Index might already exist
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Failed to create index: {e}")

                logger.info("Schema initialization completed")

        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")

    async def _store_entity_embedding(
        self, session, entity_id: str, embedding: List[float]
    ):
        """Store entity embedding vector (for future vector search)"""
        # TODO: Implement embedding storage
        # This will require proper vector storage solution
        pass

    def _create_entity_from_node(self, node_data: Dict[str, Any]) -> KnowledgeEntity:
        """Convert Memgraph node data to KnowledgeEntity object"""
        from models.entity_models import EntityMetadata

        # Handle entity type enum conversion
        entity_type_str = node_data.get("entity_type", "CONCEPT")
        try:
            entity_type = EntityType(entity_type_str)
        except ValueError:
            entity_type = EntityType.CONCEPT

        # Create metadata object
        metadata = EntityMetadata(
            file_hash=node_data.get("file_hash"),
            extraction_method=node_data.get("extraction_method", "memgraph_retrieval"),
            extraction_confidence=node_data.get("confidence_score", 0.0),
            created_at=(
                datetime.fromisoformat(node_data["created_at"])
                if node_data.get("created_at")
                else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(node_data["updated_at"])
                if node_data.get("updated_at")
                else datetime.now(timezone.utc)
            ),
        )

        return KnowledgeEntity(
            entity_id=node_data["entity_id"],
            name=node_data.get("name", ""),
            entity_type=entity_type,
            description=node_data.get("description", ""),
            source_path=node_data.get("source_path", ""),
            confidence_score=node_data.get("confidence_score", 0.0),
            source_line_number=node_data.get("source_line_number"),
            properties=node_data.get("properties", {}),
            metadata=metadata,
        )
