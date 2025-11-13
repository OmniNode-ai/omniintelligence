"""
Database Performance Optimization Module

Provides optimized connection pooling, query optimization,
and database-specific performance tuning for Archon services.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict

import asyncpg
import httpx
from gqlalchemy import Memgraph
from supabase import create_client

logger = logging.getLogger(__name__)


@dataclass
class DatabasePerformanceConfig:
    """Database performance configuration settings"""

    # PostgreSQL/Supabase Configuration
    pg_pool_min_size: int = 5
    pg_pool_max_size: int = 20
    pg_pool_timeout: float = 30.0
    pg_command_timeout: float = 60.0
    pg_max_cached_statement_lifetime: int = 300
    pg_max_cacheable_statement_size: int = 1024

    # Memgraph Configuration
    memgraph_pool_size: int = 10
    memgraph_connection_timeout: float = 30.0
    memgraph_query_timeout: float = 120.0
    memgraph_max_retry_time: float = 60.0

    # HTTP Client Configuration
    http_pool_connections: int = 100
    http_pool_maxsize: int = 100
    http_max_keepalive_connections: int = 20
    http_keepalive_expiry: float = 30.0
    http_timeout: float = 30.0

    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_expected_exception: tuple = (Exception,)


class CircuitBreaker:
    """Circuit breaker pattern for database connections"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


class OptimizedSupabaseClient:
    """Optimized Supabase client with connection pooling and circuit breaker"""

    def __init__(self, url: str, key: str, config: DatabasePerformanceConfig):
        self.url = url
        self.key = key
        self.config = config
        self.client = None
        self.http_client = None
        self.circuit_breaker = CircuitBreaker(
            config.circuit_breaker_failure_threshold,
            config.circuit_breaker_recovery_timeout,
        )

    async def initialize(self):
        """Initialize optimized Supabase client"""
        try:
            # Create optimized HTTP client
            timeout = httpx.Timeout(
                timeout=self.config.http_timeout,
                connect=10.0,
                read=self.config.http_timeout,
                write=10.0,
                pool=5.0,
            )

            limits = httpx.Limits(
                max_connections=self.config.http_pool_connections,
                max_keepalive_connections=self.config.http_max_keepalive_connections,
                keepalive_expiry=self.config.http_keepalive_expiry,
            )

            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=True,  # Enable HTTP/2 for better performance
                verify=True,
            )

            # Create Supabase client with optimized HTTP client
            self.client = create_client(self.url, self.key)

            logger.info("Optimized Supabase client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    async def execute_with_circuit_breaker(self, operation, *args, **kwargs):
        """Execute database operation with circuit breaker protection"""
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open - service unavailable")

        try:
            result = await operation(*args, **kwargs)
            self.circuit_breaker.record_success()
            return result

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Database operation failed: {e}")
            raise

    async def close(self):
        """Close HTTP client connections"""
        if self.http_client:
            await self.http_client.aclose()


class OptimizedMemgraphClient:
    """Optimized Memgraph client with connection pooling"""

    def __init__(self, uri: str, config: DatabasePerformanceConfig):
        self.uri = uri
        self.config = config
        self.connection_pool = []
        self.pool_lock = asyncio.Lock()
        self.circuit_breaker = CircuitBreaker(
            config.circuit_breaker_failure_threshold,
            config.circuit_breaker_recovery_timeout,
        )

    async def initialize(self):
        """Initialize connection pool"""
        try:
            # Create connection pool
            for _ in range(self.config.memgraph_pool_size):
                connection = Memgraph(uri=self.uri)
                self.connection_pool.append(connection)

            logger.info(
                f"Memgraph connection pool initialized with {len(self.connection_pool)} connections"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Memgraph pool: {e}")
            raise

    @asynccontextmanager
    async def get_connection(self):
        """Get connection from pool with timeout"""
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open - Memgraph unavailable")

        start_time = time.time()
        connection = None

        try:
            async with self.pool_lock:
                while (
                    not self.connection_pool
                    and (time.time() - start_time)
                    < self.config.memgraph_connection_timeout
                ):
                    await asyncio.sleep(0.1)

                if not self.connection_pool:
                    raise TimeoutError("Connection pool exhausted")

                connection = self.connection_pool.pop()

            self.circuit_breaker.record_success()
            yield connection

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Memgraph connection error: {e}")
            raise
        finally:
            if connection:
                async with self.pool_lock:
                    self.connection_pool.append(connection)

    async def execute_query(self, query: str, parameters: dict = None):
        """Execute query with connection pooling and error handling"""
        async with self.get_connection() as connection:
            try:
                # Set query timeout
                result = await asyncio.wait_for(
                    connection.execute_and_fetch(query, parameters or {}),
                    timeout=self.config.memgraph_query_timeout,
                )
                return result

            except asyncio.TimeoutError:
                logger.error(f"Memgraph query timeout: {query[:100]}...")
                raise
            except Exception as e:
                logger.error(f"Memgraph query failed: {e}")
                raise

    async def close(self):
        """Close all connections in pool"""
        async with self.pool_lock:
            for connection in self.connection_pool:
                try:
                    connection.close()
                except Exception as e:
                    logger.warning(f"Error closing Memgraph connection: {e}")
            self.connection_pool.clear()


class OptimizedPostgreSQLClient:
    """Direct PostgreSQL client with advanced connection pooling"""

    def __init__(self, database_url: str, config: DatabasePerformanceConfig):
        self.database_url = database_url
        self.config = config
        self.pool = None
        self.circuit_breaker = CircuitBreaker(
            config.circuit_breaker_failure_threshold,
            config.circuit_breaker_recovery_timeout,
        )

    async def initialize(self):
        """Initialize optimized PostgreSQL connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.config.pg_pool_min_size,
                max_size=self.config.pg_pool_max_size,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                timeout=self.config.pg_pool_timeout,
                command_timeout=self.config.pg_command_timeout,
                server_settings={
                    "application_name": "archon_optimized",
                    "tcp_keepalives_idle": "600",
                    "tcp_keepalives_interval": "30",
                    "tcp_keepalives_count": "3",
                },
            )

            logger.info("Optimized PostgreSQL connection pool initialized")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise

    async def execute_with_retry(self, query: str, *args, max_retries: int = 3):
        """Execute query with retry logic and circuit breaker"""
        if self.circuit_breaker.is_open():
            raise Exception("Circuit breaker is open - PostgreSQL unavailable")

        for attempt in range(max_retries):
            try:
                async with self.pool.acquire() as connection:
                    result = await connection.fetch(query, *args)
                    self.circuit_breaker.record_success()
                    return result

            except Exception as e:
                if attempt == max_retries - 1:
                    self.circuit_breaker.record_failure()
                    logger.error(
                        f"PostgreSQL query failed after {max_retries} attempts: {e}"
                    )
                    raise

                await asyncio.sleep(2**attempt)  # Exponential backoff

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()


class DatabaseOptimizationManager:
    """Central manager for all database optimizations"""

    def __init__(self, config: DatabasePerformanceConfig = None):
        self.config = config or DatabasePerformanceConfig()
        self.supabase_client = None
        self.memgraph_client = None
        self.postgres_client = None
        self._initialized = False

    async def initialize(
        self,
        supabase_url: str = None,
        supabase_key: str = None,
        memgraph_uri: str = None,
        postgres_url: str = None,
    ):
        """Initialize all database clients"""
        try:
            if supabase_url and supabase_key:
                self.supabase_client = OptimizedSupabaseClient(
                    supabase_url, supabase_key, self.config
                )
                await self.supabase_client.initialize()

            if memgraph_uri:
                self.memgraph_client = OptimizedMemgraphClient(
                    memgraph_uri, self.config
                )
                await self.memgraph_client.initialize()

            if postgres_url:
                self.postgres_client = OptimizedPostgreSQLClient(
                    postgres_url, self.config
                )
                await self.postgres_client.initialize()

            self._initialized = True
            logger.info("Database optimization manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database optimization manager: {e}")
            raise

    async def health_check(self) -> Dict[str, bool]:
        """Comprehensive health check for all database connections"""
        health_status = {}

        # Check Supabase
        if self.supabase_client:
            try:
                # Simple query to test connection
                (
                    self.supabase_client.client.table("archon_projects")
                    .select("id")
                    .limit(1)
                    .execute()
                )
                health_status["supabase"] = True
            except Exception as e:
                logger.warning(f"Supabase health check failed: {e}")
                health_status["supabase"] = False

        # Check Memgraph
        if self.memgraph_client:
            try:
                await self.memgraph_client.execute_query("RETURN 1")
                health_status["memgraph"] = True
            except Exception as e:
                logger.warning(f"Memgraph health check failed: {e}")
                health_status["memgraph"] = False

        # Check PostgreSQL
        if self.postgres_client:
            try:
                await self.postgres_client.execute_with_retry("SELECT 1")
                health_status["postgres"] = True
            except Exception as e:
                logger.warning(f"PostgreSQL health check failed: {e}")
                health_status["postgres"] = False

        return health_status

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from all database clients"""
        metrics = {
            "timestamp": time.time(),
            "circuit_breakers": {},
            "connection_pools": {},
        }

        # Circuit breaker states
        if self.supabase_client:
            metrics["circuit_breakers"]["supabase"] = {
                "state": self.supabase_client.circuit_breaker.state,
                "failure_count": self.supabase_client.circuit_breaker.failure_count,
            }

        if self.memgraph_client:
            metrics["circuit_breakers"]["memgraph"] = {
                "state": self.memgraph_client.circuit_breaker.state,
                "failure_count": self.memgraph_client.circuit_breaker.failure_count,
            }

        if self.postgres_client:
            metrics["circuit_breakers"]["postgres"] = {
                "state": self.postgres_client.circuit_breaker.state,
                "failure_count": self.postgres_client.circuit_breaker.failure_count,
            }

        # Connection pool metrics
        if self.memgraph_client:
            metrics["connection_pools"]["memgraph"] = {
                "available_connections": len(self.memgraph_client.connection_pool),
                "total_pool_size": self.config.memgraph_pool_size,
            }

        if self.postgres_client and self.postgres_client.pool:
            metrics["connection_pools"]["postgres"] = {
                "pool_size": self.postgres_client.pool.get_size(),
                "idle_connections": self.postgres_client.pool.get_idle_size(),
                "max_size": self.config.pg_pool_max_size,
            }

        return metrics

    async def close(self):
        """Close all database connections"""
        if self.supabase_client:
            await self.supabase_client.close()

        if self.memgraph_client:
            await self.memgraph_client.close()

        if self.postgres_client:
            await self.postgres_client.close()

        self._initialized = False
        logger.info("Database optimization manager closed")


# Global instance
db_optimization_manager = DatabaseOptimizationManager()


async def get_optimized_db_manager() -> DatabaseOptimizationManager:
    """Get the global database optimization manager instance"""
    if not db_optimization_manager._initialized:
        raise RuntimeError("Database optimization manager not initialized")
    return db_optimization_manager
