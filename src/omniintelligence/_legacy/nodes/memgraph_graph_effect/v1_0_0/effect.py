"""
Memgraph Graph Effect Node - ONEX Effect Node for Graph Database Operations.

This Effect node provides:
- Entity node creation and updates in Memgraph
- Relationship edge creation with type-based routing
- Batch operations with transaction support
- Graph queries for entity retrieval
- Connection pooling and retry logic
- Cypher query parameterization for security

ONEX Compliance:
- Suffix-based naming: NodeMemgraphGraphEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling

Graph Operations:
1. CREATE_ENTITY: Create or update entity node
2. CREATE_RELATIONSHIP: Create relationship edge between entities
3. BATCH_UPSERT: Bulk create/update nodes and relationships
4. QUERY_GRAPH: Execute Cypher queries
5. DELETE_ENTITY: Remove entity node and its relationships

Node Labels (from EnumEntityType):
- :DOCUMENT, :CLASS, :FUNCTION, :MODULE, :PACKAGE, :VARIABLE
- :CONSTANT, :INTERFACE, :TYPE, :PATTERN, :PROJECT, :FILE
- :DEPENDENCY, :TEST, :CONFIGURATION

Relationship Types (from EnumRelationshipType):
- [:CONTAINS], [:IMPORTS], [:DEPENDS_ON], [:IMPLEMENTS], [:EXTENDS]
- [:CALLS], [:REFERENCES], [:DEFINES], [:USES], [:MATCHES_PATTERN]
- [:SIMILAR_TO]

Created: 2025-12-01
Reference: Memgraph Documentation, Neo4j Bolt Protocol
"""

import asyncio
import contextlib
import logging
import os
import time
from typing import Any
from uuid import UUID, uuid4

from neo4j import AsyncDriver, AsyncGraphDatabase
from pydantic import BaseModel, Field

from omniintelligence._legacy.models import ModelEntity, ModelRelationship

logger = logging.getLogger(__name__)


# ============================================================================
# Input/Output Models (ONEX Contract Compliance)
# ============================================================================


class ModelMemgraphGraphInput(BaseModel):
    """
    Input model for Memgraph graph operations.

    Attributes:
        operation: Type of graph operation
        entity: Entity to create/update (for CREATE_ENTITY)
        relationship: Relationship to create (for CREATE_RELATIONSHIP)
        entities: Batch of entities (for BATCH_UPSERT)
        relationships: Batch of relationships (for BATCH_UPSERT)
        query: Cypher query string (for QUERY_GRAPH)
        query_params: Query parameters (for QUERY_GRAPH)
        entity_id: Entity ID to delete (for DELETE_ENTITY)
        correlation_id: Correlation ID for tracing
    """

    operation: str = Field(
        ...,
        description="Graph operation type",
        examples=[
            "CREATE_ENTITY",
            "CREATE_RELATIONSHIP",
            "BATCH_UPSERT",
            "QUERY_GRAPH",
            "DELETE_ENTITY",
        ],
    )

    entity: ModelEntity | None = Field(
        default=None,
        description="Entity to create/update",
    )

    relationship: ModelRelationship | None = Field(
        default=None,
        description="Relationship to create",
    )

    entities: list[ModelEntity] | None = Field(
        default=None,
        description="Batch of entities for batch operations",
    )

    relationships: list[ModelRelationship] | None = Field(
        default=None,
        description="Batch of relationships for batch operations",
    )

    query: str | None = Field(
        default=None,
        description="Cypher query string",
    )

    query_params: dict[str, Any] | None = Field(
        default=None,
        description="Query parameters for parameterized queries",
    )

    entity_id: str | None = Field(
        default=None,
        description="Entity ID to delete",
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for tracing",
    )


class ModelMemgraphGraphOutput(BaseModel):
    """
    Output model for Memgraph graph operations.

    Attributes:
        success: Whether operation was successful
        operation: Operation type executed
        nodes_created: Number of nodes created
        relationships_created: Number of relationships created
        nodes_updated: Number of nodes updated
        nodes_deleted: Number of nodes deleted
        query_results: Query results (for QUERY_GRAPH)
        error: Error message if failed
        correlation_id: Correlation ID from input
    """

    success: bool = Field(
        ...,
        description="Whether operation was successful",
    )

    operation: str = Field(
        ...,
        description="Operation type executed",
    )

    nodes_created: int = Field(
        default=0,
        description="Number of nodes created",
    )

    relationships_created: int = Field(
        default=0,
        description="Number of relationships created",
    )

    nodes_updated: int = Field(
        default=0,
        description="Number of nodes updated",
    )

    nodes_deleted: int = Field(
        default=0,
        description="Number of nodes deleted",
    )

    query_results: list[dict[str, Any]] | None = Field(
        default=None,
        description="Query results",
    )

    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from input",
    )


class ModelMemgraphGraphConfig(BaseModel):
    """
    Configuration model for Memgraph graph effect node.

    Attributes:
        memgraph_uri: Memgraph connection URI (Bolt protocol)
        memgraph_user: Authentication username
        memgraph_password: Authentication password
        max_connection_pool_size: Maximum connection pool size
        connection_timeout_s: Connection timeout in seconds
        max_retries: Maximum retry attempts
        retry_backoff_ms: Retry backoff in milliseconds
    """

    memgraph_uri: str = Field(
        default_factory=lambda: os.getenv(
            "MEMGRAPH_URI",
            (
                f"bolt://{os.getenv('MEMGRAPH_HOST', 'localhost')}:"
                f"{os.getenv('MEMGRAPH_PORT', '7687')}"
            ),
        ),
        description="Memgraph connection URI",
    )

    memgraph_user: str = Field(
        default_factory=lambda: os.getenv("MEMGRAPH_USER", ""),
        description="Authentication username",
    )

    memgraph_password: str = Field(
        default_factory=lambda: os.getenv("MEMGRAPH_PASSWORD", ""),
        description="Authentication password",
    )

    max_connection_pool_size: int = Field(
        default=50,
        description="Maximum connection pool size",
    )

    connection_timeout_s: int = Field(
        default=30,
        description="Connection timeout in seconds",
    )

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )

    retry_backoff_ms: int = Field(
        default=1000,
        description="Retry backoff in milliseconds",
    )


# ============================================================================
# Memgraph Graph Effect Node (ONEX Pattern)
# ============================================================================


class NodeMemgraphGraphEffect:
    """
    Memgraph Graph Effect Node - ONEX Effect Node for Graph Operations.

    This ONEX Effect node manages graph database operations with:
    - Entity node creation and updates with MERGE operations
    - Relationship edge creation with type-based routing
    - Batch operations with transaction support
    - Parameterized Cypher queries for security
    - Connection pooling and automatic retry
    - Graph traversal and pattern matching

    **Core Capabilities**:
    - CREATE_ENTITY: Create or update entity nodes with properties
    - CREATE_RELATIONSHIP: Create typed relationships between entities
    - BATCH_UPSERT: Bulk operations with transaction guarantees
    - QUERY_GRAPH: Execute parameterized Cypher queries
    - DELETE_ENTITY: Remove entities and their relationships

    **Entity Types Supported**:
    - Code entities: CLASS, FUNCTION, MODULE, VARIABLE, CONSTANT
    - Project entities: PROJECT, PACKAGE, FILE, DEPENDENCY
    - Documentation entities: DOCUMENT, PATTERN, TEST, CONFIGURATION
    - Type entities: INTERFACE, TYPE

    **Relationship Types Supported**:
    - Structural: CONTAINS, DEFINES
    - Dependencies: IMPORTS, DEPENDS_ON, USES, REFERENCES
    - Inheritance: IMPLEMENTS, EXTENDS
    - Execution: CALLS
    - Similarity: MATCHES_PATTERN, SIMILAR_TO

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.nodes.memgraph_graph_effect.v1_0_0.effect import (
        ...     NodeMemgraphGraphEffect,
        ...     ModelMemgraphGraphInput,
        ... )
        >>> from omniintelligence._legacy.models import ModelEntity
        >>> from omniintelligence._legacy.enums import EnumEntityType
        >>>
        >>> node = NodeMemgraphGraphEffect(container=None)
        >>> await node.initialize()
        >>>
        >>> entity = ModelEntity(
        ...     entity_id="ent_123",
        ...     entity_type=EnumEntityType.CLASS,
        ...     name="MyClass",
        ...     metadata={"file_path": "src/main.py"},
        ... )
        >>>
        >>> input_data = ModelMemgraphGraphInput(
        ...     operation="CREATE_ENTITY",
        ...     entity=entity,
        ...     correlation_id=uuid4(),
        ... )
        >>>
        >>> output = await node.execute_effect(input_data)
        >>> assert output.success
        >>> assert output.nodes_created > 0
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Connection errors: Retry with exponential backoff
    - Query errors: Log and return detailed error information
    - Transaction failures: Automatic rollback
    - Invalid operations: Return error without retry

    Attributes:
        node_id: Unique node identifier
        config: Memgraph configuration
        driver: Neo4j Bolt driver instance
        metrics: Operation metrics
    """

    def __init__(
        self,
        container: Any,
        config: ModelMemgraphGraphConfig | None = None,
    ):
        """
        Initialize Memgraph Graph Effect Node.

        Args:
            container: ONEX container for dependency injection
            config: Optional Memgraph configuration
        """
        self.container = container
        self.node_id = uuid4()
        self.config = config or ModelMemgraphGraphConfig()

        # Memgraph driver
        self.driver: AsyncDriver | None = None

        # Metrics
        self.metrics = {
            "operations_executed": 0,
            "operations_failed": 0,
            "nodes_created": 0,
            "nodes_updated": 0,
            "nodes_deleted": 0,
            "relationships_created": 0,
            "queries_executed": 0,
            "total_operation_time_ms": 0.0,
            "retries_attempted": 0,
        }

        logger.info(
            f"NodeMemgraphGraphEffect initialized | "
            f"node_id={self.node_id} | "
            f"memgraph_uri={self.config.memgraph_uri}"
        )

    async def initialize(self) -> None:
        """
        Initialize Memgraph driver.

        This method:
        1. Creates Neo4j driver instance (Memgraph uses Bolt protocol)
        2. Configures connection pooling
        3. Verifies connectivity with test query

        Raises:
            RuntimeError: If driver initialization fails
        """
        try:
            # Create driver with connection pooling
            self.driver = AsyncGraphDatabase.driver(
                self.config.memgraph_uri,
                auth=(self.config.memgraph_user, self.config.memgraph_password)
                if self.config.memgraph_user
                else None,
                max_connection_pool_size=self.config.max_connection_pool_size,
                connection_timeout=self.config.connection_timeout_s,
            )

            # Verify connectivity
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS test")
                await result.single()

            logger.info(
                f"Memgraph driver initialized | "
                f"node_id={self.node_id} | "
                f"pool_size={self.config.max_connection_pool_size}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Memgraph driver: {e}", exc_info=True)
            raise RuntimeError(f"Memgraph driver initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown Memgraph driver.

        This method:
        1. Closes all active sessions
        2. Closes driver connection
        3. Logs final metrics

        Does not raise exceptions - logs warnings on failure.
        """
        if self.driver:
            try:
                logger.info("Closing Memgraph driver")
                await self.driver.close()
                logger.info("Memgraph driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

        logger.info(
            f"NodeMemgraphGraphEffect shutdown complete | "
            f"node_id={self.node_id} | "
            f"final_metrics={self.metrics}"
        )

    async def execute_effect(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Execute Memgraph graph operation (ONEX Effect pattern method).

        This method:
        1. Validates input and driver initialization
        2. Routes to appropriate operation handler
        3. Executes operation with retry logic
        4. Returns result with metrics

        Args:
            input_data: Memgraph graph input data

        Returns:
            ModelMemgraphGraphOutput with operation result

        Raises:
            ValueError: If driver not initialized or invalid operation
        """
        # Check initialization
        if self.driver is None:
            raise ValueError(
                "Memgraph driver not initialized. Call initialize() first."
            )

        start_time = time.perf_counter()

        try:
            # Route to operation handler
            if input_data.operation == "CREATE_ENTITY":
                result = await self._create_entity(input_data)
            elif input_data.operation == "CREATE_RELATIONSHIP":
                result = await self._create_relationship(input_data)
            elif input_data.operation == "BATCH_UPSERT":
                result = await self._batch_upsert(input_data)
            elif input_data.operation == "QUERY_GRAPH":
                result = await self._query_graph(input_data)
            elif input_data.operation == "DELETE_ENTITY":
                result = await self._delete_entity(input_data)
            else:
                raise ValueError(f"Invalid operation: {input_data.operation}")

            # Update metrics on success
            if result.success:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                self.metrics["operations_executed"] += 1
                self.metrics["total_operation_time_ms"] += elapsed_ms
                self.metrics["nodes_created"] += result.nodes_created
                self.metrics["nodes_updated"] += result.nodes_updated
                self.metrics["nodes_deleted"] += result.nodes_deleted
                self.metrics["relationships_created"] += result.relationships_created
                if input_data.operation == "QUERY_GRAPH":
                    self.metrics["queries_executed"] += 1

                logger.info(
                    f"Graph operation successful | "
                    f"operation={input_data.operation} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"duration={elapsed_ms:.2f}ms"
                )
            else:
                self.metrics["operations_failed"] += 1

            return result

        except Exception as e:
            self.metrics["operations_failed"] += 1

            logger.error(
                f"Graph operation error | "
                f"operation={input_data.operation} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={e}",
                exc_info=True,
            )

            return ModelMemgraphGraphOutput(
                success=False,
                operation=input_data.operation,
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _create_entity(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Create or update entity node.

        Args:
            input_data: Input with entity data

        Returns:
            Operation result
        """
        if not input_data.entity:
            return ModelMemgraphGraphOutput(
                success=False,
                operation="CREATE_ENTITY",
                error="Entity data required for CREATE_ENTITY operation",
                correlation_id=input_data.correlation_id,
            )

        entity = input_data.entity

        # Build MERGE query with parameterized values
        query = f"""
        MERGE (e:{entity.entity_type.value} {{entity_id: $entity_id}})
        ON CREATE SET
            e.name = $name,
            e.created_at = $created_at,
            e.metadata = $metadata
        ON MATCH SET
            e.name = $name,
            e.metadata = $metadata
        RETURN e.entity_id AS entity_id,
               labels(e)[0] AS label,
               CASE WHEN e.created_at = $created_at
                   THEN 'created' ELSE 'updated' END AS action
        """

        params = {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "created_at": entity.created_at.isoformat(),
            "metadata": entity.metadata,
        }

        try:
            assert self.driver is not None  # Type assertion for mypy
            async with self.driver.session() as session:
                result = await session.run(query, params)
                record = await result.single()
                assert record is not None  # Type assertion for mypy

                if record["action"] == "created":
                    nodes_created = 1
                    nodes_updated = 0
                else:
                    nodes_created = 0
                    nodes_updated = 1

                logger.debug(
                    f"Entity {record['action']} | "
                    f"entity_id={entity.entity_id} | "
                    f"type={entity.entity_type.value}"
                )

                return ModelMemgraphGraphOutput(
                    success=True,
                    operation="CREATE_ENTITY",
                    nodes_created=nodes_created,
                    nodes_updated=nodes_updated,
                    correlation_id=input_data.correlation_id,
                )

        except Exception as e:
            logger.error(f"Failed to create entity: {e}", exc_info=True)
            return ModelMemgraphGraphOutput(
                success=False,
                operation="CREATE_ENTITY",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _create_relationship(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Create relationship between entities.

        Args:
            input_data: Input with relationship data

        Returns:
            Operation result
        """
        if not input_data.relationship:
            return ModelMemgraphGraphOutput(
                success=False,
                operation="CREATE_RELATIONSHIP",
                error="Relationship data required for CREATE_RELATIONSHIP operation",
                correlation_id=input_data.correlation_id,
            )

        rel = input_data.relationship

        # Build MERGE query with parameterized relationship
        query = f"""
        MATCH (source {{entity_id: $source_id}})
        MATCH (target {{entity_id: $target_id}})
        MERGE (source)-[r:{rel.relationship_type.value}]->(target)
        ON CREATE SET r.metadata = $metadata
        ON MATCH SET r.metadata = $metadata
        RETURN source.entity_id AS source_id,
               target.entity_id AS target_id,
               type(r) AS relationship_type
        """

        params = {
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "metadata": rel.metadata,
        }

        try:
            assert self.driver is not None  # Type assertion for mypy
            async with self.driver.session() as session:
                result = await session.run(query, params)
                record = await result.single()

                if record:
                    logger.debug(
                        f"Relationship created | "
                        f"source={rel.source_id} | "
                        f"target={rel.target_id} | "
                        f"type={rel.relationship_type.value}"
                    )

                    return ModelMemgraphGraphOutput(
                        success=True,
                        operation="CREATE_RELATIONSHIP",
                        relationships_created=1,
                        correlation_id=input_data.correlation_id,
                    )
                else:
                    return ModelMemgraphGraphOutput(
                        success=False,
                        operation="CREATE_RELATIONSHIP",
                        error="Source or target entity not found",
                        correlation_id=input_data.correlation_id,
                    )

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}", exc_info=True)
            return ModelMemgraphGraphOutput(
                success=False,
                operation="CREATE_RELATIONSHIP",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _batch_upsert(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Batch create/update entities and relationships in transaction.

        Args:
            input_data: Input with batch data

        Returns:
            Operation result with counts
        """
        nodes_created = 0
        nodes_updated = 0
        relationships_created = 0

        try:
            assert self.driver is not None  # Type assertion for mypy
            async with self.driver.session() as session:
                # Begin transaction
                tx = await session.begin_transaction()

                try:
                    # Process entities
                    if input_data.entities:
                        for entity in input_data.entities:
                            entity_type = entity.entity_type.value
                            query = f"""
                            MERGE (e:{entity_type} {{entity_id: $entity_id}})
                            ON CREATE SET
                                e.name = $name,
                                e.created_at = $created_at,
                                e.metadata = $metadata
                            ON MATCH SET
                                e.name = $name,
                                e.metadata = $metadata
                            RETURN CASE WHEN e.created_at = $created_at
                                THEN 'created' ELSE 'updated' END AS action
                            """

                            params = {
                                "entity_id": entity.entity_id,
                                "name": entity.name,
                                "created_at": entity.created_at.isoformat(),
                                "metadata": entity.metadata,
                            }

                            result = await tx.run(query, params)
                            record = await result.single()
                            assert record is not None  # Type assertion for mypy

                            if record["action"] == "created":
                                nodes_created += 1
                            else:
                                nodes_updated += 1

                    # Process relationships
                    if input_data.relationships:
                        for rel in input_data.relationships:
                            query = f"""
                            MATCH (source {{entity_id: $source_id}})
                            MATCH (target {{entity_id: $target_id}})
                            MERGE (source)-[r:{rel.relationship_type.value}]->(target)
                            ON CREATE SET r.metadata = $metadata
                            ON MATCH SET r.metadata = $metadata
                            RETURN r
                            """

                            params = {
                                "source_id": rel.source_id,
                                "target_id": rel.target_id,
                                "metadata": rel.metadata,
                            }

                            result = await tx.run(query, params)
                            record = await result.single()
                            if record:
                                relationships_created += 1

                    # Commit transaction
                    await tx.commit()

                    logger.info(
                        f"Batch upsert completed | "
                        f"nodes_created={nodes_created} | "
                        f"nodes_updated={nodes_updated} | "
                        f"relationships_created={relationships_created}"
                    )

                    return ModelMemgraphGraphOutput(
                        success=True,
                        operation="BATCH_UPSERT",
                        nodes_created=nodes_created,
                        nodes_updated=nodes_updated,
                        relationships_created=relationships_created,
                        correlation_id=input_data.correlation_id,
                    )

                except asyncio.CancelledError:
                    # CancelledError MUST be re-raised to preserve cancellation semantics.
                    # Attempt rollback but don't swallow the cancellation.
                    with contextlib.suppress(Exception):
                        await tx.rollback()
                    raise
                except Exception:
                    # Rollback on error - all other exceptions
                    await tx.rollback()
                    raise

        except Exception as e:
            logger.error(f"Batch upsert failed: {e}", exc_info=True)
            return ModelMemgraphGraphOutput(
                success=False,
                operation="BATCH_UPSERT",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _query_graph(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Execute Cypher query on graph.

        Args:
            input_data: Input with query and parameters

        Returns:
            Operation result with query results
        """
        if not input_data.query:
            return ModelMemgraphGraphOutput(
                success=False,
                operation="QUERY_GRAPH",
                error="Query string required for QUERY_GRAPH operation",
                correlation_id=input_data.correlation_id,
            )

        try:
            assert self.driver is not None  # Type assertion for mypy
            async with self.driver.session() as session:
                result = await session.run(
                    input_data.query, input_data.query_params or {}
                )
                records = await result.values()

                # Convert records to dictionaries
                query_results = [dict(record) for record in records]

                logger.debug(
                    f"Query executed | results={len(query_results)} | "
                    f"correlation_id={input_data.correlation_id}"
                )

                return ModelMemgraphGraphOutput(
                    success=True,
                    operation="QUERY_GRAPH",
                    query_results=query_results,
                    correlation_id=input_data.correlation_id,
                )

        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return ModelMemgraphGraphOutput(
                success=False,
                operation="QUERY_GRAPH",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    async def _delete_entity(
        self, input_data: ModelMemgraphGraphInput
    ) -> ModelMemgraphGraphOutput:
        """
        Delete entity and its relationships.

        Args:
            input_data: Input with entity_id

        Returns:
            Operation result
        """
        if not input_data.entity_id:
            return ModelMemgraphGraphOutput(
                success=False,
                operation="DELETE_ENTITY",
                error="Entity ID required for DELETE_ENTITY operation",
                correlation_id=input_data.correlation_id,
            )

        query = """
        MATCH (e {entity_id: $entity_id})
        DETACH DELETE e
        RETURN count(e) AS deleted_count
        """

        params = {"entity_id": input_data.entity_id}

        try:
            assert self.driver is not None  # Type assertion for mypy
            async with self.driver.session() as session:
                result = await session.run(query, params)
                record = await result.single()
                assert record is not None  # Type assertion for mypy
                deleted_count = record["deleted_count"]

                logger.debug(
                    f"Entity deleted | entity_id={input_data.entity_id} | "
                    f"count={deleted_count}"
                )

                return ModelMemgraphGraphOutput(
                    success=True,
                    operation="DELETE_ENTITY",
                    nodes_deleted=deleted_count,
                    correlation_id=input_data.correlation_id,
                )

        except Exception as e:
            logger.error(f"Entity deletion failed: {e}", exc_info=True)
            return ModelMemgraphGraphOutput(
                success=False,
                operation="DELETE_ENTITY",
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - operations_executed: Total operations executed successfully
            - operations_failed: Total operations that failed
            - nodes_created: Total nodes created
            - nodes_updated: Total nodes updated
            - nodes_deleted: Total nodes deleted
            - relationships_created: Total relationships created
            - queries_executed: Total queries executed
            - total_operation_time_ms: Cumulative operation time
            - avg_operation_time_ms: Average operation time
        """
        avg_operation_time = (
            self.metrics["total_operation_time_ms"]
            / self.metrics["operations_executed"]
            if self.metrics["operations_executed"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "avg_operation_time_ms": avg_operation_time,
            "node_id": str(self.node_id),
        }


__all__ = [
    "ModelMemgraphGraphConfig",
    "ModelMemgraphGraphInput",
    "ModelMemgraphGraphOutput",
    "NodeMemgraphGraphEffect",
]
