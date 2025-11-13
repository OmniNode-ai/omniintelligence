"""
Freshness Database Event Handler

Handles DB_QUERY_REQUESTED events and publishes DB_QUERY_COMPLETED/FAILED responses.
Implements direct PostgreSQL integration using asyncpg for document freshness operations.

Created: 2025-10-22
Purpose: Event-driven PostgreSQL integration for freshness system
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from asyncpg import Pool
from src.events.models.freshness_database_events import (
    EnumDbFetchMode,
    EnumDbQueryErrorCode,
    ModelDbQueryRequestPayload,
    create_query_completed_event,
    create_query_failed_event,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

logger = logging.getLogger(__name__)


class FreshnessDatabaseHandler(BaseResponsePublisher):
    """
    Handle DB_QUERY_REQUESTED events and publish query results.

    This handler implements direct PostgreSQL access for freshness database
    operations, consuming requests from the event bus and publishing results.

    Event Flow:
        1. Consume DB_QUERY_REQUESTED event
        2. Extract query, params, fetch_mode, and options
        3. Execute query against PostgreSQL using asyncpg
        4. Publish DB_QUERY_COMPLETED (success) or DB_QUERY_FAILED (error)

    Topics:
        - Request: dev.archon-intelligence.freshness.db-query-requested.v1
        - Completed: dev.archon-intelligence.freshness.db-query-completed.v1
        - Failed: dev.archon-intelligence.freshness.db-query-failed.v1
    """

    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.freshness.db-query-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.freshness.db-query-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.freshness.db-query-failed.v1"

    # PostgreSQL connection configuration
    DEFAULT_POSTGRES_HOST = "localhost"
    DEFAULT_POSTGRES_PORT = 5432
    DEFAULT_POSTGRES_DB = "omninode_bridge"
    DEFAULT_POSTGRES_USER = "postgres"
    DEFAULT_POSTGRES_PASSWORD = "postgres"

    def __init__(
        self,
        postgres_dsn: Optional[str] = None,
        pool: Optional[Pool] = None,
    ):
        """
        Initialize Freshness Database handler.

        Args:
            postgres_dsn: Optional PostgreSQL DSN (connection string)
            pool: Optional existing connection pool
        """
        super().__init__()

        # Connection configuration
        if postgres_dsn:
            self.postgres_dsn = postgres_dsn
        else:
            # Build DSN from environment variables or defaults
            host = os.getenv("POSTGRES_HOST", self.DEFAULT_POSTGRES_HOST)
            port = os.getenv("POSTGRES_PORT", str(self.DEFAULT_POSTGRES_PORT))
            database = os.getenv("POSTGRES_DB", self.DEFAULT_POSTGRES_DB)
            user = os.getenv("POSTGRES_USER", self.DEFAULT_POSTGRES_USER)
            password = os.getenv("POSTGRES_PASSWORD", self.DEFAULT_POSTGRES_PASSWORD)

            self.postgres_dsn = (
                f"postgresql://{user}:{password}@{host}:{port}/{database}"
            )

        self.pool: Optional[Pool] = pool
        self._pool_initialized = False

        # Metrics
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "queries_completed": 0,
            "queries_failed": 0,
            "total_query_time_ms": 0.0,
            "rows_affected": 0,
        }

    async def _ensure_pool_initialized(self) -> None:
        """
        Ensure PostgreSQL connection pool is initialized.

        Raises:
            RuntimeError: If pool initialization fails
        """
        if not self._pool_initialized:
            try:
                if not self.pool:
                    logger.info(
                        f"Initializing PostgreSQL connection pool: {self.postgres_dsn.split('@')[1]}"
                    )
                    self.pool = await asyncpg.create_pool(
                        self.postgres_dsn,
                        min_size=2,
                        max_size=10,
                        command_timeout=30.0,
                        timeout=10.0,
                    )
                self._pool_initialized = True
                logger.info("PostgreSQL connection pool initialized successfully")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize PostgreSQL connection pool: {str(e)}"
                ) from e

    async def shutdown(self) -> None:
        """Shutdown handler and close PostgreSQL pool."""
        if self.pool and self._pool_initialized:
            try:
                await self.pool.close()
                logger.info("PostgreSQL connection pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")
            finally:
                self._pool_initialized = False
                self.pool = None

        # Shutdown base publisher
        await self._shutdown_publisher()

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is DB_QUERY_REQUESTED
        """
        return event_type in [
            "DB_QUERY_REQUESTED",
            "freshness.db-query-requested",
            "omninode.freshness.event.db_query_requested.v1",  # Full event type from Kafka
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle DB_QUERY_REQUESTED event.

        Extracts query parameters from the event payload, executes the query
        against PostgreSQL, and publishes the appropriate response event.

        Args:
            event: Event envelope with DB_QUERY_REQUESTED payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            payload = self._get_payload(event)

            # Parse payload
            try:
                request_payload = ModelDbQueryRequestPayload(**payload)
            except Exception as e:
                logger.error(
                    f"Invalid payload in DB_QUERY_REQUESTED event {correlation_id}: {e}"
                )
                await self._publish_failed_response(
                    correlation_id=correlation_id,
                    query=payload.get("query", "unknown"),
                    fetch_mode=EnumDbFetchMode.ALL,
                    error_code=EnumDbQueryErrorCode.INVALID_QUERY,
                    error_message=f"Invalid request payload: {str(e)}",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                self.metrics["queries_failed"] += 1
                return False

            logger.info(
                f"Processing DB_QUERY_REQUESTED | correlation_id={correlation_id} | "
                f"query={request_payload.query[:100]}... | fetch_mode={request_payload.fetch_mode.value}"
            )

            # Ensure pool is initialized
            await self._ensure_pool_initialized()

            # Execute query
            query_result = await self._execute_query(
                query=request_payload.query,
                params=request_payload.params or [],
                fetch_mode=request_payload.fetch_mode,
                limit=request_payload.limit,
                timeout_seconds=request_payload.timeout_seconds,
            )

            # Publish success response
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_completed_response(
                correlation_id=correlation_id,
                query=request_payload.query,
                fetch_mode=request_payload.fetch_mode,
                query_result=query_result,
                processing_time_ms=duration_ms,
                table_name=request_payload.table_name,
                operation_type=request_payload.operation_type,
            )

            self.metrics["events_handled"] += 1
            self.metrics["queries_completed"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms
            self.metrics["total_query_time_ms"] += query_result["execution_time_ms"]
            self.metrics["rows_affected"] += query_result["row_count"]

            logger.info(
                f"DB_QUERY_COMPLETED published | correlation_id={correlation_id} | "
                f"row_count={query_result['row_count']} | "
                f"execution_time_ms={query_result['execution_time_ms']:.2f}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Database handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            # Publish error response
            try:
                if correlation_id:
                    payload = self._get_payload(event) if event else {}
                    query = payload.get("query", "unknown")
                    fetch_mode_str = payload.get("fetch_mode", "all")
                    try:
                        fetch_mode = EnumDbFetchMode(fetch_mode_str)
                    except ValueError:
                        fetch_mode = EnumDbFetchMode.ALL

                    duration_ms = (time.perf_counter() - start_time) * 1000
                    await self._publish_failed_response(
                        correlation_id=correlation_id,
                        query=query,
                        fetch_mode=fetch_mode,
                        error_code=EnumDbQueryErrorCode.INTERNAL_ERROR,
                        error_message=f"Query execution failed: {str(e)}",
                        retry_allowed=True,
                        processing_time_ms=duration_ms,
                        error_details={"exception_type": type(e).__name__},
                        table_name=payload.get("table_name"),
                        operation_type=payload.get("operation_type"),
                    )
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish error response | correlation_id={correlation_id} | "
                    f"error={publish_error}",
                    exc_info=True,
                )

            self.metrics["events_failed"] += 1
            self.metrics["queries_failed"] += 1
            return False

    async def _execute_query(
        self,
        query: str,
        params: list[Any],
        fetch_mode: EnumDbFetchMode,
        limit: Optional[int],
        timeout_seconds: Optional[float],
    ) -> Dict[str, Any]:
        """
        Execute database query using asyncpg.

        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_mode: Fetch mode (all, one, many, execute)
            limit: Optional limit for 'many' fetch mode
            timeout_seconds: Optional query timeout

        Returns:
            Dictionary with row_count, data, and execution_time_ms

        Raises:
            Exception: If query execution fails
        """
        start_time = time.perf_counter()

        try:
            # Set timeout
            timeout = timeout_seconds if timeout_seconds else 30.0

            # Execute query based on fetch mode
            async with self.pool.acquire(timeout=timeout) as conn:
                if fetch_mode == EnumDbFetchMode.ALL:
                    # Fetch all rows
                    rows = await asyncio.wait_for(
                        conn.fetch(query, *params), timeout=timeout
                    )
                    data = [dict(row) for row in rows]
                    row_count = len(rows)

                elif fetch_mode == EnumDbFetchMode.ONE:
                    # Fetch single row
                    row = await asyncio.wait_for(
                        conn.fetchrow(query, *params), timeout=timeout
                    )
                    data = [dict(row)] if row else []
                    row_count = 1 if row else 0

                elif fetch_mode == EnumDbFetchMode.MANY:
                    # Fetch limited rows
                    fetch_limit = limit if limit else 100
                    rows = await asyncio.wait_for(
                        conn.fetch(query, *params, limit=fetch_limit), timeout=timeout
                    )
                    data = [dict(row) for row in rows]
                    row_count = len(rows)

                elif fetch_mode == EnumDbFetchMode.EXECUTE:
                    # Execute without fetching (INSERT, UPDATE, DELETE)
                    result = await asyncio.wait_for(
                        conn.execute(query, *params), timeout=timeout
                    )
                    # Parse result string like "UPDATE 5" to get row count
                    row_count = 0
                    if result and " " in result:
                        try:
                            row_count = int(result.split()[-1])
                        except (ValueError, IndexError):
                            pass
                    data = None

                else:
                    raise ValueError(f"Unknown fetch mode: {fetch_mode}")

            execution_time_ms = (time.perf_counter() - start_time) * 1000

            return {
                "row_count": row_count,
                "data": data,
                "execution_time_ms": execution_time_ms,
            }

        except asyncio.TimeoutError:
            raise Exception(f"Query timeout after {timeout}s")
        except asyncpg.UndefinedTableError as e:
            raise Exception(f"Table not found: {str(e)}")
        except asyncpg.InsufficientPrivilegeError as e:
            raise Exception(f"Permission denied: {str(e)}")
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    async def _publish_completed_response(
        self,
        correlation_id: UUID,
        query: str,
        fetch_mode: EnumDbFetchMode,
        query_result: Dict[str, Any],
        processing_time_ms: float,
        table_name: Optional[str],
        operation_type: Optional[str],
    ) -> None:
        """
        Publish DB_QUERY_COMPLETED event.

        Args:
            correlation_id: Correlation ID from request
            query: Original SQL query
            fetch_mode: Fetch mode used
            query_result: Query result dictionary
            processing_time_ms: Processing time in milliseconds
            table_name: Optional table name
            operation_type: Optional operation type
        """
        try:
            await self._ensure_router_initialized()

            # Create completed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_query_completed_event(
                query=query,
                fetch_mode=fetch_mode,
                row_count=query_result["row_count"],
                execution_time_ms=query_result["execution_time_ms"],
                correlation_id=correlation_id,
                data=query_result.get("data"),
                table_name=table_name,
                operation_type=operation_type,
            )

            # Publish the ONEX-compliant envelope directly (no wrapper needed)
            await self._router.publish(
                topic=self.COMPLETED_TOPIC,
                event=event_envelope,  # Pass envelope dict directly
                key=str(correlation_id),
            )

            logger.info(
                f"Published DB_QUERY_COMPLETED | topic={self.COMPLETED_TOPIC} | "
                f"correlation_id={correlation_id} | row_count={query_result['row_count']}"
            )

        except Exception as e:
            logger.error(f"Failed to publish completed response: {e}", exc_info=True)
            raise

    async def _publish_failed_response(
        self,
        correlation_id: UUID,
        query: str,
        fetch_mode: EnumDbFetchMode,
        error_code: EnumDbQueryErrorCode,
        error_message: str,
        retry_allowed: bool = False,
        processing_time_ms: float = 0.0,
        error_details: Optional[Dict[str, Any]] = None,
        table_name: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> None:
        """
        Publish DB_QUERY_FAILED event.

        Args:
            correlation_id: Correlation ID from request
            query: SQL query that failed
            fetch_mode: Fetch mode attempted
            error_code: Error code enum value
            error_message: Human-readable error message
            retry_allowed: Whether the operation can be retried
            processing_time_ms: Time taken before failure
            error_details: Optional error context
            table_name: Optional table name
            operation_type: Optional operation type
        """
        try:
            await self._ensure_router_initialized()

            # Create failed event using helper (returns ONEX-compliant envelope)
            event_envelope = create_query_failed_event(
                query=query,
                fetch_mode=fetch_mode,
                error_message=error_message,
                error_code=error_code,
                correlation_id=correlation_id,
                retry_allowed=retry_allowed,
                execution_time_ms=processing_time_ms,
                error_details=error_details or {},
                table_name=table_name,
                operation_type=operation_type,
            )

            # Publish the ONEX-compliant envelope directly (no wrapper needed)
            await self._router.publish(
                topic=self.FAILED_TOPIC,
                event=event_envelope,  # Pass envelope dict directly
                key=str(correlation_id),
            )

            logger.warning(
                f"Published DB_QUERY_FAILED | topic={self.FAILED_TOPIC} | "
                f"correlation_id={correlation_id} | error_code={error_code.value} | "
                f"error_message={error_message}"
            )

        except Exception as e:
            logger.error(f"Failed to publish failed response: {e}", exc_info=True)
            raise

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "FreshnessDatabaseHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )
        avg_query_time = (
            self.metrics["total_query_time_ms"] / self.metrics["queries_completed"]
            if self.metrics["queries_completed"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "avg_query_time_ms": avg_query_time,
            "handler_name": self.get_handler_name(),
        }
