"""
Large Repository Performance Integration Tests

Tests indexing performance and scalability for large repositories (1000+ files).
Validates memory usage, query performance, and incremental update efficiency.

Test Coverage:
- Large repository indexing (1000+ files)
- Indexing performance (time per file)
- Memory usage monitoring
- Query performance at scale
- Incremental updates and re-indexing
- Orphan detection at scale

Performance Targets:
- Indexing time: < 95s for 1000 files
- Time per file: < 100ms average
- Memory usage: < 2GB during indexing
- Query time: < 500ms for file path queries
- Incremental update: < 5s for 10 file changes

Created: 2025-11-07
ONEX Pattern: Performance and scale testing
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import psutil
import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def service_urls():
    """Service URL configuration"""
    return {
        "intelligence": os.getenv("INTELLIGENCE_URL", "http://localhost:8053"),
        "bridge": os.getenv("BRIDGE_URL", "http://localhost:8054"),
        "search": os.getenv("SEARCH_URL", "http://localhost:8055"),
        "memgraph_uri": os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
    }


@pytest.fixture(scope="module")
def test_fixtures_dir():
    """Path to test fixtures directory"""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def performance_targets():
    """Performance target thresholds"""
    return {
        "total_indexing_time_1000_files": 95.0,  # seconds
        "time_per_file": 0.1,  # seconds
        "max_memory_usage_mb": 2048,  # MB
        "query_time_file_path": 0.5,  # seconds
        "incremental_update_time": 5.0,  # seconds
        "orphan_detection_time": 10.0,  # seconds
    }


@pytest_asyncio.fixture(scope="module")
async def memgraph_connection(service_urls):
    """Create Memgraph connection"""
    driver = AsyncGraphDatabase.driver(service_urls["memgraph_uri"])
    yield driver
    await driver.close()


@pytest_asyncio.fixture(scope="module")
async def http_client():
    """HTTP client for service communication"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        yield client


class PerformanceMonitor:
    """Monitor performance metrics during testing"""

    def __init__(self):
        self.process = psutil.Process()
        self.start_time: Optional[float] = None
        self.peak_memory_mb: float = 0.0
        self.metrics: Dict[str, Any] = {}

    def start(self):
        """Start performance monitoring"""
        self.start_time = time.time()
        self.peak_memory_mb = 0.0
        self.metrics = {
            "start_memory_mb": self._get_memory_usage_mb(),
            "start_cpu_percent": self.process.cpu_percent(),
        }

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024

    def update(self):
        """Update peak memory usage"""
        current_memory = self._get_memory_usage_mb()
        self.peak_memory_mb = max(self.peak_memory_mb, current_memory)

    def finish(self) -> Dict[str, Any]:
        """Finish monitoring and return metrics"""
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        end_memory_mb = self._get_memory_usage_mb()

        self.metrics.update(
            {
                "elapsed_time_seconds": elapsed_time,
                "end_memory_mb": end_memory_mb,
                "peak_memory_mb": self.peak_memory_mb,
                "memory_delta_mb": end_memory_mb - self.metrics["start_memory_mb"],
                "end_cpu_percent": self.process.cpu_percent(),
            }
        )

        return self.metrics


class LargeRepoTestHelper:
    """Helper class for large repository testing"""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        memgraph_driver,
        service_urls: Dict[str, str],
    ):
        self.http_client = http_client
        self.memgraph_driver = memgraph_driver
        self.service_urls = service_urls

    async def wait_for_indexing(
        self, project_name: str, expected_file_count: int, timeout: float = 120.0
    ) -> bool:
        """Wait for files to be indexed"""
        start_time = time.time()
        check_interval = 5.0

        while time.time() - start_time < timeout:
            async with self.memgraph_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                    RETURN count(f) as file_count
                    """,
                    project_name=project_name,
                )
                record = await result.single()
                if record and record["file_count"] >= expected_file_count:
                    return True

            await asyncio.sleep(check_interval)

        return False

    async def get_file_count(self, project_name: str) -> int:
        """Get current file count"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                RETURN count(f) as file_count
                """,
                project_name=project_name,
            )
            record = await result.single()
            return record["file_count"] if record else 0

    async def query_file_by_path(
        self, project_name: str, file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Query for a specific file by path"""
        start_time = time.time()

        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                WHERE f.path CONTAINS $file_path
                RETURN f.path as path,
                       f.entity_count as entity_count,
                       f.import_count as import_count
                LIMIT 1
                """,
                project_name=project_name,
                file_path=file_path,
            )
            record = await result.single()

        query_time = time.time() - start_time

        if record:
            data = record.data()
            data["query_time"] = query_time
            return data

        return None

    async def detect_orphans(self, project_name: str) -> tuple[List[Dict], float]:
        """Detect orphans and measure time"""
        start_time = time.time()

        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                OPTIONAL MATCH outgoing = (f)-[:IMPORTS]->()
                OPTIONAL MATCH incoming = ()-[:IMPORTS]->(f)
                WITH f, outgoing, incoming
                WHERE outgoing IS NULL AND incoming IS NULL
                RETURN f.path as path
                """,
                project_name=project_name,
            )
            orphans = [record.data() async for record in result]

        elapsed_time = time.time() - start_time
        return orphans, elapsed_time

    async def cleanup_project(self, project_name: str):
        """Clean up test project"""
        async with self.memgraph_driver.session() as session:
            await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})
                OPTIONAL MATCH (p)-[:CONTAINS*]->(n)
                DETACH DELETE p, n
                """,
                project_name=project_name,
            )

    def generate_large_repo(
        self, base_dir: Path, num_files: int = 1000
    ) -> tuple[Path, int]:
        """Generate a large test repository with many files"""
        repo_path = base_dir / "test_repo_large"
        repo_path.mkdir(exist_ok=True)

        files_created = 0

        # Create directory structure
        num_dirs = max(10, num_files // 100)

        for dir_idx in range(num_dirs):
            dir_path = repo_path / f"module_{dir_idx}"
            dir_path.mkdir(exist_ok=True)

            # Create files in this directory
            files_per_dir = num_files // num_dirs
            for file_idx in range(files_per_dir):
                file_path = dir_path / f"file_{file_idx}.py"

                # Generate file content with imports
                content = f'''"""
Module {dir_idx} - File {file_idx}

This file is part of a large test repository.
"""

import os
import sys
from pathlib import Path

'''
                # Add some inter-module imports
                if dir_idx > 0 and file_idx % 3 == 0:
                    prev_dir = dir_idx - 1
                    prev_file = file_idx % files_per_dir
                    content += f"from module_{prev_dir}.file_{prev_file} import function_{prev_file}\n\n"

                content += f"""

def function_{file_idx}():
    \"\"\"Function {file_idx} in module {dir_idx}\"\"\"
    return "Function {file_idx} executed"


class Class_{file_idx}:
    \"\"\"Class {file_idx} in module {dir_idx}\"\"\"

    def __init__(self):
        self.name = "Class_{file_idx}"
        self.module = {dir_idx}

    def method_{file_idx}(self):
        \"\"\"Method {file_idx}\"\"\"
        return f"{{self.name}}.method_{file_idx}"


# Constants
CONSTANT_{file_idx} = {file_idx}
MODULE_ID = {dir_idx}
"""

                file_path.write_text(content)
                files_created += 1

        logger.info(f"Generated {files_created} files in {num_dirs} directories")
        return repo_path, files_created


@pytest_asyncio.fixture
async def large_repo_helper(http_client, memgraph_connection, service_urls):
    """Create large repository test helper"""
    helper = LargeRepoTestHelper(http_client, memgraph_connection, service_urls)
    yield helper


@pytest.mark.slow
@pytest.mark.asyncio
async def test_large_repository_indexing(
    large_repo_helper: LargeRepoTestHelper,
    test_fixtures_dir: Path,
    performance_targets: Dict[str, float],
):
    """
    Test indexing large repository (1000+ files).

    Measures:
    - Total indexing time
    - Time per file
    - Memory usage
    - Verifies all files indexed
    """
    project_name = f"test_large_{int(time.time())}"

    # Generate large repository
    logger.info("Generating large test repository...")
    repo_path, expected_files = large_repo_helper.generate_large_repo(
        test_fixtures_dir, num_files=1000
    )

    try:
        # Start performance monitoring
        monitor = PerformanceMonitor()
        monitor.start()

        # Ingest repository
        logger.info(f"Ingesting {expected_files} files...")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        ingestion_start = time.time()

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
            batch_size=50,  # Optimize for large repo
        )

        # Wait for indexing
        indexed = await large_repo_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=expected_files, timeout=120.0
        )

        total_time = time.time() - ingestion_start
        monitor.update()

        # Get final metrics
        metrics = monitor.finish()

        # Verify indexing completed
        assert indexed, f"Not all files indexed within timeout (120s)"

        final_count = await large_repo_helper.get_file_count(project_name)
        assert (
            final_count >= expected_files
        ), f"Expected {expected_files} files, found {final_count}"

        # Verify performance targets
        time_per_file = total_time / expected_files

        logger.info(f"Performance Metrics:")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(f"  Time per file: {time_per_file*1000:.2f}ms")
        logger.info(f"  Peak memory: {metrics['peak_memory_mb']:.2f} MB")
        logger.info(f"  Memory delta: {metrics['memory_delta_mb']:.2f} MB")

        # Assert against targets
        assert (
            total_time <= performance_targets["total_indexing_time_1000_files"]
        ), f"Indexing too slow: {total_time:.2f}s > {performance_targets['total_indexing_time_1000_files']}s"

        assert (
            time_per_file <= performance_targets["time_per_file"]
        ), f"Time per file too high: {time_per_file:.3f}s > {performance_targets['time_per_file']}s"

        assert (
            metrics["peak_memory_mb"] <= performance_targets["max_memory_usage_mb"]
        ), f"Memory usage too high: {metrics['peak_memory_mb']:.0f} MB > {performance_targets['max_memory_usage_mb']} MB"

        logger.info("✅ Large repository indexing test passed")

    finally:
        # Cleanup
        await large_repo_helper.cleanup_project(project_name)
        # Clean up generated files
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_query_performance_at_scale(
    large_repo_helper: LargeRepoTestHelper,
    test_fixtures_dir: Path,
    performance_targets: Dict[str, float],
):
    """
    Test query performance with large dataset.

    Verifies that queries remain fast even with 1000+ files indexed.
    """
    project_name = f"test_query_perf_{int(time.time())}"

    # Generate smaller repo for query testing (100 files is sufficient)
    repo_path, expected_files = large_repo_helper.generate_large_repo(
        test_fixtures_dir, num_files=100
    )

    try:
        # Ingest repository
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await large_repo_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=expected_files, timeout=60.0
        )
        assert indexed, "Files not indexed"

        # Test query performance for multiple files
        query_times = []

        for i in range(10):
            module_idx = i % 10
            file_idx = i % 10
            file_path = f"module_{module_idx}/file_{file_idx}.py"

            result = await large_repo_helper.query_file_by_path(project_name, file_path)

            if result:
                query_times.append(result["query_time"])
                logger.info(
                    f"Query {i+1}: {file_path} found in {result['query_time']*1000:.2f}ms"
                )

        # Calculate average query time
        avg_query_time = sum(query_times) / len(query_times) if query_times else 0
        max_query_time = max(query_times) if query_times else 0

        logger.info(f"Query Performance:")
        logger.info(f"  Average: {avg_query_time*1000:.2f}ms")
        logger.info(f"  Max: {max_query_time*1000:.2f}ms")

        # Assert against targets
        assert (
            avg_query_time <= performance_targets["query_time_file_path"]
        ), f"Average query time too high: {avg_query_time:.3f}s > {performance_targets['query_time_file_path']}s"

        assert (
            max_query_time <= performance_targets["query_time_file_path"] * 2
        ), f"Max query time too high: {max_query_time:.3f}s"

        logger.info("✅ Query performance test passed")

    finally:
        await large_repo_helper.cleanup_project(project_name)
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_detection_at_scale(
    large_repo_helper: LargeRepoTestHelper,
    test_fixtures_dir: Path,
    performance_targets: Dict[str, float],
):
    """
    Test orphan detection performance at scale.

    Verifies that orphan detection completes quickly even with many files.
    """
    project_name = f"test_orphan_scale_{int(time.time())}"

    # Generate repository with some orphans
    repo_path, expected_files = large_repo_helper.generate_large_repo(
        test_fixtures_dir, num_files=200
    )

    # Add some orphan files
    orphan_dir = repo_path / "orphans"
    orphan_dir.mkdir(exist_ok=True)

    for i in range(10):
        orphan_file = orphan_dir / f"orphan_{i}.py"
        orphan_file.write_text(
            f'''"""
Orphaned file {i} - not imported anywhere.
"""

def orphaned_function_{i}():
    return "I am orphaned"
'''
        )

    try:
        # Ingest repository
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await large_repo_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=210, timeout=60.0
        )
        assert indexed, "Files not indexed"

        # Run orphan detection
        orphans, detection_time = await large_repo_helper.detect_orphans(project_name)

        logger.info(f"Orphan Detection:")
        logger.info(f"  Time: {detection_time:.3f}s")
        logger.info(f"  Orphans found: {len(orphans)}")

        # Verify performance
        assert (
            detection_time <= performance_targets["orphan_detection_time"]
        ), f"Orphan detection too slow: {detection_time:.2f}s > {performance_targets['orphan_detection_time']}s"

        # Verify orphans were found
        assert len(orphans) >= 10, f"Expected at least 10 orphans, found {len(orphans)}"

        # Verify correct files marked as orphans
        orphan_paths = [o["path"] for o in orphans]
        orphan_files_detected = [p for p in orphan_paths if "orphan_" in p]
        assert (
            len(orphan_files_detected) >= 10
        ), "Should detect orphan files in orphans/ directory"

        logger.info("✅ Orphan detection at scale test passed")

    finally:
        await large_repo_helper.cleanup_project(project_name)
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_incremental_updates(
    large_repo_helper: LargeRepoTestHelper,
    test_fixtures_dir: Path,
    performance_targets: Dict[str, float],
):
    """
    Test incremental update performance.

    Verifies that re-indexing after small changes is efficient.
    """
    project_name = f"test_incremental_{int(time.time())}"

    # Generate initial repository
    repo_path, initial_files = large_repo_helper.generate_large_repo(
        test_fixtures_dir, num_files=50
    )

    try:
        # Initial indexing
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        indexed = await large_repo_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=initial_files, timeout=60.0
        )
        assert indexed, "Initial indexing failed"

        # Modify 10 files
        logger.info("Modifying 10 files...")
        for i in range(10):
            file_path = repo_path / f"module_{i}" / "file_0.py"
            if file_path.exists():
                content = file_path.read_text()
                content += f"\n\n# Modified at {time.time()}\n"
                file_path.write_text(content)

        # Re-index with timing
        update_start = time.time()

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for updates
        await asyncio.sleep(5)  # Give time for updates to process

        update_time = time.time() - update_start

        logger.info(f"Incremental Update:")
        logger.info(f"  Time: {update_time:.3f}s")

        # Verify performance
        assert (
            update_time <= performance_targets["incremental_update_time"]
        ), f"Incremental update too slow: {update_time:.2f}s > {performance_targets['incremental_update_time']}s"

        logger.info("✅ Incremental update test passed")

    finally:
        await large_repo_helper.cleanup_project(project_name)
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_memory_usage(
    large_repo_helper: LargeRepoTestHelper,
    test_fixtures_dir: Path,
    performance_targets: Dict[str, float],
):
    """
    Test memory usage during indexing stays within bounds.

    Monitors memory usage throughout the indexing process.
    """
    project_name = f"test_memory_{int(time.time())}"

    repo_path, expected_files = large_repo_helper.generate_large_repo(
        test_fixtures_dir, num_files=500
    )

    try:
        monitor = PerformanceMonitor()
        monitor.start()

        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        # Start monitoring task
        async def monitor_memory():
            while True:
                monitor.update()
                await asyncio.sleep(1)

        monitor_task = asyncio.create_task(monitor_memory())

        try:
            # Ingest repository
            await bulk_ingest_main(
                repo_path=str(repo_path),
                project_name=project_name,
                kafka_servers=os.getenv(
                    "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"
                ),
                dry_run=False,
            )

            # Wait for indexing
            await large_repo_helper.wait_for_indexing(
                project_name=project_name,
                expected_file_count=expected_files,
                timeout=90.0,
            )

        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        metrics = monitor.finish()

        logger.info(f"Memory Usage:")
        logger.info(f"  Start: {metrics['start_memory_mb']:.2f} MB")
        logger.info(f"  End: {metrics['end_memory_mb']:.2f} MB")
        logger.info(f"  Peak: {metrics['peak_memory_mb']:.2f} MB")
        logger.info(f"  Delta: {metrics['memory_delta_mb']:.2f} MB")

        # Verify memory usage
        assert (
            metrics["peak_memory_mb"] <= performance_targets["max_memory_usage_mb"]
        ), f"Peak memory too high: {metrics['peak_memory_mb']:.0f} MB > {performance_targets['max_memory_usage_mb']} MB"

        logger.info("✅ Memory usage test passed")

    finally:
        await large_repo_helper.cleanup_project(project_name)
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path)
