#!/usr/bin/env python3
"""
Corrected Pattern Integration Script for OmniNode Bridge

Integrates 25,245 patterns from pattern_lineage_nodes table with metadata stamping service.
- Uses correct database connection (localhost:5432/omninode_bridge)
- Uses correct table (pattern_lineage_nodes, not pattern_templates)
- Uses correct API paths (/api/v1/metadata-stamping/)
- Batch processing with progress tracking
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg
import httpx
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"pattern_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


class PatternLineageNode(BaseModel):
    """Pattern from pattern_lineage_nodes table"""

    id: UUID
    pattern_id: str
    pattern_name: str
    pattern_type: str
    pattern_version: Optional[str] = None
    language: Optional[str] = None
    pattern_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def template_code(self) -> str:
        """Extract template code from pattern_data"""
        if isinstance(self.pattern_data, dict):
            return (
                self.pattern_data.get("template_code", "")
                or self.pattern_data.get("code", "")
                or self.pattern_data.get("content", "")
                or str(self.pattern_data)
            )
        return str(self.pattern_data)

    @property
    def confidence_score(self) -> float:
        """Extract confidence score"""
        if isinstance(self.metadata, dict):
            return float(self.metadata.get("confidence_score", 0.8))
        return 0.8


@dataclass
class IntegrationStats:
    """Statistics for integration process"""

    total_patterns: int = 0
    patterns_extracted: int = 0
    patterns_stamped: int = 0
    patterns_failed: int = 0
    batches_processed: int = 0
    batches_failed: int = 0
    total_duration_ms: float = 0
    extraction_duration_ms: float = 0
    stamping_duration_ms: float = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        return {
            "total_patterns": self.total_patterns,
            "patterns_extracted": self.patterns_extracted,
            "patterns_stamped": self.patterns_stamped,
            "patterns_failed": self.patterns_failed,
            "success_rate": (
                self.patterns_stamped / self.total_patterns
                if self.total_patterns > 0
                else 0
            ),
            "total_duration_ms": self.total_duration_ms,
            "avg_time_per_pattern_ms": (
                self.total_duration_ms / self.total_patterns
                if self.total_patterns > 0
                else 0
            ),
            "error_count": len(self.errors),
            "sample_errors": self.errors[:10],
        }


# ============================================================================
# Pattern Extractor
# ============================================================================


class PatternExtractor:
    """Extract patterns from pattern_lineage_nodes table"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.pool = await asyncpg.create_pool(
            self.db_url, min_size=2, max_size=10, command_timeout=60
        )
        logger.info("✓ Connected to PostgreSQL database")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.pool:
            await self.pool.close()
            logger.info("✓ Closed database connection pool")

    async def get_pattern_count(self) -> int:
        """Get total count of patterns"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM pattern_lineage_nodes")
            logger.info(f"Found {count:,} patterns in pattern_lineage_nodes")
            return count

    async def extract_patterns(
        self, limit: Optional[int] = None, offset: int = 0, batch_size: int = 500
    ) -> List[PatternLineageNode]:
        """Extract patterns from database with pagination"""
        patterns = []

        async with self.pool.acquire() as conn:
            query = """
                SELECT
                    id, pattern_id, pattern_name, pattern_type, pattern_version,
                    language, pattern_data, metadata
                FROM pattern_lineage_nodes
                ORDER BY created_at DESC
                OFFSET $1
                LIMIT $2
            """

            actual_limit = min(batch_size, limit - offset) if limit else batch_size
            rows = await conn.fetch(query, offset, actual_limit)

            for row in rows:
                # Parse JSONB strings to dicts
                pattern_data = row["pattern_data"]
                if isinstance(pattern_data, str):
                    pattern_data = json.loads(pattern_data) if pattern_data else {}
                elif pattern_data is None:
                    pattern_data = {}

                metadata = row["metadata"]
                if isinstance(metadata, str):
                    metadata = json.loads(metadata) if metadata else {}
                elif metadata is None:
                    metadata = {}

                patterns.append(
                    PatternLineageNode(
                        id=row["id"],
                        pattern_id=row["pattern_id"],
                        pattern_name=row["pattern_name"],
                        pattern_type=row["pattern_type"],
                        pattern_version=row["pattern_version"],
                        language=row["language"],
                        pattern_data=pattern_data,
                        metadata=metadata,
                    )
                )

        logger.info(f"Extracted {len(patterns)} patterns (offset: {offset})")
        return patterns


# ============================================================================
# Metadata Stamping Service Client
# ============================================================================


class MetadataStampingService:
    """Client for Metadata Stamping Service"""

    def __init__(self, base_url: str = "http://localhost:8057"):
        self.base_url = base_url
        self.api_prefix = "/api/v1/metadata-stamping"
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )

        # Health check
        try:
            response = await self.client.get(f"{self.api_prefix}/health")
            if response.status_code == 200:
                logger.info(
                    f"✓ Connected to Metadata Stamping Service at {self.base_url}"
                )
            else:
                logger.warning(
                    f"Metadata Stamping Service health check returned: {response.status_code}"
                )
        except Exception as e:
            logger.error(f"Failed to connect to Metadata Stamping Service: {e}")
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    async def stamp_pattern(
        self, pattern: PatternLineageNode, correlation_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Stamp a single pattern with metadata"""
        try:
            # Create stamp data
            stamp_data = {
                "pattern_id": pattern.pattern_id,
                "pattern_name": pattern.pattern_name,
                "pattern_type": pattern.pattern_type,
                "pattern_version": pattern.pattern_version or "1.0.0",
                "language": pattern.language or "unknown",
                "confidence_score": pattern.confidence_score,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Generate hash from pattern content
            template_code = pattern.template_code
            file_data = template_code.encode("utf-8") if template_code else b"empty"

            # Generate hash
            hash_response = await self.client.post(
                f"{self.api_prefix}/hash",
                files={"file": ("pattern.txt", file_data, "application/octet-stream")},
                params={"namespace": "pattern_integration"},
                headers={"X-Correlation-ID": str(correlation_id or uuid4())},
            )
            hash_response.raise_for_status()
            hash_result = hash_response.json()
            file_hash = hash_result["data"]["file_hash"]

            # Create stamp
            stamp_request = {
                "file_hash": file_hash,
                "file_path": f"patterns/{pattern.pattern_type}/{pattern.pattern_name}",
                "file_size": len(file_data),
                "content_type": "text/plain",
                "content": template_code or "",  # Add the actual content
                "stamp_data": stamp_data,
                "namespace": "omninode.patterns",
            }

            stamp_response = await self.client.post(
                f"{self.api_prefix}/stamp",
                json=stamp_request,
                headers={"X-Correlation-ID": str(correlation_id or uuid4())},
            )
            if stamp_response.status_code != 200:
                error_detail = stamp_response.text
                logger.error(
                    f"Stamp failed for {pattern.pattern_name}: {stamp_response.status_code} - {error_detail}"
                )
                raise Exception(f"HTTP {stamp_response.status_code}: {error_detail}")

            stamp_response.raise_for_status()
            stamp_result = stamp_response.json()

            return {
                "success": True,
                "pattern_id": pattern.pattern_id,
                "stamp_id": stamp_result.get("data", {}).get("stamp_id"),
                "file_hash": file_hash,
            }

        except Exception as e:
            logger.debug(f"Failed to stamp pattern {pattern.pattern_name}: {e}")
            return {"success": False, "pattern_id": pattern.pattern_id, "error": str(e)}

    async def batch_stamp_patterns(
        self, patterns: List[PatternLineageNode], correlation_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Stamp multiple patterns in batch"""
        results = []
        successful = 0
        failed = 0

        for pattern in patterns:
            result = await self.stamp_pattern(pattern, correlation_id)
            results.append(result)

            if result["success"]:
                successful += 1
            else:
                failed += 1

        return {
            "total": len(patterns),
            "successful": successful,
            "failed": failed,
            "results": results,
        }


# ============================================================================
# Integration Orchestrator
# ============================================================================


class PatternIntegrationOrchestrator:
    """Orchestrate pattern integration with OmniNode Bridge services"""

    def __init__(
        self,
        db_url: str,
        batch_size: int = 100,
        parallel_batches: int = 3,
        max_patterns: Optional[int] = None,
    ):
        self.db_url = db_url
        self.batch_size = batch_size
        self.parallel_batches = parallel_batches
        self.max_patterns = max_patterns
        self.stats = IntegrationStats()

    async def integrate_patterns(self) -> IntegrationStats:
        """Main integration workflow"""
        logger.info("=" * 80)
        logger.info("Pattern Integration with OmniNode Bridge Metadata Stamping")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Step 1: Extract patterns
            logger.info("\n[1/3] Extracting patterns from pattern_lineage_nodes...")
            patterns = await self._extract_all_patterns()

            # Step 2: Stamp patterns
            logger.info(f"\n[2/3] Stamping {len(patterns)} patterns with metadata...")
            await self._stamp_patterns_batch(patterns)

            # Step 3: Generate report
            logger.info("\n[3/3] Generating integration report...")
            self.stats.total_duration_ms = (time.time() - start_time) * 1000
            await self._generate_report()

            logger.info("=" * 80)
            logger.info("✓ Pattern integration completed successfully")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Integration failed: {e}", exc_info=True)
            self.stats.errors.append(
                {
                    "stage": "orchestration",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return self.stats

    async def _extract_all_patterns(self) -> List[PatternLineageNode]:
        """Extract all patterns from database"""
        extraction_start = time.time()
        all_patterns = []

        async with PatternExtractor(self.db_url) as extractor:
            total_count = await extractor.get_pattern_count()
            self.stats.total_patterns = (
                min(total_count, self.max_patterns)
                if self.max_patterns
                else total_count
            )

            logger.info(f"Extracting {self.stats.total_patterns:,} patterns...")

            offset = 0
            while offset < self.stats.total_patterns:
                batch_patterns = await extractor.extract_patterns(
                    limit=self.stats.total_patterns,
                    offset=offset,
                    batch_size=self.batch_size,
                )

                if not batch_patterns:
                    break

                all_patterns.extend(batch_patterns)
                offset += len(batch_patterns)
                self.stats.patterns_extracted = len(all_patterns)

                logger.info(
                    f"Progress: {len(all_patterns):,}/{self.stats.total_patterns:,} "
                    f"({100 * len(all_patterns) / self.stats.total_patterns:.1f}%)"
                )

        self.stats.extraction_duration_ms = (time.time() - extraction_start) * 1000
        logger.info(
            f"✓ Extracted {len(all_patterns):,} patterns in {self.stats.extraction_duration_ms:.2f}ms"
        )

        return all_patterns

    async def _stamp_patterns_batch(self, patterns: List[PatternLineageNode]):
        """Stamp patterns in batches with parallel processing"""
        stamping_start = time.time()

        async with MetadataStampingService() as stamping_service:
            batches = [
                patterns[i : i + self.batch_size]
                for i in range(0, len(patterns), self.batch_size)
            ]

            total_batches = len(batches)
            logger.info(
                f"Processing {total_batches} batches ({self.batch_size} patterns/batch)..."
            )

            for i in range(0, total_batches, self.parallel_batches):
                batch_group = batches[i : i + self.parallel_batches]
                correlation_id = uuid4()

                tasks = [
                    stamping_service.batch_stamp_patterns(batch, correlation_id)
                    for batch in batch_group
                ]

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for batch_idx, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Batch {i + batch_idx + 1} failed: {result}")
                        self.stats.batches_failed += 1
                        self.stats.errors.append(
                            {
                                "batch": i + batch_idx + 1,
                                "error": str(result),
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                    else:
                        self.stats.batches_processed += 1
                        self.stats.patterns_stamped += result["successful"]
                        self.stats.patterns_failed += result["failed"]

                        for item_result in result.get("results", []):
                            if not item_result.get("success"):
                                self.stats.errors.append(
                                    {
                                        "pattern_id": item_result.get("pattern_id"),
                                        "error": item_result.get("error"),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )

                batches_done = min(i + self.parallel_batches, total_batches)
                logger.info(
                    f"Batch progress: {batches_done}/{total_batches} "
                    f"({100 * batches_done / total_batches:.1f}%) - "
                    f"Stamped: {self.stats.patterns_stamped:,}, Failed: {self.stats.patterns_failed:,}"
                )

        self.stats.stamping_duration_ms = (time.time() - stamping_start) * 1000
        logger.info(
            f"✓ Stamping completed in {self.stats.stamping_duration_ms:.2f}ms "
            f"({self.stats.stamping_duration_ms / len(patterns):.2f}ms per pattern)"
        )

    async def _generate_report(self):
        """Generate comprehensive integration report"""
        report_path = Path(
            f"pattern_integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        report = {
            "integration_summary": {
                "timestamp": datetime.utcnow().isoformat(),
                "status": (
                    "completed"
                    if self.stats.patterns_failed == 0
                    else "completed_with_errors"
                ),
                "duration_seconds": self.stats.total_duration_ms / 1000,
            },
            "statistics": self.stats.to_dict(),
            "configuration": {
                "batch_size": self.batch_size,
                "parallel_batches": self.parallel_batches,
                "max_patterns": self.max_patterns,
            },
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"✓ Integration report saved to {report_path}")
        logger.info("\nIntegration Summary:")
        logger.info(f"  Total Patterns: {self.stats.total_patterns:,}")
        logger.info(f"  Successfully Stamped: {self.stats.patterns_stamped:,}")
        logger.info(f"  Failed: {self.stats.patterns_failed:,}")
        logger.info(
            f"  Success Rate: {100 * self.stats.patterns_stamped / self.stats.total_patterns:.1f}%"
        )
        logger.info(f"  Total Duration: {self.stats.total_duration_ms / 1000:.2f}s")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Integrate patterns with OmniNode Bridge"
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:YOUR_PASSWORD_HERE@localhost:5432/omninode_bridge",
        help="PostgreSQL connection URL (set DB_PASSWORD environment variable or use --db-url)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Patterns per batch"
    )
    parser.add_argument(
        "--parallel-batches", type=int, default=3, help="Parallel batch operations"
    )
    parser.add_argument(
        "--max-patterns", type=int, default=None, help="Max patterns to process"
    )

    args = parser.parse_args()

    orchestrator = PatternIntegrationOrchestrator(
        db_url=args.db_url,
        batch_size=args.batch_size,
        parallel_batches=args.parallel_batches,
        max_patterns=args.max_patterns,
    )

    stats = await orchestrator.integrate_patterns()
    sys.exit(0 if stats.patterns_failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
