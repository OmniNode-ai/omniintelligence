#!/usr/bin/env python3
"""
Missing Vectors Backfill Script

Generates embeddings and indexes files that exist in Memgraph but are missing
from Qdrant vector database. Uses vLLM service for embedding generation and
QdrantIndexerEffect for batch indexing.

Created: 2025-11-12
ONEX Pattern: Effect (Vector generation and indexing)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient

from scripts.lib.correlation_id import generate_correlation_id, log_pipeline_event

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration from environment
EMBEDDING_MODEL_URL = os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Alibaba-NLP/gte-Qwen2-1.5B-instruct")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
MAX_FILE_SIZE_MB = 2.0
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_MB * 1024 * 1024)


class MissingVectorsBackfiller:
    """
    Backfills missing vectors for files in Memgraph that aren't in Qdrant.

    Finds files in Memgraph, checks which are missing from Qdrant,
    generates embeddings via vLLM, and indexes them in Qdrant.
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://localhost:7687",
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "archon_vectors",
        batch_size: int = 25,
        max_concurrent: int = 5,
        dry_run: bool = False,
        verbose: bool = False,
        project_name: Optional[str] = None,
        max_files: Optional[int] = None,
    ):
        """
        Initialize missing vectors backfiller.

        Args:
            memgraph_uri: Memgraph connection URI
            qdrant_url: Qdrant service URL
            collection_name: Qdrant collection name
            batch_size: Number of files to process per batch
            max_concurrent: Maximum concurrent embedding requests
            dry_run: If True, don't actually index vectors
            verbose: Enable verbose logging
            project_name: Only backfill specific project
            max_files: Maximum files to process (for testing)
        """
        self.memgraph_uri = memgraph_uri
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.dry_run = dry_run
        self.verbose = verbose
        self.project_name = project_name
        self.max_files = max_files

        self.memgraph_driver = None
        self.qdrant_client = None
        self.http_session = None

        # Rate limiting
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limit_delay = 0.02  # 50 embeddings/sec max

        # Statistics
        self.stats = {
            "total_files": 0,
            "memgraph_files": 0,
            "qdrant_vectors": 0,
            "missing_vectors": 0,
            "vectors_created": 0,
            "skipped_too_large": 0,
            "skipped_binary": 0,
            "failed_embedding": 0,
            "failed_indexing": 0,
        }

        if verbose:
            logger.setLevel(logging.DEBUG)

    async def initialize(self) -> None:
        """Initialize connections to Memgraph, Qdrant, and HTTP client."""
        try:
            # Memgraph
            self.memgraph_driver = AsyncGraphDatabase.driver(
                self.memgraph_uri,
                max_connection_pool_size=10,
                connection_timeout=30.0,
            )
            await self.memgraph_driver.verify_connectivity()
            logger.info(f"✅ Connected to Memgraph at {self.memgraph_uri}")

            # Qdrant
            self.qdrant_client = QdrantClient(url=self.qdrant_url)
            collections = self.qdrant_client.get_collections()
            logger.info(f"✅ Connected to Qdrant at {self.qdrant_url}")

            # HTTP session for embeddings
            timeout = aiohttp.ClientTimeout(total=60.0)
            self.http_session = aiohttp.ClientSession(timeout=timeout)
            logger.info(f"✅ HTTP session initialized for embeddings")

        except Exception as e:
            logger.error(f"❌ Failed to initialize connections: {e}")
            raise

    async def close(self) -> None:
        """Close all connections."""
        if self.memgraph_driver:
            await self.memgraph_driver.close()
        if self.http_session:
            await self.http_session.close()
        logger.info("Connections closed")

    async def get_memgraph_files(self) -> List[Dict]:
        """
        Get all FILE nodes from Memgraph.

        Returns:
            List of file dictionaries with path, project_name, content_hash
        """
        query = """
        MATCH (f:File)
        """

        if self.project_name:
            query += " WHERE f.project_name = $project_name"

        query += """
        RETURN
            f.path as absolute_path,
            f.absolute_path as full_path,
            f.project_name as project_name,
            f.file_hash as content_hash,
            f.entity_id as entity_id,
            f.name as filename
        ORDER BY f.project_name, f.path
        """

        if self.max_files:
            query += f" LIMIT {self.max_files}"

        try:
            async with self.memgraph_driver.session() as session:
                params = (
                    {"project_name": self.project_name} if self.project_name else {}
                )
                result = await session.run(query, params)
                records = await result.data()

                files = []
                for record in records:
                    path = record.get("full_path") or record.get("absolute_path")
                    if path:
                        files.append(
                            {
                                "absolute_path": path,
                                "project_name": record.get("project_name", "unknown"),
                                "content_hash": record.get("content_hash", ""),
                                "entity_id": record.get("entity_id"),
                                "filename": record.get("filename", ""),
                            }
                        )

                logger.info(f"Found {len(files)} FILE nodes in Memgraph")
                return files

        except Exception as e:
            logger.error(f"❌ Failed to query Memgraph: {e}")
            raise

    def get_qdrant_vector_ids(self) -> Set[str]:
        """
        Get all vector IDs from Qdrant collection.

        Returns:
            Set of entity_ids that exist in Qdrant
        """
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            vector_count = collection_info.points_count

            logger.info(f"Fetching {vector_count} vector IDs from Qdrant...")

            # Scroll through all points to get IDs
            vector_ids = set()
            offset = None

            while True:
                result, offset = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )

                for point in result:
                    vector_ids.add(str(point.id))

                if offset is None:
                    break

            logger.info(f"Found {len(vector_ids)} vectors in Qdrant")
            return vector_ids

        except Exception as e:
            logger.error(f"❌ Failed to query Qdrant: {e}")
            raise

    def find_missing_files(
        self, memgraph_files: List[Dict], qdrant_ids: Set[str]
    ) -> List[Dict]:
        """
        Find files in Memgraph that are missing from Qdrant.

        Args:
            memgraph_files: List of file dictionaries from Memgraph
            qdrant_ids: Set of vector IDs in Qdrant

        Returns:
            List of file dictionaries that need vectors
        """
        missing = []

        for file_dict in memgraph_files:
            entity_id = file_dict["entity_id"]

            # Check if vector exists in Qdrant
            if entity_id not in qdrant_ids:
                missing.append(file_dict)

        logger.info(
            f"Missing: {len(missing)} files ({len(missing)/len(memgraph_files)*100:.1f}%)"
        )
        return missing

    def read_file_content(self, file_path: str) -> Optional[str]:
        """
        Read file content for embedding generation.

        Args:
            file_path: Absolute path to file

        Returns:
            File content as string, or None if unreadable/too large/binary
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return None

            # Check file size
            file_size = path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                self.stats["skipped_too_large"] += 1
                return None

            # Try to read as text
            content = path.read_text(encoding="utf-8")
            return content

        except UnicodeDecodeError:
            # Binary file
            self.stats["skipped_binary"] += 1
            return None
        except Exception as e:
            logger.debug(f"Failed to read {file_path}: {e}")
            return None

    async def generate_embedding(
        self,
        content: str,
        correlation_id: str,
        max_retries: int = 3,
    ) -> Optional[List[float]]:
        """
        Generate embedding for content using vLLM service.

        Args:
            content: Text content to embed
            correlation_id: Correlation ID for tracing
            max_retries: Maximum retry attempts

        Returns:
            Embedding vector (1536 dimensions) or None if failed
        """
        url = f"{EMBEDDING_MODEL_URL}/v1/embeddings"

        payload = {
            "model": EMBEDDING_MODEL,
            "input": content,
        }

        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    start_time = time.perf_counter()

                    async with self.http_session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            embedding = data["data"][0]["embedding"]

                            duration_ms = (time.perf_counter() - start_time) * 1000

                            log_pipeline_event(
                                logger,
                                logging.DEBUG,
                                stage="backfill_vectors",
                                action="embedding_generated",
                                correlation_id=correlation_id,
                                result="success",
                                duration_ms=duration_ms,
                                dimensions=len(embedding),
                            )

                            # Rate limiting
                            await asyncio.sleep(self.rate_limit_delay)

                            return embedding
                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"⚠️ Embedding request failed (attempt {attempt + 1}/{max_retries}): "
                                f"status={response.status}, error={error_text[:100]}"
                            )

            except Exception as e:
                logger.warning(
                    f"⚠️ Embedding generation error (attempt {attempt + 1}/{max_retries}): {e}"
                )

            # Exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)

        return None

    async def index_batch_to_qdrant(
        self,
        batch: List[Tuple[Dict, List[float]]],
        correlation_id: str,
    ) -> int:
        """
        Index a batch of file embeddings to Qdrant.

        Args:
            batch: List of (file_dict, embedding) tuples
            correlation_id: Correlation ID for tracing

        Returns:
            Number of successfully indexed vectors
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would index {len(batch)} vectors to Qdrant")
            return len(batch)

        try:
            from qdrant_client.models import PointStruct

            points = []
            for file_dict, embedding in batch:
                point = PointStruct(
                    id=file_dict["entity_id"],
                    vector=embedding,
                    payload={
                        "file_path": file_dict["absolute_path"],
                        "project_name": file_dict["project_name"],
                        "content_hash": file_dict.get("content_hash", ""),
                        "filename": file_dict.get("filename", ""),
                        "indexed_at": time.time(),
                    },
                )
                points.append(point)

            # Upsert batch to Qdrant
            start_time = time.perf_counter()
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            log_pipeline_event(
                logger,
                logging.INFO,
                stage="backfill_vectors",
                action="batch_indexed",
                correlation_id=correlation_id,
                result="success",
                batch_size=len(batch),
                duration_ms=duration_ms,
            )

            return len(points)

        except Exception as e:
            logger.error(f"❌ Failed to index batch: {e}")
            return 0

    async def process_file(
        self,
        file_dict: Dict,
        correlation_id: str,
    ) -> Optional[Tuple[Dict, List[float]]]:
        """
        Process a single file: read content, generate embedding.

        Args:
            file_dict: File dictionary
            correlation_id: Correlation ID for tracing

        Returns:
            Tuple of (file_dict, embedding) if successful, None otherwise
        """
        file_path = file_dict["absolute_path"]

        # Read file content
        content = self.read_file_content(file_path)

        if content is None:
            log_pipeline_event(
                logger,
                logging.WARNING,
                stage="backfill_vectors",
                action="file_skipped",
                correlation_id=correlation_id,
                result="skipped",
                file_path=file_path,
                reason="unreadable_or_too_large",
            )
            return None

        # Generate embedding
        embedding = await self.generate_embedding(content, correlation_id)

        if embedding is None:
            self.stats["failed_embedding"] += 1
            log_pipeline_event(
                logger,
                logging.ERROR,
                stage="backfill_vectors",
                action="embedding_failed",
                correlation_id=correlation_id,
                result="failed",
                file_path=file_path,
            )
            return None

        return (file_dict, embedding)

    async def process_batch(
        self,
        batch: List[Dict],
        batch_num: int,
        total_batches: int,
        correlation_id: str,
    ) -> None:
        """
        Process a batch of files: generate embeddings and index.

        Args:
            batch: List of file dictionaries
            batch_num: Batch number (0-indexed)
            total_batches: Total number of batches
            correlation_id: Correlation ID for tracing
        """
        logger.info(
            f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} files)"
        )

        # Process files concurrently
        tasks = [self.process_file(file_dict, correlation_id) for file_dict in batch]
        results = await asyncio.gather(*tasks)

        # Filter successful results
        successful = [r for r in results if r is not None]

        if successful:
            # Index batch to Qdrant
            indexed_count = await self.index_batch_to_qdrant(successful, correlation_id)
            self.stats["vectors_created"] += indexed_count

            logger.info(
                f"✅ Generated {len(successful)} embeddings, indexed {indexed_count} vectors"
            )
        else:
            logger.warning(f"⚠️ No successful embeddings in this batch")

    async def run(self) -> None:
        """Run the backfill process."""
        correlation_id = generate_correlation_id()
        start_time = time.perf_counter()

        logger.info("=" * 70)
        logger.info("Starting missing vectors backfill...")
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
        if self.project_name:
            logger.info(f"📦 Project filter: {self.project_name}")
        if self.max_files:
            logger.info(f"🔢 Max files limit: {self.max_files}")
        logger.info("=" * 70)

        # Get Memgraph files
        memgraph_files = await self.get_memgraph_files()
        self.stats["memgraph_files"] = len(memgraph_files)

        # Get Qdrant vectors
        qdrant_ids = self.get_qdrant_vector_ids()
        self.stats["qdrant_vectors"] = len(qdrant_ids)

        # Find missing files
        missing_files = self.find_missing_files(memgraph_files, qdrant_ids)
        self.stats["missing_vectors"] = len(missing_files)
        self.stats["total_files"] = len(missing_files)

        if not missing_files:
            logger.info("✅ No missing vectors - all files are indexed")
            return

        logger.info(f"Memgraph: {self.stats['memgraph_files']} FILE nodes")
        logger.info(f"Qdrant: {self.stats['qdrant_vectors']} vectors")
        logger.info(
            f"Missing: {self.stats['missing_vectors']} files ({self.stats['missing_vectors']/self.stats['memgraph_files']*100:.1f}%)"
        )
        logger.info("")

        # Split into batches
        batches = [
            missing_files[i : i + self.batch_size]
            for i in range(0, len(missing_files), self.batch_size)
        ]
        total_batches = len(batches)

        # Process each batch
        for batch_num, batch in enumerate(batches):
            await self.process_batch(
                batch=batch,
                batch_num=batch_num,
                total_batches=total_batches,
                correlation_id=correlation_id,
            )

            # Progress update
            processed = (batch_num + 1) * self.batch_size
            if processed > len(missing_files):
                processed = len(missing_files)
            percentage = (processed / len(missing_files)) * 100

            # Calculate rate and ETA
            elapsed_s = time.perf_counter() - start_time
            rate = processed / elapsed_s if elapsed_s > 0 else 0
            remaining = len(missing_files) - processed
            eta_s = remaining / rate if rate > 0 else 0

            logger.info(
                f"Progress: {processed}/{len(missing_files)} ({percentage:.1f}%) | "
                f"Rate: {rate:.1f} files/sec | "
                f"ETA: {eta_s//60:.0f}m {eta_s%60:.0f}s"
            )
            logger.info("")

        # Calculate statistics
        duration_s = time.perf_counter() - start_time
        rate = self.stats["vectors_created"] / duration_s if duration_s > 0 else 0

        # Summary
        logger.info("=" * 70)
        logger.info("Summary:")
        logger.info(f"  Files processed: {self.stats['total_files']}")
        logger.info(
            f"  Vectors created: {self.stats['vectors_created']} ({self.stats['vectors_created']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(
            f"  Skipped (too large): {self.stats['skipped_too_large']} ({self.stats['skipped_too_large']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(
            f"  Skipped (binary): {self.stats['skipped_binary']} ({self.stats['skipped_binary']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(
            f"  Failed (embedding): {self.stats['failed_embedding']} ({self.stats['failed_embedding']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(f"  Duration: {duration_s//60:.0f}m {duration_s%60:.0f}s")
        logger.info(f"  Average rate: {rate:.1f} files/sec")
        logger.info("=" * 70)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill missing vectors for files in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run to see what would be indexed
  python3 scripts/backfill_missing_vectors.py --dry-run

  # Index all missing vectors
  python3 scripts/backfill_missing_vectors.py

  # Index specific project
  python3 scripts/backfill_missing_vectors.py --project-name omniarchon

  # Test with small batch
  python3 scripts/backfill_missing_vectors.py --max-files 10 --verbose
        """,
    )

    parser.add_argument(
        "--memgraph-uri",
        default="bolt://localhost:7687",
        help="Memgraph connection URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--qdrant-url",
        default="http://localhost:6333",
        help="Qdrant service URL (default: http://localhost:6333)",
    )
    parser.add_argument(
        "--collection-name",
        default="archon_vectors",
        help="Qdrant collection name (default: archon_vectors)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Files per batch (default: 25)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Max concurrent embedding requests (default: 5)",
    )
    parser.add_argument(
        "--project-name",
        help="Only backfill specific project (default: all projects)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum files to process (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Create backfiller
    backfiller = MissingVectorsBackfiller(
        memgraph_uri=args.memgraph_uri,
        qdrant_url=args.qdrant_url,
        collection_name=args.collection_name,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent,
        dry_run=args.dry_run,
        verbose=args.verbose,
        project_name=args.project_name,
        max_files=args.max_files,
    )

    try:
        # Initialize connections
        await backfiller.initialize()

        # Run backfill
        await backfiller.run()

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await backfiller.close()


if __name__ == "__main__":
    asyncio.run(main())
