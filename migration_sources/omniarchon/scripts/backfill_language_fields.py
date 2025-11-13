#!/usr/bin/env python3
"""
Language Field Backfill Script

Updates existing FILE nodes in Memgraph with language detection metadata
without re-ingesting files. Uses enhanced language detection with content-based
fallback for files with unknown or missing language fields.

Created: 2025-11-12
ONEX Pattern: Effect (Memgraph database updates)
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase

from scripts.lib.correlation_id import generate_correlation_id, log_pipeline_event
from scripts.lib.language_detector import detect_language_enhanced

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class LanguageFieldBackfiller:
    """
    Backfills language metadata for FILE nodes in Memgraph.

    Queries Memgraph for files without language metadata, detects language
    from file content or extension, and updates the FILE nodes.
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://localhost:7687",
        batch_size: int = 100,
        dry_run: bool = False,
        verbose: bool = False,
        project_name: Optional[str] = None,
    ):
        """
        Initialize language field backfiller.

        Args:
            memgraph_uri: Memgraph connection URI
            batch_size: Number of files to process per batch
            dry_run: If True, don't actually update database
            verbose: Enable verbose logging
            project_name: Only update specific project (None = all projects)
        """
        self.memgraph_uri = memgraph_uri
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.verbose = verbose
        self.project_name = project_name
        self.driver = None

        # Statistics
        self.stats = {
            "total_files": 0,
            "updated": 0,
            "skipped_not_found": 0,
            "skipped_binary": 0,
            "failed": 0,
        }

        if verbose:
            logger.setLevel(logging.DEBUG)

    async def initialize(self) -> None:
        """Initialize Memgraph connection."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.memgraph_uri,
                max_connection_pool_size=10,
                connection_timeout=30.0,
            )
            await self.driver.verify_connectivity()
            logger.info(f"✅ Connected to Memgraph at {self.memgraph_uri}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Memgraph: {e}")
            raise

    async def close(self) -> None:
        """Close Memgraph connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Memgraph connection closed")

    async def find_files_without_language(self) -> List[Dict]:
        """
        Find FILE nodes without language metadata.

        Returns:
            List of file dictionaries with absolute_path, project_name, file_extension
        """
        query = """
        MATCH (f:File)
        WHERE f.language IS NULL OR f.language = '' OR f.language = 'unknown'
        """

        # Add project filter if specified
        if self.project_name:
            query += " AND f.project_name = $project_name"

        query += """
        RETURN
            f.path as absolute_path,
            f.absolute_path as full_path,
            f.project_name as project_name,
            f.name as filename,
            f.entity_id as entity_id
        ORDER BY f.project_name, f.path
        """

        try:
            async with self.driver.session() as session:
                params = (
                    {"project_name": self.project_name} if self.project_name else {}
                )
                result = await session.run(query, params)
                records = await result.data()

                files = []
                for record in records:
                    # Use full_path if available, otherwise path
                    path = record.get("full_path") or record.get("absolute_path")
                    if path:
                        # Extract file extension
                        filename = record.get("filename", "")
                        extension = (
                            Path(filename).suffix.lstrip(".") if filename else ""
                        )

                        files.append(
                            {
                                "absolute_path": path,
                                "project_name": record.get("project_name", "unknown"),
                                "file_extension": extension,
                                "filename": filename,
                                "entity_id": record.get("entity_id"),
                            }
                        )

                logger.info(f"Found {len(files)} files without language metadata")
                return files

        except Exception as e:
            logger.error(f"❌ Failed to query files: {e}")
            raise

    def read_file_content(self, file_path: str) -> Optional[str]:
        """
        Read file content for language detection.

        Args:
            file_path: Absolute path to file

        Returns:
            File content as string, or None if unreadable
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None

            # Only read first 1000 bytes for language detection
            content = path.read_text(encoding="utf-8", errors="ignore")
            return content[:1000] if content else None

        except UnicodeDecodeError:
            # Binary file
            return None
        except Exception as e:
            logger.debug(f"Failed to read {file_path}: {e}")
            return None

    def detect_language(self, file_dict: Dict) -> str:
        """
        Detect language for a file.

        Args:
            file_dict: File dictionary with absolute_path, file_extension

        Returns:
            Detected language
        """
        file_path = file_dict["absolute_path"]
        extension = file_dict.get("file_extension", "")

        # Map extension to language first
        extension_language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "jsx": "javascript",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rs": "rust",
            "rb": "ruby",
            "php": "php",
            "sh": "shell",
            "bash": "shell",
            "md": "markdown",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "toml": "toml",
            "sql": "sql",
        }

        extension_language = extension_language_map.get(extension.lower(), "unknown")

        # Try content-based detection if extension didn't work
        if extension_language == "unknown":
            content = self.read_file_content(file_path)
            if content:
                return detect_language_enhanced(
                    file_path=file_path,
                    extension_language=extension_language,
                    content=content,
                )

        return extension_language

    async def update_file_language(
        self,
        entity_id: str,
        language: str,
        correlation_id: str,
    ) -> bool:
        """
        Update FILE node with detected language.

        Args:
            entity_id: File entity_id
            language: Detected language
            correlation_id: Correlation ID for tracing

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {entity_id} → {language}")
            return True

        query = """
        MATCH (f:File {entity_id: $entity_id})
        SET
            f.language = $language,
            f.language_updated_at = datetime()
        RETURN f.entity_id as updated_id
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query, {"entity_id": entity_id, "language": language}
                )
                record = await result.single()

                if record:
                    return True
                else:
                    logger.warning(f"⚠️ No file found with entity_id={entity_id}")
                    return False

        except Exception as e:
            logger.error(f"❌ Failed to update {entity_id}: {e}")
            return False

    async def process_batch(
        self,
        batch: List[Dict],
        batch_num: int,
        total_batches: int,
        correlation_id: str,
    ) -> None:
        """
        Process a batch of files.

        Args:
            batch: List of file dictionaries
            batch_num: Batch number (0-indexed)
            total_batches: Total number of batches
            correlation_id: Correlation ID for tracing
        """
        logger.info(
            f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} files)"
        )

        for file_dict in batch:
            file_path = file_dict["absolute_path"]
            entity_id = file_dict["entity_id"]

            # Check if file exists
            if not Path(file_path).exists():
                log_pipeline_event(
                    logger,
                    logging.WARNING,
                    stage="backfill_language",
                    action="file_not_found",
                    correlation_id=correlation_id,
                    result="skipped",
                    file_path=file_path,
                )
                self.stats["skipped_not_found"] += 1
                logger.warning(f"⏭️ Skipped: {file_path} (file not found)")
                continue

            # Detect language
            language = self.detect_language(file_dict)

            # Update database
            success = await self.update_file_language(
                entity_id=entity_id,
                language=language,
                correlation_id=correlation_id,
            )

            if success:
                log_pipeline_event(
                    logger,
                    logging.INFO,
                    stage="backfill_language",
                    action="language_updated",
                    correlation_id=correlation_id,
                    result="success",
                    file_path=file_path,
                    language=language,
                )
                self.stats["updated"] += 1
                logger.info(f"✅ Updated: {file_path} → {language}")
            else:
                self.stats["failed"] += 1
                logger.error(f"❌ Failed: {file_path}")

    async def run(self) -> None:
        """Run the backfill process."""
        correlation_id = generate_correlation_id()
        start_time = time.perf_counter()

        logger.info("=" * 70)
        logger.info("Starting language field backfill...")
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
        if self.project_name:
            logger.info(f"📦 Project filter: {self.project_name}")
        logger.info("=" * 70)

        # Find files without language
        files = await self.find_files_without_language()
        self.stats["total_files"] = len(files)

        if not files:
            logger.info("✅ No files need language updates")
            return

        # Split into batches
        batches = [
            files[i : i + self.batch_size]
            for i in range(0, len(files), self.batch_size)
        ]
        total_batches = len(batches)

        logger.info(f"Processing {len(files)} files in {total_batches} batches")
        logger.info("")

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
            if processed > len(files):
                processed = len(files)
            percentage = (processed / len(files)) * 100
            logger.info(f"Progress: {processed}/{len(files)} ({percentage:.1f}%)")
            logger.info("")

        # Calculate statistics
        duration_s = time.perf_counter() - start_time

        # Summary
        logger.info("=" * 70)
        logger.info("Summary:")
        logger.info(f"  Files processed: {self.stats['total_files']}")
        logger.info(
            f"  Successfully updated: {self.stats['updated']} ({self.stats['updated']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(
            f"  Skipped (file not found): {self.stats['skipped_not_found']} ({self.stats['skipped_not_found']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(
            f"  Failed: {self.stats['failed']} ({self.stats['failed']/self.stats['total_files']*100:.1f}%)"
        )
        logger.info(f"  Duration: {duration_s//60:.0f}m {duration_s%60:.0f}s")
        logger.info("=" * 70)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill language metadata for FILE nodes in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run to see what would be updated
  python3 scripts/backfill_language_fields.py --dry-run

  # Update all files
  python3 scripts/backfill_language_fields.py

  # Update specific project
  python3 scripts/backfill_language_fields.py --project-name omniarchon

  # Smaller batches with verbose logging
  python3 scripts/backfill_language_fields.py --batch-size 50 --verbose
        """,
    )

    parser.add_argument(
        "--memgraph-uri",
        default="bolt://localhost:7687",
        help="Memgraph connection URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Files per batch (default: 100)",
    )
    parser.add_argument(
        "--project-name",
        help="Only update specific project (default: all projects)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Create backfiller
    backfiller = LanguageFieldBackfiller(
        memgraph_uri=args.memgraph_uri,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        verbose=args.verbose,
        project_name=args.project_name,
    )

    try:
        # Initialize connection
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
