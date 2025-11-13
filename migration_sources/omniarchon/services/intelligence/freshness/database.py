"""
Bridge Service Database Integration for Archon Document Freshness System

Comprehensive database layer through Bridge Service API with audit trails,
batch operations, and intelligent data management following Archon patterns.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg import Pool

from .models import (
    Dependency,
    DocumentFreshness,
    FreshnessAnalysis,
    FreshnessLevel,
    FreshnessScore,
    FreshnessStats,
    RefreshResult,
    RefreshStrategy,
)

logger = logging.getLogger(__name__)


class FreshnessDatabase:
    """
    Direct PostgreSQL database adapter for document freshness data
    with comprehensive audit trails and batch processing.
    """

    # PostgreSQL connection configuration
    DEFAULT_POSTGRES_HOST = "localhost"
    DEFAULT_POSTGRES_PORT = 5432
    DEFAULT_POSTGRES_DB = "omninode_bridge"
    DEFAULT_POSTGRES_USER = "postgres"
    DEFAULT_POSTGRES_PASSWORD = "postgres"

    def __init__(self, postgres_dsn: Optional[str] = None):
        """Initialize PostgreSQL connection"""
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

        self.pool: Optional[Pool] = None
        self._initialized = False

        # Database schema version for migrations
        self.schema_version = "1.0.0"

        logger.info(
            f"FreshnessDatabase initialized with PostgreSQL DSN: {self.postgres_dsn.split('@')[1]}"
        )

    async def initialize(self):
        """Initialize PostgreSQL connection pool"""
        try:
            # Create PostgreSQL connection pool
            logger.info(
                f"Creating PostgreSQL connection pool: {self.postgres_dsn.split('@')[1]}"
            )
            self.pool = await asyncpg.create_pool(
                self.postgres_dsn,
                min_size=2,
                max_size=10,
                command_timeout=30.0,
                timeout=10.0,
            )

            # Verify connectivity with a simple query
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

            self._initialized = True
            logger.info("PostgreSQL database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection: {e}")
            if self.pool:
                await self.pool.close()
                self.pool = None
            raise

    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._initialized = False
            logger.info("PostgreSQL database connection closed")

    async def _execute_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        fetch_mode: str = "all",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute query directly against PostgreSQL using asyncpg

        Args:
            query: SQL query to execute
            params: Query parameters
            fetch_mode: 'all', 'one', 'many', or 'execute'
            limit: Limit number of results

        Returns:
            Dictionary with success status, data, and metadata
        """
        if not self.pool:
            raise Exception("PostgreSQL connection pool not initialized")

        try:
            # Convert params list to tuple for asyncpg
            query_params = tuple(params) if params else ()

            async with self.pool.acquire() as conn:
                if fetch_mode == "all":
                    # Fetch all rows
                    rows = await conn.fetch(query, *query_params)
                    data = [dict(row) for row in rows]

                elif fetch_mode == "one":
                    # Fetch single row
                    row = await conn.fetchrow(query, *query_params)
                    data = [dict(row)] if row else []

                elif fetch_mode == "many":
                    # Fetch limited rows
                    fetch_limit = limit if limit else 100
                    rows = await conn.fetch(query, *query_params, limit=fetch_limit)
                    data = [dict(row) for row in rows]

                elif fetch_mode == "execute":
                    # Execute without fetching (INSERT, UPDATE, DELETE)
                    result = await conn.execute(query, *query_params)
                    # Parse result string like "UPDATE 5" to get row count
                    row_count = 0
                    if result and " " in result:
                        try:
                            row_count = int(result.split()[-1])
                        except (ValueError, IndexError):
                            pass
                    data = []  # No data for execute mode

                else:
                    raise ValueError(f"Unknown fetch mode: {fetch_mode}")

            return {
                "success": True,
                "data": data,
                "message": "Query executed successfully",
            }

        except Exception as e:
            logger.error(f"PostgreSQL query execution failed: {e}")
            return {"success": False, "data": None, "message": str(e)}

    async def _initialize_schema(self):
        """Create database schema if it doesn't exist"""

        schema_queries = [
            # Document freshness tracking table
            """
            CREATE TABLE IF NOT EXISTS document_freshness (
                id SERIAL PRIMARY KEY,
                document_id VARCHAR(64) UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                last_modified TIMESTAMP NOT NULL,
                last_analyzed TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP,

                -- Classification
                document_type VARCHAR(50) NOT NULL,
                classification_confidence FLOAT NOT NULL DEFAULT 0.0,
                language VARCHAR(50),

                -- Content analysis
                content_hash VARCHAR(64),
                content_summary TEXT,
                key_terms JSONB DEFAULT '[]',

                -- Freshness scoring
                freshness_score FLOAT NOT NULL DEFAULT 0.0,
                freshness_level VARCHAR(20) NOT NULL DEFAULT 'unknown',
                importance_score FLOAT NOT NULL DEFAULT 0.0,

                -- Dependencies
                depends_on JSONB DEFAULT '[]',
                dependent_by JSONB DEFAULT '[]',

                -- Metadata
                metadata JSONB DEFAULT '{}',
                tags JSONB DEFAULT '[]',

                -- Audit fields
                created_by VARCHAR(100) DEFAULT 'system',
                updated_by VARCHAR(100) DEFAULT 'system',
                updated_at TIMESTAMP DEFAULT NOW(),
                version INTEGER DEFAULT 1
            )
            """,
            # Freshness scores history table
            """
            CREATE TABLE IF NOT EXISTS freshness_scores_history (
                id SERIAL PRIMARY KEY,
                document_id VARCHAR(64) NOT NULL,
                score_timestamp TIMESTAMP DEFAULT NOW(),
                freshness_score FLOAT NOT NULL,
                freshness_level VARCHAR(20) NOT NULL,
                importance_score FLOAT NOT NULL,

                -- Score components
                age_score FLOAT,
                dependency_score FLOAT,
                usage_score FLOAT,
                content_change_score FLOAT,

                -- Context
                calculation_method VARCHAR(50),
                metadata JSONB DEFAULT '{}',

                FOREIGN KEY (document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE
            )
            """,
            # Dependencies tracking table
            """
            CREATE TABLE IF NOT EXISTS document_dependencies (
                id SERIAL PRIMARY KEY,
                source_document_id VARCHAR(64) NOT NULL,
                target_document_id VARCHAR(64) NOT NULL,
                dependency_type VARCHAR(50) NOT NULL,
                dependency_strength FLOAT DEFAULT 1.0,

                -- Context
                detected_method VARCHAR(50),
                confidence FLOAT DEFAULT 1.0,
                metadata JSONB DEFAULT '{}',

                -- Timestamps
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(source_document_id, target_document_id, dependency_type),
                FOREIGN KEY (source_document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE,
                FOREIGN KEY (target_document_id) REFERENCES document_freshness(document_id) ON DELETE CASCADE
            )
            """,
            # Refresh operations log
            """
            CREATE TABLE IF NOT EXISTS refresh_operations_log (
                id SERIAL PRIMARY KEY,
                operation_id VARCHAR(64) UNIQUE NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',

                -- Scope
                target_documents JSONB DEFAULT '[]',
                refresh_strategy JSONB DEFAULT '{}',

                -- Execution
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                duration_seconds FLOAT,

                -- Results
                documents_processed INTEGER DEFAULT 0,
                documents_updated INTEGER DEFAULT 0,
                documents_failed INTEGER DEFAULT 0,

                -- Details
                error_message TEXT,
                metadata JSONB DEFAULT '{}',

                -- Context
                triggered_by VARCHAR(100) DEFAULT 'system',
                trigger_reason TEXT
            )
            """,
            # Performance metrics table
            """
            CREATE TABLE IF NOT EXISTS freshness_metrics (
                id SERIAL PRIMARY KEY,
                metric_timestamp TIMESTAMP DEFAULT NOW(),
                metric_type VARCHAR(50) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value FLOAT NOT NULL,

                -- Context
                document_id VARCHAR(64),
                operation_id VARCHAR(64),
                metadata JSONB DEFAULT '{}',

                -- Grouping
                metric_category VARCHAR(50),
                metric_tags JSONB DEFAULT '[]'
            )
            """,
        ]

        # Create indexes
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_document_freshness_document_id ON document_freshness(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_freshness_last_modified ON document_freshness(last_modified)",
            "CREATE INDEX IF NOT EXISTS idx_document_freshness_freshness_level ON document_freshness(freshness_level)",
            "CREATE INDEX IF NOT EXISTS idx_document_freshness_document_type ON document_freshness(document_type)",
            "CREATE INDEX IF NOT EXISTS idx_freshness_scores_document_id ON freshness_scores_history(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_freshness_scores_timestamp ON freshness_scores_history(score_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_document_dependencies_source ON document_dependencies(source_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_document_dependencies_target ON document_dependencies(target_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_operations_status ON refresh_operations_log(status)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_operations_started ON refresh_operations_log(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_freshness_metrics_timestamp ON freshness_metrics(metric_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_freshness_metrics_type ON freshness_metrics(metric_type)",
        ]

        try:
            # Execute schema creation queries
            for query in schema_queries:
                result = await self._execute_query(query, fetch_mode="execute")
                if not result.get("success", False):
                    logger.error(f"Schema creation failed: {result.get('message')}")

            # Create indexes
            for query in index_queries:
                result = await self._execute_query(query, fetch_mode="execute")
                if not result.get("success", False):
                    logger.warning(f"Index creation failed: {result.get('message')}")

            logger.info("Database schema initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise

    async def health_check(self, timeout_seconds: float = 5.0) -> bool:
        """
        Check PostgreSQL database health with timeout.

        Args:
            timeout_seconds: Maximum time to wait for health check (default: 5s)

        Returns:
            True if healthy, False otherwise (including timeout)
        """
        try:
            if not self.pool:
                return False

            # Wrap health check in timeout to prevent blocking
            async def _do_health_check():
                # Test basic query - use document_freshness table to verify schema exists
                result = await self._execute_query(
                    "SELECT COUNT(*) as test_connection FROM document_freshness",
                    fetch_mode="one",
                )

                return result.get("success", False)

            # Execute with timeout
            return await asyncio.wait_for(_do_health_check(), timeout=timeout_seconds)

        except asyncio.TimeoutError:
            logger.warning(f"Database health check timed out after {timeout_seconds}s")
            return False
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    # Document operations
    async def upsert_document(
        self, document: DocumentFreshness, update_strategy: str = "merge"
    ) -> bool:
        """
        Insert or update document freshness record

        Args:
            document: Document freshness data
            update_strategy: 'merge', 'replace', 'skip_existing'

        Returns:
            True if operation successful
        """
        try:
            # Check if document exists
            existing_result = await self._execute_query(
                "SELECT document_id FROM document_freshness WHERE document_id = $1",
                params=[document.document_id],
                fetch_mode="one",
            )

            if existing_result.get("data") and update_strategy == "skip_existing":
                logger.debug(f"Document {document.document_id} exists, skipping")
                return True

            # Prepare document data
            document_data = {
                "document_id": document.document_id,
                "file_path": document.file_path,
                "file_size_bytes": document.file_size_bytes,
                "last_modified": document.last_modified.isoformat(),
                "last_analyzed": (
                    document.last_analyzed.isoformat()
                    if document.last_analyzed
                    else None
                ),
                "created_at": (
                    document.created_at.isoformat() if document.created_at else None
                ),
                "document_type": document.document_type,
                "classification_confidence": document.classification_confidence,
                "language": document.language,
                "content_hash": document.content_hash,
                "content_summary": document.content_summary,
                "key_terms": (
                    json.dumps(document.key_terms) if document.key_terms else "[]"
                ),
                "freshness_score": document.freshness_score,
                "freshness_level": document.freshness_level.value,
                "importance_score": document.importance_score,
                "depends_on": (
                    json.dumps([dep.dict() for dep in document.depends_on])
                    if document.depends_on
                    else "[]"
                ),
                "dependent_by": (
                    json.dumps([dep.dict() for dep in document.dependent_by])
                    if document.dependent_by
                    else "[]"
                ),
                "metadata": (
                    json.dumps(document.metadata) if document.metadata else "{}"
                ),
                "tags": json.dumps(document.tags) if document.tags else "[]",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if existing_result.get("data"):
                # Update existing document
                update_query = """
                UPDATE document_freshness SET
                    file_path = $2, file_size_bytes = $3, last_modified = $4,
                    last_analyzed = $5, document_type = $6, classification_confidence = $7,
                    language = $8, content_hash = $9, content_summary = $10,
                    key_terms = $11, freshness_score = $12, freshness_level = $13,
                    importance_score = $14, depends_on = $15, dependent_by = $16,
                    metadata = $17, tags = $18, updated_at = $19, version = version + 1
                WHERE document_id = $1
                """

                params = [
                    document.document_id,
                    document_data["file_path"],
                    document_data["file_size_bytes"],
                    document_data["last_modified"],
                    document_data["last_analyzed"],
                    document_data["document_type"],
                    document_data["classification_confidence"],
                    document_data["language"],
                    document_data["content_hash"],
                    document_data["content_summary"],
                    document_data["key_terms"],
                    document_data["freshness_score"],
                    document_data["freshness_level"],
                    document_data["importance_score"],
                    document_data["depends_on"],
                    document_data["dependent_by"],
                    document_data["metadata"],
                    document_data["tags"],
                    document_data["updated_at"],
                ]

            else:
                # Insert new document
                insert_query = """
                INSERT INTO document_freshness (
                    document_id, file_path, file_size_bytes, last_modified,
                    last_analyzed, created_at, document_type, classification_confidence,
                    language, content_hash, content_summary, key_terms,
                    freshness_score, freshness_level, importance_score,
                    depends_on, dependent_by, metadata, tags, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                """

                params = [
                    document.document_id,
                    document_data["file_path"],
                    document_data["file_size_bytes"],
                    document_data["last_modified"],
                    document_data["last_analyzed"],
                    document_data["created_at"],
                    document_data["document_type"],
                    document_data["classification_confidence"],
                    document_data["language"],
                    document_data["content_hash"],
                    document_data["content_summary"],
                    document_data["key_terms"],
                    document_data["freshness_score"],
                    document_data["freshness_level"],
                    document_data["importance_score"],
                    document_data["depends_on"],
                    document_data["dependent_by"],
                    document_data["metadata"],
                    document_data["tags"],
                    document_data["updated_at"],
                ]

                update_query = insert_query

            # Execute the query
            result = await self._execute_query(
                update_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(f"Document upsert failed: {result.get('message')}")
                return False

            logger.debug(f"Document {document.document_id} upserted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to upsert document {document.document_id}: {e}")
            return False

    async def get_document(self, document_id: str) -> Optional[DocumentFreshness]:
        """Get document by ID"""
        try:
            result = await self._execute_query(
                "SELECT * FROM document_freshness WHERE document_id = $1",
                params=[document_id],
                fetch_mode="one",
            )

            if not result.get("success", False) or not result.get("data"):
                return None

            row = (
                result["data"][0]
                if isinstance(result["data"], list)
                else result["data"]
            )
            return self._row_to_document(row)

        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            return None

    def _row_to_document(self, row: Dict[str, Any]) -> DocumentFreshness:
        """Convert database row to DocumentFreshness object"""
        return DocumentFreshness(
            document_id=row["document_id"],
            file_path=row["file_path"],
            file_size_bytes=row["file_size_bytes"],
            last_modified=datetime.fromisoformat(
                row["last_modified"].replace("Z", "+00:00")
            ),
            last_analyzed=(
                datetime.fromisoformat(row["last_analyzed"].replace("Z", "+00:00"))
                if row.get("last_analyzed")
                else None
            ),
            created_at=(
                datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                if row.get("created_at")
                else None
            ),
            document_type=row["document_type"],
            classification_confidence=row.get("classification_confidence", 0.0),
            language=row.get("language"),
            content_hash=row.get("content_hash"),
            content_summary=row.get("content_summary"),
            key_terms=(
                json.loads(row.get("key_terms", "[]")) if row.get("key_terms") else []
            ),
            freshness_score=row.get("freshness_score", 0.0),
            freshness_level=FreshnessLevel(row.get("freshness_level", "unknown")),
            importance_score=row.get("importance_score", 0.0),
            depends_on=(
                [Dependency(**dep) for dep in json.loads(row.get("depends_on", "[]"))]
                if row.get("depends_on")
                else []
            ),
            dependent_by=(
                [Dependency(**dep) for dep in json.loads(row.get("dependent_by", "[]"))]
                if row.get("dependent_by")
                else []
            ),
            metadata=(
                json.loads(row.get("metadata", "{}")) if row.get("metadata") else {}
            ),
            tags=json.loads(row.get("tags", "[]")) if row.get("tags") else [],
        )

    async def get_documents_by_filter(
        self,
        freshness_level: Optional[FreshnessLevel] = None,
        document_type: Optional[str] = None,
        modified_since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[DocumentFreshness]:
        """Get documents by various filters"""
        try:
            where_conditions = []
            params = []
            param_count = 0

            if freshness_level:
                param_count += 1
                where_conditions.append(f"freshness_level = ${param_count}")
                params.append(freshness_level.value)

            if document_type:
                param_count += 1
                where_conditions.append(f"document_type = ${param_count}")
                params.append(document_type)

            if modified_since:
                param_count += 1
                where_conditions.append(f"last_modified >= ${param_count}")
                params.append(modified_since.isoformat())

            query = "SELECT * FROM document_freshness"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            query += " ORDER BY last_modified DESC"

            result = await self._execute_query(query, params=params, limit=limit)

            if not result.get("success", False) or not result.get("data"):
                return []

            documents = []
            for row in result["data"]:
                try:
                    document = self._row_to_document(row)
                    documents.append(document)
                except Exception as e:
                    logger.warning(f"Failed to parse document row: {e}")
                    continue

            return documents

        except Exception as e:
            logger.error(f"Failed to get documents by filter: {e}")
            return []

    async def get_stale_documents(
        self,
        staleness_threshold: timedelta = timedelta(days=7),
        limit: Optional[int] = None,
        freshness_levels: Optional[List[FreshnessLevel]] = None,
        priority_filter: Optional[str] = None,
        document_types: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
    ) -> List[DocumentFreshness]:
        """Get documents that are stale with comprehensive filtering options"""
        try:
            where_conditions = []
            params = []
            param_count = 0

            # Default staleness filter
            if max_age_days:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            else:
                cutoff_time = datetime.now(timezone.utc) - staleness_threshold

            param_count += 1
            where_conditions.append(f"last_analyzed <= ${param_count}")
            params.append(cutoff_time.isoformat())

            # Filter by freshness levels
            if freshness_levels:
                param_count += 1
                freshness_values = [
                    level.value if isinstance(level, FreshnessLevel) else level
                    for level in freshness_levels
                ]
                where_conditions.append(f"freshness_level = ANY(${param_count})")
                params.append(freshness_values)

            # Filter by document types
            if document_types:
                param_count += 1
                where_conditions.append(f"document_type = ANY(${param_count})")
                params.append(document_types)

            # Priority filter (based on importance_score)
            if priority_filter:
                if priority_filter.upper() == "LOW":
                    param_count += 1
                    where_conditions.append(f"importance_score < ${param_count}")
                    params.append(0.3)
                elif priority_filter.upper() == "MEDIUM":
                    param_count += 1
                    where_conditions.append(
                        f"importance_score >= ${param_count} AND importance_score < ${param_count + 1}"
                    )
                    params.append(0.3)
                    param_count += 1
                    params.append(0.7)
                elif priority_filter.upper() in ["HIGH", "CRITICAL"]:
                    param_count += 1
                    where_conditions.append(f"importance_score >= ${param_count}")
                    params.append(0.7)

            # Build and execute query
            query = "SELECT * FROM document_freshness"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            query += " ORDER BY last_analyzed ASC, importance_score DESC"

            result = await self._execute_query(query, params=params, limit=limit)

            if not result.get("success", False) or not result.get("data"):
                return []

            documents = []
            for row in result["data"]:
                try:
                    document = self._row_to_document(row)
                    documents.append(document)
                except Exception as e:
                    logger.warning(f"Failed to parse stale document row: {e}")
                    continue

            return documents

        except Exception as e:
            logger.error(f"Failed to get stale documents: {e}")
            return []

    async def record_freshness_score(
        self,
        document_id: str,
        score: FreshnessScore,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record freshness score in history"""
        try:
            insert_query = """
            INSERT INTO freshness_scores_history (
                document_id, score_timestamp, freshness_score, freshness_level,
                importance_score, age_score, dependency_score, usage_score,
                content_change_score, calculation_method, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """

            params = [
                document_id,
                score.timestamp.isoformat(),
                score.overall_score,
                score.freshness_level.value,
                score.importance_score,
                score.age_score,
                score.dependency_score,
                score.usage_score,
                score.content_change_score,
                score.calculation_method,
                json.dumps(metadata or {}),
            ]

            result = await self._execute_query(
                insert_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(
                    f"Failed to record freshness score: {result.get('message')}"
                )
                return False

            logger.debug(f"Freshness score recorded for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to record freshness score for {document_id}: {e}")
            return False

    async def get_freshness_stats(
        self, base_path: Optional[str] = None
    ) -> FreshnessStats:
        """Get comprehensive freshness statistics"""
        try:
            # Build query with optional base_path filter
            base_query = """
                SELECT
                    COUNT(*) as total_documents,
                    COUNT(CASE WHEN freshness_level = 'fresh' THEN 1 END) as fresh_count,
                    COUNT(CASE WHEN freshness_level = 'stale' THEN 1 END) as stale_count,
                    COUNT(CASE WHEN freshness_level = 'critical' THEN 1 END) as critical_count,
                    AVG(freshness_score) as avg_freshness_score,
                    AVG(importance_score) as avg_importance_score
                FROM document_freshness
            """

            params = []
            if base_path:
                base_query += " WHERE file_path LIKE $1"
                params.append(f"{base_path}%")

            # Get basic counts
            count_result = await self._execute_query(
                base_query, params=params, fetch_mode="one"
            )

            if not count_result.get("success", False) or not count_result.get("data"):
                return FreshnessStats(
                    total_documents=0,
                    fresh_count=0,
                    stale_count=0,
                    outdated_count=0,
                    critical_count=0,
                    average_age_days=0.0,
                    average_freshness_score=0.0,
                    recently_updated_count=0,
                    last_updated=datetime.now(timezone.utc),
                )

            counts = (
                count_result["data"][0]
                if isinstance(count_result["data"], list)
                else count_result["data"]
            )

            # Get recent refresh operations
            recent_ops_query = """
                SELECT COUNT(*) as recent_refreshes
                FROM refresh_operations_log
                WHERE started_at >= $1 AND status = 'completed'
            """
            recent_ops_params = [datetime.now(timezone.utc) - timedelta(hours=24)]

            if base_path:
                # Filter refresh operations that targeted documents in the base_path
                recent_ops_query += """
                    AND EXISTS (
                        SELECT 1 FROM document_freshness df
                        WHERE df.document_id = ANY(
                            SELECT jsonb_array_elements_text(target_documents)
                        ) AND df.file_path LIKE $2
                    )
                """
                recent_ops_params.append(f"{base_path}%")

            recent_ops_result = await self._execute_query(
                recent_ops_query, params=recent_ops_params, fetch_mode="one"
            )

            recent_refreshes = 0
            if recent_ops_result.get("success", False) and recent_ops_result.get(
                "data"
            ):
                recent_data = (
                    recent_ops_result["data"][0]
                    if isinstance(recent_ops_result["data"], list)
                    else recent_ops_result["data"]
                )
                recent_refreshes = recent_data.get("recent_refreshes", 0)

            return FreshnessStats(
                total_documents=counts.get("total_documents", 0),
                fresh_count=counts.get("fresh_count", 0),
                stale_count=counts.get("stale_count", 0),
                outdated_count=0,  # TODO: Add proper tracking for outdated docs
                critical_count=counts.get("critical_count", 0),
                average_age_days=0.0,  # TODO: Calculate proper average age
                average_freshness_score=counts.get("avg_freshness_score", 0.0),
                recently_updated_count=recent_refreshes,
                last_updated=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Failed to get freshness stats: {e}")
            return FreshnessStats(
                total_documents=0,
                fresh_count=0,
                stale_count=0,
                outdated_count=0,
                critical_count=0,
                average_age_days=0.0,
                average_freshness_score=0.0,
                recently_updated_count=0,
                last_updated=datetime.now(timezone.utc),
            )

    async def log_refresh_operation(
        self,
        operation_id: str,
        operation_type: str,
        target_documents: List[str],
        strategy: RefreshStrategy,
        triggered_by: str = "system",
        trigger_reason: str = "",
    ) -> bool:
        """Log refresh operation start"""
        try:
            insert_query = """
            INSERT INTO refresh_operations_log (
                operation_id, operation_type, status, target_documents,
                refresh_strategy, triggered_by, trigger_reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            params = [
                operation_id,
                operation_type,
                "pending",
                json.dumps(target_documents),
                json.dumps(strategy.dict()),
                triggered_by,
                trigger_reason,
            ]

            result = await self._execute_query(
                insert_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(
                    f"Failed to log refresh operation: {result.get('message')}"
                )
                return False

            logger.debug(f"Refresh operation {operation_id} logged")
            return True

        except Exception as e:
            logger.error(f"Failed to log refresh operation {operation_id}: {e}")
            return False

    async def update_refresh_operation_status(
        self,
        operation_id: str,
        status: str,
        documents_processed: int = 0,
        documents_updated: int = 0,
        documents_failed: int = 0,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update refresh operation status"""
        try:
            update_query = """
            UPDATE refresh_operations_log SET
                status = $2,
                completed_at = $3,
                documents_processed = $4,
                documents_updated = $5,
                documents_failed = $6,
                error_message = $7,
                metadata = $8
            WHERE operation_id = $1
            """

            params = [
                operation_id,
                status,
                (
                    datetime.now(timezone.utc).isoformat()
                    if status in ["completed", "failed"]
                    else None
                ),
                documents_processed,
                documents_updated,
                documents_failed,
                error_message,
                json.dumps(metadata or {}),
            ]

            result = await self._execute_query(
                update_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(
                    f"Failed to update refresh operation status: {result.get('message')}"
                )
                return False

            logger.debug(f"Refresh operation {operation_id} status updated to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update refresh operation {operation_id}: {e}")
            return False

    async def record_metric(
        self,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        document_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metric_category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Record performance metric"""
        try:
            insert_query = """
            INSERT INTO freshness_metrics (
                metric_type, metric_name, metric_value, document_id,
                operation_id, metadata, metric_category, metric_tags
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """

            params = [
                metric_type,
                metric_name,
                metric_value,
                document_id,
                operation_id,
                json.dumps(metadata or {}),
                metric_category,
                json.dumps(tags or []),
            ]

            result = await self._execute_query(
                insert_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(f"Failed to record metric: {result.get('message')}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
            return False

    async def get_recent_analyses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent freshness analyses"""
        try:
            result = await self._execute_query(
                """
                SELECT
                    df.document_id,
                    df.file_path,
                    df.document_type,
                    df.freshness_level,
                    df.freshness_score,
                    df.importance_score,
                    df.last_analyzed,
                    df.content_summary
                FROM document_freshness df
                WHERE df.last_analyzed IS NOT NULL
                ORDER BY df.last_analyzed DESC
                LIMIT $1
            """,
                params=[limit],
            )

            if not result.get("success", False) or not result.get("data"):
                return []

            analyses = []
            for row in result["data"]:
                try:
                    analysis = {
                        "document_id": row["document_id"],
                        "file_path": row["file_path"],
                        "document_type": row["document_type"],
                        "freshness_level": row["freshness_level"],
                        "freshness_score": row.get("freshness_score", 0.0),
                        "importance_score": row.get("importance_score", 0.0),
                        "last_analyzed": row.get("last_analyzed"),
                        "content_summary": row.get("content_summary"),
                    }
                    analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse recent analysis row: {e}")
                    continue

            return analyses

        except Exception as e:
            logger.error(f"Failed to get recent analyses: {e}")
            return []

    async def get_document_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get document by file path"""
        try:
            result = await self._execute_query(
                "SELECT * FROM document_freshness WHERE file_path = $1",
                params=[file_path],
                fetch_mode="one",
            )

            if not result.get("success", False) or not result.get("data"):
                return None

            row = (
                result["data"][0]
                if isinstance(result["data"], list)
                else result["data"]
            )

            # Return as dictionary rather than DocumentFreshness object for API compatibility
            return {
                "document_id": row["document_id"],
                "file_path": row["file_path"],
                "file_size_bytes": row["file_size_bytes"],
                "last_modified": row["last_modified"],
                "last_analyzed": row.get("last_analyzed"),
                "created_at": row.get("created_at"),
                "document_type": row["document_type"],
                "classification_confidence": row.get("classification_confidence", 0.0),
                "language": row.get("language"),
                "content_hash": row.get("content_hash"),
                "content_summary": row.get("content_summary"),
                "key_terms": (
                    json.loads(row.get("key_terms", "[]"))
                    if row.get("key_terms")
                    else []
                ),
                "freshness_score": row.get("freshness_score", 0.0),
                "freshness_level": row.get("freshness_level", "unknown"),
                "importance_score": row.get("importance_score", 0.0),
                "depends_on": (
                    json.loads(row.get("depends_on", "[]"))
                    if row.get("depends_on")
                    else []
                ),
                "dependent_by": (
                    json.loads(row.get("dependent_by", "[]"))
                    if row.get("dependent_by")
                    else []
                ),
                "metadata": (
                    json.loads(row.get("metadata", "{}")) if row.get("metadata") else {}
                ),
                "tags": json.loads(row.get("tags", "[]")) if row.get("tags") else [],
            }

        except Exception as e:
            logger.error(f"Failed to get document by path {file_path}: {e}")
            return None

    async def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Clean up old freshness data to prevent database bloat"""
        try:
            if days_to_keep < 7:
                raise ValueError("days_to_keep must be at least 7")

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            # Delete old freshness scores history
            result1 = await self._execute_query(
                """
                DELETE FROM freshness_scores_history
                WHERE score_timestamp < $1
            """,
                params=[cutoff_date.isoformat()],
                fetch_mode="execute",
            )

            # Delete old refresh operations log
            result2 = await self._execute_query(
                """
                DELETE FROM refresh_operations_log
                WHERE started_at < $1
            """,
                params=[cutoff_date.isoformat()],
                fetch_mode="execute",
            )

            # Delete old metrics
            result3 = await self._execute_query(
                """
                DELETE FROM freshness_metrics
                WHERE metric_timestamp < $1
            """,
                params=[cutoff_date.isoformat()],
                fetch_mode="execute",
            )

            # Count total deletions (simplified approach - return estimated count)
            total_deleted = 0
            if result1.get("success", False):
                total_deleted += result1.get("rows_affected", 0)
            if result2.get("success", False):
                total_deleted += result2.get("rows_affected", 0)
            if result3.get("success", False):
                total_deleted += result3.get("rows_affected", 0)

            logger.info(
                f"Cleaned up {total_deleted} old freshness records older than {days_to_keep} days"
            )
            return total_deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0

    async def store_analysis(self, analysis: "FreshnessAnalysis") -> bool:
        """
        Store complete freshness analysis results in database

        Args:
            analysis: FreshnessAnalysis object containing analysis results

        Returns:
            True if operation successful
        """
        try:
            # First, store all documents in the analysis
            documents_stored = 0
            for document in analysis.documents:
                success = await self.upsert_document(document, update_strategy="merge")
                if success:
                    documents_stored += 1
                else:
                    logger.warning(
                        f"Failed to store document {document.document_id} from analysis {analysis.analysis_id}"
                    )

            # Store analysis metadata in refresh operations log
            operation_id = analysis.analysis_id
            analysis_metadata = {
                "analysis_type": (
                    "directory_analysis"
                    if len(analysis.documents) > 1
                    else "single_document_analysis"
                ),
                "base_path": analysis.base_path,
                "total_documents": analysis.total_documents,
                "analyzed_documents": analysis.analyzed_documents,
                "skipped_documents": analysis.skipped_documents,
                "average_freshness_score": analysis.average_freshness_score,
                "stale_documents_count": analysis.stale_documents_count,
                "critical_documents_count": analysis.critical_documents_count,
                "total_dependencies": analysis.total_dependencies,
                "broken_dependencies": analysis.broken_dependencies,
                "freshness_distribution": analysis.freshness_distribution,
                "recommendations": analysis.recommendations,
                "priority_actions": analysis.priority_actions,
                "analysis_time_seconds": analysis.analysis_time_seconds,
                "memory_usage_mb": analysis.memory_usage_mb,
                "error_count": analysis.error_count,
                "warnings": analysis.warnings,
                "documents_stored": documents_stored,
            }

            # Log the analysis as a refresh operation for tracking
            insert_query = """
            INSERT INTO refresh_operations_log (
                operation_id, operation_type, status, target_documents,
                refresh_strategy, started_at, completed_at,
                documents_processed, documents_updated, documents_failed,
                metadata, triggered_by, trigger_reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (operation_id) DO UPDATE SET
                documents_processed = EXCLUDED.documents_processed,
                documents_updated = EXCLUDED.documents_updated,
                metadata = EXCLUDED.metadata,
                completed_at = EXCLUDED.completed_at
            """

            params = [
                operation_id,
                "freshness_analysis",
                "completed",
                json.dumps([doc.document_id for doc in analysis.documents]),
                json.dumps({"analysis_scope": analysis.base_path}),
                analysis.analyzed_at.isoformat(),
                analysis.analyzed_at.isoformat(),  # completed_at same as analyzed_at for analysis
                analysis.analyzed_documents,
                documents_stored,
                analysis.error_count,
                json.dumps(analysis_metadata),
                "freshness_monitor",
                f"Analysis of {analysis.base_path}",
            ]

            result = await self._execute_query(
                insert_query, params=params, fetch_mode="execute"
            )

            if not result.get("success", False):
                logger.error(
                    f"Failed to store analysis metadata: {result.get('message')}"
                )
                return False

            logger.info(
                f"Stored analysis {analysis.analysis_id} with {documents_stored}/{len(analysis.documents)} documents"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store analysis {analysis.analysis_id}: {e}")
            return False

    async def store_document_freshness(self, document: "DocumentFreshness") -> bool:
        """
        Store individual document freshness analysis

        Args:
            document: DocumentFreshness object to store

        Returns:
            True if operation successful
        """
        try:
            return await self.upsert_document(document, update_strategy="merge")

        except Exception as e:
            logger.error(
                f"Failed to store document freshness for {document.document_id}: {e}"
            )
            return False

    async def store_refresh_result(self, result: "RefreshResult") -> bool:
        """
        Store refresh operation results

        Args:
            result: RefreshResult object containing refresh operation results

        Returns:
            True if operation successful
        """
        try:
            # Calculate duration if completed
            duration_seconds = None
            if result.completed_at:
                duration_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()

            # Prepare metadata
            metadata = {
                "freshness_improvement": result.freshness_improvement,
                "dependencies_fixed": result.dependencies_fixed,
                "backup_locations": result.backup_locations,
                "total_time_seconds": result.total_time_seconds,
                "average_time_per_document": result.average_time_per_document,
                "success_rate": result.success_rate,
                "processed_documents": result.processed_documents,
                "skipped_documents": result.skipped_documents,
                "failed_documents": result.failed_documents,
                "warnings": result.warnings,
                "errors": result.errors,
            }

            # Store or update refresh operation log
            upsert_query = """
            INSERT INTO refresh_operations_log (
                operation_id, operation_type, status, target_documents,
                started_at, completed_at, duration_seconds,
                documents_processed, documents_updated, documents_failed,
                error_message, metadata, triggered_by, trigger_reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (operation_id) DO UPDATE SET
                status = EXCLUDED.status,
                completed_at = EXCLUDED.completed_at,
                duration_seconds = EXCLUDED.duration_seconds,
                documents_processed = EXCLUDED.documents_processed,
                documents_updated = EXCLUDED.documents_updated,
                documents_failed = EXCLUDED.documents_failed,
                error_message = EXCLUDED.error_message,
                metadata = EXCLUDED.metadata
            """

            error_message = None
            if result.errors:
                error_message = "; ".join(result.errors[:5])  # Store first 5 errors

            status = "completed" if result.completed_at else "in_progress"
            if result.failure_count > 0 and result.success_count == 0:
                status = "failed"
            elif result.failure_count > 0:
                status = "partial_success"

            params = [
                result.refresh_id,
                "document_refresh",
                status,
                json.dumps(result.requested_documents),
                result.started_at.isoformat(),
                result.completed_at.isoformat() if result.completed_at else None,
                duration_seconds,
                len(result.processed_documents),
                result.success_count,
                result.failure_count,
                error_message,
                json.dumps(metadata),
                "data_refresh_worker",
                f"Refresh of {len(result.requested_documents)} documents",
            ]

            db_result = await self._execute_query(
                upsert_query, params=params, fetch_mode="execute"
            )

            if not db_result.get("success", False):
                logger.error(
                    f"Failed to store refresh result: {db_result.get('message')}"
                )
                return False

            logger.info(
                f"Stored refresh result {result.refresh_id} - {result.success_count} success, {result.failure_count} failed"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store refresh result {result.refresh_id}: {e}")
            return False
