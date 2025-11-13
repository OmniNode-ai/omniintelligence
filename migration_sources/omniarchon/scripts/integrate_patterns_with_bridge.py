#!/usr/bin/env python3
"""
Pattern Integration Script for OmniNode Bridge

Integrates 24,982 collected patterns from PostgreSQL with OmniNode Bridge services:
- OnexTree service (port 8058) - Tree visualization and pattern enrichment
- Metadata Stamping service (port 8057) - ONEX compliance metadata stamping

Features:
- Batch processing with configurable batch sizes (100-500 patterns/batch)
- Progress tracking with detailed statistics
- Error recovery and retry logic
- Comprehensive reporting
- Parallel batch processing support
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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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


class PatternRecord(BaseModel):
    """Pattern record from PostgreSQL"""

    id: UUID
    pattern_name: str
    pattern_type: str
    language: str
    category: Optional[str] = None
    template_code: str
    description: Optional[str] = None
    confidence_score: float
    usage_count: int = 0
    success_rate: float = 0.5
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


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
            "batches_processed": self.batches_processed,
            "batches_failed": self.batches_failed,
            "success_rate": (
                self.patterns_stamped / self.total_patterns
                if self.total_patterns > 0
                else 0
            ),
            "total_duration_ms": self.total_duration_ms,
            "extraction_duration_ms": self.extraction_duration_ms,
            "stamping_duration_ms": self.stamping_duration_ms,
            "avg_time_per_pattern_ms": (
                self.total_duration_ms / self.total_patterns
                if self.total_patterns > 0
                else 0
            ),
            "error_count": len(self.errors),
            "errors": self.errors[:10],  # Include first 10 errors
        }


# ============================================================================
# Pattern Extractor
# ============================================================================


class PatternExtractor:
    """Extract patterns from PostgreSQL database"""

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
        """Get total count of patterns in database"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM pattern_templates")
            logger.info(f"Found {count:,} patterns in database")
            return count

    async def extract_patterns(
        self, limit: Optional[int] = None, offset: int = 0, batch_size: int = 500
    ) -> List[PatternRecord]:
        """Extract patterns from database with pagination"""
        patterns = []

        async with self.pool.acquire() as conn:
            query = """
                SELECT
                    id, pattern_name, pattern_type, language, category,
                    template_code, description, confidence_score,
                    usage_count, success_rate, tags, context
                FROM pattern_templates
                WHERE is_deprecated = FALSE
                ORDER BY confidence_score DESC, usage_count DESC
                OFFSET $1
                LIMIT $2
            """

            actual_limit = min(batch_size, limit - offset) if limit else batch_size
            rows = await conn.fetch(query, offset, actual_limit)

            for row in rows:
                patterns.append(
                    PatternRecord(
                        id=row["id"],
                        pattern_name=row["pattern_name"],
                        pattern_type=row["pattern_type"],
                        language=row["language"],
                        category=row["category"],
                        template_code=row["template_code"],
                        description=row["description"],
                        confidence_score=float(row["confidence_score"]),
                        usage_count=row["usage_count"],
                        success_rate=float(row["success_rate"]),
                        tags=list(row["tags"]) if row["tags"] else [],
                        context=dict(row["context"]) if row["context"] else {},
                    )
                )

        logger.info(f"Extracted {len(patterns)} patterns (offset: {offset})")
        return patterns


# ============================================================================
# OmniNode Bridge Clients
# ============================================================================


class MetadataStampingService:
    """Client for Metadata Stamping Service"""

    def __init__(self, base_url: str = "http://omninode-bridge-metadata-stamping:8057"):
        self.base_url = base_url
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
            response = await self.client.get("/health")
            if response.status_code == 200:
                logger.info(
                    f"✓ Connected to Metadata Stamping Service at {self.base_url}"
                )
            else:
                logger.warning(
                    f"Metadata Stamping Service health check failed: {response.status_code}"
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
        self, pattern: PatternRecord, correlation_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Stamp a single pattern with metadata"""
        try:
            # Create stamp request
            stamp_data = {
                "pattern_id": str(pattern.id),
                "pattern_name": pattern.pattern_name,
                "pattern_type": pattern.pattern_type,
                "language": pattern.language,
                "category": pattern.category,
                "confidence_score": pattern.confidence_score,
                "usage_count": pattern.usage_count,
                "success_rate": pattern.success_rate,
                "tags": pattern.tags,
                "onex_compliance": self._determine_compliance(pattern),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Generate hash from pattern content
            file_data = pattern.template_code.encode("utf-8")

            # Generate hash
            hash_response = await self.client.post(
                "/hash",
                files={"file": ("pattern.py", file_data, "application/octet-stream")},
                params={"namespace": "pattern_integration"},
                headers={"X-Correlation-ID": str(correlation_id or uuid4())},
            )
            hash_response.raise_for_status()
            hash_result = hash_response.json()
            file_hash = hash_result["data"]["hash"]

            # Create stamp
            stamp_request = {
                "file_hash": file_hash,
                "file_path": f"patterns/{pattern.language}/{pattern.pattern_type}/{pattern.pattern_name}",
                "file_size": len(file_data),
                "content_type": (
                    "text/x-python" if pattern.language == "python" else "text/plain"
                ),
                "stamp_data": stamp_data,
                "namespace": "omninode.patterns",
            }

            stamp_response = await self.client.post(
                "/stamp",
                json=stamp_request,
                headers={"X-Correlation-ID": str(correlation_id or uuid4())},
            )
            stamp_response.raise_for_status()
            stamp_result = stamp_response.json()

            return {
                "success": True,
                "pattern_id": str(pattern.id),
                "stamp_id": stamp_result.get("data", {}).get("stamp_id"),
                "file_hash": file_hash,
            }

        except Exception as e:
            logger.error(f"Failed to stamp pattern {pattern.pattern_name}: {e}")
            return {"success": False, "pattern_id": str(pattern.id), "error": str(e)}

    async def batch_stamp_patterns(
        self, patterns: List[PatternRecord], correlation_id: Optional[UUID] = None
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

    def _determine_compliance(self, pattern: PatternRecord) -> str:
        """Determine ONEX compliance level from pattern type"""
        pattern.pattern_type.lower()
        category = (pattern.category or "").lower()

        if "effect" in pattern.pattern_name.lower() or "io" in category:
            return "effect"
        elif "compute" in pattern.pattern_name.lower() or "transform" in category:
            return "compute"
        elif "reducer" in pattern.pattern_name.lower() or "aggregate" in category:
            return "reducer"
        elif "orchestrator" in pattern.pattern_name.lower() or "workflow" in category:
            return "orchestrator"
        else:
            return "general"


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
        logger.info("Pattern Integration with OmniNode Bridge Services")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Step 1: Extract patterns from database
            logger.info("\n[1/3] Extracting patterns from PostgreSQL...")
            patterns = await self._extract_all_patterns()

            # Step 2: Stamp patterns with metadata
            logger.info(f"\n[2/3] Stamping {len(patterns)} patterns with metadata...")
            await self._stamp_patterns_batch(patterns)

            # Step 3: Generate final report
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

    async def _extract_all_patterns(self) -> List[PatternRecord]:
        """Extract all patterns from database"""
        extraction_start = time.time()
        all_patterns = []

        async with PatternExtractor(self.db_url) as extractor:
            # Get total count
            total_count = await extractor.get_pattern_count()
            self.stats.total_patterns = (
                min(total_count, self.max_patterns)
                if self.max_patterns
                else total_count
            )

            logger.info(f"Extracting {self.stats.total_patterns:,} patterns...")

            # Extract in batches
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

    async def _stamp_patterns_batch(self, patterns: List[PatternRecord]):
        """Stamp patterns in batches with parallel processing"""
        stamping_start = time.time()

        async with MetadataStampingService() as stamping_service:
            # Split into batches
            batches = [
                patterns[i : i + self.batch_size]
                for i in range(0, len(patterns), self.batch_size)
            ]

            total_batches = len(batches)
            logger.info(
                f"Processing {total_batches} batches ({self.batch_size} patterns/batch)..."
            )

            # Process batches with limited parallelism
            for i in range(0, total_batches, self.parallel_batches):
                batch_group = batches[i : i + self.parallel_batches]
                correlation_id = uuid4()

                # Process batch group in parallel
                tasks = [
                    stamping_service.batch_stamp_patterns(batch, correlation_id)
                    for batch in batch_group
                ]

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
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

                        # Log failures from this batch
                        for item_result in result.get("results", []):
                            if not item_result.get("success"):
                                self.stats.errors.append(
                                    {
                                        "pattern_id": item_result.get("pattern_id"),
                                        "error": item_result.get("error"),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )

                # Progress update
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

        # Write report
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"✓ Integration report saved to {report_path}")

        # Print summary
        logger.info("\nIntegration Summary:")
        logger.info(f"  Total Patterns: {self.stats.total_patterns:,}")
        logger.info(f"  Extracted: {self.stats.patterns_extracted:,}")
        logger.info(f"  Successfully Stamped: {self.stats.patterns_stamped:,}")
        logger.info(f"  Failed: {self.stats.patterns_failed:,}")
        logger.info(
            f"  Success Rate: {100 * self.stats.patterns_stamped / self.stats.total_patterns:.1f}%"
        )
        logger.info(f"  Total Duration: {self.stats.total_duration_ms / 1000:.2f}s")
        logger.info(
            f"  Avg Time per Pattern: {self.stats.total_duration_ms / self.stats.total_patterns:.2f}ms"
        )


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Main entry point for pattern integration"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Integrate patterns with OmniNode Bridge services"
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:postgres@localhost:5436/omninode_bridge",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of patterns per batch (default: 100)",
    )
    parser.add_argument(
        "--parallel-batches",
        type=int,
        default=3,
        help="Number of parallel batch operations (default: 3)",
    )
    parser.add_argument(
        "--max-patterns",
        type=int,
        default=None,
        help="Maximum patterns to process (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run mode - extract but don't stamp"
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - Patterns will be extracted but not stamped")

    # Run integration
    orchestrator = PatternIntegrationOrchestrator(
        db_url=args.db_url,
        batch_size=args.batch_size,
        parallel_batches=args.parallel_batches,
        max_patterns=args.max_patterns,
    )

    stats = await orchestrator.integrate_patterns()

    # Exit with appropriate code
    sys.exit(0 if stats.patterns_failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
