#!/usr/bin/env python3
"""
Batch Reprocess Pattern Quality Metrics

Purpose: Re-analyze existing patterns to populate quality metrics
Usage: python batch_reprocess_pattern_quality.py [--limit N] [--dry-run] [--pattern-id UUID]

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (POSTGRES_HOST, etc.)

Features:
- Fetches existing patterns from database
- Runs quality assessment on each pattern
- Updates patterns with calculated quality metrics
- Supports dry-run mode for testing
- Parallel processing for performance
- Progress tracking and error handling

Performance Target: <500ms per pattern
Integration: Uses NodePatternQualityAssessorCompute for assessment

Created: 2025-10-28
ONEX Pattern: Orchestrator (workflow coordination and CLI interface)
Correlation ID: a06eb29a-8922-4fdf-bb27-96fc40fae415
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "intelligence" / "src"))

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

# Import quality assessment components
from services.pattern_learning.phase1_foundation.quality import (
    ModelContractPatternQuality,
    NodePatternQualityAssessorCompute,
)

# ==============================================================================
# Configuration
# ==============================================================================

# Logging configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

# Database configuration
# Uses environment variables with fallback to documented defaults
# Override these in .env or via environment variables
DEFAULT_DB_HOST = os.getenv("POSTGRES_HOST", "192.168.86.200")
DEFAULT_DB_PORT = int(os.getenv("POSTGRES_PORT", "5436"))
DEFAULT_DB_NAME = os.getenv("POSTGRES_DATABASE", "omninode_bridge")
DEFAULT_DB_USER = os.getenv("POSTGRES_USER", "postgres")
DEFAULT_DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Batch processing configuration
DEFAULT_BATCH_SIZE = 10  # Patterns per batch
DEFAULT_MAX_CONCURRENT = 5  # Concurrent assessments


# ==============================================================================
# Batch Reprocessing Application
# ==============================================================================


class BatchPatternQualityReprocessor:
    """
    Batch reprocessing application for pattern quality metrics.

    Workflow:
    1. Fetch existing patterns from database
    2. For each pattern:
       a. Run quality assessment (NodePatternQualityAssessorCompute)
       b. Update pattern with quality metrics
    3. Report results
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize batch reprocessor.

        Args:
            db_pool: AsyncPG connection pool
            batch_size: Number of patterns per batch
            max_concurrent: Maximum concurrent assessments
            dry_run: If True, don't update database
            verbose: Enable verbose logging
        """
        self.pool = db_pool
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.dry_run = dry_run
        self.verbose = verbose

        # Configure logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        self.logger = logging.getLogger(__name__)

        # Initialize quality assessor
        self.quality_assessor = NodePatternQualityAssessorCompute()

    async def run(
        self,
        limit: Optional[int] = None,
        pattern_id: Optional[UUID] = None,
    ) -> int:
        """
        Run batch reprocessing workflow.

        Args:
            limit: Maximum number of patterns to process (None = all)
            pattern_id: Specific pattern ID to process (None = all)

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        try:
            # Phase 1: Fetch patterns
            self.logger.info("=" * 70)
            self.logger.info("PHASE 1: FETCH EXISTING PATTERNS")
            self.logger.info("=" * 70)

            patterns = await self._fetch_patterns(limit=limit, pattern_id=pattern_id)

            if not patterns:
                self.logger.warning("No patterns found to process")
                return 0

            self.logger.info(f"Found {len(patterns)} patterns to process")
            self.logger.info("")

            # Phase 2: Batch Processing
            self.logger.info("=" * 70)
            self.logger.info("PHASE 2: QUALITY ASSESSMENT & UPDATE")
            self.logger.info("=" * 70)
            self.logger.info(f"Batch size: {self.batch_size}")
            self.logger.info(f"Max concurrent: {self.max_concurrent}")
            if self.dry_run:
                self.logger.info("⚠️  DRY RUN MODE - No database updates")
            self.logger.info("")

            total_processed = 0
            total_succeeded = 0
            total_failed = 0

            # Process in batches
            for i in range(0, len(patterns), self.batch_size):
                batch = patterns[i : i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(patterns) + self.batch_size - 1) // self.batch_size

                self.logger.info(
                    f"Processing batch {batch_num}/{total_batches} ({len(batch)} patterns)"
                )

                # Process batch with concurrency limit
                batch_results = await self._process_batch(batch)

                # Aggregate results
                batch_succeeded = sum(1 for r in batch_results if r["success"])
                batch_failed = len(batch_results) - batch_succeeded

                total_processed += len(batch)
                total_succeeded += batch_succeeded
                total_failed += batch_failed

                self.logger.info(
                    f"Batch {batch_num} complete: {batch_succeeded} succeeded, {batch_failed} failed"
                )
                self.logger.info("")

            # Phase 3: Results Summary
            self.logger.info("=" * 70)
            self.logger.info("PHASE 3: RESULTS SUMMARY")
            self.logger.info("=" * 70)
            self.logger.info(f"Total processed: {total_processed}")
            self.logger.info(f"Successful: {total_succeeded}")
            self.logger.info(f"Failed: {total_failed}")
            if self.dry_run:
                self.logger.info("Mode: DRY RUN (no database updates)")
            self.logger.info("")

            # Success/failure determination
            if total_failed == 0:
                self.logger.info("✅ All patterns processed successfully!")
                return 0
            elif total_succeeded > 0:
                self.logger.warning(
                    f"⚠️  Partial success: {total_succeeded} succeeded, {total_failed} failed"
                )
                return 1
            else:
                self.logger.error("❌ All patterns failed")
                return 1

        except KeyboardInterrupt:
            self.logger.warning("\n\nInterrupted by user - shutting down...")
            return 130  # Standard exit code for SIGINT

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=self.verbose)
            return 1

    async def _fetch_patterns(
        self, limit: Optional[int] = None, pattern_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch patterns from database.

        Args:
            limit: Maximum number of patterns to fetch
            pattern_id: Specific pattern ID to fetch

        Returns:
            List of pattern dictionaries
        """
        query = """
            SELECT
                id,
                pattern_name,
                pattern_type,
                language,
                template_code,
                description,
                discovered_at,
                updated_at
            FROM pattern_templates
        """

        params = []

        if pattern_id:
            query += " WHERE id = $1"
            params.append(pattern_id)

        query += " ORDER BY discovered_at DESC"

        if limit:
            param_idx = len(params) + 1
            query += f" LIMIT ${param_idx}"
            params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def _process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of patterns with concurrent quality assessment.

        Args:
            batch: List of pattern dictionaries

        Returns:
            List of result dictionaries
        """
        # Process with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_semaphore(pattern: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self._process_single_pattern(pattern)

        results = await asyncio.gather(
            *[process_with_semaphore(pattern) for pattern in batch],
            return_exceptions=True,
        )

        # Convert exceptions to result dictionaries
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "success": False,
                        "pattern_id": batch[i]["id"],
                        "pattern_name": batch[i]["pattern_name"],
                        "error": str(result),
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _process_single_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single pattern: assess quality and update database.

        Args:
            pattern: Pattern dictionary from database

        Returns:
            Result dictionary with success status and metrics
        """
        pattern_id = pattern["id"]
        pattern_name = pattern["pattern_name"]

        try:
            start_time = datetime.now(timezone.utc)

            # Step 1: Create quality assessment contract
            contract = ModelContractPatternQuality(
                name=f"reprocess_{pattern_name}",
                pattern_name=pattern_name,
                pattern_type=pattern["pattern_type"],
                language=pattern["language"],
                pattern_code=pattern["template_code"],
                description=pattern.get("description"),
                file_last_modified=pattern.get("updated_at"),
            )

            # Step 2: Execute quality assessment
            assessment_result = await self.quality_assessor.execute_compute(contract)

            if not assessment_result.success:
                return {
                    "success": False,
                    "pattern_id": str(pattern_id),
                    "pattern_name": pattern_name,
                    "error": f"Quality assessment failed: {assessment_result.error}",
                }

            metrics = assessment_result.data

            # Step 3: Update database (unless dry run)
            if not self.dry_run:
                await self._update_pattern_quality(pattern_id, metrics)

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.debug(
                f"Processed: {pattern_name} | Quality: {metrics.quality_score:.2f} | Duration: {duration_ms:.0f}ms"
            )

            return {
                "success": True,
                "pattern_id": str(pattern_id),
                "pattern_name": pattern_name,
                "quality_score": metrics.quality_score,
                "confidence_score": metrics.confidence_score,
                "complexity_score": metrics.complexity_score,
                "duration_ms": round(duration_ms, 2),
            }

        except Exception as e:
            self.logger.error(
                f"Failed to process pattern {pattern_name}: {e}", exc_info=self.verbose
            )
            return {
                "success": False,
                "pattern_id": str(pattern_id),
                "pattern_name": pattern_name,
                "error": str(e),
            }

    async def _update_pattern_quality(self, pattern_id: UUID, metrics: Any) -> None:
        """
        Update pattern quality metrics in database.

        Args:
            pattern_id: Pattern UUID
            metrics: ModelQualityMetrics with quality scores
        """
        query = """
            UPDATE pattern_templates
            SET
                confidence_score = $2,
                success_rate = $3,
                complexity_score = $4,
                maintainability_score = $5,
                performance_score = $6,
                updated_at = NOW(),
                context = COALESCE(context, '{}'::jsonb) || $7::jsonb
            WHERE id = $1
        """

        context_update = {
            "quality_metadata": metrics.metadata,
            "quality_score": metrics.quality_score,
            "onex_compliance_score": metrics.onex_compliance_score,
            "quality_reprocessed_at": datetime.now(timezone.utc).isoformat(),
        }

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                pattern_id,
                metrics.confidence_score,
                metrics.success_rate,
                metrics.complexity_score,
                metrics.maintainability_score,
                metrics.performance_score,
                context_update,
            )


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Batch reprocess pattern quality metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reprocess all patterns
  %(prog)s

  # Reprocess with limit
  %(prog)s --limit 100

  # Dry run (no database updates)
  %(prog)s --dry-run

  # Reprocess specific pattern
  %(prog)s --pattern-id a06eb29a-8922-4fdf-bb27-96fc40fae415

  # Verbose logging
  %(prog)s --verbose
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of patterns to process",
    )

    parser.add_argument(
        "--pattern-id",
        type=str,
        help="Specific pattern ID to process",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of patterns per batch (default: {DEFAULT_BATCH_SIZE})",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT,
        help=f"Maximum concurrent assessments (default: {DEFAULT_MAX_CONCURRENT})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't update database)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


async def main_async() -> int:
    """
    Async main entry point.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    args = parse_args()

    # Build database URL
    db_url = (
        f"postgresql://{DEFAULT_DB_USER}:{DEFAULT_DB_PASSWORD}"
        f"@{DEFAULT_DB_HOST}:{DEFAULT_DB_PORT}/{DEFAULT_DB_NAME}"
    )

    # Create connection pool
    try:
        pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    except Exception as e:
        print(f"Error: Failed to connect to database: {e}", file=sys.stderr)
        return 1

    try:
        # Parse pattern_id if provided
        pattern_id = UUID(args.pattern_id) if args.pattern_id else None

        # Create application
        app = BatchPatternQualityReprocessor(
            db_pool=pool,
            batch_size=args.batch_size,
            max_concurrent=args.max_concurrent,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        # Run application
        return await app.run(limit=args.limit, pattern_id=pattern_id)

    finally:
        await pool.close()


def main() -> int:
    """
    Main entry point (sync wrapper).

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
