"""
Pattern Ingestion Pipeline
===========================

Main pipeline for extracting patterns from codebases and storing them in the database.

This module integrates:
- PatternExtractor: AST-based pattern extraction
- PatternScorer: Quality scoring for patterns
- Database persistence: asyncpg for efficient bulk inserts
- Duplicate handling: Check for existing patterns before inserting

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from pattern_extraction import PatternExtractor
from src.archon_services.quality.pattern_scorer import PatternScorer

logger = logging.getLogger(__name__)


@dataclass
class IngestionMetrics:
    """Metrics for pattern ingestion."""

    files_processed: int = 0
    patterns_found: int = 0
    patterns_inserted: int = 0
    patterns_updated: int = 0
    patterns_skipped: int = 0
    errors: int = 0
    processing_time_ms: float = 0.0


class IngestionPipeline:
    """
    Main pattern ingestion pipeline.

    Orchestrates the complete flow:
    1. Scan directories for Python files
    2. Extract patterns using PatternExtractor
    3. Calculate quality scores using PatternScorer
    4. Store patterns in pattern_lineage_nodes table
    5. Handle duplicates (update if pattern already exists)
    6. Track ingestion metrics

    Example:
        pipeline = IngestionPipeline(db_config)
        metrics = await pipeline.ingest_directory(
            directory="/path/to/code",
            min_quality=0.6,
            batch_size=100
        )
        print(f"Processed {metrics.files_processed} files")
        print(f"Found {metrics.patterns_found} patterns")
    """

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        correlation_id: Optional[uuid.UUID] = None,
    ):
        """
        Initialize ingestion pipeline.

        Args:
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            correlation_id: Optional correlation ID for tracing
        """
        self.db_config = {
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_user,
            "password": db_password,
        }
        self.correlation_id = correlation_id or uuid.uuid4()

        # Initialize extractors
        self.extractor = PatternExtractor()
        self.scorer = PatternScorer()

        # Connection pool (initialized in async context)
        self.pool: Optional[asyncpg.Pool] = None

        logger.info(
            f"IngestionPipeline initialized (correlation_id={self.correlation_id})"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Create database connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                **self.db_config, min_size=2, max_size=10
            )
            logger.info("Database connection pool created")

    async def disconnect(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    async def ingest_directory(
        self,
        directory: str,
        min_quality: float = 0.0,
        batch_size: int = 50,
        recursive: bool = True,
        file_pattern: str = "*.py",
    ) -> IngestionMetrics:
        """
        Ingest patterns from all Python files in a directory.

        Args:
            directory: Root directory to scan
            min_quality: Minimum quality score (0.0-1.0) to include pattern
            batch_size: Number of patterns to insert per batch
            recursive: Whether to scan subdirectories
            file_pattern: File pattern to match (default: "*.py")

        Returns:
            IngestionMetrics with processing statistics
        """
        import time

        start_time = time.time()

        metrics = IngestionMetrics()
        dir_path = Path(directory)

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        # Find all Python files
        if recursive:
            files = list(dir_path.rglob(file_pattern))
        else:
            files = list(dir_path.glob(file_pattern))

        logger.info(f"Found {len(files)} files to process in {directory}")

        # Process files in batches
        pattern_batch = []

        for file_path in files:
            try:
                # Extract patterns from file
                patterns = await self._extract_patterns_from_file(
                    str(file_path), min_quality
                )

                metrics.files_processed += 1
                metrics.patterns_found += len(patterns)

                pattern_batch.extend(patterns)

                # Insert batch when it reaches batch_size
                if len(pattern_batch) >= batch_size:
                    batch_metrics = await self._insert_pattern_batch(pattern_batch)
                    metrics.patterns_inserted += batch_metrics["inserted"]
                    metrics.patterns_updated += batch_metrics["updated"]
                    metrics.patterns_skipped += batch_metrics["skipped"]
                    pattern_batch = []

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                metrics.errors += 1

        # Insert remaining patterns
        if pattern_batch:
            batch_metrics = await self._insert_pattern_batch(pattern_batch)
            metrics.patterns_inserted += batch_metrics["inserted"]
            metrics.patterns_updated += batch_metrics["updated"]
            metrics.patterns_skipped += batch_metrics["skipped"]

        metrics.processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Ingestion complete: {metrics.files_processed} files, "
            f"{metrics.patterns_found} patterns found, "
            f"{metrics.patterns_inserted} inserted, "
            f"{metrics.patterns_updated} updated, "
            f"{metrics.errors} errors "
            f"({metrics.processing_time_ms:.2f}ms)"
        )

        return metrics

    async def _extract_patterns_from_file(
        self, file_path: str, min_quality: float
    ) -> List[Dict[str, Any]]:
        """
        Extract and score patterns from a single file.

        Args:
            file_path: Path to Python file
            min_quality: Minimum quality score to include

        Returns:
            List of pattern dictionaries ready for database insertion
        """
        # Extract patterns using PatternExtractor
        patterns = self.extractor.extract_from_file(file_path)

        enriched_patterns = []

        for pattern in patterns:
            # Calculate quality score
            quality_result = self.scorer.calculate_overall_quality(
                code=pattern["implementation"],
                file_path=file_path,
                usage_count=1,
            )

            # Skip if below minimum quality
            if quality_result["quality_score"] < min_quality:
                logger.debug(
                    f"Skipping {pattern['pattern_name']} "
                    f"(quality={quality_result['quality_score']:.2f} < {min_quality})"
                )
                continue

            # Enrich pattern with quality scores
            enriched_pattern = {
                "pattern_id": self._generate_pattern_id(pattern),
                "pattern_name": pattern["pattern_name"],
                "pattern_type": pattern["pattern_type"],
                "pattern_version": "1.0.0",
                "lineage_id": uuid.uuid4(),
                "generation": 1,
                "source_system": "pattern_ingestion_pipeline",
                "correlation_id": self.correlation_id,
                "file_path": file_path,
                "language": "python",
                "pattern_data": {
                    "category": pattern["category"],
                    "implementation": pattern["implementation"],
                    "line_range": pattern["line_range"],
                    "tags": pattern["tags"],
                    "docstring": pattern.get("docstring"),
                },
                "metadata": {
                    "extraction_method": "ast_parser",
                    "quality_weights": quality_result.get("weights", {}),
                },
                # Quality scores
                "complexity_score": quality_result["components"].get("complexity", 0.0),
                "documentation_score": quality_result["components"].get(
                    "documentation", 0.0
                ),
                "test_coverage_score": quality_result["components"].get(
                    "test_coverage", 0.0
                ),
                "reusability_score": quality_result["components"].get(
                    "reusability", 0.0
                ),
                "maintainability_score": quality_result["components"].get(
                    "maintainability", 0.0
                ),
                "overall_quality": quality_result["quality_score"],
                "usage_count": 1,
            }

            enriched_patterns.append(enriched_pattern)

        return enriched_patterns

    def _generate_pattern_id(self, pattern: Dict[str, Any]) -> str:
        """
        Generate unique pattern ID from pattern data.

        Uses: file_path + pattern_name + pattern_type

        Args:
            pattern: Pattern dictionary from PatternExtractor

        Returns:
            Unique pattern ID string
        """
        # Create stable hash from file path and pattern name
        components = [
            pattern.get("file_path", ""),
            pattern.get("pattern_name", ""),
            pattern.get("pattern_type", ""),
        ]
        pattern_id = "_".join(str(c).replace("/", "_") for c in components if c)
        return pattern_id[:255]  # Limit to VARCHAR(255)

    async def _insert_pattern_batch(
        self, patterns: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Insert a batch of patterns into the database.

        Handles duplicates by checking for existing pattern_id+pattern_version.
        Updates existing patterns instead of inserting duplicates.

        Args:
            patterns: List of pattern dictionaries

        Returns:
            Dictionary with counts: {inserted, updated, skipped}
        """
        if not self.pool:
            await self.connect()

        inserted = 0
        updated = 0
        skipped = 0

        async with self.pool.acquire() as conn:
            for pattern in patterns:
                try:
                    # Check if pattern already exists
                    existing = await conn.fetchrow(
                        """
                        SELECT id, pattern_version
                        FROM pattern_lineage_nodes
                        WHERE pattern_id = $1 AND pattern_version = $2
                        """,
                        pattern["pattern_id"],
                        pattern["pattern_version"],
                    )

                    if existing:
                        # Update existing pattern
                        await conn.execute(
                            """
                            UPDATE pattern_lineage_nodes
                            SET
                                pattern_data = $3,
                                metadata = $4,
                                complexity_score = $5,
                                documentation_score = $6,
                                test_coverage_score = $7,
                                reusability_score = $8,
                                maintainability_score = $9,
                                overall_quality = $10,
                                last_used_at = NOW()
                            WHERE pattern_id = $1 AND pattern_version = $2
                            """,
                            pattern["pattern_id"],
                            pattern["pattern_version"],
                            pattern["pattern_data"],
                            pattern["metadata"],
                            pattern["complexity_score"],
                            pattern["documentation_score"],
                            pattern["test_coverage_score"],
                            pattern["reusability_score"],
                            pattern["maintainability_score"],
                            pattern["overall_quality"],
                        )
                        updated += 1
                        logger.debug(f"Updated pattern: {pattern['pattern_id']}")
                    else:
                        # Insert new pattern
                        await conn.execute(
                            """
                            INSERT INTO pattern_lineage_nodes (
                                pattern_id, pattern_name, pattern_type, pattern_version,
                                lineage_id, generation, source_system, correlation_id,
                                file_path, language, pattern_data, metadata,
                                complexity_score, documentation_score, test_coverage_score,
                                reusability_score, maintainability_score, overall_quality,
                                usage_count
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                                $13, $14, $15, $16, $17, $18, $19
                            )
                            """,
                            pattern["pattern_id"],
                            pattern["pattern_name"],
                            pattern["pattern_type"],
                            pattern["pattern_version"],
                            pattern["lineage_id"],
                            pattern["generation"],
                            pattern["source_system"],
                            pattern["correlation_id"],
                            pattern["file_path"],
                            pattern["language"],
                            pattern["pattern_data"],
                            pattern["metadata"],
                            pattern["complexity_score"],
                            pattern["documentation_score"],
                            pattern["test_coverage_score"],
                            pattern["reusability_score"],
                            pattern["maintainability_score"],
                            pattern["overall_quality"],
                            pattern["usage_count"],
                        )
                        inserted += 1
                        logger.debug(f"Inserted pattern: {pattern['pattern_id']}")

                except Exception as e:
                    logger.error(
                        f"Error inserting pattern {pattern['pattern_id']}: {e}",
                        exc_info=True,
                    )
                    skipped += 1

        return {"inserted": inserted, "updated": updated, "skipped": skipped}
