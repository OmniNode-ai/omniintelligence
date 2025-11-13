"""
ONEX Effect Node: Pattern Storage

Purpose: Handle PostgreSQL I/O operations for pattern template persistence
Node Type: Effect (External I/O, side effects, database operations)
File: node_pattern_storage_effect.py
Class: NodePatternStorageEffect

Pattern: ONEX 4-Node Architecture - Effect
Track: Track 3-1.2 - PostgreSQL Storage Layer
ONEX Compliant: Suffix naming (Node*Effect), file pattern (node_*_effect.py)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logging.warning("asyncpg not available - pattern storage will be disabled")

# Import contract models from same package
from src.archon_services.pattern_learning.phase1_foundation.storage.model_contract_pattern_storage import (
    ModelContractPatternStorage,
    ModelResult,
)

# ONEX base imports - use local copy to avoid circular dependencies
from src.archon_services.pattern_learning.phase1_foundation.storage.node_base_effect import (
    NodeBaseEffect,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Effect Node: Pattern Storage
# ============================================================================


class NodePatternStorageEffect(NodeBaseEffect):
    """
    ONEX Effect Node for pattern storage operations.

    Implements:
    - ONEX naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelContractPatternStorage) -> ModelResult
    - Pure I/O operations (no business logic)
    - Transaction management via NodeBaseEffect
    - AsyncPG connection pooling

    Responsibilities:
    - Insert pattern templates into PostgreSQL
    - Update existing pattern templates
    - Delete pattern templates
    - Batch insert multiple patterns
    - Track correlation IDs for distributed tracing

    Database:
    - Table: pattern_templates
    - Connection: AsyncPG connection pool
    - Transactions: Automatic via async with conn.transaction()

    Performance Targets:
    - Query execution: <50ms
    - Batch insert: <100ms for 10 patterns
    - Transaction overhead: <5ms

    Example:
        >>> pool = await asyncpg.create_pool(database_url)
        >>> node = NodePatternStorageEffect(pool)
        >>> contract = ModelContractPatternStorage(
        ...     name="insert_pattern",
        ...     operation="insert",
        ...     data={"pattern_name": "AsyncPattern", ...}
        ... )
        >>> result = await node.execute_effect(contract)
        >>> print(result.success, result.data)
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern storage Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        super().__init__()
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternStorageEffect")

    async def execute_effect(
        self, contract: ModelContractPatternStorage
    ) -> ModelResult:
        """
        Execute pattern storage operation with transaction management.

        ONEX Method Signature: async def execute_effect(self, contract) -> ModelResult

        Args:
            contract: ModelContractPatternStorage with operation details and correlation ID

        Returns:
            ModelResult with success status, data, and metadata including:
            - correlation_id: Request correlation ID
            - operation: Executed operation name
            - duration_ms: Operation duration in milliseconds

        Operations:
            - insert: Insert new pattern template
            - update: Update existing pattern template
            - delete: Delete pattern template
            - batch_insert: Insert multiple patterns in transaction

        Raises:
            Does not raise exceptions - returns ModelResult with error details

        Performance:
            - Single operations: <50ms
            - Batch operations: <100ms for 10 patterns
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
                    # Start database transaction
                    async with conn.transaction():
                        self.logger.info(
                            f"Executing pattern storage operation: {operation_name}",
                            extra={
                                "correlation_id": str(contract.correlation_id),
                                "operation": operation_name,
                            },
                        )

                        # Route to appropriate handler
                        if operation_name == "insert":
                            result_data = await self._insert_pattern(conn, contract)
                        elif operation_name == "update":
                            result_data = await self._update_pattern(conn, contract)
                        elif operation_name == "delete":
                            result_data = await self._delete_pattern(conn, contract)
                        elif operation_name == "batch_insert":
                            result_data = await self._batch_insert_patterns(
                                conn, contract
                            )
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
                f"Pattern storage operation completed: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": duration_ms,
                    "operation": operation_name,
                },
            )

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        except asyncpg.exceptions.UniqueViolationError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.warning(
                f"Pattern already exists: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Pattern already exists: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "unique_violation",
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
                f"Pattern storage operation failed: {e}",
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
    # Private Operation Handlers
    # ========================================================================

    async def _insert_pattern(
        self, conn: "asyncpg.Connection", contract: ModelContractPatternStorage
    ) -> Dict[str, Any]:
        """
        Insert new pattern template into database.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern data

        Returns:
            Dict with pattern_id, pattern_name, and created_at

        Raises:
            ValueError: If required fields are missing
            asyncpg.UniqueViolationError: If pattern already exists
        """
        pattern_data = contract.data
        pattern_id = uuid4()

        # SQL query for pattern insertion
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
            RETURNING id, pattern_name, created_at
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

        # Calculate and record quality metric for newly inserted pattern
        try:
            quality_result = self._calculate_quality_score(pattern_data)
            pattern_version = pattern_data.get("context", {}).get("version")

            await self._record_quality_metric(
                conn=conn,
                pattern_id=result["id"],
                quality_result=quality_result,
                pattern_version=pattern_version,
            )

            self.logger.info(
                f"Recorded quality metric for pattern {result['id']} | "
                f"quality={quality_result['quality_score']:.3f}"
            )
        except Exception as e:
            # Log error but don't fail the insert operation
            self.logger.warning(
                f"Failed to record quality metric for pattern {result['id']}: {e}",
                exc_info=True,
            )

        return {
            "pattern_id": str(result["id"]),
            "pattern_name": result["pattern_name"],
            "created_at": result["created_at"].isoformat(),
        }

    async def _update_pattern(
        self, conn: "asyncpg.Connection", contract: ModelContractPatternStorage
    ) -> Dict[str, Any]:
        """
        Update existing pattern template.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern_id and updates

        Returns:
            Dict with pattern_id, pattern_name, updated_at, and fields_updated

        Raises:
            ValueError: If pattern_id not found or no updates provided
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
        self, conn: "asyncpg.Connection", contract: ModelContractPatternStorage
    ) -> Dict[str, Any]:
        """
        Delete pattern template from database.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern_id to delete

        Returns:
            Dict with pattern_id, pattern_name, and deleted=True

        Raises:
            ValueError: If pattern_id not found
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
        self, conn: "asyncpg.Connection", contract: ModelContractPatternStorage
    ) -> Dict[str, Any]:
        """
        Batch insert multiple pattern templates.

        All inserts are executed within the same transaction for atomicity.
        If any insert fails, the entire batch is rolled back.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with list of patterns to insert

        Returns:
            Dict with pattern_ids list, count, and success status

        Raises:
            ValueError: If no patterns provided or validation fails
        """
        patterns = contract.patterns

        if not patterns:
            raise ValueError("No patterns provided for batch insert")

        inserted_ids = []
        inserted_names = []

        for idx, pattern_data in enumerate(patterns):
            try:
                # Create temporary contract for single insert
                temp_contract = ModelContractPatternStorage(
                    name=f"batch_insert_{idx}",
                    operation="insert",
                    data=pattern_data,
                    correlation_id=contract.correlation_id,
                )

                # Reuse single insert logic
                result = await self._insert_pattern(conn, temp_contract)
                inserted_ids.append(result["pattern_id"])
                inserted_names.append(result["pattern_name"])

            except Exception as e:
                self.logger.error(
                    f"Batch insert failed at pattern {idx}: {e}",
                    extra={"correlation_id": str(contract.correlation_id)},
                )
                raise ValueError(f"Batch insert failed at pattern {idx}: {str(e)}")

        self.logger.info(
            f"Batch inserted {len(inserted_ids)} patterns: {', '.join(inserted_names)}"
        )

        return {
            "pattern_ids": inserted_ids,
            "pattern_names": inserted_names,
            "count": len(inserted_ids),
            "batch_success": True,
        }

    # ========================================================================
    # Quality Metrics Calculation and Storage
    # ========================================================================

    def _calculate_quality_score(self, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate quality score from pattern metadata.

        Quality calculation considers multiple factors:
        - Code complexity (lower is better)
        - Test coverage (higher is better)
        - Documentation completeness (higher is better)
        - Usage history (higher is better)
        - Success rate (higher is better)

        Args:
            pattern_data: Pattern metadata dictionary

        Returns:
            Dict with quality_score (0.0-1.0), confidence (0.0-1.0), and metadata
        """
        # Extract metrics from pattern data
        complexity_score = pattern_data.get(
            "complexity_score", 5
        )  # Default: medium (1-10 scale)
        maintainability_score = pattern_data.get(
            "maintainability_score", 0.5
        )  # 0.0-1.0
        performance_score = pattern_data.get("performance_score", 0.5)  # 0.0-1.0
        usage_count = pattern_data.get("usage_count", 0)
        success_rate = pattern_data.get("success_rate", 0.5)  # 0.0-1.0
        confidence_score = pattern_data.get("confidence_score", 0.5)  # 0.0-1.0

        # Check documentation completeness
        has_description = bool(pattern_data.get("description"))
        has_example_usage = bool(pattern_data.get("example_usage"))
        template_code_length = len(pattern_data.get("template_code", ""))

        # Calculate component scores (0.0-1.0)

        # 1. Complexity score (inverted - lower complexity is better)
        # Scale: 1-10, where 1=simple, 10=very complex
        complexity_quality = max(0.0, min(1.0, (10 - complexity_score) / 10.0))

        # 2. Maintainability score (already 0.0-1.0)
        maintainability_quality = max(0.0, min(1.0, maintainability_score))

        # 3. Performance score (already 0.0-1.0)
        performance_quality = max(0.0, min(1.0, performance_score))

        # 4. Documentation score
        doc_score = 0.0
        if has_description:
            doc_score += 0.4
        if has_example_usage:
            doc_score += 0.3
        if template_code_length > 100:  # Substantial code
            doc_score += 0.3
        documentation_quality = min(1.0, doc_score)

        # 5. Usage history score (logarithmic scaling)
        import math

        if usage_count > 0:
            # Logarithmic scale: 1 usage=0.2, 10=0.5, 100=0.75, 1000+=1.0
            usage_quality = min(1.0, math.log10(usage_count + 1) / 3.0)
        else:
            usage_quality = 0.0

        # 6. Success rate (already 0.0-1.0)
        success_quality = max(0.0, min(1.0, success_rate))

        # Calculate weighted quality score
        # Weights total to 1.0
        weights = {
            "complexity": 0.15,  # 15% - code complexity
            "maintainability": 0.20,  # 20% - maintainability
            "performance": 0.15,  # 15% - performance
            "documentation": 0.15,  # 15% - documentation
            "usage": 0.15,  # 15% - usage history
            "success_rate": 0.20,  # 20% - success rate
        }

        quality_score = (
            weights["complexity"] * complexity_quality
            + weights["maintainability"] * maintainability_quality
            + weights["performance"] * performance_quality
            + weights["documentation"] * documentation_quality
            + weights["usage"] * usage_quality
            + weights["success_rate"] * success_quality
        )

        # Calculate confidence based on data availability
        # More complete data = higher confidence
        confidence_factors = []

        if complexity_score != 5:  # Non-default value
            confidence_factors.append(0.15)
        if maintainability_score != 0.5:  # Non-default value
            confidence_factors.append(0.15)
        if performance_score != 0.5:  # Non-default value
            confidence_factors.append(0.15)
        if has_description and has_example_usage:
            confidence_factors.append(0.20)
        if usage_count > 10:  # Significant usage
            confidence_factors.append(0.15)
        if success_rate != 0.5:  # Non-default value
            confidence_factors.append(0.20)

        # Base confidence from pattern's own confidence_score
        base_confidence = confidence_score

        # Adjust based on available data
        data_confidence = sum(confidence_factors)

        # Final confidence is weighted average
        final_confidence = (base_confidence * 0.4) + (data_confidence * 0.6)
        final_confidence = max(0.0, min(1.0, final_confidence))

        # Build detailed metadata for transparency
        metadata = {
            "components": {
                "complexity": round(complexity_quality, 3),
                "maintainability": round(maintainability_quality, 3),
                "performance": round(performance_quality, 3),
                "documentation": round(documentation_quality, 3),
                "usage": round(usage_quality, 3),
                "success_rate": round(success_quality, 3),
            },
            "weights": weights,
            "raw_metrics": {
                "complexity_score": complexity_score,
                "maintainability_score": maintainability_score,
                "performance_score": performance_score,
                "usage_count": usage_count,
                "success_rate": success_rate,
                "has_description": has_description,
                "has_example_usage": has_example_usage,
                "template_code_length": template_code_length,
            },
            "confidence_factors": confidence_factors,
        }

        return {
            "quality_score": round(quality_score, 4),
            "confidence": round(final_confidence, 4),
            "metadata": metadata,
        }

    async def _record_quality_metric(
        self,
        conn: "asyncpg.Connection",
        pattern_id: UUID,
        quality_result: Dict[str, Any],
        pattern_version: Optional[str] = None,
    ) -> None:
        """
        Record quality metric to pattern_quality_metrics table.

        Uses UPSERT to handle re-ingestion of patterns by updating existing
        metrics instead of failing on duplicate pattern_id.

        Args:
            conn: AsyncPG connection (within transaction)
            pattern_id: UUID of pattern
            quality_result: Quality calculation result from _calculate_quality_score
            pattern_version: Optional pattern version string

        Raises:
            Exception: If database operation fails
        """
        # UPSERT query with ON CONFLICT handling
        # Solution A: Remove ::uuid cast from VALUES to allow proper constraint matching
        query = """
            INSERT INTO pattern_quality_metrics (
                id, pattern_id, quality_score, confidence,
                measurement_timestamp, version, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb
            )
            ON CONFLICT (pattern_id)
            DO UPDATE SET
                quality_score = EXCLUDED.quality_score,
                confidence = EXCLUDED.confidence,
                measurement_timestamp = EXCLUDED.measurement_timestamp,
                version = EXCLUDED.version,
                metadata = EXCLUDED.metadata
            RETURNING id
        """

        metric_id = uuid4()
        measurement_timestamp = datetime.now(timezone.utc)

        result = await conn.fetchrow(
            query,
            metric_id,
            pattern_id,
            quality_result["quality_score"],
            quality_result["confidence"],
            measurement_timestamp,
            pattern_version,
            json.dumps(quality_result["metadata"]),
        )

        self.logger.info(
            f"Recorded quality metric for pattern {pattern_id} | "
            f"quality={quality_result['quality_score']:.3f} | "
            f"confidence={quality_result['confidence']:.3f}"
        )


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """
    Example usage of NodePatternStorageEffect.

    Demonstrates:
    - Creating connection pool
    - Inserting a pattern
    - Updating a pattern
    - Batch inserting patterns
    - Error handling
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
        node = NodePatternStorageEffect(pool)

        # Example 1: Insert a pattern
        print("\n=== Example 1: Insert Pattern ===")
        contract = ModelContractPatternStorage(
            name="insert_async_pattern",
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
        )

        result = await node.execute_effect(contract)
        print(f"Success: {result.success}")
        print(f"Data: {result.data}")
        print(f"Duration: {result.metadata.get('duration_ms')}ms")

        # Example 2: Update pattern
        if result.success:
            print("\n=== Example 2: Update Pattern ===")
            pattern_id = UUID(result.data["pattern_id"])

            update_contract = ModelContractPatternStorage(
                name="update_pattern_score",
                operation="update",
                pattern_id=pattern_id,
                data={
                    "confidence_score": 0.95,
                    "usage_count": 10,
                    "description": "Updated: ONEX Effect pattern with examples",
                },
            )

            update_result = await node.execute_effect(update_contract)
            print(f"Success: {update_result.success}")
            print(f"Data: {update_result.data}")
            print(f"Duration: {update_result.metadata.get('duration_ms')}ms")

        # Example 3: Batch insert
        print("\n=== Example 3: Batch Insert ===")
        batch_contract = ModelContractPatternStorage(
            name="batch_import_patterns",
            operation="batch_insert",
            patterns=[
                {
                    "pattern_name": "ComputePattern1",
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "def compute(data): return transform(data)",
                    "confidence_score": 0.88,
                    "tags": ["onex", "compute"],
                },
                {
                    "pattern_name": "ReducerPattern1",
                    "pattern_type": "code",
                    "language": "python",
                    "template_code": "async def reduce(items): return aggregate(items)",
                    "confidence_score": 0.90,
                    "tags": ["onex", "reducer"],
                },
            ],
        )

        batch_result = await node.execute_effect(batch_contract)
        print(f"Success: {batch_result.success}")
        print(f"Inserted: {batch_result.data.get('count')} patterns")
        print(f"Duration: {batch_result.metadata.get('duration_ms')}ms")

    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
