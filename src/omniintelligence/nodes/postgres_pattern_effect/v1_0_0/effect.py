"""
PostgreSQL Pattern Effect Node - ONEX Effect Node for Pattern Storage.

This Effect node provides:
- Pattern storage and retrieval in PostgreSQL
- Pattern lineage tracking across 4 phases
- Full-text search on pattern names and metadata
- Batch operations with transaction support
- Connection pooling and retry logic

ONEX Compliance:
- Suffix-based naming: NodePostgresPatternEffect
- Effect pattern: async execute_effect() method
- Strong typing with Pydantic models
- Correlation ID preservation
- Comprehensive error handling

Pattern Operations:
1. store_pattern: Store pattern with metadata
2. store_lineage: Store complete pattern lineage (all 4 phases)
3. query_patterns: Query patterns by criteria
4. update_scores: Update pattern confidence scores
5. get_lineage: Get complete lineage for a pattern
6. search_patterns: Full-text search for patterns

Created: 2025-12-02
Reference: Pattern Learning Compute Node, Qdrant Vector Effect Node
"""

import hashlib
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Input/Output Models (ONEX Contract Compliance)
# ============================================================================


class ModelPostgresPatternInput(BaseModel):
    """
    Input model for PostgreSQL pattern operations.

    Attributes:
        operation: Operation type (store_pattern, store_lineage, query_patterns, etc.)
        patterns: List of patterns to store
        lineage: Pattern lineage data across 4 phases
        query_params: Query parameters for pattern search
        pattern_id: Pattern ID for get/update operations
        search_query: Full-text search query string
        scores: Scores to update
        correlation_id: Correlation ID for tracing
    """

    operation: str = Field(
        ...,
        description="Operation type",
        examples=[
            "store_pattern",
            "store_lineage",
            "query_patterns",
            "update_scores",
            "get_lineage",
            "search_patterns",
        ],
    )

    patterns: list[dict[str, Any]] | None = Field(
        default=None,
        description="Patterns to store",
    )

    lineage: dict[str, Any] | None = Field(
        default=None,
        description="Pattern lineage across 4 phases",
    )

    query_params: dict[str, Any] | None = Field(
        default=None,
        description="Query parameters for pattern search",
    )

    pattern_id: str | None = Field(
        default=None,
        description="Pattern ID for get/update operations",
    )

    search_query: str | None = Field(
        default=None,
        description="Full-text search query string",
    )

    scores: dict[str, float] | None = Field(
        default=None,
        description="Scores to update",
    )

    limit: int = Field(
        default=50,
        description="Limit for query results",
    )

    offset: int = Field(
        default=0,
        description="Offset for query results",
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for tracing",
    )


class ModelPostgresPatternOutput(BaseModel):
    """
    Output model for PostgreSQL pattern operations.

    Attributes:
        success: Whether operation succeeded
        operation: Operation that was executed
        patterns_stored: Number of patterns stored
        lineage_id: ID of stored lineage
        query_results: Query results
        total_count: Total count for pagination
        error: Error message if failed
        correlation_id: Correlation ID from input
        metadata: Additional operation metadata
    """

    success: bool = Field(
        ...,
        description="Whether operation succeeded",
    )

    operation: str = Field(
        ...,
        description="Operation that was executed",
    )

    patterns_stored: int = Field(
        default=0,
        description="Number of patterns stored",
    )

    lineage_id: str | None = Field(
        default=None,
        description="ID of stored lineage",
    )

    pattern_id: str | None = Field(
        default=None,
        description="ID of stored pattern",
    )

    query_results: list[dict[str, Any]] | None = Field(
        default=None,
        description="Query results",
    )

    total_count: int | None = Field(
        default=None,
        description="Total count for pagination",
    )

    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from input",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional operation metadata",
    )


class ModelPostgresPatternConfig(BaseModel):
    """
    Configuration model for PostgreSQL pattern effect node.

    Attributes:
        database_url: PostgreSQL connection URL
        postgres_host: PostgreSQL host
        postgres_port: PostgreSQL port
        postgres_user: PostgreSQL user
        postgres_password: PostgreSQL password
        postgres_database: PostgreSQL database name
        enable_full_text_search: Enable full-text search on patterns
        enable_lineage_tracking: Track complete pattern lineage
        batch_size: Batch size for bulk operations
        max_retries: Maximum retry attempts
        retry_backoff_ms: Retry backoff in milliseconds
        connection_pool_min: Minimum pool size
        connection_pool_max: Maximum pool size
        auto_create_tables: Auto-create tables if not exist
    """

    database_url: str | None = Field(
        default_factory=lambda: os.getenv("DATABASE_URL"),
        description="PostgreSQL connection URL (takes precedence)",
    )

    postgres_host: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"),
        description="PostgreSQL host",
    )

    postgres_port: int = Field(
        default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")),
        description="PostgreSQL port",
    )

    postgres_user: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"),
        description="PostgreSQL user",
    )

    postgres_password: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""),
        description="PostgreSQL password",
    )

    postgres_database: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_DATABASE", "omniintelligence"),
        description="PostgreSQL database name",
    )

    enable_full_text_search: bool = Field(
        default=True,
        description="Enable full-text search on patterns",
    )

    enable_lineage_tracking: bool = Field(
        default=True,
        description="Track complete pattern lineage",
    )

    batch_size: int = Field(
        default=50,
        description="Batch size for bulk operations",
    )

    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts",
    )

    retry_backoff_ms: int = Field(
        default=1000,
        description="Retry backoff in milliseconds",
    )

    connection_pool_min: int = Field(
        default=5,
        description="Minimum pool size",
    )

    connection_pool_max: int = Field(
        default=20,
        description="Maximum pool size",
    )

    auto_create_tables: bool = Field(
        default=True,
        description="Auto-create tables if not exist",
    )

    def get_dsn(self) -> str:
        """Get the database connection string."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )


# ============================================================================
# PostgreSQL Pattern Effect Node (ONEX Pattern)
# ============================================================================


class NodePostgresPatternEffect:
    """
    PostgreSQL Pattern Effect Node - ONEX Effect Node for Pattern Storage.

    This ONEX Effect node stores and retrieves patterns in PostgreSQL with:
    - Pattern storage with metadata and scoring
    - Pattern lineage tracking across 4 phases
    - Full-text search capabilities
    - Batch operations with transaction support
    - Connection pooling and automatic retry

    **Core Capabilities**:
    - store_pattern: Store pattern with metadata
    - store_lineage: Store complete pattern lineage (all 4 phases)
    - query_patterns: Query patterns by criteria
    - update_scores: Update pattern confidence scores
    - get_lineage: Get complete lineage for a pattern
    - search_patterns: Full-text search for patterns

    **Lineage Phases**:
    - Foundation: Basic structural pattern matching
    - Matching: Semantic matching and refinement
    - Validation: Pattern validation and scoring
    - Traceability: Complete lineage and traceability

    **Usage**:
        >>> from uuid import uuid4
        >>> from omniintelligence.nodes.postgres_pattern_effect.v1_0_0.effect import (
        ...     NodePostgresPatternEffect,
        ...     ModelPostgresPatternInput,
        ... )
        >>>
        >>> node = NodePostgresPatternEffect(container=None)
        >>> await node.initialize()
        >>>
        >>> # Store a pattern
        >>> input_data = ModelPostgresPatternInput(
        ...     operation="store_pattern",
        ...     patterns=[{
        ...         "pattern_name": "singleton",
        ...         "pattern_type": "creational",
        ...         "project_name": "myproject",
        ...         "confidence_score": 0.95,
        ...         "metadata": {"language": "python"},
        ...     }],
        ...     correlation_id=uuid4(),
        ... )
        >>>
        >>> output = await node.execute_effect(input_data)
        >>> assert output.success
        >>> assert output.patterns_stored > 0
        >>>
        >>> await node.shutdown()

    **Error Handling**:
    - Connection errors: Retry with exponential backoff
    - Constraint violations: Log and skip
    - Invalid operations: Return error without retry

    Attributes:
        node_id: Unique node identifier
        config: PostgreSQL configuration
        pool: Connection pool
        metrics: Operation metrics
    """

    def __init__(
        self,
        container: Any,
        config: ModelPostgresPatternConfig | None = None,
    ):
        """
        Initialize PostgreSQL Pattern Effect Node.

        Args:
            container: ONEX container for dependency injection
            config: Optional PostgreSQL configuration
        """
        self.container = container
        self.node_id = uuid4()
        self.config = config or ModelPostgresPatternConfig()

        # Connection pool
        self.pool: asyncpg.Pool | None = None

        # Metrics
        self.metrics = {
            "patterns_stored": 0,
            "lineages_stored": 0,
            "queries_executed": 0,
            "searches_performed": 0,
            "updates_executed": 0,
            "operations_failed": 0,
            "total_operation_time_ms": 0.0,
            "retries_attempted": 0,
        }

        logger.info(
            f"NodePostgresPatternEffect initialized | "
            f"node_id={self.node_id} | "
            f"host={self.config.postgres_host}"
        )

    async def initialize(self) -> None:
        """
        Initialize PostgreSQL connection pool and create tables.

        This method:
        1. Creates connection pool
        2. Verifies connectivity
        3. Creates tables if auto_create_tables is enabled

        Raises:
            RuntimeError: If initialization fails
        """
        try:
            dsn = self.config.get_dsn()

            self.pool = await asyncpg.create_pool(
                dsn,
                min_size=self.config.connection_pool_min,
                max_size=self.config.connection_pool_max,
            )

            # Verify connection
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            logger.info(
                f"PostgreSQL pool initialized | "
                f"node_id={self.node_id} | "
                f"pool_size={self.config.connection_pool_min}-{self.config.connection_pool_max}"
            )

            # Auto-create tables if enabled
            if self.config.auto_create_tables:
                await self._create_tables()

        except Exception as e:
            logger.error(
                f"Failed to initialize PostgreSQL pool: {e}", exc_info=True
            )
            raise RuntimeError(f"PostgreSQL pool initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown PostgreSQL connection pool.

        This method:
        1. Closes all connections in the pool
        2. Logs final metrics

        Does not raise exceptions - logs warnings on failure.
        """
        if self.pool:
            try:
                await self.pool.close()
                logger.info("PostgreSQL pool closed successfully")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")

        logger.info(
            f"NodePostgresPatternEffect shutdown complete | "
            f"node_id={self.node_id} | "
            f"final_metrics={self.metrics}"
        )

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        if self.pool is None:
            return

        create_patterns_table = """
        CREATE TABLE IF NOT EXISTS patterns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pattern_id VARCHAR(255) UNIQUE NOT NULL,
            pattern_name VARCHAR(255) NOT NULL,
            pattern_type VARCHAR(50),
            project_name VARCHAR(255),
            confidence_score FLOAT DEFAULT 0.0,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_patterns_pattern_id ON patterns(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_patterns_project ON patterns(project_name);
        CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_patterns_score ON patterns(confidence_score DESC);
        CREATE INDEX IF NOT EXISTS idx_patterns_metadata_gin ON patterns USING GIN(metadata);
        """

        create_lineage_table = """
        CREATE TABLE IF NOT EXISTS pattern_lineage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            lineage_id VARCHAR(255) UNIQUE NOT NULL,
            pattern_id VARCHAR(255) REFERENCES patterns(pattern_id) ON DELETE CASCADE,
            source_code_hash VARCHAR(64),
            project_name VARCHAR(255),
            foundation_phase JSONB DEFAULT '{}',
            matching_phase JSONB DEFAULT '{}',
            validation_phase JSONB DEFAULT '{}',
            traceability_phase JSONB DEFAULT '{}',
            correlation_id VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_lineage_pattern ON pattern_lineage(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_project ON pattern_lineage(project_name);
        CREATE INDEX IF NOT EXISTS idx_lineage_correlation ON pattern_lineage(correlation_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_code_hash ON pattern_lineage(source_code_hash);
        """

        create_matches_table = """
        CREATE TABLE IF NOT EXISTS pattern_matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pattern_id VARCHAR(255) REFERENCES patterns(pattern_id) ON DELETE CASCADE,
            source_code TEXT,
            file_path VARCHAR(500),
            line_start INTEGER,
            line_end INTEGER,
            confidence FLOAT DEFAULT 0.0,
            metadata JSONB DEFAULT '{}',
            matched_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_matches_pattern ON pattern_matches(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_matches_file ON pattern_matches(file_path);
        CREATE INDEX IF NOT EXISTS idx_matches_confidence ON pattern_matches(confidence DESC);
        """

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(create_patterns_table)
                await conn.execute(create_lineage_table)
                await conn.execute(create_matches_table)

            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}", exc_info=True)
            raise

    async def execute_effect(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Execute PostgreSQL pattern operation (ONEX Effect pattern method).

        This method:
        1. Validates operation and parameters
        2. Routes to appropriate operation handler
        3. Executes operation with retry logic
        4. Returns operation result

        Args:
            input_data: PostgreSQL pattern operation input data

        Returns:
            ModelPostgresPatternOutput with operation result

        Raises:
            ValueError: If pool not initialized or invalid parameters
        """
        # Check initialization
        if self.pool is None:
            raise ValueError(
                "PostgreSQL pool not initialized. Call initialize() first."
            )

        start_time = time.perf_counter()

        try:
            # Route to operation handler
            if input_data.operation == "store_pattern":
                result = await self._store_patterns(input_data)
            elif input_data.operation == "store_lineage":
                result = await self._store_lineage(input_data)
            elif input_data.operation == "query_patterns":
                result = await self._query_patterns(input_data)
            elif input_data.operation == "update_scores":
                result = await self._update_scores(input_data)
            elif input_data.operation == "get_lineage":
                result = await self._get_lineage(input_data)
            elif input_data.operation == "search_patterns":
                result = await self._search_patterns(input_data)
            else:
                return ModelPostgresPatternOutput(
                    success=False,
                    operation=input_data.operation,
                    error=f"Unknown operation: {input_data.operation}",
                    correlation_id=input_data.correlation_id,
                )

            # Update metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_operation_time_ms"] += elapsed_ms

            if result.success:
                logger.info(
                    f"Pattern operation completed | "
                    f"operation={input_data.operation} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"duration={elapsed_ms:.2f}ms"
                )
            else:
                logger.error(
                    f"Pattern operation failed | "
                    f"operation={input_data.operation} | "
                    f"correlation_id={input_data.correlation_id} | "
                    f"error={result.error}"
                )

            return result

        except Exception as e:
            self.metrics["operations_failed"] += 1

            logger.error(
                f"Pattern operation error | "
                f"operation={input_data.operation} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={e}",
                exc_info=True,
            )

            return ModelPostgresPatternOutput(
                success=False,
                operation=input_data.operation,
                error=str(e),
                correlation_id=input_data.correlation_id,
            )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _store_patterns(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Store patterns in PostgreSQL.

        Args:
            input_data: Input data with patterns

        Returns:
            Output with operation result
        """
        if not input_data.patterns:
            return ModelPostgresPatternOutput(
                success=False,
                operation="store_pattern",
                error="patterns list is required for store_pattern operation",
                correlation_id=input_data.correlation_id,
            )

        assert self.pool is not None  # Type assertion for mypy

        patterns_stored = 0
        last_pattern_id = None

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for pattern in input_data.patterns:
                    # Generate pattern_id if not provided
                    pattern_id = pattern.get("pattern_id") or str(uuid4())
                    pattern_name = pattern.get("pattern_name", "unnamed")
                    pattern_type = pattern.get("pattern_type", "unknown")
                    project_name = pattern.get("project_name", "")
                    confidence_score = pattern.get("confidence_score", 0.0)
                    metadata = pattern.get("metadata", {})

                    try:
                        await conn.execute(
                            """
                            INSERT INTO patterns (
                                pattern_id, pattern_name, pattern_type,
                                project_name, confidence_score, metadata
                            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                            ON CONFLICT (pattern_id) DO UPDATE SET
                                pattern_name = EXCLUDED.pattern_name,
                                pattern_type = EXCLUDED.pattern_type,
                                project_name = EXCLUDED.project_name,
                                confidence_score = CASE
                                    WHEN EXCLUDED.confidence_score > patterns.confidence_score
                                    THEN EXCLUDED.confidence_score
                                    ELSE patterns.confidence_score
                                END,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                            """,
                            pattern_id,
                            pattern_name,
                            pattern_type,
                            project_name,
                            confidence_score,
                            str(metadata) if isinstance(metadata, dict) else metadata,
                        )
                        patterns_stored += 1
                        last_pattern_id = pattern_id
                    except Exception as e:
                        logger.warning(
                            f"Failed to store pattern: {e} | pattern_id={pattern_id}"
                        )

        self.metrics["patterns_stored"] += patterns_stored

        return ModelPostgresPatternOutput(
            success=True,
            operation="store_pattern",
            patterns_stored=patterns_stored,
            pattern_id=last_pattern_id,
            correlation_id=input_data.correlation_id,
            metadata={"total_in_batch": len(input_data.patterns)},
        )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _store_lineage(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Store pattern lineage in PostgreSQL.

        Args:
            input_data: Input data with lineage

        Returns:
            Output with operation result
        """
        if not input_data.lineage:
            return ModelPostgresPatternOutput(
                success=False,
                operation="store_lineage",
                error="lineage data is required for store_lineage operation",
                correlation_id=input_data.correlation_id,
            )

        assert self.pool is not None  # Type assertion for mypy

        lineage = input_data.lineage
        lineage_id = str(uuid4())
        pattern_id = lineage.get("pattern_id")
        source_code = lineage.get("source_code", "")
        source_code_hash = hashlib.sha256(source_code.encode()).hexdigest()[:64]
        project_name = lineage.get("project_name", "")
        foundation_phase = lineage.get("foundation_phase", {})
        matching_phase = lineage.get("matching_phase", {})
        validation_phase = lineage.get("validation_phase", {})
        traceability_phase = lineage.get("traceability_phase", {})

        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO pattern_lineage (
                        lineage_id, pattern_id, source_code_hash, project_name,
                        foundation_phase, matching_phase, validation_phase,
                        traceability_phase, correlation_id
                    ) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb, $9)
                    """,
                    lineage_id,
                    pattern_id,
                    source_code_hash,
                    project_name,
                    str(foundation_phase),
                    str(matching_phase),
                    str(validation_phase),
                    str(traceability_phase),
                    str(input_data.correlation_id),
                )

                self.metrics["lineages_stored"] += 1

                return ModelPostgresPatternOutput(
                    success=True,
                    operation="store_lineage",
                    lineage_id=lineage_id,
                    correlation_id=input_data.correlation_id,
                    metadata={
                        "pattern_id": pattern_id,
                        "source_code_hash": source_code_hash,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to store lineage: {e}", exc_info=True)
                return ModelPostgresPatternOutput(
                    success=False,
                    operation="store_lineage",
                    error=str(e),
                    correlation_id=input_data.correlation_id,
                )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _query_patterns(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Query patterns from PostgreSQL.

        Args:
            input_data: Input data with query parameters

        Returns:
            Output with query results
        """
        assert self.pool is not None  # Type assertion for mypy

        query_params = input_data.query_params or {}
        project_name = query_params.get("project_name")
        pattern_type = query_params.get("pattern_type")
        min_confidence = query_params.get("min_confidence", 0.0)

        async with self.pool.acquire() as conn:
            # Build query
            query = "SELECT * FROM patterns WHERE confidence_score >= $1"
            params: list[Any] = [min_confidence]
            param_idx = 2

            if project_name:
                query += f" AND project_name = ${param_idx}"
                params.append(project_name)
                param_idx += 1

            if pattern_type:
                query += f" AND pattern_type = ${param_idx}"
                params.append(pattern_type)
                param_idx += 1

            query += f" ORDER BY confidence_score DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
            params.extend([input_data.limit, input_data.offset])

            # Execute query
            rows = await conn.fetch(query, *params)

            # Get total count
            count_query = "SELECT COUNT(*) FROM patterns WHERE confidence_score >= $1"
            count_params: list[Any] = [min_confidence]
            if project_name:
                count_query += " AND project_name = $2"
                count_params.append(project_name)
            if pattern_type:
                count_query += f" AND pattern_type = ${len(count_params) + 1}"
                count_params.append(pattern_type)

            total_count = await conn.fetchval(count_query, *count_params)

            # Convert rows to dicts
            results = [dict(row) for row in rows]

            # Convert datetime objects to ISO format strings
            for result in results:
                for key, value in result.items():
                    if isinstance(value, datetime):
                        result[key] = value.isoformat()

            self.metrics["queries_executed"] += 1

            return ModelPostgresPatternOutput(
                success=True,
                operation="query_patterns",
                query_results=results,
                total_count=total_count,
                correlation_id=input_data.correlation_id,
                metadata={
                    "limit": input_data.limit,
                    "offset": input_data.offset,
                },
            )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _update_scores(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Update pattern confidence scores.

        Args:
            input_data: Input data with pattern_id and scores

        Returns:
            Output with operation result
        """
        if not input_data.pattern_id:
            return ModelPostgresPatternOutput(
                success=False,
                operation="update_scores",
                error="pattern_id is required for update_scores operation",
                correlation_id=input_data.correlation_id,
            )

        if not input_data.scores:
            return ModelPostgresPatternOutput(
                success=False,
                operation="update_scores",
                error="scores dict is required for update_scores operation",
                correlation_id=input_data.correlation_id,
            )

        assert self.pool is not None  # Type assertion for mypy

        confidence_score = input_data.scores.get("confidence_score")
        if confidence_score is None:
            return ModelPostgresPatternOutput(
                success=False,
                operation="update_scores",
                error="confidence_score is required in scores dict",
                correlation_id=input_data.correlation_id,
            )

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE patterns
                SET confidence_score = $1, updated_at = NOW()
                WHERE pattern_id = $2
                """,
                confidence_score,
                input_data.pattern_id,
            )

            # Check if row was updated
            updated = result.split()[-1] != "0"

            self.metrics["updates_executed"] += 1

            return ModelPostgresPatternOutput(
                success=True,
                operation="update_scores",
                pattern_id=input_data.pattern_id,
                correlation_id=input_data.correlation_id,
                metadata={"updated": updated, "new_score": confidence_score},
            )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _get_lineage(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Get pattern lineage from PostgreSQL.

        Args:
            input_data: Input data with pattern_id

        Returns:
            Output with lineage data
        """
        if not input_data.pattern_id:
            return ModelPostgresPatternOutput(
                success=False,
                operation="get_lineage",
                error="pattern_id is required for get_lineage operation",
                correlation_id=input_data.correlation_id,
            )

        assert self.pool is not None  # Type assertion for mypy

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM pattern_lineage
                WHERE pattern_id = $1
                ORDER BY created_at DESC
                """,
                input_data.pattern_id,
            )

            # Convert rows to dicts
            results = [dict(row) for row in rows]

            # Convert datetime objects to ISO format strings
            for result in results:
                for key, value in result.items():
                    if isinstance(value, datetime):
                        result[key] = value.isoformat()

            return ModelPostgresPatternOutput(
                success=True,
                operation="get_lineage",
                query_results=results,
                pattern_id=input_data.pattern_id,
                correlation_id=input_data.correlation_id,
                metadata={"lineage_count": len(results)},
            )

    @retry(
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _search_patterns(
        self, input_data: ModelPostgresPatternInput
    ) -> ModelPostgresPatternOutput:
        """
        Full-text search for patterns.

        Args:
            input_data: Input data with search_query

        Returns:
            Output with search results
        """
        if not input_data.search_query:
            return ModelPostgresPatternOutput(
                success=False,
                operation="search_patterns",
                error="search_query is required for search_patterns operation",
                correlation_id=input_data.correlation_id,
            )

        if not self.config.enable_full_text_search:
            return ModelPostgresPatternOutput(
                success=False,
                operation="search_patterns",
                error="Full-text search is disabled",
                correlation_id=input_data.correlation_id,
            )

        assert self.pool is not None  # Type assertion for mypy

        async with self.pool.acquire() as conn:
            # Use ILIKE for simple search (full-text search requires proper setup)
            rows = await conn.fetch(
                """
                SELECT *,
                    CASE
                        WHEN pattern_name ILIKE $1 THEN 1.0
                        WHEN pattern_name ILIKE $2 THEN 0.8
                        ELSE 0.5
                    END as search_rank
                FROM patterns
                WHERE pattern_name ILIKE $2
                   OR pattern_type ILIKE $2
                ORDER BY search_rank DESC, confidence_score DESC
                LIMIT $3
                """,
                input_data.search_query,
                f"%{input_data.search_query}%",
                input_data.limit,
            )

            # Convert rows to dicts
            results = [dict(row) for row in rows]

            # Convert datetime objects to ISO format strings
            for result in results:
                for key, value in result.items():
                    if isinstance(value, datetime):
                        result[key] = value.isoformat()

            self.metrics["searches_performed"] += 1

            return ModelPostgresPatternOutput(
                success=True,
                operation="search_patterns",
                query_results=results,
                correlation_id=input_data.correlation_id,
                metadata={
                    "search_query": input_data.search_query,
                    "results_count": len(results),
                },
            )

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on PostgreSQL connection.

        Returns:
            Health check result with connection status
        """
        health = {
            "node_id": str(self.node_id),
            "status": "unhealthy",
            "pool_initialized": self.pool is not None,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if self.pool is None:
            health["error"] = "Pool not initialized"
            return health

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            health["status"] = "healthy"
            health["pool_size"] = self.pool.get_size()
            health["pool_free"] = self.pool.get_idle_size()
        except Exception as e:
            health["error"] = str(e)

        return health

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current operation metrics.

        Returns:
            Dictionary with metrics including:
            - patterns_stored: Total patterns stored
            - lineages_stored: Total lineages stored
            - queries_executed: Total queries executed
            - searches_performed: Total searches performed
            - updates_executed: Total updates executed
            - operations_failed: Total failed operations
            - total_operation_time_ms: Cumulative operation time
            - avg_operation_time_ms: Average operation time
        """
        total_ops = (
            self.metrics["patterns_stored"]
            + self.metrics["lineages_stored"]
            + self.metrics["queries_executed"]
            + self.metrics["searches_performed"]
            + self.metrics["updates_executed"]
        )
        avg_operation_time = (
            self.metrics["total_operation_time_ms"] / total_ops
            if total_ops > 0
            else 0.0
        )

        return {
            **self.metrics,
            "avg_operation_time_ms": avg_operation_time,
            "node_id": str(self.node_id),
        }


__all__ = [
    "ModelPostgresPatternConfig",
    "ModelPostgresPatternInput",
    "ModelPostgresPatternOutput",
    "NodePostgresPatternEffect",
]
