"""
ONEX Effect Node: Pattern Lineage Tracker

Purpose: Track pattern ancestry and evolution over time with PostgreSQL persistence
Node Type: Effect (External I/O, side effects, database operations)
File: node_pattern_lineage_tracker_effect.py
Class: NodePatternLineageTrackerEffect

Pattern: ONEX 4-Node Architecture - Effect
Track: Track 3 Phase 4 - Pattern Traceability
ONEX Compliant: Suffix naming (Node*Effect), file pattern (node_*_effect.py)

Performance Targets:
- Event tracking: <50ms
- Ancestry query: <200ms
- Graph traversal: <300ms
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List
from uuid import UUID, uuid4

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - pattern lineage tracking will be disabled")

# ONEX base imports
from src.archon_services.pattern_learning.phase1_foundation.storage.node_base_effect import (
    NodeBaseEffect,
)

# Import contract models from same package
from src.archon_services.pattern_learning.phase4_traceability.model_contract_pattern_lineage import (
    EdgeType,
    LineageEventType,
    ModelAncestorRecord,
    ModelDescendantRecord,
    ModelPatternLineageInput,
    ModelResult,
    TransformationType,
)

logger = logging.getLogger(__name__)


def with_db_retry(max_retries: int = 3, base_delay: float = 0.1):
    """
    Retry decorator for database operations that might fail due to concurrency.

    Implements exponential backoff with jitter to avoid thundering herd problems.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if this is a retryable error
                    error_str = str(e).lower()
                    retryable_errors = [
                        "could not serialize access",
                        "deadlock detected",
                        "connection closed",
                        "timeout",
                        "too many connections",
                        "unique_constraint",  # Already handled by our logic, but just in case
                    ]

                    is_retryable = any(
                        error_type in error_str for error_type in retryable_errors
                    )

                    if not is_retryable or attempt == max_retries:
                        # Non-retryable error or final attempt
                        logger.error(
                            f"[PatternLineageTracker] Operation failed after {attempt + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff and jitter
                    delay = base_delay * (2**attempt) + random.uniform(0, 0.1)
                    delay = min(delay, 2.0)  # Cap at 2 seconds maximum delay

                    logger.warning(
                        f"[PatternLineageTracker] Retryable error on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# ONEX Effect Node: Pattern Lineage Tracker
# ============================================================================


class NodePatternLineageTrackerEffect(NodeBaseEffect):
    """
    ONEX Effect Node for pattern lineage tracking operations.

    Implements:
    - ONEX naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelPatternLineageInput) -> ModelResult
    - Pure I/O operations (no business logic)
    - Transaction management via NodeBaseEffect
    - AsyncPG connection pooling

    Responsibilities:
    - Track pattern creation events
    - Track pattern modification events
    - Track pattern merge events
    - Track pattern application/usage events
    - Track pattern deprecation events
    - Query pattern ancestry chains
    - Query pattern descendants
    - Build and cache lineage graphs

    Database:
    - Tables: pattern_lineage_nodes, pattern_lineage_edges, pattern_lineage_events, pattern_ancestry_cache
    - Connection: AsyncPG connection pool
    - Transactions: Automatic via async with conn.transaction()

    Performance Targets:
    - Event tracking: <50ms
    - Ancestry query: <200ms for depth up to 10
    - Graph traversal: <300ms for complex relationships

    Example:
        >>> pool = await asyncpg.create_pool(database_url)
        >>> node = NodePatternLineageTrackerEffect(pool)
        >>> contract = ModelPatternLineageInput(
        ...     name="track_pattern_creation",
        ...     operation="track_creation",
        ...     event_type=LineageEventType.PATTERN_CREATED,
        ...     pattern_id="async_db_writer_v1",
        ...     pattern_data={"template_code": "..."}
        ... )
        >>> result = await node.execute_effect(contract)
        >>> print(result.success, result.data)
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern lineage tracker Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        super().__init__()
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternLineageTrackerEffect")

    async def execute_effect(self, contract: ModelPatternLineageInput) -> ModelResult:
        """
        Execute pattern lineage tracking operation with transaction management.

        ONEX Method Signature: async def execute_effect(self, contract) -> ModelResult

        Args:
            contract: ModelPatternLineageInput with operation details and correlation ID

        Returns:
            ModelResult with success status, data, and metadata including:
            - correlation_id: Request correlation ID
            - operation: Executed operation name
            - duration_ms: Operation duration in milliseconds

        Operations:
            - track_creation: Track new pattern creation
            - track_modification: Track pattern update
            - track_merge: Track pattern merge
            - track_application: Track pattern usage
            - track_deprecation: Track pattern deprecation
            - track_fork: Track pattern branching
            - query_ancestry: Query pattern ancestry chain
            - query_descendants: Query pattern descendants

        Raises:
            Does not raise exceptions - returns ModelResult with error details

        Performance:
            - Tracking operations: <50ms
            - Query operations: <200ms
        """
        if not ASYNCPG_AVAILABLE:
            return ModelResult(
                success=False,
                error="AsyncPG not available - cannot execute database operations",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        start_time = datetime.now(timezone.utc)
        operation_name = contract.operation

        try:
            # Execute operation within transaction context from base class
            async with self.transaction_manager.begin(contract.correlation_id):
                # Acquire connection from pool
                async with self.pool.acquire() as conn:
                    # Use database transaction for atomic operations
                    async with conn.transaction():
                        self.logger.info(
                            f"Executing pattern lineage operation: {operation_name}",
                            extra={
                                "correlation_id": str(contract.correlation_id),
                                "operation": operation_name,
                                "pattern_id": contract.pattern_id,
                            },
                        )

                        # Route to appropriate handler
                        if operation_name == "track_creation":
                            result_data = await self._track_creation(conn, contract)
                        elif operation_name == "track_modification":
                            result_data = await self._track_modification(conn, contract)
                        elif operation_name == "track_merge":
                            result_data = await self._track_merge(conn, contract)
                        elif operation_name == "track_application":
                            result_data = await self._track_application(conn, contract)
                        elif operation_name == "track_deprecation":
                            result_data = await self._track_deprecation(conn, contract)
                        elif operation_name == "track_fork":
                            result_data = await self._track_fork(conn, contract)
                        elif operation_name == "query_ancestry":
                            result_data = await self._query_ancestry(conn, contract)
                        elif operation_name == "query_descendants":
                            result_data = await self._query_descendants(conn, contract)
                        else:
                            return ModelResult(
                                success=False,
                                error=f"Unsupported operation: {operation_name}",
                                metadata={
                                    "correlation_id": str(contract.correlation_id)
                                },
                            )

            # Calculate operation duration
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Record performance metric
            self._record_metric(f"{operation_name}_duration_ms", duration_ms)

            self.logger.info(
                f"Pattern lineage operation completed: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": duration_ms,
                    "operation": operation_name,
                    "pattern_id": contract.pattern_id,
                },
            )

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "pattern_id": contract.pattern_id,
                },
            )

        except asyncpg.exceptions.UniqueViolationError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.warning(
                f"Lineage record already exists: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )

            # For unique violations, we should treat this as success since the pattern exists
            # This is a normal outcome of concurrent requests
            return ModelResult(
                success=True,
                data={
                    "status": "already_exists",
                    "message": "Pattern lineage already tracked",
                    "existing_record": True,
                },
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "unique_violation_handled",
                },
            )

        except asyncpg.exceptions.ForeignKeyViolationError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Foreign key violation: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Invalid reference (foreign key violation): {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "foreign_key_violation",
                },
            )

        except ValueError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Validation error: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Validation error: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "validation_error",
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Pattern lineage operation failed: {e}",
                exc_info=True,
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Operation failed: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )

    # ========================================================================
    # Private Operation Handlers - Tracking Operations
    # ========================================================================

    async def _track_creation(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """
        Track new pattern creation event.

        Creates:
        - New lineage node
        - Creation event record
        - Initial ancestry cache entry

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern creation details

        Returns:
            Dict with lineage_id, pattern_node_id, event_id

        Raises:
            ValueError: If required fields missing
        """
        # Generate IDs for new pattern
        lineage_id = uuid4()
        node_id = uuid4()
        event_id = uuid4()

        # Check if pattern already exists first to avoid race conditions
        existing_pattern = await conn.fetchrow(
            "SELECT id, lineage_id FROM pattern_lineage_nodes WHERE pattern_id = $1 AND pattern_version = $2",
            contract.pattern_id,
            contract.pattern_version,
        )

        if existing_pattern:
            # Pattern already exists, return existing lineage info
            logger.info(
                f"[PatternLineageTracker] Pattern {contract.pattern_id} v{contract.pattern_version} "
                f"already exists with lineage_id {existing_pattern['lineage_id']}"
            )

            # Create event for the duplicate attempt
            event_query = """
                INSERT INTO pattern_lineage_events (
                    id, event_type, pattern_id, pattern_node_id,
                    event_data, metadata, reason, triggered_by,
                    correlation_id, timestamp
                ) VALUES (
                    $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, NOW()
                )
                RETURNING id, timestamp
            """

            await conn.fetchrow(
                event_query,
                event_id,
                contract.event_type.value,
                contract.pattern_id,
                existing_pattern["id"],
                json.dumps(contract.pattern_data),
                json.dumps(
                    {
                        **contract.metadata,
                        "duplicate_attempt": True,
                        "original_lineage_id": str(existing_pattern["lineage_id"]),
                    }
                ),
                "Duplicate pattern creation attempt - original exists",
                contract.triggered_by,
                contract.correlation_id,
            )

            return {
                "lineage_id": str(existing_pattern["lineage_id"]),
                "pattern_node_id": str(existing_pattern["id"]),
                "event_id": str(event_id),
                "status": "already_exists",
                "message": "Pattern already exists in lineage",
            }

        # Insert new lineage node with ON CONFLICT to prevent race conditions
        node_query = """
            INSERT INTO pattern_lineage_nodes (
                id, pattern_id, pattern_name, pattern_type, pattern_version,
                lineage_id, generation, source_system, source_user, source_event_id,
                pattern_data, metadata, correlation_id,
                event_type, tool_name, file_path, language
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb, $13,
                $14, $15, $16, $17
            )
            ON CONFLICT (pattern_id, pattern_version) DO NOTHING
            RETURNING id, lineage_id, created_at
        """

        try:
            node_result = await conn.fetchrow(
                node_query,
                node_id,
                contract.pattern_id,
                contract.pattern_name,
                contract.pattern_type,
                contract.pattern_version,
                lineage_id,
                1,  # generation (root pattern)
                "pattern_learning_system",
                contract.triggered_by,
                event_id,
                json.dumps(contract.pattern_data),
                json.dumps(contract.metadata),
                contract.correlation_id,
                contract.event_type.value,
                contract.tool_name,
                contract.file_path,
                contract.language,
            )

            # If ON CONFLICT triggered, node_result will be None
            if node_result is None:
                # Pattern already exists, fetch existing record
                existing_query = """
                    SELECT id, lineage_id, created_at
                    FROM pattern_lineage_nodes
                    WHERE pattern_id = $1 AND pattern_version = $2
                """
                node_result = await conn.fetchrow(
                    existing_query, contract.pattern_id, contract.pattern_version
                )
                if not node_result:
                    raise RuntimeError(
                        "Pattern should exist after ON CONFLICT but was not found"
                    )

                self.logger.info(
                    f"Pattern already exists in lineage: {contract.pattern_name} ({contract.pattern_id})",
                    extra={"correlation_id": str(contract.correlation_id)},
                )
        except Exception as e:
            logger.error(f"[PatternLineageTracker] Failed to create pattern node: {e}")
            raise

        # Insert lineage event
        event_query = """
            INSERT INTO pattern_lineage_events (
                id, event_type, pattern_id, pattern_node_id,
                event_data, metadata, reason, triggered_by,
                correlation_id, timestamp
            ) VALUES (
                $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, NOW()
            )
            RETURNING id, timestamp
        """

        await conn.fetchrow(
            event_query,
            event_id,
            contract.event_type.value,
            contract.pattern_id,
            node_id,
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.reason,
            contract.triggered_by,
            contract.correlation_id,
        )

        # Initialize ancestry cache
        await self._initialize_ancestry_cache(
            conn, node_id, contract.pattern_id, lineage_id
        )

        self.logger.info(
            f"Tracked pattern creation: {contract.pattern_name} ({contract.pattern_id})",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        return {
            "lineage_id": str(lineage_id),
            "pattern_node_id": str(node_id),
            "event_id": str(event_id),
            "pattern_id": contract.pattern_id,
            "pattern_name": contract.pattern_name,
            "created_at": node_result["created_at"].isoformat(),
        }

    async def _track_modification(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """
        Track pattern modification event.

        Creates:
        - New lineage node (new version)
        - Lineage edge from parent
        - Modification event record
        - Updated ancestry cache

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with modification details

        Returns:
            Dict with lineage_id, pattern_node_id, event_id, parent_node_ids

        Raises:
            ValueError: If parent pattern not found
        """
        # Get parent node
        parent_query = """
            SELECT id, lineage_id, generation
            FROM pattern_lineage_nodes
            WHERE pattern_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        parent_result = await conn.fetchrow(
            parent_query, contract.parent_pattern_ids[0]
        )

        if not parent_result:
            raise ValueError(
                f"Parent pattern not found: {contract.parent_pattern_ids[0]}"
            )

        parent_node_id = parent_result["id"]
        lineage_id = parent_result["lineage_id"]
        generation = parent_result["generation"] + 1

        # Generate IDs
        node_id = uuid4()
        event_id = uuid4()

        # Insert new lineage node with ON CONFLICT to prevent race conditions
        node_query = """
            INSERT INTO pattern_lineage_nodes (
                id, pattern_id, pattern_name, pattern_type, pattern_version,
                lineage_id, generation, source_system, source_user, source_event_id,
                pattern_data, metadata, correlation_id,
                event_type, tool_name, file_path, language
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb, $13,
                $14, $15, $16, $17
            )
            ON CONFLICT (pattern_id, pattern_version) DO NOTHING
            RETURNING id, created_at
        """

        node_result = await conn.fetchrow(
            node_query,
            node_id,
            contract.pattern_id,
            contract.pattern_name,
            contract.pattern_type,
            contract.pattern_version,
            lineage_id,
            generation,
            "pattern_learning_system",
            contract.triggered_by,
            event_id,
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.correlation_id,
            contract.event_type.value,
            contract.tool_name,
            contract.file_path,
            contract.language,
        )

        # If ON CONFLICT triggered, node_result will be None
        if node_result is None:
            # Pattern version already exists, fetch existing record
            existing_query = """
                SELECT id, created_at
                FROM pattern_lineage_nodes
                WHERE pattern_id = $1 AND pattern_version = $2
            """
            node_result = await conn.fetchrow(
                existing_query, contract.pattern_id, contract.pattern_version
            )
            if not node_result:
                raise RuntimeError(
                    "Pattern version should exist after ON CONFLICT but was not found"
                )

            self.logger.info(
                f"Pattern modification already tracked: {contract.pattern_name} v{contract.pattern_version}",
                extra={"correlation_id": str(contract.correlation_id)},
            )
            # Use existing node_id for subsequent operations
            node_id = node_result["id"]

        # Create lineage edge with ON CONFLICT to prevent duplicates
        edge_type = contract.edge_type or EdgeType.MODIFIED_FROM
        transformation_type = (
            contract.transformation_type or TransformationType.REFACTOR
        )

        edge_query = """
            INSERT INTO pattern_lineage_edges (
                source_node_id, target_node_id, edge_type, transformation_type,
                metadata, correlation_id, created_by
            ) VALUES (
                $1, $2, $3, $4, $5::jsonb, $6, $7
            )
            ON CONFLICT (source_node_id, target_node_id, edge_type) DO NOTHING
            RETURNING id
        """

        edge_result = await conn.fetchrow(
            edge_query,
            parent_node_id,
            node_id,
            edge_type.value,
            transformation_type.value,
            json.dumps(contract.metadata),
            contract.correlation_id,
            contract.triggered_by,
        )

        # Log if edge already exists
        if edge_result is None:
            self.logger.info(
                f"Lineage edge already exists: {parent_node_id} -> {node_id} ({edge_type.value})",
                extra={"correlation_id": str(contract.correlation_id)},
            )

        # Insert lineage event
        event_query = """
            INSERT INTO pattern_lineage_events (
                id, event_type, pattern_id, pattern_node_id,
                parent_pattern_ids, parent_node_ids,
                event_data, metadata, reason, triggered_by,
                correlation_id, timestamp
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, NOW()
            )
            RETURNING id, timestamp
        """

        await conn.fetchrow(
            event_query,
            event_id,
            contract.event_type.value,
            contract.pattern_id,
            node_id,
            contract.parent_pattern_ids,
            [str(parent_node_id)],
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.reason,
            contract.triggered_by,
            contract.correlation_id,
        )

        # Update ancestry cache
        await self._update_ancestry_cache(
            conn, node_id, contract.pattern_id, lineage_id, [parent_node_id]
        )

        self.logger.info(
            f"Tracked pattern modification: {contract.pattern_name} ({contract.pattern_id})",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        return {
            "lineage_id": str(lineage_id),
            "pattern_node_id": str(node_id),
            "event_id": str(event_id),
            "pattern_id": contract.pattern_id,
            "parent_node_ids": [str(parent_node_id)],
            "generation": generation,
            "created_at": node_result["created_at"].isoformat(),
        }

    async def _track_merge(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """
        Track pattern merge event.

        Creates:
        - New lineage node (merged pattern)
        - Multiple lineage edges from parents
        - Merge event record
        - Updated ancestry cache with multiple parents

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with merge details

        Returns:
            Dict with lineage_id, pattern_node_id, event_id, parent_node_ids

        Raises:
            ValueError: If any parent pattern not found
        """
        # Get all parent nodes
        parent_nodes = []
        max_generation = 0

        for parent_pattern_id in contract.parent_pattern_ids:
            parent_query = """
                SELECT id, lineage_id, generation
                FROM pattern_lineage_nodes
                WHERE pattern_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """

            parent_result = await conn.fetchrow(parent_query, parent_pattern_id)

            if not parent_result:
                raise ValueError(f"Parent pattern not found: {parent_pattern_id}")

            parent_nodes.append(parent_result)
            max_generation = max(max_generation, parent_result["generation"])

        # Use lineage_id from first parent (could create new lineage if desired)
        lineage_id = parent_nodes[0]["lineage_id"]
        generation = max_generation + 1

        # Generate IDs
        node_id = uuid4()
        event_id = uuid4()

        # Insert new lineage node with ON CONFLICT to prevent race conditions
        node_query = """
            INSERT INTO pattern_lineage_nodes (
                id, pattern_id, pattern_name, pattern_type, pattern_version,
                lineage_id, generation, source_system, source_user, source_event_id,
                pattern_data, metadata, correlation_id,
                event_type, tool_name, file_path, language
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb, $13,
                $14, $15, $16, $17
            )
            ON CONFLICT (pattern_id, pattern_version) DO NOTHING
            RETURNING id, created_at
        """

        node_result = await conn.fetchrow(
            node_query,
            node_id,
            contract.pattern_id,
            contract.pattern_name,
            contract.pattern_type,
            contract.pattern_version,
            lineage_id,
            generation,
            "pattern_learning_system",
            contract.triggered_by,
            event_id,
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.correlation_id,
            contract.event_type.value,
            contract.tool_name,
            contract.file_path,
            contract.language,
        )

        # If ON CONFLICT triggered, node_result will be None
        if node_result is None:
            # Merged pattern already exists, fetch existing record
            existing_query = """
                SELECT id, created_at
                FROM pattern_lineage_nodes
                WHERE pattern_id = $1 AND pattern_version = $2
            """
            node_result = await conn.fetchrow(
                existing_query, contract.pattern_id, contract.pattern_version
            )
            if not node_result:
                raise RuntimeError(
                    "Merged pattern should exist after ON CONFLICT but was not found"
                )

            self.logger.info(
                f"Pattern merge already tracked: {contract.pattern_name} v{contract.pattern_version}",
                extra={"correlation_id": str(contract.correlation_id)},
            )
            # Use existing node_id for subsequent operations
            node_id = node_result["id"]

        # Create lineage edges for all parents with ON CONFLICT to prevent duplicates
        edge_type = contract.edge_type or EdgeType.MERGED_FROM

        for parent_node in parent_nodes:
            edge_query = """
                INSERT INTO pattern_lineage_edges (
                    source_node_id, target_node_id, edge_type, transformation_type,
                    metadata, correlation_id, created_by
                ) VALUES (
                    $1, $2, $3, $4, $5::jsonb, $6, $7
                )
                ON CONFLICT (source_node_id, target_node_id, edge_type) DO NOTHING
            """

            await conn.execute(
                edge_query,
                parent_node["id"],
                node_id,
                edge_type.value,
                TransformationType.MERGE.value,
                json.dumps(contract.metadata),
                contract.correlation_id,
                contract.triggered_by,
            )

        # Insert lineage event
        parent_node_ids = [str(p["id"]) for p in parent_nodes]

        event_query = """
            INSERT INTO pattern_lineage_events (
                id, event_type, pattern_id, pattern_node_id,
                parent_pattern_ids, parent_node_ids,
                event_data, metadata, reason, triggered_by,
                correlation_id, timestamp
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, NOW()
            )
            RETURNING id, timestamp
        """

        await conn.fetchrow(
            event_query,
            event_id,
            contract.event_type.value,
            contract.pattern_id,
            node_id,
            contract.parent_pattern_ids,
            parent_node_ids,
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.reason,
            contract.triggered_by,
            contract.correlation_id,
        )

        # Update ancestry cache with multiple parents
        parent_ids = [p["id"] for p in parent_nodes]
        await self._update_ancestry_cache(
            conn, node_id, contract.pattern_id, lineage_id, parent_ids
        )

        self.logger.info(
            f"Tracked pattern merge: {contract.pattern_name} ({contract.pattern_id}) from {len(parent_nodes)} parents",
            extra={"correlation_id": str(contract.correlation_id)},
        )

        return {
            "lineage_id": str(lineage_id),
            "pattern_node_id": str(node_id),
            "event_id": str(event_id),
            "pattern_id": contract.pattern_id,
            "parent_node_ids": parent_node_ids,
            "parent_count": len(parent_nodes),
            "generation": generation,
            "created_at": node_result["created_at"].isoformat(),
        }

    async def _track_application(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """Track pattern application/usage event."""
        event_id = uuid4()

        # Get current pattern node
        node_query = """
            SELECT id FROM pattern_lineage_nodes
            WHERE pattern_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        node_result = await conn.fetchrow(node_query, contract.pattern_id)

        if not node_result:
            raise ValueError(f"Pattern not found: {contract.pattern_id}")

        # Insert usage event
        event_query = """
            INSERT INTO pattern_lineage_events (
                id, event_type, pattern_id, pattern_node_id,
                event_data, metadata, reason, triggered_by,
                correlation_id, timestamp
            ) VALUES (
                $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, NOW()
            )
            RETURNING id, timestamp
        """

        event_result = await conn.fetchrow(
            event_query,
            event_id,
            LineageEventType.PATTERN_APPLIED.value,
            contract.pattern_id,
            node_result["id"],
            json.dumps(contract.pattern_data),
            json.dumps(contract.metadata),
            contract.reason,
            contract.triggered_by,
            contract.correlation_id,
        )

        return {
            "event_id": str(event_id),
            "pattern_id": contract.pattern_id,
            "pattern_node_id": str(node_result["id"]),
            "timestamp": event_result["timestamp"].isoformat(),
        }

    async def _track_deprecation(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """Track pattern deprecation event."""
        event_id = uuid4()

        # Get current pattern node
        node_query = """
            SELECT id FROM pattern_lineage_nodes
            WHERE pattern_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        node_result = await conn.fetchrow(node_query, contract.pattern_id)

        if not node_result:
            raise ValueError(f"Pattern not found: {contract.pattern_id}")

        # Insert deprecation event
        event_query = """
            INSERT INTO pattern_lineage_events (
                id, event_type, pattern_id, pattern_node_id,
                event_data, metadata, reason, triggered_by,
                correlation_id, timestamp
            ) VALUES (
                $1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, NOW()
            )
            RETURNING id, timestamp
        """

        event_result = await conn.fetchrow(
            event_query,
            event_id,
            LineageEventType.PATTERN_DEPRECATED.value,
            contract.pattern_id,
            node_result["id"],
            json.dumps({"deprecated": True, "reason": contract.reason}),
            json.dumps(contract.metadata),
            contract.reason,
            contract.triggered_by,
            contract.correlation_id,
        )

        return {
            "event_id": str(event_id),
            "pattern_id": contract.pattern_id,
            "pattern_node_id": str(node_result["id"]),
            "deprecated": True,
            "timestamp": event_result["timestamp"].isoformat(),
        }

    async def _track_fork(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """Track pattern fork/branch event (similar to modification but creates new lineage)."""
        # Similar to modification but could create new lineage_id for branching
        return await self._track_modification(conn, contract)

    # ========================================================================
    # Private Operation Handlers - Query Operations
    # ========================================================================

    async def _query_ancestry(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """
        Query pattern ancestry chain.

        Uses recursive CTE to traverse lineage graph backwards from current pattern.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id to query

        Returns:
            Dict with ancestors list, ancestry_depth, total_ancestors

        Performance Target: <200ms for depth up to 10
        """
        # Get current pattern node
        node_query = """
            SELECT id, lineage_id FROM pattern_lineage_nodes
            WHERE pattern_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        node_result = await conn.fetchrow(node_query, contract.pattern_id)

        if not node_result:
            raise ValueError(f"Pattern not found: {contract.pattern_id}")

        # Use PostgreSQL function for ancestry query
        ancestry_query = """
            SELECT * FROM get_pattern_ancestry($1)
        """

        ancestry_results = await conn.fetch(ancestry_query, node_result["id"])

        # Convert to ancestor records
        ancestors = [
            ModelAncestorRecord(
                ancestor_id=row["ancestor_id"],
                ancestor_pattern_id=row["ancestor_pattern_id"],
                generation=row["generation"],
                edge_type=row["edge_type"],
                created_at=row["created_at"],
            )
            for row in ancestry_results
        ]

        return {
            "pattern_id": contract.pattern_id,
            "pattern_node_id": str(node_result["id"]),
            "lineage_id": str(node_result["lineage_id"]),
            "ancestors": [a.to_dict() for a in ancestors],
            "ancestry_depth": len(ancestors) - 1 if ancestors else 0,  # Exclude self
            "total_ancestors": len(ancestors) - 1 if ancestors else 0,
        }

    async def _query_descendants(
        self, conn: "asyncpg.Connection", contract: ModelPatternLineageInput
    ) -> Dict[str, Any]:
        """
        Query pattern descendants.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id to query

        Returns:
            Dict with descendants list, total_descendants
        """
        # Get current pattern node
        node_query = """
            SELECT id FROM pattern_lineage_nodes
            WHERE pattern_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        node_result = await conn.fetchrow(node_query, contract.pattern_id)

        if not node_result:
            raise ValueError(f"Pattern not found: {contract.pattern_id}")

        # Use PostgreSQL function for descendants query
        descendants_query = """
            SELECT * FROM get_pattern_descendants($1)
        """

        descendants_results = await conn.fetch(descendants_query, node_result["id"])

        # Convert to descendant records
        descendants = [
            ModelDescendantRecord(
                descendant_id=row["descendant_id"],
                descendant_pattern_id=row["descendant_pattern_id"],
                edge_type=row["edge_type"],
                transformation_type=row["transformation_type"],
                created_at=row["created_at"],
            )
            for row in descendants_results
        ]

        return {
            "pattern_id": contract.pattern_id,
            "pattern_node_id": str(node_result["id"]),
            "descendants": [d.to_dict() for d in descendants],
            "total_descendants": len(descendants),
        }

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _initialize_ancestry_cache(
        self,
        conn: "asyncpg.Connection",
        node_id: UUID,
        pattern_id: str,
        lineage_id: UUID,
    ) -> None:
        """Initialize ancestry cache for new root pattern with ON CONFLICT handling."""
        cache_query = """
            INSERT INTO pattern_ancestry_cache (
                pattern_id, pattern_node_id, ancestor_ids, ancestor_pattern_ids,
                ancestry_depth, total_ancestors, cache_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, 1
            )
            ON CONFLICT (pattern_node_id) DO UPDATE SET
                ancestor_ids = EXCLUDED.ancestor_ids,
                ancestor_pattern_ids = EXCLUDED.ancestor_pattern_ids,
                ancestry_depth = EXCLUDED.ancestry_depth,
                total_ancestors = EXCLUDED.total_ancestors,
                cache_version = pattern_ancestry_cache.cache_version + 1,
                last_updated = NOW(),
                is_stale = false
        """

        await conn.execute(
            cache_query,
            pattern_id,
            node_id,
            [str(node_id)],  # Only self in ancestors
            [pattern_id],
            0,  # Root has depth 0
            0,  # Root has 0 ancestors
        )

    async def _update_ancestry_cache(
        self,
        conn: "asyncpg.Connection",
        node_id: UUID,
        pattern_id: str,
        lineage_id: UUID,
        parent_node_ids: List[UUID],
    ) -> None:
        """Update ancestry cache for new pattern with parents."""
        # Get ancestors from all parents
        all_ancestors = set()
        all_ancestor_patterns = set()

        for parent_id in parent_node_ids:
            parent_cache_query = """
                SELECT ancestor_ids, ancestor_pattern_ids, ancestry_depth
                FROM pattern_ancestry_cache
                WHERE pattern_node_id = $1
            """

            parent_cache = await conn.fetchrow(parent_cache_query, parent_id)

            if parent_cache:
                all_ancestors.update(parent_cache["ancestor_ids"])
                all_ancestor_patterns.update(parent_cache["ancestor_pattern_ids"])

        # Add self to ancestors
        all_ancestors.add(str(node_id))
        all_ancestor_patterns.add(pattern_id)

        # Insert or update cache entry with ON CONFLICT handling
        cache_query = """
            INSERT INTO pattern_ancestry_cache (
                pattern_id, pattern_node_id, ancestor_ids, ancestor_pattern_ids,
                ancestry_depth, total_ancestors, cache_version
            ) VALUES (
                $1, $2, $3, $4, $5, $6, 1
            )
            ON CONFLICT (pattern_node_id) DO UPDATE SET
                ancestor_ids = EXCLUDED.ancestor_ids,
                ancestor_pattern_ids = EXCLUDED.ancestor_pattern_ids,
                ancestry_depth = EXCLUDED.ancestry_depth,
                total_ancestors = EXCLUDED.total_ancestors,
                cache_version = pattern_ancestry_cache.cache_version + 1,
                last_updated = NOW(),
                is_stale = false
        """

        await conn.execute(
            cache_query,
            pattern_id,
            node_id,
            list(all_ancestors),
            list(all_ancestor_patterns),
            len(all_ancestors) - 1,  # Depth excludes self
            len(all_ancestors) - 1,  # Total excludes self
        )

        # Invalidate downstream caches
        await conn.execute("SELECT invalidate_ancestry_cache($1)", node_id)


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """
    Example usage of NodePatternLineageTrackerEffect.

    Demonstrates:
    - Tracking pattern creation
    - Tracking pattern modification
    - Tracking pattern merge
    - Querying ancestry
    - Querying descendants
    """
    import os

    # Get database URL from environment
    db_password = os.getenv("DB_PASSWORD", "")
    db_url = os.getenv(
        "TRACEABILITY_DB_URL_EXTERNAL",
        f"postgresql://postgres:{db_password}@localhost:5436/omninode_bridge",
    )

    # Create connection pool
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

    try:
        # Create Effect node
        node = NodePatternLineageTrackerEffect(pool)

        # Example 1: Track pattern creation
        print("\n=== Example 1: Track Pattern Creation ===")
        create_contract = ModelPatternLineageInput(
            name="track_async_pattern_creation",
            operation="track_creation",
            event_type=LineageEventType.PATTERN_CREATED,
            pattern_id="async_db_writer_v1",
            pattern_name="AsyncDatabaseWriter",
            pattern_type="code",
            pattern_version="1.0.0",
            pattern_data={
                "template_code": "async def execute_effect(self, contract): ...",
                "language": "python",
                "framework": "onex",
            },
            triggered_by="ai_assistant",
            reason="Initial pattern extraction from codebase",
        )

        result = await node.execute_effect(create_contract)
        print(f"Success: {result.success}")
        print(f"Data: {json.dumps(result.data, indent=2)}")
        print(f"Duration: {result.metadata.get('duration_ms')}ms")

        # Example 2: Track pattern modification
        print("\n=== Example 2: Track Pattern Modification ===")
        modify_contract = ModelPatternLineageInput(
            name="track_pattern_enhancement",
            operation="track_modification",
            event_type=LineageEventType.PATTERN_MODIFIED,
            pattern_id="async_db_writer_v2",
            pattern_name="AsyncDatabaseWriter",
            pattern_type="code",
            pattern_version="2.0.0",
            pattern_data={
                "template_code": "async def execute_effect(self, contract): # with retry logic",
                "language": "python",
                "framework": "onex",
                "enhancements": ["retry_logic", "error_handling"],
            },
            parent_pattern_ids=["async_db_writer_v1"],
            edge_type=EdgeType.MODIFIED_FROM,
            transformation_type=TransformationType.ENHANCEMENT,
            triggered_by="ai_assistant",
            reason="Added retry logic and enhanced error handling",
        )

        result = await node.execute_effect(modify_contract)
        print(f"Success: {result.success}")
        print(f"Data: {json.dumps(result.data, indent=2)}")

        # Example 3: Query ancestry
        print("\n=== Example 3: Query Pattern Ancestry ===")
        ancestry_contract = ModelPatternLineageInput(
            name="query_pattern_history",
            operation="query_ancestry",
            pattern_id="async_db_writer_v2",
        )

        result = await node.execute_effect(ancestry_contract)
        print(f"Success: {result.success}")
        print(f"Ancestry depth: {result.data.get('ancestry_depth')}")
        print(f"Ancestors: {len(result.data.get('ancestors', []))}")
        print(f"Duration: {result.metadata.get('duration_ms')}ms")

    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
