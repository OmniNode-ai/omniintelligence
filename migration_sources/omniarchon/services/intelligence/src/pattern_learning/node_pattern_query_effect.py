"""
ONEX Effect Node: Pattern Query
Purpose: Handle database query operations for pattern retrieval and search
Node Type: Effect (External I/O, read-only database operations)

File: node_pattern_query_effect.py
Class: NodePatternQueryEffect
Pattern: ONEX 4-Node Architecture - Effect

Track: Track 3-1.2 - PostgreSQL Storage Layer
AI Generated: 70% (Codestral-inspired base, human refinement)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - pattern query will be disabled")


logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Contract Models (Simplified for standalone operation)
# ============================================================================


class ModelResult:
    """Standard result format for ONEX operations"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class ModelContractEffect:
    """Contract for Effect nodes with query specifications"""

    def __init__(
        self,
        operation: str,
        pattern_id: Optional[UUID] = None,
        filters: Optional[Dict[str, Any]] = None,
        search_query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        correlation_id: Optional[UUID] = None,
    ):
        self.operation = operation
        self.pattern_id = pattern_id
        self.filters = filters or {}
        self.search_query = search_query
        self.limit = limit
        self.offset = offset
        self.correlation_id = correlation_id or uuid4()


# ============================================================================
# ONEX Effect Node: Pattern Query
# ============================================================================


class NodePatternQueryEffect:
    """
    ONEX Effect Node for pattern query operations.

    Implements:
    - Suffix naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelContractEffect) -> ModelResult
    - Pure read-only I/O operations (no mutations)
    - Connection pooling for efficient reads

    Responsibilities:
    - Query pattern templates by ID
    - Search patterns by name/type/language
    - Filter patterns by category/tags
    - Retrieve pattern relationships
    - Get top-performing patterns

    Database Tables:
    - pattern_templates: Main pattern storage
    - pattern_relationships: Pattern relationships
    - v_top_patterns: Materialized view for top patterns
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern query Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternQueryEffect")

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """
        Execute pattern query operation with connection pooling.

        Args:
            contract: ModelContractEffect with query parameters

        Returns:
            ModelResult with success status, data, and metadata

        Operations:
            - get_by_id: Get pattern by UUID
            - search: Search patterns by text query
            - filter: Filter patterns by criteria
            - get_related: Get related patterns
            - get_top: Get top-performing patterns

        Example:
            >>> contract = ModelContractEffect(
            ...     operation="search",
            ...     search_query="async database",
            ...     filters={"language": "python"},
            ...     limit=5,
            ...     correlation_id=uuid4()
            ... )
            >>> result = await node.execute_effect(contract)
            >>> print(result.success, len(result.data))
        """
        if not ASYNCPG_AVAILABLE:
            return ModelResult(
                success=False,
                error="AsyncPG not available",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        start_time = datetime.now(timezone.utc)

        try:
            async with self.pool.acquire() as conn:
                self.logger.info(
                    f"Executing pattern query operation: {contract.operation}",
                    extra={"correlation_id": str(contract.correlation_id)},
                )

                # Route to appropriate handler
                if contract.operation == "get_by_id":
                    result_data = await self._get_pattern_by_id(conn, contract)
                elif contract.operation == "search":
                    result_data = await self._search_patterns(conn, contract)
                elif contract.operation == "filter":
                    result_data = await self._filter_patterns(conn, contract)
                elif contract.operation == "get_related":
                    result_data = await self._get_related_patterns(conn, contract)
                elif contract.operation == "get_top":
                    result_data = await self._get_top_patterns(conn, contract)
                elif contract.operation == "get_by_type":
                    result_data = await self._get_patterns_by_type(conn, contract)
                else:
                    return ModelResult(
                        success=False,
                        error=f"Unsupported operation: {contract.operation}",
                        metadata={"correlation_id": str(contract.correlation_id)},
                    )

            # Calculate duration
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": contract.operation,
                    "duration_ms": duration_ms,
                    "result_count": (
                        len(result_data) if isinstance(result_data, list) else 1
                    ),
                },
            )

        except Exception as e:
            self.logger.error(
                f"Pattern query operation failed: {e}",
                exc_info=True,
                extra={"correlation_id": str(contract.correlation_id)},
            )
            return ModelResult(
                success=False,
                error=str(e),
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": contract.operation,
                },
            )

    async def _get_pattern_by_id(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Retrieve pattern template by ID.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id

        Returns:
            Dict with pattern data
        """
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for get_by_id operation")

        query = """
            SELECT
                id, pattern_name, pattern_type, language, category,
                template_code, description, example_usage,
                source, confidence_score, usage_count, success_rate,
                complexity_score, maintainability_score, performance_score,
                parent_pattern_id, is_deprecated, deprecated_by_id,
                discovered_at, last_used_at, updated_at, created_by,
                tags, context
            FROM pattern_templates
            WHERE id = $1
        """

        result = await conn.fetchrow(query, pattern_id)

        if not result:
            raise ValueError(f"Pattern not found: {pattern_id}")

        return dict(result)

    async def _search_patterns(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Search patterns by text query using trigram similarity.

        Args:
            conn: AsyncPG connection
            contract: Contract with search_query and filters

        Returns:
            List of matching patterns
        """
        search_query = contract.search_query

        if not search_query:
            raise ValueError("search_query required for search operation")

        # Base query with similarity search
        query = """
            SELECT
                id, pattern_name, pattern_type, language, category,
                template_code, description, example_usage,
                confidence_score, usage_count, success_rate,
                tags, context,
                similarity(pattern_name, $1) as name_similarity
            FROM pattern_templates
            WHERE
                (pattern_name % $1 OR description ILIKE $2)
                AND is_deprecated = FALSE
        """

        params = [search_query, f"%{search_query}%"]
        param_idx = 3

        # Add filters
        if contract.filters.get("language"):
            query += f" AND language = ${param_idx}"
            params.append(contract.filters["language"])
            param_idx += 1

        if contract.filters.get("pattern_type"):
            query += f" AND pattern_type = ${param_idx}"
            params.append(contract.filters["pattern_type"])
            param_idx += 1

        if contract.filters.get("category"):
            query += f" AND category = ${param_idx}"
            params.append(contract.filters["category"])
            param_idx += 1

        # Order by relevance
        query += f" ORDER BY name_similarity DESC, confidence_score DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([contract.limit, contract.offset])

        results = await conn.fetch(query, *params)

        return [dict(row) for row in results]

    async def _filter_patterns(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Filter patterns by multiple criteria.

        Args:
            conn: AsyncPG connection
            contract: Contract with filters

        Returns:
            List of filtered patterns
        """
        filters = contract.filters

        if not filters:
            raise ValueError("filters required for filter operation")

        # Build dynamic filter query
        where_clauses = ["is_deprecated = FALSE"]
        params = []
        param_idx = 1

        for key, value in filters.items():
            if key == "tags":
                where_clauses.append(f"tags @> ${param_idx}")
                params.append(value if isinstance(value, list) else [value])
            elif key == "min_confidence_score":
                where_clauses.append(f"confidence_score >= ${param_idx}")
                params.append(value)
            elif key == "min_success_rate":
                where_clauses.append(f"success_rate >= ${param_idx}")
                params.append(value)
            else:
                where_clauses.append(f"{key} = ${param_idx}")
                params.append(value)
            param_idx += 1

        query = f"""
            SELECT
                id, pattern_name, pattern_type, language, category,
                description, confidence_score, usage_count, success_rate,
                tags, context
            FROM pattern_templates
            WHERE {" AND ".join(where_clauses)}
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        params.extend([contract.limit, contract.offset])

        results = await conn.fetch(query, *params)

        return [dict(row) for row in results]

    async def _get_related_patterns(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Get patterns related to a given pattern.

        Args:
            conn: AsyncPG connection
            contract: Contract with pattern_id

        Returns:
            List of related patterns with relationship info
        """
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for get_related operation")

        query = """
            SELECT
                pt.id, pt.pattern_name, pt.pattern_type, pt.language,
                pt.description, pt.confidence_score, pt.usage_count,
                pr.relationship_type, pr.strength,
                pr.description as relationship_description
            FROM pattern_relationships pr
            JOIN pattern_templates pt ON pr.target_pattern_id = pt.id
            WHERE pr.source_pattern_id = $1
                AND pt.is_deprecated = FALSE
            ORDER BY pr.strength DESC, pt.confidence_score DESC
            LIMIT $2 OFFSET $3
        """

        results = await conn.fetch(query, pattern_id, contract.limit, contract.offset)

        return [dict(row) for row in results]

    async def _get_top_patterns(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Get top-performing patterns from materialized view.

        Args:
            conn: AsyncPG connection
            contract: Contract with optional filters

        Returns:
            List of top patterns
        """
        query = """
            SELECT
                id, pattern_name, pattern_type, language,
                usage_count, success_rate, confidence_score,
                avg_quality_improvement, recent_usage_count, last_used_at
            FROM v_top_patterns
            WHERE 1=1
        """

        params = []
        param_idx = 1

        # Add optional filters
        if contract.filters.get("language"):
            query += f" AND language = ${param_idx}"
            params.append(contract.filters["language"])
            param_idx += 1

        if contract.filters.get("pattern_type"):
            query += f" AND pattern_type = ${param_idx}"
            params.append(contract.filters["pattern_type"])
            param_idx += 1

        query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([contract.limit, contract.offset])

        results = await conn.fetch(query, *params)

        return [dict(row) for row in results]

    async def _get_patterns_by_type(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> List[Dict[str, Any]]:
        """
        Get patterns grouped by type.

        Args:
            conn: AsyncPG connection
            contract: Contract with filters

        Returns:
            List of patterns grouped by type
        """
        pattern_type = contract.filters.get("pattern_type")

        if not pattern_type:
            raise ValueError(
                "pattern_type required in filters for get_by_type operation"
            )

        query = """
            SELECT
                id, pattern_name, pattern_type, language, category,
                description, confidence_score, usage_count, success_rate,
                tags
            FROM pattern_templates
            WHERE pattern_type = $1
                AND is_deprecated = FALSE
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT $2 OFFSET $3
        """

        results = await conn.fetch(query, pattern_type, contract.limit, contract.offset)

        return [dict(row) for row in results]
