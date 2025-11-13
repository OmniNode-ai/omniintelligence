#!/usr/bin/env python3
"""
Sync PostgreSQL Code Patterns to Qdrant

Automatically syncs code patterns from PostgreSQL pattern_lineage_nodes table
to Qdrant code_patterns collection for code similarity search.

This script creates a SEPARATE collection from execution_patterns to avoid
mixing code patterns (actual implementations) with ONEX architectural patterns.

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (DATABASE_URL, QDRANT_URL, etc.)

Usage:
    # Full sync (all patterns)
    python3 scripts/sync_patterns_to_qdrant.py

    # Incremental sync (only new patterns since last sync)
    python3 scripts/sync_patterns_to_qdrant.py --incremental

    # Dry run (no actual changes)
    python3 scripts/sync_patterns_to_qdrant.py --dry-run

Environment Variables:
    DATABASE_URL: PostgreSQL connection URL (override centralized config)
    QDRANT_URL: Qdrant URL (override centralized config)
    EMBEDDING_MODEL_URL: vLLM URL for embeddings (default: http://192.168.86.201:8002)
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

# Add parent directory to path for config imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add services to path
sys.path.insert(0, str(PROJECT_ROOT / "services" / "intelligence"))

from src.services.pattern_learning.phase1_foundation.storage.model_contract_vector_index import (
    ModelContractVectorIndexEffect,
    ModelVectorIndexPoint,
)
from src.services.pattern_learning.phase1_foundation.storage.node_qdrant_vector_index_effect import (
    NodeQdrantVectorIndexEffect,
)

# Import centralized configuration
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PatternSyncManager:
    """
    Manager for syncing PostgreSQL code patterns to Qdrant.

    Handles:
    - Incremental sync (only new patterns)
    - Batch processing (100 patterns per batch)
    - Progress tracking
    - Error handling
    """

    COLLECTION_NAME = "code_patterns"  # Separate from execution_patterns
    BATCH_SIZE = 100  # Patterns per batch
    CODE_SAMPLE_LENGTH = 500  # Characters of code to embed

    def __init__(
        self,
        postgres_url: str,
        qdrant_url: str,
        embedding_model_url: str,
        dry_run: bool = False,
    ):
        """
        Initialize sync manager.

        Args:
            postgres_url: PostgreSQL connection URL
            qdrant_url: Qdrant URL
            embedding_model_url: Embedding model URL for embeddings
            dry_run: If True, don't make actual changes
        """
        self.postgres_url = postgres_url
        self.qdrant_url = qdrant_url
        self.embedding_model_url = embedding_model_url
        self.dry_run = dry_run

        self.vector_index: Optional[NodeQdrantVectorIndexEffect] = None
        self.pg_conn: Optional[asyncpg.Connection] = None

    async def initialize(self):
        """Initialize connections to PostgreSQL and Qdrant."""
        logger.info("Initializing connections...")

        # Initialize Qdrant vector index
        self.vector_index = NodeQdrantVectorIndexEffect(
            qdrant_url=self.qdrant_url,
            embedding_model_url=self.embedding_model_url,
        )

        # Connect to PostgreSQL
        self.pg_conn = await asyncpg.connect(self.postgres_url, timeout=10.0)

        logger.info("✅ Connections initialized")

    async def cleanup(self):
        """Cleanup connections."""
        if self.vector_index:
            await self.vector_index.close()
        if self.pg_conn:
            await self.pg_conn.close()

    async def get_patterns_to_sync(
        self, last_sync_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get patterns from PostgreSQL that need syncing.

        Args:
            last_sync_time: Only get patterns created after this time

        Returns:
            List of pattern records
        """
        if last_sync_time:
            logger.info(f"Fetching patterns created after {last_sync_time}...")
            query = """
                SELECT
                    id,
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    pattern_data,
                    metadata,
                    file_path,
                    language,
                    created_at
                FROM pattern_lineage_nodes
                WHERE pattern_type = 'code'
                  AND created_at > $1
                ORDER BY created_at ASC
            """
            rows = await self.pg_conn.fetch(query, last_sync_time)
        else:
            logger.info("Fetching all code patterns...")
            query = """
                SELECT
                    id,
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    pattern_data,
                    metadata,
                    file_path,
                    language,
                    created_at
                FROM pattern_lineage_nodes
                WHERE pattern_type = 'code'
                ORDER BY created_at ASC
            """
            rows = await self.pg_conn.fetch(query)

        patterns = []
        for row in rows:
            # Parse JSON fields if they're strings
            pattern_data = row["pattern_data"]
            if isinstance(pattern_data, str):
                import json

                pattern_data = json.loads(pattern_data)

            metadata = row["metadata"] or {}
            if isinstance(metadata, str):
                import json

                metadata = json.loads(metadata)

            pattern = {
                "id": row["id"],
                "pattern_id": row["pattern_id"],
                "pattern_name": row["pattern_name"],
                "pattern_type": row["pattern_type"],
                "pattern_data": pattern_data,
                "metadata": metadata,
                "file_path": row["file_path"] or "",
                "language": row["language"] or "unknown",
                "created_at": row["created_at"],
            }
            patterns.append(pattern)

        logger.info(f"✅ Found {len(patterns)} patterns to sync")
        return patterns

    def create_search_text(self, pattern: Dict[str, Any]) -> str:
        """
        Create search text for embedding generation.

        Uses first N characters of code plus metadata.

        Args:
            pattern: Pattern record

        Returns:
            Search text for embedding
        """
        code = pattern["pattern_data"].get("code", "")
        code_sample = code[: self.CODE_SAMPLE_LENGTH]

        # Create rich search text
        search_text = (
            f"File: {pattern['pattern_name']}\n"
            f"Language: {pattern['language']}\n"
            f"Path: {pattern['file_path']}\n\n"
            f"Code:\n{code_sample}"
        )

        return search_text

    def create_qdrant_point(self, pattern: Dict[str, Any]) -> ModelVectorIndexPoint:
        """
        Create Qdrant point from pattern record.

        Args:
            pattern: Pattern record

        Returns:
            Vector index point
        """
        search_text = self.create_search_text(pattern)

        # Create payload with full pattern data
        payload = {
            "text": search_text,
            "pattern_id": pattern["pattern_id"],
            "pattern_name": pattern["pattern_name"],
            "pattern_type": pattern["pattern_type"],
            "file_path": pattern["file_path"],
            "language": pattern["language"],
            "code": pattern["pattern_data"].get("code", ""),
            "metadata": pattern["metadata"],
            "created_at": pattern["created_at"].isoformat(),
            "sync_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Use PostgreSQL UUID as point ID for idempotency
        point = ModelVectorIndexPoint(
            id=pattern["id"],  # UUID from PostgreSQL
            payload=payload,
        )

        return point

    async def sync_patterns_batch(self, patterns: List[Dict[str, Any]]) -> int:
        """
        Sync a batch of patterns to Qdrant.

        Args:
            patterns: List of pattern records

        Returns:
            Number of patterns synced
        """
        if not patterns:
            return 0

        if self.dry_run:
            logger.info(f"[DRY RUN] Would sync {len(patterns)} patterns")
            return len(patterns)

        # Create Qdrant points
        points = [self.create_qdrant_point(p) for p in patterns]

        # Create index contract
        contract = ModelContractVectorIndexEffect(
            collection_name=self.COLLECTION_NAME,
            points=points,
        )

        # Execute indexing
        result = await self.vector_index.execute_effect(contract)

        logger.info(
            f"✅ Synced batch: {result.indexed_count} patterns in {result.duration_ms:.2f}ms"
        )

        return result.indexed_count

    async def sync_all_patterns(self, incremental: bool = False) -> Dict[str, Any]:
        """
        Sync all patterns to Qdrant.

        Args:
            incremental: If True, only sync new patterns since last sync

        Returns:
            Sync statistics
        """
        start_time = time.perf_counter()

        # Determine last sync time for incremental sync
        last_sync_time = None
        if incremental:
            # TODO: Implement last_sync_time tracking (Redis/PostgreSQL)
            logger.warning(
                "Incremental sync not yet implemented. Performing full sync."
            )

        # Get patterns to sync
        patterns = await self.get_patterns_to_sync(last_sync_time)

        if not patterns:
            logger.info("✅ No patterns to sync")
            return {
                "total_patterns": 0,
                "synced_patterns": 0,
                "batches": 0,
                "duration_ms": (time.perf_counter() - start_time) * 1000,
            }

        # Sync in batches
        total_synced = 0
        batches = 0

        for i in range(0, len(patterns), self.BATCH_SIZE):
            batch = patterns[i : i + self.BATCH_SIZE]
            batch_num = (i // self.BATCH_SIZE) + 1
            total_batches = (len(patterns) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            logger.info(
                f"Processing batch {batch_num}/{total_batches} ({len(batch)} patterns)..."
            )

            synced = await self.sync_patterns_batch(batch)
            total_synced += synced
            batches += 1

            # Progress update
            progress = (i + len(batch)) / len(patterns) * 100
            logger.info(f"Progress: {progress:.1f}% ({i + len(batch)}/{len(patterns)})")

        duration_ms = (time.perf_counter() - start_time) * 1000

        stats = {
            "total_patterns": len(patterns),
            "synced_patterns": total_synced,
            "batches": batches,
            "duration_ms": duration_ms,
            "patterns_per_second": total_synced / (duration_ms / 1000),
        }

        logger.info(f"\n✅ Sync complete!")
        logger.info(f"   Total patterns: {stats['total_patterns']}")
        logger.info(f"   Synced patterns: {stats['synced_patterns']}")
        logger.info(f"   Batches: {stats['batches']}")
        logger.info(f"   Duration: {stats['duration_ms']:.2f}ms")
        logger.info(f"   Rate: {stats['patterns_per_second']:.2f} patterns/sec")

        return stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync PostgreSQL code patterns to Qdrant"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only sync new patterns since last sync",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't make actual changes, just show what would be done",
    )
    args = parser.parse_args()

    # Get configuration from centralized config module
    # Override these in .env or via environment variables
    # Defaults from config/settings.py
    postgres_url = os.getenv(
        "DATABASE_URL",
        settings.get_postgres_dsn(
            async_driver=False
        ),  # Use sync driver for this script
    )
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    embedding_model_url = os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")

    logger.info("=" * 70)
    logger.info("PostgreSQL to Qdrant Pattern Sync")
    logger.info("=" * 70)
    logger.info(f"Mode: {'Incremental' if args.incremental else 'Full Sync'}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Collection: code_patterns")
    logger.info(
        f"PostgreSQL: {postgres_url.split('@')[1] if '@' in postgres_url else postgres_url}"
    )
    logger.info(f"Qdrant: {qdrant_url}")
    logger.info("=" * 70)

    manager = PatternSyncManager(
        postgres_url=postgres_url,
        qdrant_url=qdrant_url,
        embedding_model_url=embedding_model_url,
        dry_run=args.dry_run,
    )

    try:
        await manager.initialize()
        stats = await manager.sync_all_patterns(incremental=args.incremental)

        # Exit code based on success
        return 0 if stats["synced_patterns"] >= 0 else 1

    except Exception as e:
        logger.error(f"❌ Sync failed: {e}", exc_info=True)
        return 1

    finally:
        await manager.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
