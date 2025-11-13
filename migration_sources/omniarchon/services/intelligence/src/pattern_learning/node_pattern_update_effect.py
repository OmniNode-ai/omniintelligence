"""
ONEX Effect Node: Pattern Update
Purpose: Handle pattern usage tracking and statistics updates
Node Type: Effect (External I/O, database write operations)

File: node_pattern_update_effect.py
Class: NodePatternUpdateEffect
Pattern: ONEX 4-Node Architecture - Effect

Track: Track 3-1.2 - PostgreSQL Storage Layer
AI Generated: 70% (Codestral-inspired base, human refinement)
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
    logging.warning("asyncpg not available - pattern updates will be disabled")


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


class ModelContractEffect:
    """Contract for Effect nodes with update specifications"""

    def __init__(
        self,
        operation: str,
        pattern_id: Optional[UUID] = None,
        usage_data: Optional[Dict[str, Any]] = None,
        relationship_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[UUID] = None,
    ):
        self.operation = operation
        self.pattern_id = pattern_id
        self.usage_data = usage_data or {}
        self.relationship_data = relationship_data or {}
        self.correlation_id = correlation_id or uuid4()


# ============================================================================
# ONEX Effect Node: Pattern Update
# ============================================================================


class NodePatternUpdateEffect:
    """
    ONEX Effect Node for pattern update operations.

    Implements:
    - Suffix naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(self, contract: ModelContractEffect) -> ModelResult
    - Pure I/O operations (no business logic)
    - Transaction management for consistency

    Responsibilities:
    - Record pattern usage events
    - Update pattern statistics (usage_count, success_rate)
    - Create/update pattern relationships
    - Track quality improvements

    Database Tables:
    - pattern_usage_events: Usage tracking
    - pattern_templates: Statistics updates
    - pattern_relationships: Relationship management
    """

    def __init__(self, db_pool: "asyncpg.Pool"):
        """
        Initialize pattern update Effect node.

        Args:
            db_pool: AsyncPG connection pool for database operations
        """
        self.pool = db_pool
        self.logger = logging.getLogger("NodePatternUpdateEffect")

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """
        Execute pattern update operation with transaction management.

        Args:
            contract: ModelContractEffect with update details

        Returns:
            ModelResult with success status and data

        Operations:
            - record_usage: Record pattern usage event
            - update_stats: Update pattern statistics
            - create_relationship: Create pattern relationship
            - update_relationship: Update relationship strength
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
                async with conn.transaction():
                    self.logger.info(
                        f"Executing pattern update operation: {contract.operation}",
                        extra={"correlation_id": str(contract.correlation_id)},
                    )

                    if contract.operation == "record_usage":
                        result_data = await self._record_usage_event(conn, contract)
                    elif contract.operation == "update_stats":
                        result_data = await self._update_pattern_stats(conn, contract)
                    elif contract.operation == "create_relationship":
                        result_data = await self._create_relationship(conn, contract)
                    elif contract.operation == "update_relationship":
                        result_data = await self._update_relationship(conn, contract)
                    else:
                        return ModelResult(
                            success=False,
                            error=f"Unsupported operation: {contract.operation}",
                            metadata={"correlation_id": str(contract.correlation_id)},
                        )

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

        except Exception as e:
            self.logger.error(
                f"Pattern update operation failed: {e}",
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

    async def _record_usage_event(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Record pattern usage event with quality metrics.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with usage_data

        Returns:
            Dict with event ID and recorded data
        """
        usage_data = contract.usage_data
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for record_usage operation")

        event_id = uuid4()

        query = """
            INSERT INTO pattern_usage_events (
                id, pattern_id, correlation_id, file_path, project_id,
                success, execution_time_ms, error_message,
                quality_before, quality_after,
                context, tags
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10,
                $11::jsonb, $12
            )
            RETURNING id, used_at, quality_improvement
        """

        result = await conn.fetchrow(
            query,
            event_id,
            pattern_id,
            contract.correlation_id,
            usage_data.get("file_path"),
            usage_data.get("project_id"),
            usage_data.get("success", True),
            usage_data.get("execution_time_ms"),
            usage_data.get("error_message"),
            usage_data.get("quality_before"),
            usage_data.get("quality_after"),
            json.dumps(usage_data.get("context", {})),
            usage_data.get("tags", []),
        )

        # Trigger will auto-update pattern statistics
        self.logger.info(f"Recorded usage event for pattern {pattern_id}: {event_id}")

        return {
            "event_id": str(result["id"]),
            "pattern_id": str(pattern_id),
            "used_at": result["used_at"].isoformat(),
            "quality_improvement": (
                float(result["quality_improvement"])
                if result["quality_improvement"]
                else None
            ),
        }

    async def _update_pattern_stats(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Manually update pattern statistics (alternative to trigger-based updates).

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with pattern_id

        Returns:
            Dict with updated statistics
        """
        pattern_id = contract.pattern_id

        if not pattern_id:
            raise ValueError("pattern_id required for update_stats operation")

        # Call database function to update stats
        query = "SELECT update_pattern_stats($1)"
        await conn.execute(query, pattern_id)

        # Retrieve updated stats
        stats_query = """
            SELECT
                usage_count, success_rate, last_used_at,
                confidence_score
            FROM pattern_templates
            WHERE id = $1
        """

        result = await conn.fetchrow(stats_query, pattern_id)

        if not result:
            raise ValueError(f"Pattern not found: {pattern_id}")

        self.logger.info(f"Updated statistics for pattern {pattern_id}")

        return {
            "pattern_id": str(pattern_id),
            "usage_count": result["usage_count"],
            "success_rate": (
                float(result["success_rate"]) if result["success_rate"] else 0.5
            ),
            "last_used_at": (
                result["last_used_at"].isoformat() if result["last_used_at"] else None
            ),
            "confidence_score": float(result["confidence_score"]),
        }

    async def _create_relationship(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Create relationship between two patterns.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with relationship_data

        Returns:
            Dict with relationship ID and data
        """
        rel_data = contract.relationship_data

        source_pattern_id = rel_data.get("source_pattern_id")
        target_pattern_id = rel_data.get("target_pattern_id")
        relationship_type = rel_data.get("relationship_type")

        if not all([source_pattern_id, target_pattern_id, relationship_type]):
            raise ValueError(
                "source_pattern_id, target_pattern_id, and relationship_type required"
            )

        relationship_id = uuid4()

        query = """
            INSERT INTO pattern_relationships (
                id, source_pattern_id, target_pattern_id,
                relationship_type, strength, description, context
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7::jsonb
            )
            ON CONFLICT (source_pattern_id, target_pattern_id, relationship_type)
            DO UPDATE SET
                strength = EXCLUDED.strength,
                description = EXCLUDED.description,
                context = EXCLUDED.context,
                updated_at = NOW()
            RETURNING id, discovered_at
        """

        result = await conn.fetchrow(
            query,
            relationship_id,
            (
                UUID(source_pattern_id)
                if isinstance(source_pattern_id, str)
                else source_pattern_id
            ),
            (
                UUID(target_pattern_id)
                if isinstance(target_pattern_id, str)
                else target_pattern_id
            ),
            relationship_type,
            rel_data.get("strength", 0.5),
            rel_data.get("description"),
            json.dumps(rel_data.get("context", {})),
        )

        self.logger.info(
            f"Created relationship: {source_pattern_id} -> {target_pattern_id} ({relationship_type})"
        )

        return {
            "relationship_id": str(result["id"]),
            "source_pattern_id": str(source_pattern_id),
            "target_pattern_id": str(target_pattern_id),
            "relationship_type": relationship_type,
            "discovered_at": result["discovered_at"].isoformat(),
        }

    async def _update_relationship(
        self, conn: "asyncpg.Connection", contract: ModelContractEffect
    ) -> Dict[str, Any]:
        """
        Update existing pattern relationship strength.

        Args:
            conn: AsyncPG connection (within transaction)
            contract: Contract with relationship_data and updates

        Returns:
            Dict with updated relationship data
        """
        rel_data = contract.relationship_data

        source_pattern_id = rel_data.get("source_pattern_id")
        target_pattern_id = rel_data.get("target_pattern_id")
        relationship_type = rel_data.get("relationship_type")

        if not all([source_pattern_id, target_pattern_id, relationship_type]):
            raise ValueError(
                "source_pattern_id, target_pattern_id, and relationship_type required"
            )

        query = """
            UPDATE pattern_relationships
            SET
                strength = COALESCE($4, strength),
                description = COALESCE($5, description),
                updated_at = NOW()
            WHERE source_pattern_id = $1
                AND target_pattern_id = $2
                AND relationship_type = $3
            RETURNING id, strength, updated_at
        """

        result = await conn.fetchrow(
            query,
            (
                UUID(source_pattern_id)
                if isinstance(source_pattern_id, str)
                else source_pattern_id
            ),
            (
                UUID(target_pattern_id)
                if isinstance(target_pattern_id, str)
                else target_pattern_id
            ),
            relationship_type,
            rel_data.get("strength"),
            rel_data.get("description"),
        )

        if not result:
            raise ValueError("Relationship not found")

        self.logger.info(
            f"Updated relationship: {source_pattern_id} -> {target_pattern_id}"
        )

        return {
            "relationship_id": str(result["id"]),
            "strength": float(result["strength"]),
            "updated_at": result["updated_at"].isoformat(),
        }
