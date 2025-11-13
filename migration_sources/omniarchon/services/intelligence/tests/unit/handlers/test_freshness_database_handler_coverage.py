"""
Comprehensive Unit Tests for FreshnessDatabaseHandler

Tests database event handler methods with mocked asyncpg:
- Initialization with different configurations
- Event routing (can_handle)
- Database query execution (all fetch modes)
- Event handling (success/failure)
- Response publishing
- Error handling and recovery
- Metrics tracking
- Connection pool management
- Shutdown and cleanup

Created: 2025-11-04
Purpose: Improve coverage from 0% to 70%+
Target: ~115 statements covered out of 164 total
"""

import asyncio
import os
from datetime import UTC, datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from events.models.freshness_database_events import (
    EnumDbFetchMode,
    EnumDbQueryErrorCode,
    ModelDbQueryRequestPayload,
)
from handlers.freshness_database_handler import FreshnessDatabaseHandler

# ==============================================================================
# Mock Event Envelope
# ==============================================================================


class MockEventEnvelope:
    """Mock event envelope for testing without real Kafka."""

    def __init__(
        self,
        event_id: str = None,
        event_type: str = "DB_QUERY_REQUESTED",
        correlation_id: str = None,
        payload: Dict[str, Any] = None,
        timestamp: datetime = None,
    ):
        self.event_id = event_id or str(uuid4())
        self.event_type = event_type
        self.correlation_id = correlation_id or str(uuid4())
        self.payload = payload or {}
        self.timestamp = timestamp or datetime.now(UTC)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def get(self, key: str, default=None):
        """Dict-like get method."""
        return self.to_dict().get(key, default)


# ==============================================================================
# Mock Database Pool and Connection
# ==============================================================================


class MockAsyncpgRecord:
    """Mock asyncpg record."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data.keys())


class MockAsyncpgConnection:
    """Mock asyncpg connection."""

    def __init__(self, return_data=None, raise_error=None):
        self.return_data = return_data or []
        self.raise_error = raise_error
        self.executed_queries = []

    async def fetch(self, query, *params, **kwargs):
        """Mock fetch method."""
        self.executed_queries.append(
            {"query": query, "params": params, "kwargs": kwargs}
        )
        if self.raise_error:
            raise self.raise_error
        return [MockAsyncpgRecord(item) for item in self.return_data]

    async def fetchrow(self, query, *params):
        """Mock fetchrow method."""
        self.executed_queries.append({"query": query, "params": params})
        if self.raise_error:
            raise self.raise_error
        if self.return_data:
            return MockAsyncpgRecord(self.return_data[0])
        return None

    async def execute(self, query, *params):
        """Mock execute method."""
        self.executed_queries.append({"query": query, "params": params})
        if self.raise_error:
            raise self.raise_error
        # Return result string like PostgreSQL does (e.g., "UPDATE 5")
        return "UPDATE 3"


class MockAsyncpgPool:
    """Mock asyncpg pool."""

    def __init__(self, connection=None):
        self.connection = connection or MockAsyncpgConnection()
        self.closed = False

    def acquire(self, timeout=None):
        """Mock acquire context manager."""
        return MockAcquireContext(self.connection)

    async def close(self):
        """Mock close method."""
        self.closed = True


class MockAcquireContext:
    """Mock context manager for pool.acquire()."""

    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_pool():
    """Create mock asyncpg pool."""
    return MockAsyncpgPool()


@pytest.fixture
def mock_router():
    """Create mock HybridEventRouter."""
    router = AsyncMock()
    router.publish = AsyncMock()
    return router


@pytest.fixture
async def handler(mock_pool):
    """Create handler with mock pool."""
    handler = FreshnessDatabaseHandler(
        postgres_dsn="postgresql://user:pass@localhost:5432/testdb",
        pool=mock_pool,
    )
    handler._pool_initialized = True
    yield handler
    await handler.shutdown()


@pytest.fixture
async def handler_with_router(mock_pool, mock_router):
    """Create handler with mock pool and router."""
    handler = FreshnessDatabaseHandler(
        postgres_dsn="postgresql://user:pass@localhost:5432/testdb",
        pool=mock_pool,
    )
    handler._pool_initialized = True
    handler._router = mock_router
    handler._router_initialized = True
    yield handler
    await handler.shutdown()


# ==============================================================================
# Initialization Tests
# ==============================================================================


@pytest.mark.asyncio
class TestInitialization:
    """Test handler initialization."""

    def test_init_with_dsn(self):
        """Test initialization with explicit DSN."""
        dsn = "postgresql://user:pass@localhost:5432/testdb"
        handler = FreshnessDatabaseHandler(postgres_dsn=dsn)

        assert handler.postgres_dsn == dsn
        assert handler.pool is None
        assert not handler._pool_initialized
        assert handler.metrics["events_handled"] == 0

    def test_init_with_pool(self, mock_pool):
        """Test initialization with existing pool."""
        handler = FreshnessDatabaseHandler(pool=mock_pool)

        assert handler.pool is mock_pool
        assert not handler._pool_initialized

    def test_init_from_env_variables(self):
        """Test initialization from environment variables."""
        with patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "testhost",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "testdb",
                "POSTGRES_USER": "testuser",
                "POSTGRES_PASSWORD": "testpass",
            },
        ):
            handler = FreshnessDatabaseHandler()

            expected_dsn = "postgresql://testuser:testpass@testhost:5433/testdb"
            assert handler.postgres_dsn == expected_dsn

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            handler = FreshnessDatabaseHandler()

            expected_dsn = (
                "postgresql://postgres:postgres@localhost:5432/omninode_bridge"
            )
            assert handler.postgres_dsn == expected_dsn

    def test_metrics_initialized(self, handler):
        """Test that metrics are properly initialized."""
        assert "events_handled" in handler.metrics
        assert "events_failed" in handler.metrics
        assert "total_processing_time_ms" in handler.metrics
        assert "queries_completed" in handler.metrics
        assert "queries_failed" in handler.metrics
        assert "total_query_time_ms" in handler.metrics
        assert "rows_affected" in handler.metrics


# ==============================================================================
# Event Routing Tests
# ==============================================================================


@pytest.mark.asyncio
class TestEventRouting:
    """Test event routing and type handling."""

    def test_can_handle_db_query_requested(self, handler):
        """Test handling of DB_QUERY_REQUESTED event."""
        assert handler.can_handle("DB_QUERY_REQUESTED")

    def test_can_handle_freshness_variant(self, handler):
        """Test handling of freshness.db-query-requested event."""
        assert handler.can_handle("freshness.db-query-requested")

    def test_can_handle_full_event_type(self, handler):
        """Test handling of full Kafka event type."""
        assert handler.can_handle("omninode.freshness.event.db_query_requested.v1")

    def test_cannot_handle_other_events(self, handler):
        """Test rejection of non-database events."""
        assert not handler.can_handle("SOME_OTHER_EVENT")
        assert not handler.can_handle("tree.index-project-requested")
        assert not handler.can_handle("freshness.analyze-requested")

    def test_get_handler_name(self, handler):
        """Test handler name retrieval."""
        assert handler.get_handler_name() == "FreshnessDatabaseHandler"


# ==============================================================================
# Pool Management Tests
# ==============================================================================


@pytest.mark.asyncio
class TestPoolManagement:
    """Test connection pool management."""

    async def test_ensure_pool_initialized_creates_pool(self):
        """Test that pool is created if not provided."""
        handler = FreshnessDatabaseHandler(
            postgres_dsn="postgresql://user:pass@localhost:5432/testdb"
        )

        with patch(
            "handlers.freshness_database_handler.asyncpg.create_pool"
        ) as mock_create:
            # Make it return an awaitable that resolves to the pool
            async def async_pool():
                return MockAsyncpgPool()

            mock_create.return_value = async_pool()

            await handler._ensure_pool_initialized()

            assert handler._pool_initialized
            assert handler.pool is not None
            mock_create.assert_called_once()

    async def test_ensure_pool_initialized_reuses_pool(self, handler):
        """Test that existing pool is reused."""
        original_pool = handler.pool
        await handler._ensure_pool_initialized()

        assert handler.pool is original_pool
        assert handler._pool_initialized

    async def test_ensure_pool_initialization_failure(self):
        """Test handling of pool initialization failure."""
        handler = FreshnessDatabaseHandler(
            postgres_dsn="postgresql://user:pass@localhost:5432/testdb"
        )

        with patch(
            "handlers.freshness_database_handler.asyncpg.create_pool",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(
                RuntimeError, match="Failed to initialize PostgreSQL connection pool"
            ):
                await handler._ensure_pool_initialized()

    async def test_shutdown_closes_pool(self, mock_pool):
        """Test that shutdown closes the pool."""
        handler = FreshnessDatabaseHandler(pool=mock_pool)
        handler._pool_initialized = True

        await handler.shutdown()

        assert mock_pool.closed
        assert not handler._pool_initialized
        assert handler.pool is None

    async def test_shutdown_handles_close_error(self, mock_pool):
        """Test that shutdown handles pool close errors gracefully."""
        mock_pool.close = AsyncMock(side_effect=Exception("Close failed"))
        handler = FreshnessDatabaseHandler(pool=mock_pool)
        handler._pool_initialized = True

        # Should not raise exception
        await handler.shutdown()

        assert not handler._pool_initialized
        assert handler.pool is None


# ==============================================================================
# Query Execution Tests
# ==============================================================================


@pytest.mark.asyncio
class TestQueryExecution:
    """Test database query execution."""

    async def test_execute_query_fetch_all(self, handler):
        """Test query execution with FETCH ALL mode."""
        test_data = [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test",
            params=[],
            fetch_mode=EnumDbFetchMode.ALL,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0] == test_data[0]
        assert result["execution_time_ms"] > 0

    async def test_execute_query_fetch_one_with_data(self, handler):
        """Test query execution with FETCH ONE mode (data exists)."""
        test_data = [{"id": 1, "name": "test1"}]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test WHERE id = $1",
            params=[1],
            fetch_mode=EnumDbFetchMode.ONE,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 1
        assert len(result["data"]) == 1
        assert result["data"][0] == test_data[0]

    async def test_execute_query_fetch_one_no_data(self, handler):
        """Test query execution with FETCH ONE mode (no data)."""
        handler.pool.connection.return_data = []

        result = await handler._execute_query(
            query="SELECT * FROM test WHERE id = $1",
            params=[999],
            fetch_mode=EnumDbFetchMode.ONE,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 0
        assert result["data"] == []

    async def test_execute_query_fetch_many(self, handler):
        """Test query execution with FETCH MANY mode."""
        test_data = [{"id": i, "name": f"test{i}"} for i in range(10)]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test",
            params=[],
            fetch_mode=EnumDbFetchMode.MANY,
            limit=5,
            timeout_seconds=30.0,
        )

        # Note: Our mock returns all data, but real implementation would respect limit
        assert result["row_count"] == 10
        assert len(result["data"]) == 10

    async def test_execute_query_fetch_many_default_limit(self, handler):
        """Test query execution with FETCH MANY mode using default limit."""
        test_data = [{"id": i} for i in range(10)]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test",
            params=[],
            fetch_mode=EnumDbFetchMode.MANY,
            limit=None,  # Should default to 100
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 10

    async def test_execute_query_execute_mode(self, handler):
        """Test query execution with EXECUTE mode (no fetch)."""
        result = await handler._execute_query(
            query="UPDATE test SET name = $1 WHERE id = $2",
            params=["updated", 1],
            fetch_mode=EnumDbFetchMode.EXECUTE,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 3  # From mock "UPDATE 3"
        assert result["data"] is None

    async def test_execute_query_with_params(self, handler):
        """Test query execution with parameters."""
        test_data = [{"id": 1, "name": "test"}]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test WHERE id = $1 AND name = $2",
            params=[1, "test"],
            fetch_mode=EnumDbFetchMode.ALL,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 1
        # Verify params were passed
        assert handler.pool.connection.executed_queries[0]["params"] == (1, "test")

    async def test_execute_query_custom_timeout(self, handler):
        """Test query execution with custom timeout."""
        test_data = [{"id": 1}]
        handler.pool.connection.return_data = test_data

        result = await handler._execute_query(
            query="SELECT * FROM test",
            params=[],
            fetch_mode=EnumDbFetchMode.ALL,
            limit=None,
            timeout_seconds=5.0,
        )

        assert result["row_count"] == 1

    async def test_execute_query_timeout_error(self, handler):
        """Test query execution timeout handling."""

        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow query
            return []

        handler.pool.connection.fetch = slow_fetch

        with pytest.raises(Exception, match="Query timeout"):
            await handler._execute_query(
                query="SELECT * FROM test",
                params=[],
                fetch_mode=EnumDbFetchMode.ALL,
                limit=None,
                timeout_seconds=0.1,
            )

    async def test_execute_query_table_not_found(self, handler):
        """Test handling of table not found error."""
        import asyncpg

        handler.pool.connection.raise_error = asyncpg.UndefinedTableError(
            "table does not exist"
        )

        with pytest.raises(Exception, match="Table not found"):
            await handler._execute_query(
                query="SELECT * FROM nonexistent",
                params=[],
                fetch_mode=EnumDbFetchMode.ALL,
                limit=None,
                timeout_seconds=30.0,
            )

    async def test_execute_query_permission_denied(self, handler):
        """Test handling of permission denied error."""
        import asyncpg

        handler.pool.connection.raise_error = asyncpg.InsufficientPrivilegeError(
            "permission denied"
        )

        with pytest.raises(Exception, match="Permission denied"):
            await handler._execute_query(
                query="SELECT * FROM restricted",
                params=[],
                fetch_mode=EnumDbFetchMode.ALL,
                limit=None,
                timeout_seconds=30.0,
            )

    async def test_execute_query_unknown_fetch_mode(self, handler):
        """Test handling of unknown fetch mode."""
        with pytest.raises(ValueError, match="Unknown fetch mode"):
            await handler._execute_query(
                query="SELECT * FROM test",
                params=[],
                fetch_mode="INVALID",  # Invalid fetch mode
                limit=None,
                timeout_seconds=30.0,
            )


# ==============================================================================
# Event Handling Tests
# ==============================================================================


@pytest.mark.asyncio
class TestEventHandling:
    """Test event handling logic."""

    async def test_handle_event_success(self, handler_with_router):
        """Test successful event handling."""
        handler_with_router.pool.connection.return_data = [{"id": 1, "name": "test"}]

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                "query": "SELECT * FROM test",
                "params": [],
                "fetch_mode": "all",
            },
        )

        success = await handler_with_router.handle_event(event)

        assert success
        assert handler_with_router.metrics["events_handled"] == 1
        assert handler_with_router.metrics["queries_completed"] == 1
        assert handler_with_router.metrics["events_failed"] == 0

    async def test_handle_event_invalid_payload(self, handler_with_router):
        """Test handling of invalid payload."""
        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                # Missing required 'query' field
                "fetch_mode": "all",
            },
        )

        success = await handler_with_router.handle_event(event)

        assert not success
        assert handler_with_router.metrics["events_failed"] == 1
        assert handler_with_router.metrics["queries_failed"] == 1

    async def test_handle_event_query_execution_failure(self, handler_with_router):
        """Test handling of query execution failure."""
        handler_with_router.pool.connection.raise_error = Exception("Database error")

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                "query": "SELECT * FROM test",
                "params": [],
                "fetch_mode": "all",
            },
        )

        success = await handler_with_router.handle_event(event)

        assert not success
        assert handler_with_router.metrics["events_failed"] == 1
        assert handler_with_router.metrics["queries_failed"] == 1

    async def test_handle_event_with_all_payload_fields(self, handler_with_router):
        """Test event handling with all optional payload fields."""
        handler_with_router.pool.connection.return_data = [{"id": 1}]

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                "query": "SELECT * FROM test",
                "params": [1],
                "fetch_mode": "one",
                "limit": 10,
                "timeout_seconds": 5.0,
                "table_name": "test",
                "operation_type": "SELECT",
            },
        )

        success = await handler_with_router.handle_event(event)

        assert success
        assert handler_with_router.metrics["events_handled"] == 1

    async def test_handle_event_metrics_tracking(self, handler_with_router):
        """Test that metrics are properly tracked."""
        handler_with_router.pool.connection.return_data = [{"id": 1}, {"id": 2}]

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                "query": "SELECT * FROM test",
                "params": [],
                "fetch_mode": "all",
            },
        )

        await handler_with_router.handle_event(event)

        assert handler_with_router.metrics["events_handled"] == 1
        assert handler_with_router.metrics["queries_completed"] == 1
        assert handler_with_router.metrics["rows_affected"] == 2
        assert handler_with_router.metrics["total_processing_time_ms"] > 0
        assert handler_with_router.metrics["total_query_time_ms"] > 0


# ==============================================================================
# Response Publishing Tests
# ==============================================================================


@pytest.mark.asyncio
class TestResponsePublishing:
    """Test response publishing logic."""

    async def test_publish_completed_response(self, handler_with_router):
        """Test publishing successful query response."""
        correlation_id = str(uuid4())
        query_result = {
            "row_count": 5,
            "data": [{"id": i} for i in range(5)],
            "execution_time_ms": 10.5,
        }

        await handler_with_router._publish_completed_response(
            correlation_id=correlation_id,
            query="SELECT * FROM test",
            fetch_mode=EnumDbFetchMode.ALL,
            query_result=query_result,
            processing_time_ms=15.0,
            table_name="test",
            operation_type="SELECT",
        )

        handler_with_router._router.publish.assert_called_once()
        call_args = handler_with_router._router.publish.call_args

        assert call_args.kwargs["topic"] == handler_with_router.COMPLETED_TOPIC
        assert call_args.kwargs["key"] == correlation_id

    async def test_publish_failed_response(self, handler_with_router):
        """Test publishing failed query response."""
        correlation_id = str(uuid4())

        await handler_with_router._publish_failed_response(
            correlation_id=correlation_id,
            query="SELECT * FROM test",
            fetch_mode=EnumDbFetchMode.ALL,
            error_code=EnumDbQueryErrorCode.INTERNAL_ERROR,
            error_message="Query failed",
            retry_allowed=True,
            processing_time_ms=5.0,
            error_details={"exception": "DatabaseError"},
            table_name="test",
            operation_type="SELECT",
        )

        handler_with_router._router.publish.assert_called_once()
        call_args = handler_with_router._router.publish.call_args

        assert call_args.kwargs["topic"] == handler_with_router.FAILED_TOPIC
        assert call_args.kwargs["key"] == correlation_id

    async def test_publish_completed_response_error_handling(self, handler_with_router):
        """Test error handling in publish_completed_response."""
        handler_with_router._router.publish.side_effect = Exception("Publish failed")

        with pytest.raises(Exception, match="Publish failed"):
            await handler_with_router._publish_completed_response(
                correlation_id=str(uuid4()),
                query="SELECT * FROM test",
                fetch_mode=EnumDbFetchMode.ALL,
                query_result={"row_count": 0, "data": [], "execution_time_ms": 1.0},
                processing_time_ms=2.0,
                table_name=None,
                operation_type=None,
            )

    async def test_publish_failed_response_error_handling(self, handler_with_router):
        """Test error handling in publish_failed_response."""
        handler_with_router._router.publish.side_effect = Exception("Publish failed")

        with pytest.raises(Exception, match="Publish failed"):
            await handler_with_router._publish_failed_response(
                correlation_id=str(uuid4()),
                query="SELECT * FROM test",
                fetch_mode=EnumDbFetchMode.ALL,
                error_code=EnumDbQueryErrorCode.INTERNAL_ERROR,
                error_message="Error",
                retry_allowed=False,
            )


# ==============================================================================
# Metrics Tests
# ==============================================================================


@pytest.mark.asyncio
class TestMetrics:
    """Test metrics tracking and reporting."""

    def test_get_metrics_initial_state(self, handler):
        """Test metrics in initial state."""
        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["queries_completed"] == 0
        assert metrics["queries_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 0.0
        assert metrics["avg_query_time_ms"] == 0.0
        assert metrics["handler_name"] == "FreshnessDatabaseHandler"

    async def test_get_metrics_after_successful_events(self, handler_with_router):
        """Test metrics after successful event processing."""
        handler_with_router.pool.connection.return_data = [{"id": 1}]

        # Process two events
        for _ in range(2):
            event = MockEventEnvelope(
                event_type="DB_QUERY_REQUESTED",
                correlation_id=str(uuid4()),
                payload={
                    "query": "SELECT * FROM test",
                    "params": [],
                    "fetch_mode": "all",
                },
            )
            await handler_with_router.handle_event(event)

        metrics = handler_with_router.get_metrics()

        assert metrics["events_handled"] == 2
        assert metrics["queries_completed"] == 2
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] > 0
        assert metrics["avg_query_time_ms"] > 0

    async def test_get_metrics_after_failed_events(self, handler_with_router):
        """Test metrics after failed event processing."""
        # Process event with invalid payload
        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={"invalid": "data"},  # Missing required fields
        )
        await handler_with_router.handle_event(event)

        metrics = handler_with_router.get_metrics()

        assert metrics["events_failed"] == 1
        assert metrics["queries_failed"] == 1
        assert metrics["success_rate"] == 0.0

    async def test_get_metrics_mixed_results(self, handler_with_router):
        """Test metrics with mixed success/failure results."""
        handler_with_router.pool.connection.return_data = [{"id": 1}]

        # Successful event
        event1 = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={"query": "SELECT * FROM test", "params": [], "fetch_mode": "all"},
        )
        await handler_with_router.handle_event(event1)

        # Failed event
        event2 = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={"invalid": "data"},
        )
        await handler_with_router.handle_event(event2)

        metrics = handler_with_router.get_metrics()

        assert metrics["events_handled"] == 1
        assert metrics["events_failed"] == 1
        assert metrics["success_rate"] == 0.5


# ==============================================================================
# Error Handling and Edge Cases
# ==============================================================================


@pytest.mark.asyncio
class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    async def test_handle_event_with_dict_event(self, handler_with_router):
        """Test handling event as dictionary instead of object."""
        handler_with_router.pool.connection.return_data = [{"id": 1}]

        event_dict = {
            "event_type": "DB_QUERY_REQUESTED",
            "correlation_id": str(uuid4()),
            "payload": {
                "query": "SELECT * FROM test",
                "params": [],
                "fetch_mode": "all",
            },
        }

        success = await handler_with_router.handle_event(event_dict)

        assert success

    async def test_handle_event_publish_error_recovery(self, handler_with_router):
        """Test that publish errors during error handling don't crash handler."""
        handler_with_router.pool.connection.raise_error = Exception("Query error")
        handler_with_router._router.publish.side_effect = Exception("Publish error")

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={"query": "SELECT * FROM test", "params": [], "fetch_mode": "all"},
        )

        # Should not raise exception despite both query and publish failing
        success = await handler_with_router.handle_event(event)

        assert not success
        assert handler_with_router.metrics["events_failed"] == 1

    async def test_execute_query_execute_mode_parse_failure(self, handler):
        """Test EXECUTE mode when result string parsing fails."""

        # Mock connection that returns malformed result
        class BadExecuteConnection(MockAsyncpgConnection):
            async def execute(self, query, *params):
                return "MALFORMED_RESULT"

        handler.pool.connection = BadExecuteConnection()

        result = await handler._execute_query(
            query="UPDATE test SET value = 1",
            params=[],
            fetch_mode=EnumDbFetchMode.EXECUTE,
            limit=None,
            timeout_seconds=30.0,
        )

        assert result["row_count"] == 0  # Should default to 0 on parse failure

    async def test_handle_event_with_string_correlation_id(self, handler_with_router):
        """Test event handling with UUID string correlation ID."""
        handler_with_router.pool.connection.return_data = [{"id": 1}]

        # Use a valid UUID string
        correlation_id = str(uuid4())
        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=correlation_id,
            payload={"query": "SELECT * FROM test", "params": [], "fetch_mode": "all"},
        )

        success = await handler_with_router.handle_event(event)

        assert success

    async def test_handle_event_invalid_fetch_mode_in_error_path(
        self, handler_with_router
    ):
        """Test error path with invalid fetch_mode string."""
        handler_with_router.pool.connection.raise_error = Exception("Query error")

        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=str(uuid4()),
            payload={
                "query": "SELECT * FROM test",
                "params": [],
                "fetch_mode": "invalid_mode",  # Invalid fetch mode
            },
        )

        success = await handler_with_router.handle_event(event)

        assert not success
        # Should publish failure with default fetch_mode=ALL


# ==============================================================================
# Integration Tests
# ==============================================================================


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests combining multiple components."""

    async def test_full_query_lifecycle(self, handler_with_router):
        """Test complete query lifecycle from event to response."""
        handler_with_router.pool.connection.return_data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        correlation_id = str(uuid4())
        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=correlation_id,
            payload={
                "query": "SELECT id, name FROM users WHERE active = $1",
                "params": [True],
                "fetch_mode": "all",
                "table_name": "users",
                "operation_type": "SELECT",
            },
        )

        # Handle event
        success = await handler_with_router.handle_event(event)

        # Verify success
        assert success

        # Verify metrics updated
        metrics = handler_with_router.get_metrics()
        assert metrics["events_handled"] == 1
        assert metrics["queries_completed"] == 1
        assert metrics["rows_affected"] == 2

        # Verify response published
        handler_with_router._router.publish.assert_called_once()
        call_args = handler_with_router._router.publish.call_args
        assert call_args.kwargs["topic"] == handler_with_router.COMPLETED_TOPIC

    async def test_error_lifecycle(self, handler_with_router):
        """Test error handling lifecycle."""
        # Simulate table not found error
        import asyncpg

        handler_with_router.pool.connection.raise_error = asyncpg.UndefinedTableError(
            "table does not exist"
        )

        correlation_id = str(uuid4())
        event = MockEventEnvelope(
            event_type="DB_QUERY_REQUESTED",
            correlation_id=correlation_id,
            payload={
                "query": "SELECT * FROM nonexistent",
                "params": [],
                "fetch_mode": "all",
            },
        )

        # Handle event
        success = await handler_with_router.handle_event(event)

        # Verify failure
        assert not success

        # Verify metrics
        metrics = handler_with_router.get_metrics()
        assert metrics["events_failed"] == 1
        assert metrics["queries_failed"] == 1

        # Verify error response published
        handler_with_router._router.publish.assert_called_once()
        call_args = handler_with_router._router.publish.call_args
        assert call_args.kwargs["topic"] == handler_with_router.FAILED_TOPIC
