#!/usr/bin/env python3
"""
Bulk Repository Ingestion CLI Tool

Indexes entire repositories into Archon Intelligence by discovering files,
generating metadata, and publishing events to Kafka for async processing.

Features:
- Recursive file discovery with filtering
- Inline content inclusion in Kafka events (Phase 1)
- Batch processing for performance
- Concurrent event publishing
- Progress tracking and error handling
- Dry-run mode for testing
- Partial failure recovery
- Automatic directory tree building (can be skipped)

Usage:
    # Index current directory (auto-loads .env for Kafka configuration)
    python bulk_ingest_repository.py .

    # Index with custom project name
    python bulk_ingest_repository.py /path/to/project --project-name my-project

    # Dry run (no events published)
    python bulk_ingest_repository.py /path/to/project --dry-run

    # Skip automatic tree building
    python bulk_ingest_repository.py /path/to/project --skip-tree

    # Custom batch size and concurrency (overrides .env defaults)
    python bulk_ingest_repository.py /path/to/project --batch-size 100 --max-concurrent 5

    # Custom rate limiting (events per second)
    python bulk_ingest_repository.py /path/to/project --rate-limit 50

    # Override Kafka servers from .env
    python bulk_ingest_repository.py /path/to/project --kafka-servers localhost:9092

Environment Variables (.env):
    KAFKA_BOOTSTRAP_SERVERS - Kafka server address (default: auto-configured via config.kafka_helper)
    KAFKA_TOPIC_PREFIX - Topic prefix (default: dev.archon-intelligence)
    BULK_INGEST_BATCH_SIZE - Batch size (default: 10)
    BULK_INGEST_MAX_FILE_SIZE - Max file size in bytes (default: 5242880)
    BULK_INGEST_RATE_LIMIT - Rate limit in events/sec (default: 25, 0=unlimited)

Performance Target: <95s for 1000 files (discovery + stamping + indexing)
Integration: Kafka event bus + Archon Intelligence Service
Event Schema: v2.0.0 (inline content support)

Created: 2025-10-27
Updated: 2025-11-10 - Added automatic directory tree building
ONEX Pattern: Orchestrator (workflow coordination and CLI interface)
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Add project root and intelligence service to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INTELLIGENCE_SERVICE_DIR = PROJECT_ROOT / "services" / "intelligence"
# Add INTELLIGENCE_SERVICE_DIR first for tree building imports,
# then PROJECT_ROOT (will be searched first due to insert order)
sys.path.insert(0, str(INTELLIGENCE_SERVICE_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from project root
env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# Import centralized configuration (after .env is loaded and path is set)
from config.kafka_helper import KAFKA_HOST_SERVERS, get_kafka_bootstrap_servers

# ==============================================================================
# Fail-Fast Validation
# ==============================================================================


async def verify_kafka_connectivity(bootstrap_servers: str, timeout: int = 5) -> None:
    """
    Verify Kafka/Redpanda is reachable BEFORE starting ingestion.
    Fail fast if unreachable to prevent silent failures.

    Args:
        bootstrap_servers: Kafka bootstrap servers (e.g., "192.168.86.200:29092" for host scripts)
        timeout: Connection timeout in seconds (default: 5)

    Raises:
        SystemExit: If Kafka is unreachable (exits with code 1)
    """
    from aiokafka import AIOKafkaProducer

    print(f"🔍 Verifying Kafka connectivity to {bootstrap_servers}...")

    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            request_timeout_ms=timeout * 1000,
        )

        # Attempt to connect with timeout
        await asyncio.wait_for(producer.start(), timeout=timeout)
        await producer.stop()

        print(f"✅ Kafka connectivity verified: {bootstrap_servers}\n")

    except asyncio.TimeoutError:
        print(f"\n❌ FATAL: Kafka connection timeout after {timeout}s", file=sys.stderr)
        print(f"   Bootstrap servers: {bootstrap_servers}", file=sys.stderr)
        print(f"   ", file=sys.stderr)
        print(f"   Troubleshooting:", file=sys.stderr)
        print(
            f"   1. Verify Kafka/Redpanda is running on {bootstrap_servers}",
            file=sys.stderr,
        )
        print(
            f"   2. Check network connectivity: nc -zv {bootstrap_servers.split(':')[0]} {bootstrap_servers.split(':')[1]}",
            file=sys.stderr,
        )
        print(
            f"   3. Verify firewall rules allow connections to {bootstrap_servers}",
            file=sys.stderr,
        )
        print(
            f"   4. Check /etc/hosts for DNS resolution (if using hostname)",
            file=sys.stderr,
        )
        sys.exit(1)

    except ConnectionRefusedError as e:
        print(f"\n❌ FATAL: Kafka connection refused", file=sys.stderr)
        print(f"   Bootstrap servers: {bootstrap_servers}", file=sys.stderr)
        print(f"   Error: {e}", file=sys.stderr)
        print(f"   ", file=sys.stderr)
        print(f"   Troubleshooting:", file=sys.stderr)
        print(f"   1. Verify Kafka/Redpanda service is running", file=sys.stderr)
        print(
            f"   2. Check if port {bootstrap_servers.split(':')[1]} is open",
            file=sys.stderr,
        )
        print(f"   3. For Docker services: use internal port 9092", file=sys.stderr)
        print(
            f"   4. For host scripts: use external port 29092 (configured in config.kafka_helper)",
            file=sys.stderr,
        )
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ FATAL: Cannot connect to Kafka", file=sys.stderr)
        print(f"   Bootstrap servers: {bootstrap_servers}", file=sys.stderr)
        print(f"   Error: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"   ", file=sys.stderr)
        print(f"   This is a CRITICAL infrastructure failure.", file=sys.stderr)
        print(
            f"   The script cannot proceed without Kafka connectivity.", file=sys.stderr
        )
        sys.exit(1)


from scripts.lib.batch_processor import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_CONCURRENT_BATCHES,
    DEFAULT_RATE_LIMIT,
    BatchProcessor,
)
from scripts.lib.file_discovery import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_SUPPORTED_EXTENSIONS,
    FileDiscovery,
)

# ==============================================================================
# Configuration
# ==============================================================================

# Logging configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

import json as json_module

# Structured logging with JSON support
import uuid
from datetime import datetime


def log_structured(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    correlation_id: str,
    **extra_fields,
) -> None:
    """
    Log with structured JSON format for machine parsing.

    Args:
        logger_instance: Logger instance to use
        level: Log level (logging.DEBUG, INFO, WARNING, ERROR)
        message: Human-readable message
        correlation_id: Correlation ID for tracing
        **extra_fields: Additional context fields
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "correlation_id": correlation_id,
        "message": message,
        **extra_fields,
    }

    # Log with extra fields
    logger_instance.log(
        level,
        message,
        extra={
            "correlation_id": correlation_id,
            "structured_data": json_module.dumps(log_entry),
            **extra_fields,
        },
    )


# Kafka configuration from environment
# Use centralized configuration with context-aware defaults
# Respects KAFKA_BOOTSTRAP_SERVERS env var if set, otherwise uses host context
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    get_kafka_bootstrap_servers(context="host"),  # Auto-configured for host scripts
)
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "dev.archon-intelligence")
DEFAULT_KAFKA_TOPIC = f"{KAFKA_TOPIC_PREFIX}.enrich-document.v1"

# Batch processing configuration from environment (with fallback to lib defaults)
ENV_BATCH_SIZE = int(os.getenv("BULK_INGEST_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
ENV_MAX_FILE_SIZE = int(
    os.getenv("BULK_INGEST_MAX_FILE_SIZE", str(DEFAULT_MAX_FILE_SIZE))
)
ENV_RATE_LIMIT = int(os.getenv("BULK_INGEST_RATE_LIMIT", str(DEFAULT_RATE_LIMIT)))


# ==============================================================================
# CLI Application
# ==============================================================================


class BulkIngestApp:
    """
    Bulk ingestion CLI application.

    Orchestrates file discovery, batch processing, and event publishing.
    """

    def __init__(
        self,
        project_path: Path,
        project_name: Optional[str] = None,
        kafka_bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        kafka_topic: str = DEFAULT_KAFKA_TOPIC,
        batch_size: int = ENV_BATCH_SIZE,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_BATCHES,
        max_file_size: int = ENV_MAX_FILE_SIZE,
        rate_limit: int = ENV_RATE_LIMIT,
        supported_extensions: Optional[set] = None,
        exclude_patterns: Optional[list] = None,
        dry_run: bool = False,
        force_reindex: bool = False,
        skip_tree: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize bulk ingestion application.

        Args:
            project_path: Path to project root directory
            project_name: Project name slug (default: directory name)
            kafka_bootstrap_servers: Kafka bootstrap servers
            kafka_topic: Kafka topic for index project requests
            batch_size: Number of files per batch
            max_concurrent: Maximum concurrent batches
            max_file_size: Maximum file size in bytes
            rate_limit: Rate limit in events per second (0 = no rate limiting)
            supported_extensions: Set of supported file extensions
            exclude_patterns: List of exclusion patterns
            dry_run: If True, don't publish events
            force_reindex: If True, force reindexing of already indexed projects
            skip_tree: If True, skip automatic directory tree building
            verbose: Enable verbose logging
        """
        self.project_path = project_path.resolve()
        self.project_name = project_name or self.project_path.name
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_topic = kafka_topic
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.max_file_size = max_file_size
        self.rate_limit = rate_limit
        self.dry_run = dry_run
        self.force_reindex = force_reindex
        self.skip_tree = skip_tree
        self.verbose = verbose

        # Configure logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        self.logger = logging.getLogger(__name__)

        # Log configuration
        self.logger.info("=" * 70)
        self.logger.info("CONFIGURATION")
        self.logger.info("=" * 70)
        self.logger.info(f"Project: {self.project_name}")
        self.logger.info(f"Project path: {self.project_path}")
        self.logger.info(f"Kafka servers: {self.kafka_bootstrap_servers}")
        self.logger.info(f"Kafka topic: {self.kafka_topic}")
        self.logger.info(f"Kafka topic prefix: {KAFKA_TOPIC_PREFIX}")
        self.logger.info(f"Batch size: {self.batch_size}")
        self.logger.info(f"Max concurrent batches: {self.max_concurrent}")
        self.logger.info(
            f"Max file size: {self.max_file_size // 1024 // 1024}MB ({self.max_file_size} bytes)"
        )
        if self.rate_limit > 0:
            self.logger.info(
                f"Rate limiting: {self.rate_limit} events/sec "
                f"({self.batch_size / self.rate_limit:.2f}s delay per batch)"
            )
        else:
            self.logger.info("Rate limiting: DISABLED (maximum speed)")
        self.logger.info(f"Config source: .env file (override with CLI args)")
        self.logger.info(f"Dry run mode: {self.dry_run}")
        self.logger.info(f"Force reindex: {self.force_reindex}")
        self.logger.info(f"Skip tree building: {self.skip_tree}")
        self.logger.info("=" * 70)
        self.logger.info("")

        # Initialize file discovery
        self.file_discovery = FileDiscovery(
            supported_extensions=supported_extensions or DEFAULT_SUPPORTED_EXTENSIONS,
            exclude_patterns=exclude_patterns or DEFAULT_EXCLUDE_PATTERNS,
            max_file_size=max_file_size,
            follow_symlinks=False,
        )

        # Initialize batch processor
        self.batch_processor = BatchProcessor(
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            kafka_topic=kafka_topic,
            batch_size=batch_size,
            max_concurrent_batches=max_concurrent,
            rate_limit=rate_limit,
            dry_run=dry_run,
            force_reindex=force_reindex,
        )

    async def wait_for_consumer_processing(
        self, correlation_id: str, expected_file_count: int, max_wait_seconds: int = 30
    ) -> bool:
        """
        Wait for Kafka consumer to create File nodes in Memgraph.

        Polls Memgraph to check if expected File nodes have been created.
        This ensures tree building doesn't run before consumer has processed events.

        Args:
            correlation_id: Correlation ID for logging
            expected_file_count: Number of files expected to be indexed
            max_wait_seconds: Maximum time to wait (default: 30s)

        Returns:
            True if nodes found, False if timeout
        """
        from storage.memgraph_adapter import MemgraphKnowledgeAdapter

        log_structured(
            self.logger,
            logging.INFO,
            f"⏳ Waiting for consumer to process {expected_file_count} files (max {max_wait_seconds}s)...",
            correlation_id,
            phase="consumer_wait",
            operation="start",
            expected_count=expected_file_count,
            max_wait_seconds=max_wait_seconds,
        )

        memgraph_uri = "bolt://localhost:7687"
        memgraph_adapter = MemgraphKnowledgeAdapter(
            uri=memgraph_uri, username=None, password=None
        )
        await memgraph_adapter.initialize()

        poll_interval = 2  # Check every 2 seconds
        elapsed = 0

        try:
            while elapsed < max_wait_seconds:
                # Query for File nodes
                query = """
                MATCH (f:File)
                WHERE f.project_name = $project_name
                RETURN count(f) as file_count
                """

                async with memgraph_adapter.driver.session() as session:
                    result = await session.run(query, project_name=self.project_name)
                    record = await result.single()
                    file_count = record["file_count"] if record else 0

                    if file_count >= expected_file_count:
                        log_structured(
                            self.logger,
                            logging.INFO,
                            f"✅ Consumer processing complete: {file_count} File nodes found",
                            correlation_id,
                            phase="consumer_wait",
                            operation="complete",
                            file_count=file_count,
                            elapsed_seconds=elapsed,
                        )
                        await memgraph_adapter.close()
                        return True

                    log_structured(
                        self.logger,
                        logging.DEBUG,
                        f"⏳ Waiting... ({file_count}/{expected_file_count} files, {elapsed}s elapsed)",
                        correlation_id,
                        phase="consumer_wait",
                        operation="polling",
                        file_count=file_count,
                        expected_count=expected_file_count,
                        elapsed_seconds=elapsed,
                    )

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout reached
            log_structured(
                self.logger,
                logging.WARNING,
                f"⚠️  Timeout waiting for consumer (found {file_count}/{expected_file_count} files after {max_wait_seconds}s)",
                correlation_id,
                phase="consumer_wait",
                operation="timeout",
                file_count=file_count,
                expected_count=expected_file_count,
                elapsed_seconds=elapsed,
            )
            await memgraph_adapter.close()
            return False

        except Exception as e:
            log_structured(
                self.logger,
                logging.ERROR,
                f"❌ Error waiting for consumer: {e}",
                correlation_id,
                phase="consumer_wait",
                operation="error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            await memgraph_adapter.close()
            return False

    async def build_directory_tree(self, correlation_id: str) -> bool:
        """
        Build directory tree structure in Memgraph.

        This creates PROJECT and DIRECTORY nodes with CONTAINS relationships,
        enabling file tree visualization and queries.

        Args:
            correlation_id: Correlation ID for logging

        Returns:
            True if successful, False if failed (non-fatal)
        """
        tree_start_time = datetime.utcnow()

        if self.skip_tree:
            log_structured(
                self.logger,
                logging.INFO,
                "⏭️  Skipping directory tree building (--skip-tree enabled)",
                correlation_id,
                phase="tree_building",
                operation="skip",
                project_name=self.project_name,
            )
            return True

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("🌳 BUILDING DIRECTORY TREE")
        self.logger.info("=" * 70)

        log_structured(
            self.logger,
            logging.INFO,
            f"🚀 Starting directory tree building for {self.project_name}",
            correlation_id,
            phase="tree_building",
            operation="start",
            project_name=self.project_name,
            project_root=str(self.project_path),
        )

        try:
            # Import tree builder (lazy import to avoid dependency issues)
            from src.services.directory_indexer import DirectoryIndexer
            from storage.memgraph_adapter import MemgraphKnowledgeAdapter

            # Initialize Memgraph adapter
            # Note: Host scripts must use localhost:7687, not Docker hostname
            # Docker services use bolt://memgraph:7687 (via MEMGRAPH_URI env var)
            # Host scripts use bolt://localhost:7687 (hardcoded for consistency)
            memgraph_uri = "bolt://localhost:7687"
            memgraph_adapter = MemgraphKnowledgeAdapter(
                uri=memgraph_uri, username=None, password=None
            )
            await memgraph_adapter.initialize()

            # Initialize DirectoryIndexer
            directory_indexer = DirectoryIndexer(memgraph_adapter)

            # Query for File nodes to extract file paths
            query = """
            MATCH (f:File)
            WHERE f.project_name = $project_name OR f.path CONTAINS $project_name
            RETURN f.path as file_path, f.entity_id as entity_id
            ORDER BY f.path
            """

            log_structured(
                self.logger,
                logging.DEBUG,
                "🔍 Querying Memgraph for File nodes",
                correlation_id,
                phase="tree_building",
                operation="query_files",
                project_name=self.project_name,
            )

            async with memgraph_adapter.driver.session() as session:
                result = await session.run(query, project_name=self.project_name)
                records = await result.data()

                if not records:
                    log_structured(
                        self.logger,
                        logging.WARNING,
                        f"⚠️  No File nodes found for project: {self.project_name}",
                        correlation_id,
                        phase="tree_building",
                        operation="query_files",
                        project_name=self.project_name,
                        file_count=0,
                        status="skipped",
                    )
                    await memgraph_adapter.close()
                    return False

                # Extract file paths from archon:// URIs
                file_paths = []
                file_entity_mapping = {}

                for record in records:
                    uri = record["file_path"]
                    entity_id = record["entity_id"]

                    if "documents/" in uri:
                        actual_path = uri.split("documents/", 1)[1]
                        file_paths.append(actual_path)
                        file_entity_mapping[actual_path] = entity_id
                    else:
                        file_paths.append(uri)
                        file_entity_mapping[uri] = entity_id

                log_structured(
                    self.logger,
                    logging.INFO,
                    f"📁 Found {len(file_paths)} FILE nodes in Memgraph",
                    correlation_id,
                    phase="tree_building",
                    operation="query_files",
                    file_count=len(file_paths),
                    project_name=self.project_name,
                )

                # Build directory tree
                log_structured(
                    self.logger,
                    logging.INFO,
                    f"🏗️  Building directory hierarchy",
                    correlation_id,
                    phase="tree_building",
                    operation="build_hierarchy",
                    project_name=self.project_name,
                    file_count=len(file_paths),
                )

                stats = await directory_indexer.index_directory_hierarchy(
                    project_name=self.project_name,
                    project_root=str(self.project_path),
                    file_paths=file_paths,
                    file_entity_mapping=file_entity_mapping,
                )

                # Calculate duration
                tree_duration_ms = (
                    datetime.utcnow() - tree_start_time
                ).total_seconds() * 1000

                log_structured(
                    self.logger,
                    logging.INFO,
                    f"✅ Directory tree built successfully",
                    correlation_id,
                    phase="tree_building",
                    operation="complete",
                    project_name=self.project_name,
                    nodes_created=stats.get("projects", 0)
                    + stats.get("directories", 0),
                    projects_created=stats.get("projects", 0),
                    directories_created=stats.get("directories", 0),
                    files_linked=stats.get("files", 0),
                    relationships_created=stats.get("relationships", 0),
                    duration_ms=round(tree_duration_ms, 2),
                )

                # Log detailed stats for debugging
                if self.verbose:
                    log_structured(
                        self.logger,
                        logging.DEBUG,
                        f"Tree building stats: {stats}",
                        correlation_id,
                        phase="tree_building",
                        operation="stats",
                        stats=stats,
                    )

                # Detect orphaned File nodes using Data Quality API
                # This centralizes orphan detection logic in the API service
                log_structured(
                    self.logger,
                    logging.DEBUG,
                    "🔍 Checking for orphaned File nodes via Data Quality API",
                    correlation_id,
                    phase="tree_building",
                    operation="orphan_detection",
                    project_name=self.project_name,
                )

                try:
                    # Call Data Quality API for orphan count
                    intelligence_port = os.getenv("INTELLIGENCE_SERVICE_PORT", "8053")
                    api_url = f"http://localhost:{intelligence_port}/api/data-quality/orphan-count"
                    params = {"project": self.project_name}

                    response = requests.get(api_url, params=params, timeout=5)
                    response.raise_for_status()

                    orphan_data = response.json()
                    orphan_count = orphan_data.get("orphan_count", 0)
                    orphan_files = orphan_data.get("orphan_files", [])

                    if orphan_count > 0:
                        log_structured(
                            self.logger,
                            logging.WARNING,
                            f"⚠️  Detected {orphan_count} orphaned File nodes (no parent Directory/PROJECT)",
                            correlation_id,
                            phase="tree_building",
                            operation="orphan_detection",
                            orphan_count=orphan_count,
                            project_name=self.project_name,
                        )

                        # Log first few orphans for debugging
                        for i, orphan in enumerate(orphan_files[:5]):
                            log_structured(
                                self.logger,
                                logging.WARNING,
                                f"  Orphan file: {orphan.get('file_path', 'unknown')}",
                                correlation_id,
                                phase="tree_building",
                                operation="orphan_detail",
                                file_path=orphan.get("file_path"),
                                entity_id=orphan.get("entity_id"),
                                orphan_index=i + 1,
                            )

                        if orphan_count > 5:
                            log_structured(
                                self.logger,
                                logging.WARNING,
                                f"  ... and {orphan_count - 5} more orphaned files",
                                correlation_id,
                                phase="tree_building",
                                operation="orphan_summary",
                                remaining_orphans=orphan_count - 5,
                            )
                    else:
                        log_structured(
                            self.logger,
                            logging.INFO,
                            "✅ No orphaned File nodes detected",
                            correlation_id,
                            phase="tree_building",
                            operation="orphan_detection",
                            orphan_count=0,
                            project_name=self.project_name,
                        )

                except requests.RequestException as e:
                    # Log API error but don't fail the entire tree building
                    log_structured(
                        self.logger,
                        logging.WARNING,
                        f"⚠️  Could not check orphans via API: {e}",
                        correlation_id,
                        phase="tree_building",
                        operation="orphan_detection_failed",
                        error=str(e),
                    )

            await memgraph_adapter.close()
            return True

        except ImportError as e:
            log_structured(
                self.logger,
                logging.WARNING,
                f"⚠️  Cannot import tree building dependencies: {e}",
                correlation_id,
                phase="tree_building",
                operation="error",
                error_type="ImportError",
                error_message=str(e),
                status="skipped",
            )
            return False

        except Exception as e:
            tree_duration_ms = (
                datetime.utcnow() - tree_start_time
            ).total_seconds() * 1000

            log_structured(
                self.logger,
                logging.ERROR,
                f"❌ Failed to build directory tree: {e}",
                correlation_id,
                phase="tree_building",
                operation="error",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round(tree_duration_ms, 2),
                status="failed",
            )

            if self.verbose:
                self.logger.debug("Tree building error details:", exc_info=True)
            return False

    async def run(self) -> int:
        """
        Run bulk ingestion workflow.

        Workflow:
        1. Discover files
        2. Initialize Kafka producer
        3. Process files in batches
        4. Shutdown producer
        5. Build directory tree (optional, controlled by skip_tree flag)
        6. Report results

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        # Generate correlation ID for this ingestion run
        correlation_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        try:
            # Phase 1: File Discovery
            self.logger.info(
                "🚀 Starting bulk ingestion workflow",
                extra={
                    "correlation_id": correlation_id,
                    "project_name": self.project_name,
                    "project_path": str(self.project_path),
                    "timestamp": start_time.isoformat(),
                    "dry_run": self.dry_run,
                },
            )

            self.logger.info("=" * 70)
            self.logger.info("📁 PHASE 1: FILE DISCOVERY")
            self.logger.info("=" * 70)
            self.logger.info(
                f"Project: {self.project_name}",
                extra={
                    "correlation_id": correlation_id,
                    "phase": "discovery",
                    "project_name": self.project_name,
                    "project_path": str(self.project_path),
                },
            )
            self.logger.info(f"Path: {self.project_path}")
            self.logger.info("")

            files, discovery_stats = self.file_discovery.discover(self.project_path)

            self.logger.info(
                f"✅ Discovery complete: {discovery_stats}",
                extra={
                    "correlation_id": correlation_id,
                    "phase": "discovery",
                    "files_discovered": discovery_stats.total_files,
                    "filtered_files": discovery_stats.filtered_files,
                    "excluded_files": discovery_stats.excluded_files,
                    "language_breakdown": discovery_stats.language_breakdown,
                },
            )
            self.logger.info("")

            # Display language breakdown
            if discovery_stats.language_breakdown:
                self.logger.info("Language breakdown:")
                for lang, count in sorted(
                    discovery_stats.language_breakdown.items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    self.logger.info(f"  {lang:15s}: {count:5d} files")
                self.logger.info("")

            if not files:
                self.logger.warning("No files discovered - nothing to process")
                return 0

            # Phase 2: Batch Processing
            self.logger.info("=" * 70)
            self.logger.info("📤 PHASE 2: BATCH PROCESSING & EVENT PUBLISHING")
            self.logger.info("=" * 70)
            self.logger.info(
                f"Event schema version: v2.0.0 (inline content support)",
                extra={
                    "correlation_id": correlation_id,
                    "phase": "batch_processing",
                    "schema_version": "v2.0.0",
                    "batch_size": self.batch_size,
                    "max_concurrent": self.max_concurrent,
                    "total_files": len(files),
                },
            )
            self.logger.info(f"Content strategy: inline (with SHA256 checksums)")
            self.logger.info(f"Batch size: {self.batch_size}")
            self.logger.info(f"Max concurrent batches: {self.max_concurrent}")
            self.logger.info(f"Kafka topic: {self.kafka_topic}")
            if self.dry_run:
                self.logger.info("⚠️  DRY RUN MODE - No events will be published")
            self.logger.info("")

            # Initialize Kafka producer
            self.logger.info(
                "🔌 Initializing Kafka producer",
                extra={
                    "correlation_id": correlation_id,
                    "kafka_servers": self.kafka_bootstrap_servers,
                    "kafka_topic": self.kafka_topic,
                },
            )
            await self.batch_processor.initialize()

            # Convert FileInfo to dictionaries
            file_dicts = [f.to_dict() for f in files]

            # Process files with progress tracking
            def progress_callback(batch_num: int, total_batches: int):
                """Progress callback for batch processing."""
                percent = (batch_num / total_batches) * 100
                self.logger.info(
                    f"📊 Progress: {batch_num}/{total_batches} batches ({percent:.0f}%)",
                    extra={
                        "correlation_id": correlation_id,
                        "phase": "batch_processing",
                        "batch_num": batch_num,
                        "total_batches": total_batches,
                        "percent": round(percent, 1),
                        "files_processed": batch_num * self.batch_size,
                    },
                )

            batch_results, processing_stats = await self.batch_processor.process_files(
                files=file_dicts,
                project_name=self.project_name,
                project_path=self.project_path,
                progress_callback=progress_callback,
            )

            # Shutdown Kafka producer
            self.logger.info(
                "🔌 Shutting down Kafka producer",
                extra={"correlation_id": correlation_id, "phase": "shutdown"},
            )
            await self.batch_processor.shutdown()

            # Wait for consumer to process events, then build directory tree
            if not self.skip_tree and not self.dry_run:
                consumer_ready = await self.wait_for_consumer_processing(
                    correlation_id=correlation_id,
                    expected_file_count=processing_stats.total_files,
                    max_wait_seconds=30,
                )
                if consumer_ready:
                    await self.build_directory_tree(correlation_id)
                else:
                    log_structured(
                        self.logger,
                        logging.WARNING,
                        "⚠️  Skipping tree building - consumer not ready",
                        correlation_id,
                        phase="tree_building",
                        operation="skip",
                        reason="consumer_timeout",
                    )
            elif self.skip_tree:
                log_structured(
                    self.logger,
                    logging.INFO,
                    "⏭️  Skipping tree building (--skip-tree flag)",
                    correlation_id,
                    phase="tree_building",
                    operation="skip",
                    reason="skip_tree_flag",
                )
            else:  # dry_run
                await self.build_directory_tree(correlation_id)

            # Phase 3: Results Summary
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info("📊 PHASE 3: RESULTS SUMMARY")
            self.logger.info("=" * 70)
            self.logger.info(
                f"Processing complete: {processing_stats}",
                extra={
                    "correlation_id": correlation_id,
                    "phase": "results",
                    "total_files": processing_stats.total_files,
                    "successful_batches": processing_stats.successful_batches,
                    "failed_batches": processing_stats.failed_batches,
                    "duration_ms": round(duration_ms, 2),
                    "files_per_second": (
                        round(processing_stats.total_files / (duration_ms / 1000), 2)
                        if duration_ms > 0
                        else 0
                    ),
                },
            )
            self.logger.info("")

            # Display batch results
            if processing_stats.failed_batches > 0:
                self.logger.warning(
                    f"❌ Failed batches: {processing_stats.failed_batches}",
                    extra={
                        "correlation_id": correlation_id,
                        "failed_batches": processing_stats.failed_batches,
                    },
                )
                for result in batch_results:
                    if not result.success:
                        self.logger.warning(f"  {result}")
                self.logger.info("")

            # Success/failure determination
            if processing_stats.failed_batches == 0:
                self.logger.info(
                    "✅ All batches processed successfully!",
                    extra={
                        "correlation_id": correlation_id,
                        "status": "success",
                        "total_batches": processing_stats.successful_batches,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return 0
            elif processing_stats.successful_batches > 0:
                self.logger.warning(
                    f"⚠️  Partial success: {processing_stats.successful_batches} batches succeeded, "
                    f"{processing_stats.failed_batches} failed",
                    extra={
                        "correlation_id": correlation_id,
                        "status": "partial_success",
                        "successful_batches": processing_stats.successful_batches,
                        "failed_batches": processing_stats.failed_batches,
                    },
                )
                return 1
            else:
                self.logger.error(
                    "❌ All batches failed",
                    extra={
                        "correlation_id": correlation_id,
                        "status": "failed",
                        "failed_batches": processing_stats.failed_batches,
                    },
                )
                return 1

        except KeyboardInterrupt:
            self.logger.warning("\n\nInterrupted by user - shutting down...")
            try:
                await self.batch_processor.shutdown()
            except Exception:
                pass
            return 130  # Standard exit code for SIGINT

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=self.verbose)
            try:
                await self.batch_processor.shutdown()
            except Exception:
                pass
            return 1


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
        description="Bulk repository ingestion CLI tool for Archon Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index current directory (with automatic tree building)
  %(prog)s .

  # Index with custom project name
  %(prog)s /path/to/project --project-name my-project

  # Dry run (no events published)
  %(prog)s /path/to/project --dry-run

  # Skip automatic tree building
  %(prog)s /path/to/project --skip-tree

  # Custom batch size and concurrency
  %(prog)s /path/to/project --batch-size 100 --max-concurrent 5

  # Custom rate limiting (events per second)
  %(prog)s /path/to/project --rate-limit 50

  # Disable rate limiting (maximum speed, use with caution)
  %(prog)s /path/to/project --rate-limit 0

  # Custom Kafka configuration
  %(prog)s /path/to/project --kafka-servers localhost:9092

  # Verbose logging
  %(prog)s /path/to/project --verbose
        """,
    )

    # Required arguments
    parser.add_argument(
        "project_path",
        type=Path,
        help="Path to project root directory",
    )

    # Optional arguments
    parser.add_argument(
        "--project-name",
        type=str,
        help="Project name slug (default: directory name)",
    )

    parser.add_argument(
        "--kafka-servers",
        type=str,
        default=KAFKA_BOOTSTRAP_SERVERS,
        help=f"Kafka bootstrap servers (env: KAFKA_BOOTSTRAP_SERVERS, default: {KAFKA_BOOTSTRAP_SERVERS})",
    )

    parser.add_argument(
        "--kafka-topic",
        type=str,
        default=DEFAULT_KAFKA_TOPIC,
        help=f"Kafka topic for index project requests (default: {DEFAULT_KAFKA_TOPIC})",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=ENV_BATCH_SIZE,
        help=f"Number of files per batch (env: BULK_INGEST_BATCH_SIZE, default: {ENV_BATCH_SIZE})",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_BATCHES,
        help=f"Maximum concurrent batches (default: {DEFAULT_MAX_CONCURRENT_BATCHES})",
    )

    parser.add_argument(
        "--max-file-size",
        type=int,
        default=ENV_MAX_FILE_SIZE,
        help=f"Maximum file size in bytes (env: BULK_INGEST_MAX_FILE_SIZE, default: {ENV_MAX_FILE_SIZE // 1024 // 1024}MB)",
    )

    parser.add_argument(
        "--rate-limit",
        type=int,
        default=ENV_RATE_LIMIT,
        help=f"Rate limit in events per second (env: BULK_INGEST_RATE_LIMIT, default: {ENV_RATE_LIMIT}, 0=unlimited)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't publish events)",
    )

    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Force reindexing of already indexed projects",
    )

    parser.add_argument(
        "--skip-tree",
        action="store_true",
        help="Skip automatic directory tree building after indexing",
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

    # Validate project path
    if not args.project_path.exists():
        print(
            f"Error: Project path does not exist: {args.project_path}", file=sys.stderr
        )
        return 1

    if not args.project_path.is_dir():
        print(
            f"Error: Project path is not a directory: {args.project_path}",
            file=sys.stderr,
        )
        return 1

    # FAIL FAST: Verify Kafka connectivity before processing files
    # Skip verification in dry-run mode (no Kafka operations)
    if not args.dry_run:
        await verify_kafka_connectivity(args.kafka_servers, timeout=5)

    # Create application
    app = BulkIngestApp(
        project_path=args.project_path,
        project_name=args.project_name,
        kafka_bootstrap_servers=args.kafka_servers,
        kafka_topic=args.kafka_topic,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent,
        max_file_size=args.max_file_size,
        rate_limit=args.rate_limit,
        dry_run=args.dry_run,
        force_reindex=args.force_reindex,
        skip_tree=args.skip_tree,
        verbose=args.verbose,
    )

    # Run application
    return await app.run()


def main() -> int:
    """
    Main entry point (sync wrapper).

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
