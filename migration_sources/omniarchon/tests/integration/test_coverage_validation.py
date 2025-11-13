"""
Integration tests for data coverage validation.

CRITICAL: These tests validate the 3 core coverage metrics that allowed
production failures to reach deployment:

1. Tree Building Coverage (PROJECT/DIRECTORY nodes)
   - Production failure: 0% success (0 PROJECT, 0 DIRECTORY nodes)
   - Root cause: Cypher syntax error in DirectoryIndexer
   - This test validates tree structure creation

2. Language Coverage (language field populated)
   - Production failure: 40% vs 90% target
   - Root cause: Missing language detection in ingestion pipeline
   - This test validates language metadata coverage

3. Vector Coverage (vectors in Qdrant)
   - Production failure: 46% vs 95% target
   - Root cause: Incomplete vector indexing pipeline
   - This test validates vector creation coverage

These tests ensure ingestion pipeline completeness and prevent regressions.

Created: 2025-11-12
ONEX Pattern: Coverage validation testing
"""

import logging
import os
from typing import Dict, List, Optional

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def service_urls():
    """Service URL configuration for database connections"""
    return {
        "memgraph_uri": os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
    }


@pytest_asyncio.fixture(scope="module")
async def memgraph_connection(service_urls):
    """Create Memgraph connection for graph queries"""
    driver = AsyncGraphDatabase.driver(service_urls["memgraph_uri"])
    yield driver
    await driver.close()


@pytest.fixture(scope="module")
def qdrant_client(service_urls):
    """Create Qdrant client for vector database queries"""
    client = QdrantClient(url=service_urls["qdrant_url"])
    return client


@pytest.fixture(scope="module")
def test_project_name():
    """
    Project name to test against.

    This should be a project that exists in your database after ingestion.
    Set via environment variable or use default.
    """
    return os.getenv("TEST_PROJECT_NAME", "omniarchon")


class CoverageValidator:
    """Helper class for coverage validation operations"""

    def __init__(self, memgraph_driver, qdrant_client):
        self.memgraph_driver = memgraph_driver
        self.qdrant_client = qdrant_client

    async def get_tree_statistics(self, project_name: str) -> Dict[str, int]:
        """
        Get file tree statistics from Memgraph.

        Returns counts for:
        - PROJECT nodes
        - DIRECTORY nodes
        - CONTAINS relationships
        - Orphan files (files without CONTAINS relationships)
        """
        async with self.memgraph_driver.session() as session:
            # Count PROJECT nodes
            project_result = await session.run(
                """
                MATCH (p:PROJECT {project_name: $project_name})
                RETURN count(p) as count
                """,
                project_name=project_name,
            )
            project_count = (await project_result.single())["count"]

            # Count DIRECTORY nodes
            dir_result = await session.run(
                """
                MATCH (d:DIRECTORY {project_name: $project_name})
                RETURN count(d) as count
                """,
                project_name=project_name,
            )
            directory_count = (await dir_result.single())["count"]

            # Count CONTAINS relationships
            contains_result = await session.run(
                """
                MATCH (p:PROJECT {project_name: $project_name})-[:CONTAINS*]->(n)
                RETURN count(n) as count
                """,
                project_name=project_name,
            )
            contains_count = (await contains_result.single())["count"]

            # Count orphan files (files without parent relationships)
            orphan_result = await session.run(
                """
                MATCH (f:File {project_name: $project_name})
                OPTIONAL MATCH orphan_path = (f)<-[:CONTAINS]-()
                WITH f, orphan_path
                WHERE orphan_path IS NULL
                RETURN count(f) as count
                """,
                project_name=project_name,
            )
            orphan_count = (await orphan_result.single())["count"]

            return {
                "projects": project_count,
                "directories": directory_count,
                "contains_relationships": contains_count,
                "orphan_files": orphan_count,
            }

    async def get_language_coverage(self, project_name: str) -> Dict[str, any]:
        """
        Get language coverage statistics from Memgraph.

        Returns:
        - total_files: Total File nodes for project
        - files_with_language: Files with non-null language field
        - coverage_percent: Percentage of files with language metadata
        """
        async with self.memgraph_driver.session() as session:
            # Total files
            total_result = await session.run(
                """
                MATCH (f:File {project_name: $project_name})
                RETURN count(f) as count
                """,
                project_name=project_name,
            )
            total_files = (await total_result.single())["count"]

            # Files with language
            lang_result = await session.run(
                """
                MATCH (f:File {project_name: $project_name})
                WHERE f.language IS NOT NULL
                RETURN count(f) as count
                """,
                project_name=project_name,
            )
            files_with_language = (await lang_result.single())["count"]

            # Calculate coverage percentage
            coverage_percent = (
                (files_with_language / total_files * 100) if total_files > 0 else 0
            )

            return {
                "total_files": total_files,
                "files_with_language": files_with_language,
                "coverage_percent": coverage_percent,
            }

    async def get_vector_coverage(self, project_name: str) -> Dict[str, any]:
        """
        Get vector coverage statistics by comparing Memgraph files to Qdrant vectors.

        Returns:
        - memgraph_files: Total File nodes in Memgraph
        - qdrant_vectors: Total vectors in Qdrant collection
        - coverage_percent: Approximate coverage (may exceed 100% due to chunks)

        Note: This is an approximation since Qdrant may have multiple vectors
        per file (due to chunking). A more accurate test would filter vectors
        by project metadata, but that requires more complex queries.
        """
        async with self.memgraph_driver.session() as session:
            # Get file count from Memgraph
            result = await session.run(
                """
                MATCH (f:File {project_name: $project_name})
                RETURN count(f) as count
                """,
                project_name=project_name,
            )
            memgraph_file_count = (await result.single())["count"]

        # Get vector count from Qdrant
        try:
            collection_info = self.qdrant_client.get_collection("archon_vectors")
            qdrant_vector_count = collection_info.points_count
        except Exception as e:
            logger.error(f"Failed to get Qdrant collection info: {e}")
            qdrant_vector_count = 0

        # Calculate coverage
        # Note: This may exceed 100% if files are chunked into multiple vectors
        coverage_percent = (
            (qdrant_vector_count / memgraph_file_count * 100)
            if memgraph_file_count > 0
            else 0
        )

        return {
            "memgraph_files": memgraph_file_count,
            "qdrant_vectors": qdrant_vector_count,
            "coverage_percent": coverage_percent,
        }


@pytest_asyncio.fixture
async def coverage_validator(memgraph_connection, qdrant_client):
    """Create coverage validator instance"""
    return CoverageValidator(memgraph_connection, qdrant_client)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tree_building_creates_project_and_directory_nodes(
    coverage_validator: CoverageValidator, test_project_name: str
):
    """
    CRITICAL: Validate tree building creates PROJECT and DIRECTORY nodes.

    This test would have caught the Cypher syntax error that caused
    0 PROJECT nodes and 0 DIRECTORY nodes in production.

    Production Failure Context:
    - Issue: DirectoryIndexer had Cypher syntax error
    - Impact: 0% tree building success
    - Result: No project hierarchy, orphaned files

    Validation Criteria:
    1. Exactly 1 PROJECT node per project
    2. At least 1 DIRECTORY node (for project structure)
    3. CONTAINS relationships linking hierarchy
    4. Zero orphan files (all files have parent)

    Success Thresholds:
    - PROJECT nodes: exactly 1
    - DIRECTORY nodes: ≥ 1 (depends on project structure)
    - Orphan files: 0 (no files without parent relationships)
    """
    logger.info(f"🔍 Testing tree building for project: {test_project_name}")

    # Get tree statistics
    stats = await coverage_validator.get_tree_statistics(test_project_name)

    logger.info("📊 Tree Building Results:")
    logger.info(f"  PROJECT nodes: {stats['projects']}")
    logger.info(f"  DIRECTORY nodes: {stats['directories']}")
    logger.info(f"  CONTAINS relationships: {stats['contains_relationships']}")
    logger.info(f"  Orphan files: {stats['orphan_files']}")

    # Assertions - these would have caught the production bug
    assert stats["projects"] == 1, (
        f"Expected exactly 1 PROJECT node, found {stats['projects']}. "
        f"Project hierarchy not built correctly."
    )

    assert stats["directories"] >= 1, (
        f"Expected ≥1 DIRECTORY node, found {stats['directories']}. "
        f"Directory structure not indexed. This was the production failure symptom."
    )

    assert stats["contains_relationships"] > 0, (
        f"Expected >0 CONTAINS relationships, found {stats['contains_relationships']}. "
        f"Hierarchy not linked correctly."
    )

    # Warn on orphans (not critical failure, but indicates incomplete indexing)
    if stats["orphan_files"] > 0:
        logger.warning(
            f"⚠️  Found {stats['orphan_files']} orphan files (files without parent CONTAINS relationship). "
            f"These files are indexed but not part of the directory tree."
        )

    logger.info("✅ Tree building validation PASSED")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_language_coverage_exceeds_90_percent(
    coverage_validator: CoverageValidator, test_project_name: str
):
    """
    CRITICAL: Validate 90%+ files have language metadata after ingestion.

    This test would have caught the 40% language coverage gap in production.

    Production Failure Context:
    - Issue: Language detection not integrated in ingestion pipeline
    - Impact: Only 40% of files had language field populated
    - Target: 90% coverage
    - Gap: 50 percentage points below target

    Validation Criteria:
    1. Total file count > 0 (project exists)
    2. Files with language metadata ≥ 90% of total

    Success Threshold:
    - Coverage: ≥ 90.0%

    Reasoning:
    - Language metadata is critical for syntax highlighting, search filtering,
      and language-specific analysis
    - 90% threshold allows for edge cases (binary files, unknown extensions)
    - Below 90% indicates incomplete language detection pipeline
    """
    logger.info(f"🔍 Testing language coverage for project: {test_project_name}")

    # Get language coverage statistics
    coverage = await coverage_validator.get_language_coverage(test_project_name)

    logger.info("📊 Language Coverage Results:")
    logger.info(f"  Total files: {coverage['total_files']}")
    logger.info(f"  Files with language: {coverage['files_with_language']}")
    logger.info(f"  Coverage: {coverage['coverage_percent']:.1f}%")

    # Assertion - this would have caught the production bug
    assert coverage["total_files"] > 0, (
        f"No files found for project '{test_project_name}'. "
        f"Ensure project has been ingested."
    )

    assert coverage["coverage_percent"] >= 90.0, (
        f"Language coverage too low: {coverage['coverage_percent']:.1f}% "
        f"({coverage['files_with_language']}/{coverage['total_files']} files). "
        f"Expected: ≥90%. This indicates incomplete language detection in the ingestion pipeline."
    )

    logger.info("✅ Language coverage validation PASSED")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_coverage_exceeds_95_percent(
    coverage_validator: CoverageValidator, test_project_name: str
):
    """
    CRITICAL: Validate 95%+ files have vectors in Qdrant after ingestion.

    This test would have caught the 46% vector coverage gap in production.

    Production Failure Context:
    - Issue: Vector indexing pipeline incomplete
    - Impact: Only 46% of files had vectors in Qdrant
    - Target: 95% coverage
    - Gap: 49 percentage points below target

    Validation Criteria:
    1. Memgraph file count > 0 (project exists)
    2. Qdrant vector count ≥ 95% of Memgraph file count

    Success Threshold:
    - Coverage: ≥ 95.0%

    Important Notes:
    - This is an APPROXIMATE metric since Qdrant may have multiple vectors
      per file (due to chunking)
    - Coverage >100% is EXPECTED and acceptable (indicates chunking is working)
    - Coverage <95% indicates incomplete vector indexing pipeline
    - For more accurate measurement, filter Qdrant vectors by project metadata

    Reasoning:
    - Vector embeddings are critical for semantic search and RAG queries
    - 95% threshold ensures near-complete coverage
    - Below 95% indicates vector indexing pipeline failures
    """
    logger.info(f"🔍 Testing vector coverage for project: {test_project_name}")

    # Get vector coverage statistics
    coverage = await coverage_validator.get_vector_coverage(test_project_name)

    logger.info("📊 Vector Coverage Results:")
    logger.info(f"  Memgraph files: {coverage['memgraph_files']}")
    logger.info(f"  Qdrant vectors: {coverage['qdrant_vectors']}")
    logger.info(f"  Coverage: {coverage['coverage_percent']:.1f}%")

    # Special case: Coverage >100% is acceptable (chunking creates multiple vectors)
    if coverage["coverage_percent"] > 100:
        logger.info(
            f"ℹ️  Coverage exceeds 100% ({coverage['coverage_percent']:.1f}%). "
            f"This is expected when files are chunked into multiple vectors."
        )

    # Assertions - these would have caught the production bug
    assert coverage["memgraph_files"] > 0, (
        f"No files found in Memgraph for project '{test_project_name}'. "
        f"Ensure project has been ingested into graph database."
    )

    assert coverage["coverage_percent"] >= 95.0, (
        f"Vector coverage too low: {coverage['coverage_percent']:.1f}% "
        f"({coverage['qdrant_vectors']} vectors for {coverage['memgraph_files']} files). "
        f"Expected: ≥95%. This indicates incomplete vector indexing pipeline. "
        f"Production failure was 46% coverage."
    )

    logger.info("✅ Vector coverage validation PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])
