"""
ONEX Effect Node: Pattern Storage
Purpose: Handle database I/O operations for pattern template persistence
Node Type: Effect (External I/O, side effects, database operations)

File: node_pattern_storage_effect.py
Class: NodePatternStorageEffect
Pattern: ONEX 4-Node Architecture - Effect

Track: Track 3-1.2 - PostgreSQL Storage Layer
AI Generated: 75% (Codestral base, human refinement)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - pattern storage will be disabled")


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
    """Contract for Effect nodes with operation specifications"""

    def __init__(
        self,
        operation: str,
        data: Optional[Dict[str, Any]] = None,
        pattern_id: Optional[UUID] = None,
        patterns: Optional[List[Dict[str, Any]]] = None,
        correlation_id: Optional[UUID] = None,
    ):
        self.operation = operation
        self.data = data or {}
        self.pattern_id = pattern_id
        self.patterns = patterns or []
        self.correlation_id = correlation_id or uuid4()


# ============================================================================
# ONEX Effect Node: Pattern Storage
# ============================================================================


class NodePatternStorageEffect:
    """
    ONEX Effect Node for pattern storage operations.

    Implements:
    - Suffix naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelContractEffect) -> ModelResult
    - Pure I/O operations (no business logic)
    - Transaction management
    - AsyncPG connection pooling

    Responsibilities:
    - Insert pattern templates into database
    - Update existing pattern templates
    - Delete pattern templates
    - Batch insert multiple patterns
    - Track correlation IDs for tracing

    Database Tables:
    - pattern_templates: Main pattern storage
    - pattern_usage_events: Usage tracking (separate node)
    - pattern_relationships: Pattern relationships (separate node)
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern storage Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternStorageEffect")

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """
        Execute pattern storage operation with transaction management.

        Args:
            contract: ModelContractEffect with operation details and correlation ID

        Returns:
            ModelResult with success status, data, and metadata

        Operations:
            - insert: Insert new pattern template
            - update: Update existing pattern template
            - delete: Delete pattern template
            - batch_insert: Insert multiple patterns

        Example:
            >>> contract = ModelContractEffect(
            ...     operation="insert",
            ...     data={
            ...         "pattern_name": "AsyncIOPattern",
            ...         "pattern_type": "code",
            ...         "language": "python",
            ...         "template_code": "async def...",
            ...         "confidence_score": 0.95
            ...     },
            ...     correlation_id=uuid4()
            ... )
            >>> result = await node.execute_effect(contract)
            >>> print(result.success, result.data)
        """
        if not ASYNCPG_AVAILABLE:
            return ModelResult(
                success=False,
                error="AsyncPG not available",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        start_time = datetime.now(timezone.utc)

        try:
            # Execute operation within transaction
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    self.logger.info(
                        f"Executing pattern storage operation: {contract.operation}",
                        extra={"correlation_id": str(contract.correlation_id)},
                    )

                    # Route to appropriate handler
                    if contract.operation == "insert":
                        result_data = await self._insert_pattern(conn, contract)
                    elif contract.operation == "update":
                        result_data = await self._update_pattern(conn, contract)
                    elif contract.operation == "delete":
                        result_data = await self._delete_pattern(conn, contract)
                    elif contract.operation == "batch_insert":
                        result_data = await self._batch_insert_patterns(conn, contract)
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
                },
            )

        except asyncpg.exceptions.UniqueViolationError as e:
            self.logger.warning(
                f"Pattern already exists: {e}",
                extra={"correlation_id": str(contract.correlation_id)},
            )
            return ModelResult(
                success=False,
                error=f"Pattern already exists: {str(e)}",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        except asyncpg.exceptions.ForeignKeyViolationError as e:
            self.logger.error(
                f"Foreign key violation: {e}",
                extra={"correlation_id": str(contract.correlation_id)},
            )
            return ModelResult(
                success=False,
                error=f"Invalid reference: {str(e)}",
                metadata={"correlation_id": str(contract.correlation_id)},
            )

        except Exception as e:
            self.logger.error(
                f"Pattern storage operation failed: {e}",
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

    async def _insert_pattern(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Insert new pattern template into database.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern data

        Returns:
            Dict with pattern_id and inserted data
        """
        pattern_data = contract.data
        pattern_id = uuid4()

        query = """
            INSERT INTO pattern_templates (
                id, pattern_name, pattern_type, language, category,
                template_code, description, example_usage,
                source, confidence_score, usage_count, success_rate,
                complexity_score, maintainability_score, performance_score,
                parent_pattern_id, is_deprecated,
                created_by, tags, context
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11, $12,
                $13, $14, $15,
                $16, $17,
                $18, $19, $20::jsonb
            )
            RETURNING id, pattern_name, discovered_at
        """

        result = await conn.fetchrow(
            query,
            pattern_id,
            pattern_data.get("pattern_name"),
            pattern_data.get("pattern_type"),
            pattern_data.get("language"),
            pattern_data.get("category"),
            pattern_data.get("template_code"),
            pattern_data.get("description"),
            pattern_data.get("example_usage"),
            pattern_data.get("source"),
            pattern_data.get("confidence_score", 0.5),
            pattern_data.get("usage_count", 0),
            pattern_data.get("success_rate", 0.5),
            pattern_data.get("complexity_score"),
            pattern_data.get("maintainability_score"),
            pattern_data.get("performance_score"),
            pattern_data.get("parent_pattern_id"),
            pattern_data.get("is_deprecated", False),
            pattern_data.get("created_by", "system"),
            pattern_data.get("tags", []),
            json.dumps(pattern_data.get("context", {})),
        )

        self.logger.info(f"Inserted pattern: {result['pattern_name']} ({result['id']})")

        return {
            "pattern_id": str(result["id"]),
            "pattern_name": result["pattern_name"],
            "discovered_at": result["discovered_at"].isoformat(),
        }

    async def _update_pattern(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Update existing pattern template.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern_id and updates

        Returns:
            Dict with update status and affected fields
        """
        pattern_id = contract.pattern_id
        updates = contract.data

        if not pattern_id:
            raise ValueError("pattern_id required for update operation")

        if not updates:
            raise ValueError("No updates provided")

        # Build dynamic UPDATE query
        set_clauses = []
        values = [pattern_id]
        param_idx = 2

        for key, value in updates.items():
            if key == "context":
                set_clauses.append(f"{key} = ${param_idx}::jsonb")
                values.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ${param_idx}")
                values.append(value)
            param_idx += 1

        # Always update timestamp
        set_clauses.append("updated_at = NOW()")

        query = f"""
            UPDATE pattern_templates
            SET {", ".join(set_clauses)}
            WHERE id = $1
            RETURNING id, pattern_name, updated_at
        """

        result = await conn.fetchrow(query, *values)

        if not result:
            raise ValueError(f"Pattern not found: {pattern_id}")

        self.logger.info(f"Updated pattern: {result['pattern_name']} ({result['id']})")

        return {
            "pattern_id": str(result["id"]),
            "pattern_name": result["pattern_name"],
            "updated_at": result["updated_at"].isoformat(),
            "fields_updated": list(updates.keys()),
        }

    async def _delete_pattern(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Delete pattern template from database.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern_id to delete

        Returns:
            Dict with deletion status
        """
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for delete operation")

        query = """
            DELETE FROM pattern_templates
            WHERE id = $1
            RETURNING id, pattern_name
        """

        result = await conn.fetchrow(query, pattern_id)

        if not result:
            raise ValueError(f"Pattern not found: {pattern_id}")

        self.logger.info(f"Deleted pattern: {result['pattern_name']} ({result['id']})")

        return {
            "pattern_id": str(result["id"]),
            "pattern_name": result["pattern_name"],
            "deleted": True,
        }

    async def _batch_insert_patterns(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Batch insert multiple pattern templates.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with list of patterns to insert

        Returns:
            Dict with list of inserted pattern IDs and count
        """
        patterns = contract.patterns

        if not patterns:
            raise ValueError("No patterns provided for batch insert")

        inserted_ids = []

        for pattern_data in patterns:
            # Create temporary contract for single insert
            temp_contract = ModelContractEffect(
                operation="insert",
                data=pattern_data,
                correlation_id=contract.correlation_id,
            )

            # Reuse single insert logic
            result = await self._insert_pattern(conn, temp_contract)
            inserted_ids.append(result["pattern_id"])

        self.logger.info(f"Batch inserted {len(inserted_ids)} patterns")

        return {"pattern_ids": inserted_ids, "count": len(inserted_ids)}


# ============================================================================
# Example Usage and Testing
# ============================================================================


async def example_usage():
    """Example usage of NodePatternStorageEffect"""
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
        node = NodePatternStorageEffect(pool)

        # Example 1: Insert a pattern
        contract = ModelContractEffect(
            operation="insert",
            data={
                "pattern_name": "AsyncDatabaseWriterPattern",
                "pattern_type": "code",
                "language": "python",
                "category": "database",
                "template_code": "async def execute_effect(self, contract): ...",
                "description": "ONEX Effect pattern for async database writes",
                "confidence_score": 0.92,
                "tags": ["onex", "effect", "database", "async"],
                "context": {"framework": "onex", "version": "1.0"},
            },
            correlation_id=uuid4(),
        )

        result = await node.execute_effect(contract)
        print(f"Insert result: {result.to_dict()}")

        # Example 2: Update a pattern
        if result.success:
            pattern_id = UUID(result.data["pattern_id"])

            update_contract = ModelContractEffect(
                operation="update",
                pattern_id=pattern_id,
                data={
                    "confidence_score": 0.95,
                    "usage_count": 10,
                    "description": "Updated description with examples",
                },
                correlation_id=uuid4(),
            )

            update_result = await node.execute_effect(update_contract)
            print(f"Update result: {update_result.to_dict()}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
