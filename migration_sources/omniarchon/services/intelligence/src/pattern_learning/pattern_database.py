"""
Pattern Learning Engine Database Connection Module

Provides AsyncPG connection pooling and initialization for pattern storage.
Integrates with Track 2 Intelligence Hook System for tracing.

Track: Track 3-1.2 - PostgreSQL Storage Layer
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID, uuid4

# Add config path for centralized timeout configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from src.config.timeout_config import get_db_timeout, get_retry_config

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available")


logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class PatternDatabaseManager:
    """
    Database connection manager for Pattern Learning Engine.

    Provides:
    - AsyncPG connection pool management
    - Schema initialization and migration
    - Health checks and monitoring
    - Integration with Track 2 PostgreSQL client

    Configuration via environment variables:
    - TRACEABILITY_DB_URL_EXTERNAL: PostgreSQL connection URL
    - TRACEABILITY_DB_HOST: Database host (fallback)
    - TRACEABILITY_DB_USER: Database user (fallback)
    - TRACEABILITY_DB_PASSWORD: Database password (fallback)
    """

    def __init__(
        self,
        connection_url: Optional[str] = None,
        min_pool_size: int = 5,
        max_pool_size: int = 20,
        command_timeout: Optional[float] = None,
        max_retry_attempts: Optional[int] = None,
        retry_base_delay: Optional[float] = None,
    ):
        """
        Initialize database manager.

        Args:
            connection_url: PostgreSQL connection URL (if None, uses env vars)
            min_pool_size: Minimum connections in pool (default: 5)
            max_pool_size: Maximum connections in pool (default: 20)
            command_timeout: Query timeout in seconds (default: from config)
            max_retry_attempts: Maximum retry attempts (default: from config)
            retry_base_delay: Base delay for exponential backoff (default: from config)
        """
        self.connection_url = connection_url or self._get_connection_url()
        self.pool: Optional["asyncpg.Pool"] = None
        self._pool_lock = asyncio.Lock()
        self._initialized = False
        self._connection_failed = False

        # Pool configuration with centralized config
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.command_timeout = (
            command_timeout if command_timeout is not None else get_db_timeout("query")
        )

        # Retry configuration from centralized config
        retry_config = get_retry_config()
        self.max_retry_attempts = (
            max_retry_attempts
            if max_retry_attempts is not None
            else retry_config["max_attempts"]
        )
        self.retry_base_delay = (
            retry_base_delay if retry_base_delay is not None else 1.0
        )

    def _get_connection_url(self) -> str:
        """Construct connection URL from environment variables."""
        # Primary: TRACEABILITY_DB_URL_EXTERNAL
        db_url = os.getenv("TRACEABILITY_DB_URL_EXTERNAL")
        if db_url:
            return db_url

        # Fallback: TRACEABILITY_DB_URL
        db_url = os.getenv("TRACEABILITY_DB_URL")
        if db_url:
            return db_url

        # Fallback: Construct from individual components
        host = os.getenv("TRACEABILITY_DB_HOST", "localhost")
        port = os.getenv("TRACEABILITY_DB_PORT", "5436")
        db = os.getenv("TRACEABILITY_DB_NAME", "omninode_bridge")
        user = os.getenv("TRACEABILITY_DB_USER", "postgres")
        password = os.getenv("TRACEABILITY_DB_PASSWORD", os.getenv("DB_PASSWORD", ""))

        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    async def initialize(self) -> bool:
        """
        Initialize connection pool with retry logic.

        Returns:
            True if successful, False otherwise
        """
        if not ASYNCPG_AVAILABLE:
            logger.error("AsyncPG not available - pattern learning disabled")
            return False

        if self._initialized or self._connection_failed:
            return self._initialized

        async with self._pool_lock:
            if self._initialized:
                return True

            attempt = 0

            while attempt < self.max_retry_attempts:
                try:
                    logger.info(
                        f"Initializing pattern database pool (attempt {attempt + 1}/{self.max_retry_attempts})"
                    )

                    self.pool = await asyncpg.create_pool(
                        self.connection_url,
                        min_size=self.min_pool_size,
                        max_size=self.max_pool_size,
                        command_timeout=self.command_timeout,
                        server_settings={
                            "application_name": "pattern_learning_engine",
                            "jit": "off",  # Disable JIT for short queries
                        },
                    )

                    # Verify connection with simple query
                    async with self.pool.acquire() as conn:
                        await conn.fetchval("SELECT 1")

                    self._initialized = True
                    logger.info(
                        "Pattern database pool initialized successfully",
                        extra={
                            "pool_size": f"{self.min_pool_size}-{self.max_pool_size}"
                        },
                    )
                    return True

                except Exception as e:
                    attempt += 1

                    if attempt < self.max_retry_attempts:
                        # Exponential backoff
                        delay = self.retry_base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"Connection attempt {attempt} failed, retrying in {delay}s: {e}",
                            extra={"attempt": attempt},
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Failed to initialize pattern database pool after {attempt} attempts: {e}",
                            exc_info=True,
                        )

            # Silent failure - don't break application
            self._connection_failed = True
            return False

    async def close(self):
        """Close connection pool gracefully."""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Pattern database pool closed")

    async def health_check(self) -> bool:
        """
        Perform health check on database connection.

        Returns:
            True if database is healthy, False otherwise
        """
        if not self._initialized or not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Pattern database health check failed: {e}")
            return False

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire connection from pool with error handling.

        Usage:
            async with db_manager.acquire() as conn:
                result = await conn.fetch("SELECT * FROM pattern_templates")
        """
        if not self._initialized:
            await self.initialize()

        if not self._initialized:
            # Return None for graceful degradation
            yield None
            return

        try:
            async with self.pool.acquire() as conn:
                yield conn
        except Exception as e:
            logger.error(f"Connection acquisition error: {e}", exc_info=True)
            yield None

    async def initialize_schema(self, schema_file: Optional[str] = None) -> bool:
        """
        Initialize pattern learning schema in database.

        Args:
            schema_file: Path to SQL schema file (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            if not await self.initialize():
                return False

        try:
            async with self.acquire() as conn:
                if not conn:
                    return False

                # Check if schema already exists
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'pattern_templates'
                    )
                """
                )

                if exists:
                    logger.info("Pattern learning schema already exists")
                    return True

                # If schema file provided, execute it
                if schema_file and os.path.exists(schema_file):
                    logger.info(f"Executing schema file: {schema_file}")
                    with open(schema_file, "r") as f:
                        schema_sql = f.read()
                    await conn.execute(schema_sql)
                    logger.info("Pattern learning schema initialized from file")
                    return True

                # Otherwise, find schema file in standard locations
                possible_paths = [
                    "./database/schema/pattern_learning_schema.sql",
                    "../database/schema/pattern_learning_schema.sql",
                ]

                for path in possible_paths:
                    if os.path.exists(path):
                        logger.info(f"Found schema file: {path}")
                        with open(path, "r") as f:
                            schema_sql = f.read()
                        await conn.execute(schema_sql)
                        logger.info("Pattern learning schema initialized")
                        return True

                logger.warning(
                    "No schema file found - schema must be initialized manually"
                )
                return False

        except Exception as e:
            logger.error(f"Schema initialization failed: {e}", exc_info=True)
            return False

    async def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics.

        Returns:
            Dict with pool statistics
        """
        if not self.pool:
            return {
                "initialized": False,
                "pool_size": 0,
                "idle_connections": 0,
                "active_connections": 0,
            }

        return {
            "initialized": self._initialized,
            "pool_size": self.pool.get_size(),
            "idle_connections": self.pool.get_idle_size(),
            "active_connections": self.pool.get_size() - self.pool.get_idle_size(),
            "min_pool_size": self.min_pool_size,
            "max_pool_size": self.max_pool_size,
        }


# ============================================================================
# Global Database Manager Instance
# ============================================================================

# Singleton instance for application-wide use
_db_manager: Optional[PatternDatabaseManager] = None


async def get_pattern_db_manager() -> PatternDatabaseManager:
    """
    Get or create global database manager instance.

    Returns:
        PatternDatabaseManager instance
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = PatternDatabaseManager()
        await _db_manager.initialize()

    return _db_manager


async def close_pattern_db_manager():
    """Close global database manager instance."""
    global _db_manager

    if _db_manager:
        await _db_manager.close()
        _db_manager = None


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """Example usage of PatternDatabaseManager"""
    # Create manager
    db_manager = await get_pattern_db_manager()

    # Initialize schema
    await db_manager.initialize_schema()

    # Health check
    healthy = await db_manager.health_check()
    print(f"Database healthy: {healthy}")

    # Get pool stats
    stats = await db_manager.get_pool_stats()
    print(f"Pool stats: {stats}")

    # Use connection
    async with db_manager.acquire() as conn:
        if conn:
            result = await conn.fetchval("SELECT COUNT(*) FROM pattern_templates")
            print(f"Pattern count: {result}")

    # Close manager
    await close_pattern_db_manager()


if __name__ == "__main__":
    asyncio.run(example_usage())
