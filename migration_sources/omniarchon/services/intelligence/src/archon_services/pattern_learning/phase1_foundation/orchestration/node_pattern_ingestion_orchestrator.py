"""
ONEX Orchestrator Node: Pattern Ingestion with Quality Assessment

Purpose: Coordinate pattern ingestion workflow with quality assessment
Node Type: Orchestrator (Workflow coordination)
File: node_pattern_ingestion_orchestrator.py
Class: NodePatternIngestionOrchestrator

Pattern: ONEX 4-Node Architecture - Orchestrator
Track: Pattern Ingestion Enhancement
ONEX Compliant: Suffix naming (Node*Orchestrator), workflow coordination
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

# Import ONEX nodes
from src.archon_services.pattern_learning.phase1_foundation.quality.model_contract_pattern_quality import (
    ModelContractPatternQuality,
    ModelQualityMetrics,
    ModelResult,
)
from src.archon_services.pattern_learning.phase1_foundation.quality.node_pattern_quality_assessor_compute import (
    NodePatternQualityAssessorCompute,
)
from src.archon_services.pattern_learning.phase1_foundation.storage.model_contract_pattern_storage import (
    ModelContractPatternStorage,
)
from src.archon_services.pattern_learning.phase1_foundation.storage.node_pattern_storage_effect import (
    NodePatternStorageEffect,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Pattern Ingestion Contract
# ============================================================================


class ModelContractPatternIngestion:
    """
    Contract for pattern ingestion orchestration.

    Defines all data needed for end-to-end pattern ingestion:
    1. Quality assessment
    2. Pattern storage
    3. Quality metrics tracking
    """

    def __init__(
        self,
        pattern_name: str,
        pattern_type: str,
        language: str,
        template_code: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        example_usage: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None,
        file_last_modified: Optional[datetime] = None,
        git_commit_date: Optional[datetime] = None,
        created_by: str = "system",
        correlation_id: Optional[UUID] = None,
    ):
        """
        Initialize pattern ingestion contract.

        Args:
            pattern_name: Pattern name
            pattern_type: Pattern type (code, architecture, etc.)
            language: Programming language
            template_code: Pattern source code
            category: Pattern category (optional)
            description: Pattern description (optional)
            example_usage: Usage example (optional)
            source: Pattern source (optional)
            tags: Pattern tags (optional)
            context: Additional context (optional)
            file_last_modified: File modification time (optional)
            git_commit_date: Git commit date (optional)
            created_by: Creator identifier
            correlation_id: Correlation ID for tracing
        """
        self.pattern_name = pattern_name
        self.pattern_type = pattern_type
        self.language = language
        self.template_code = template_code
        self.category = category
        self.description = description
        self.example_usage = example_usage
        self.source = source
        self.tags = tags or []
        self.context = context or {}
        self.file_last_modified = file_last_modified
        self.git_commit_date = git_commit_date
        self.created_by = created_by
        self.correlation_id = correlation_id or uuid4()


# ============================================================================
# ONEX Orchestrator Node: Pattern Ingestion
# ============================================================================


class NodePatternIngestionOrchestrator:
    """
    ONEX Orchestrator Node for pattern ingestion with quality assessment.

    Workflow:
    1. Validate input
    2. Assess pattern quality (NodePatternQualityAssessorCompute)
    3. Store pattern with quality metrics (NodePatternStorageEffect)
    4. Return ingestion result

    Implements:
    - ONEX naming convention: Node<Name>Orchestrator
    - Workflow coordination across Compute and Effect nodes
    - End-to-end pattern ingestion with quality gates

    Performance Targets:
    - Total ingestion time: <500ms per pattern
    - Quality assessment: <400ms
    - Storage: <100ms

    Example:
        >>> pool = await asyncpg.create_pool(db_url)
        >>> orchestrator = NodePatternIngestionOrchestrator(db_pool=pool)
        >>> contract = ModelContractPatternIngestion(
        ...     pattern_name="AsyncDatabaseWriter",
        ...     pattern_type="code",
        ...     language="python",
        ...     template_code="async def execute_effect(...): ..."
        ... )
        >>> result = await orchestrator.execute_orchestration(contract)
        >>> print(f"Success: {result.success}, Pattern ID: {result.data['pattern_id']}")
    """

    def __init__(self, db_pool: Any):
        """
        Initialize pattern ingestion orchestrator.

        Args:
            db_pool: AsyncPG database connection pool
        """
        self.logger = logging.getLogger("NodePatternIngestionOrchestrator")
        self.db_pool = db_pool

        # Initialize ONEX nodes
        self.quality_assessor = NodePatternQualityAssessorCompute()
        self.pattern_storage = NodePatternStorageEffect(db_pool)

    async def execute_orchestration(
        self, contract: ModelContractPatternIngestion
    ) -> ModelResult:
        """
        Execute pattern ingestion workflow with quality assessment.

        Workflow:
        1. Validate input contract
        2. Assess pattern quality (Compute node)
        3. Store pattern with quality metrics (Effect node)
        4. Return result with pattern ID and quality scores

        Args:
            contract: ModelContractPatternIngestion with pattern data

        Returns:
            ModelResult with:
            - success: True if pattern ingested successfully
            - data: Dict with pattern_id, quality_metrics, and storage result
            - metadata: Orchestration metadata including timing

        Raises:
            Does not raise exceptions - returns ModelResult with error details
        """
        start_time = datetime.now(timezone.utc)
        correlation_id = contract.correlation_id

        try:
            self.logger.info(
                f"Starting pattern ingestion: {contract.pattern_name}",
                extra={
                    "correlation_id": str(correlation_id),
                    "pattern_type": contract.pattern_type,
                    "language": contract.language,
                },
            )

            # ============================================================
            # Phase 1: Quality Assessment (Compute Node)
            # ============================================================
            quality_contract = ModelContractPatternQuality(
                name=f"assess_{contract.pattern_name}",
                pattern_name=contract.pattern_name,
                pattern_type=contract.pattern_type,
                language=contract.language,
                pattern_code=contract.template_code,
                description=contract.description,
                file_last_modified=contract.file_last_modified,
                git_commit_date=contract.git_commit_date,
                correlation_id=correlation_id,
            )

            quality_result = await self.quality_assessor.execute_compute(
                quality_contract
            )

            if not quality_result.success:
                return ModelResult(
                    success=False,
                    error=f"Quality assessment failed: {quality_result.error}",
                    metadata={
                        "correlation_id": str(correlation_id),
                        "phase": "quality_assessment",
                    },
                )

            quality_metrics: ModelQualityMetrics = quality_result.data

            self.logger.info(
                f"Quality assessment completed: {contract.pattern_name}",
                extra={
                    "correlation_id": str(correlation_id),
                    "quality_score": quality_metrics.quality_score,
                    "confidence_score": quality_metrics.confidence_score,
                },
            )

            # ============================================================
            # Phase 2: Pattern Storage (Effect Node)
            # ============================================================
            storage_contract = ModelContractPatternStorage(
                name=f"store_{contract.pattern_name}",
                operation="insert",
                data={
                    "pattern_name": contract.pattern_name,
                    "pattern_type": contract.pattern_type,
                    "language": contract.language,
                    "category": contract.category,
                    "template_code": contract.template_code,
                    "description": contract.description,
                    "example_usage": contract.example_usage,
                    "source": contract.source,
                    # Quality metrics from assessment
                    "confidence_score": quality_metrics.confidence_score,
                    "usage_count": quality_metrics.usage_count,
                    "success_rate": quality_metrics.success_rate,
                    "complexity_score": quality_metrics.complexity_score,
                    "maintainability_score": quality_metrics.maintainability_score,
                    "performance_score": quality_metrics.performance_score,
                    # Metadata
                    "created_by": contract.created_by,
                    "tags": contract.tags,
                    "context": {
                        **contract.context,
                        "quality_metadata": quality_metrics.metadata,
                        "quality_score": quality_metrics.quality_score,
                        "onex_compliance_score": quality_metrics.onex_compliance_score,
                    },
                },
                correlation_id=correlation_id,
            )

            storage_result = await self.pattern_storage.execute_effect(storage_contract)

            if not storage_result.success:
                return ModelResult(
                    success=False,
                    error=f"Pattern storage failed: {storage_result.error}",
                    metadata={
                        "correlation_id": str(correlation_id),
                        "phase": "pattern_storage",
                        "quality_metrics": quality_metrics.model_dump(),
                    },
                )

            # ============================================================
            # Phase 3: Return Result
            # ============================================================
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.info(
                f"Pattern ingestion completed: {contract.pattern_name}",
                extra={
                    "correlation_id": str(correlation_id),
                    "duration_ms": duration_ms,
                    "pattern_id": storage_result.data["pattern_id"],
                    "quality_score": quality_metrics.quality_score,
                },
            )

            return ModelResult(
                success=True,
                data={
                    "pattern_id": storage_result.data["pattern_id"],
                    "pattern_name": storage_result.data["pattern_name"],
                    "quality_metrics": quality_metrics.model_dump(),
                    "storage_result": storage_result.data,
                },
                metadata={
                    "correlation_id": str(correlation_id),
                    "duration_ms": round(duration_ms, 2),
                    "quality_assessment_ms": quality_result.metadata.get(
                        "duration_ms", 0
                    ),
                    "storage_ms": storage_result.metadata.get("duration_ms", 0),
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Pattern ingestion orchestration failed: {e}",
                exc_info=True,
                extra={
                    "correlation_id": str(correlation_id),
                    "pattern_name": contract.pattern_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Orchestration failed: {str(e)}",
                metadata={
                    "correlation_id": str(correlation_id),
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )


# ============================================================================
# Batch Ingestion Orchestrator
# ============================================================================


class BatchPatternIngestionOrchestrator:
    """
    Batch orchestrator for ingesting multiple patterns with quality assessment.

    Provides:
    - Batch ingestion of multiple patterns
    - Parallel processing for performance
    - Aggregate reporting
    - Error handling and partial success
    """

    def __init__(self, db_pool: Any, max_concurrent: int = 5):
        """
        Initialize batch ingestion orchestrator.

        Args:
            db_pool: AsyncPG database connection pool
            max_concurrent: Maximum concurrent ingestions
        """
        self.logger = logging.getLogger("BatchPatternIngestionOrchestrator")
        self.db_pool = db_pool
        self.max_concurrent = max_concurrent
        self.single_orchestrator = NodePatternIngestionOrchestrator(db_pool)

    async def execute_batch_orchestration(
        self, contracts: list[ModelContractPatternIngestion]
    ) -> ModelResult:
        """
        Execute batch pattern ingestion with quality assessment.

        Args:
            contracts: List of ModelContractPatternIngestion

        Returns:
            ModelResult with batch ingestion results
        """
        import asyncio

        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info(f"Starting batch ingestion: {len(contracts)} patterns")

            # Process in batches with concurrency limit
            results = []
            for i in range(0, len(contracts), self.max_concurrent):
                batch = contracts[i : i + self.max_concurrent]
                batch_results = await asyncio.gather(
                    *[
                        self.single_orchestrator.execute_orchestration(contract)
                        for contract in batch
                    ],
                    return_exceptions=True,
                )
                results.extend(batch_results)

            # Aggregate results
            successful = sum(
                1 for r in results if isinstance(r, ModelResult) and r.success
            )
            failed = len(results) - successful

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.info(
                f"Batch ingestion completed: {successful} succeeded, {failed} failed",
                extra={"duration_ms": duration_ms},
            )

            return ModelResult(
                success=failed == 0,
                data={
                    "total": len(contracts),
                    "successful": successful,
                    "failed": failed,
                    "results": [
                        (
                            r.model_dump()
                            if isinstance(r, ModelResult)
                            else {"error": str(r)}
                        )
                        for r in results
                    ],
                },
                metadata={
                    "duration_ms": round(duration_ms, 2),
                    "avg_duration_ms": (
                        round(duration_ms / len(contracts), 2) if contracts else 0
                    ),
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(f"Batch ingestion failed: {e}", exc_info=True)
            return ModelResult(
                success=False,
                error=f"Batch orchestration failed: {str(e)}",
                metadata={
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """
    Example usage of NodePatternIngestionOrchestrator.

    Demonstrates:
    - Creating ingestion contract
    - Executing orchestration
    - Interpreting results
    """
    import os

    import asyncpg

    # Get database URL
    db_password = os.getenv("DB_PASSWORD", "")
    db_url = os.getenv(
        "TRACEABILITY_DB_URL_EXTERNAL",
        f"postgresql://postgres:{db_password}@localhost:5436/omninode_bridge",
    )

    # Create connection pool
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

    try:
        # Create orchestrator
        orchestrator = NodePatternIngestionOrchestrator(db_pool=pool)

        # Create ingestion contract
        contract = ModelContractPatternIngestion(
            pattern_name="AsyncDatabaseWriterEnhanced",
            pattern_type="code",
            language="python",
            category="database",
            template_code='''
"""
ONEX Effect Node: Database Writer

Purpose: Write data to database with quality assessment
"""
async def execute_effect(self, contract: ModelContractDatabaseWrite) -> ModelResult:
    """Write data to database."""
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("INSERT INTO patterns ...", contract.data)
    return ModelResult(success=True)
''',
            description="ONEX Effect pattern for database writes with quality gates",
            example_usage="result = await node.execute_effect(contract)",
            source="omniarchon",
            tags=["onex", "effect", "database", "quality"],
            created_by="pattern_ingestion_orchestrator",
        )

        # Execute orchestration
        result = await orchestrator.execute_orchestration(contract)

        if result.success:
            print("\n=== Pattern Ingestion Success ===")
            print(f"Pattern ID: {result.data['pattern_id']}")
            print(f"Pattern Name: {result.data['pattern_name']}")
            print(
                f"Quality Score: {result.data['quality_metrics']['quality_score']:.2f}"
            )
            print(
                f"Confidence: {result.data['quality_metrics']['confidence_score']:.2f}"
            )
            print(f"Complexity: {result.data['quality_metrics']['complexity_score']}")
            print(f"Duration: {result.metadata['duration_ms']}ms")
        else:
            print(f"Ingestion failed: {result.error}")

    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
