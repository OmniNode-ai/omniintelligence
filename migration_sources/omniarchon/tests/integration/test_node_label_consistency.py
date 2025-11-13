#!/usr/bin/env python3
"""
Node Label Consistency Tests for Memgraph

Validates that all node labels follow Neo4j/Memgraph best practices:
- PascalCase for most labels (:File, :Directory)
- Intentional uppercase for project markers (:PROJECT)

This test suite ensures schema consistency across the knowledge graph,
preventing query errors and improving maintainability.

Test Coverage:
1. test_no_uppercase_file_labels - Verify no :FILE labels exist
2. test_all_file_nodes_pascalcase - Verify all file nodes use :File
3. test_directory_labels_consistent - Verify :Directory not :DIRECTORY
4. test_project_labels_consistent - Verify :PROJECT (intentionally uppercase)

Expected Behavior:
- Tests should FAIL initially (uppercase :FILE labels exist)
- Tests should PASS after Phase 3 label migration
- Clear messages indicating which labels are inconsistent

Created: 2025-11-11
ONEX Pattern: Schema validation testing
Reference: services/intelligence/src/services/directory_indexer.py:164,172
"""

import logging
import os
from typing import Dict, List, Tuple

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
        "memgraph_uri": os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        "memgraph_user": os.getenv("MEMGRAPH_USER", ""),
        "memgraph_password": os.getenv("MEMGRAPH_PASSWORD", ""),
    }


@pytest_asyncio.fixture(scope="function")
async def memgraph_connection(service_urls):
    """Create Memgraph connection with auth if provided"""
    auth = None
    if service_urls["memgraph_user"] and service_urls["memgraph_password"]:
        auth = (service_urls["memgraph_user"], service_urls["memgraph_password"])

    driver = AsyncGraphDatabase.driver(service_urls["memgraph_uri"], auth=auth)
    yield driver
    await driver.close()


class LabelConsistencyChecker:
    """Helper class for checking node label consistency"""

    def __init__(self, memgraph_driver):
        self.driver = memgraph_driver

    async def count_nodes_with_label(self, label: str) -> int:
        """Count nodes with specific label"""
        async with self.driver.session() as session:
            result = await session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            record = await result.single()
            return record["count"] if record else 0

    async def get_sample_nodes_with_label(
        self, label: str, limit: int = 5
    ) -> List[Dict]:
        """Get sample nodes with specific label for debugging"""
        async with self.driver.session() as session:
            result = await session.run(f"MATCH (n:{label}) RETURN n LIMIT {limit}")
            records = await result.data()
            return [record["n"] for record in records]

    async def get_all_node_labels(self) -> Dict[str, int]:
        """Get all unique node labels and their counts"""
        async with self.driver.session() as session:
            # Query to get all labels and their counts
            result = await session.run(
                """
                MATCH (n)
                UNWIND labels(n) AS label
                RETURN label, count(*) as count
                ORDER BY label
                """
            )
            records = await result.data()
            return {record["label"]: record["count"] for record in records}

    async def check_label_consistency(
        self, correct_label: str, incorrect_label: str
    ) -> Tuple[bool, str]:
        """
        Check if a label is consistent (no incorrect labels exist)

        Returns:
            (is_consistent, error_message)
        """
        incorrect_count = await self.count_nodes_with_label(incorrect_label)
        correct_count = await self.count_nodes_with_label(correct_label)

        if incorrect_count > 0:
            samples = await self.get_sample_nodes_with_label(incorrect_label, limit=3)
            sample_info = "\n".join([f"  - {node}" for node in samples[:3]])
            return (
                False,
                f"Found {incorrect_count} nodes with incorrect label :{incorrect_label}\n"
                f"Expected label: :{correct_label}\n"
                f"Sample nodes:\n{sample_info}",
            )

        if correct_count == 0:
            return (
                True,
                f"✓ No nodes found with either label (:{correct_label} or :{incorrect_label})",
            )

        return (
            True,
            f"✓ All {correct_count} nodes use correct label :{correct_label}",
        )


@pytest_asyncio.fixture
async def label_checker(memgraph_connection):
    """Create label consistency checker"""
    return LabelConsistencyChecker(memgraph_connection)


# ============================================================================
# TEST SUITE: Node Label Consistency
# ============================================================================


@pytest.mark.asyncio
async def test_memgraph_connectivity(memgraph_connection):
    """Verify Memgraph connectivity before running label tests"""
    logger.info("🔌 Testing Memgraph connectivity...")

    try:
        async with memgraph_connection.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            assert record["test"] == 1, "Memgraph query failed"

        logger.info("✅ Memgraph connection successful")
    except Exception as e:
        pytest.fail(f"❌ Memgraph connection failed: {e}")


@pytest.mark.asyncio
async def test_get_all_labels_inventory(label_checker):
    """
    Inventory test: Display all node labels in the graph

    This is not a pass/fail test, but provides visibility into
    the current state of labels before consistency checks.
    """
    logger.info("📊 Retrieving all node labels from Memgraph...")

    all_labels = await label_checker.get_all_node_labels()

    logger.info(f"Found {len(all_labels)} unique label(s):")
    for label, count in sorted(all_labels.items()):
        logger.info(f"  :{label} → {count} nodes")

    # This test always passes - it's just for visibility
    assert len(all_labels) >= 0, "Should retrieve label inventory"


@pytest.mark.asyncio
async def test_no_uppercase_file_labels(label_checker):
    """
    Test 1: Verify no nodes have :FILE label (uppercase)

    Expected: Should be 0 nodes with :FILE label
    Standard: File nodes should use :File (PascalCase)

    This test will FAIL initially if uppercase :FILE labels exist.
    """
    logger.info("🔍 Test 1: Checking for uppercase :FILE labels...")

    is_consistent, message = await label_checker.check_label_consistency(
        correct_label="File", incorrect_label="FILE"
    )

    logger.info(message)

    if not is_consistent:
        pytest.fail(
            f"❌ Label consistency violation detected:\n{message}\n\n"
            "Action Required: Migrate :FILE labels to :File (PascalCase)\n"
            "Reference: Neo4j/Memgraph best practices for node label naming"
        )

    logger.info("✅ No uppercase :FILE labels found")


@pytest.mark.asyncio
async def test_all_file_nodes_pascalcase(label_checker):
    """
    Test 2: Verify all file nodes use :File label (PascalCase)

    Expected: File nodes should use :File (not :FILE, :file, or other variants)
    Standard: PascalCase is the Neo4j/Memgraph convention

    This test ensures proper label casing after migration.
    """
    logger.info("🔍 Test 2: Checking for :File (PascalCase) labels...")

    file_count = await label_checker.count_nodes_with_label("File")
    uppercase_file_count = await label_checker.count_nodes_with_label("FILE")
    lowercase_file_count = await label_checker.count_nodes_with_label("file")

    logger.info(f"File label distribution:")
    logger.info(f"  :File (correct) → {file_count} nodes")
    logger.info(f"  :FILE (incorrect) → {uppercase_file_count} nodes")
    logger.info(f"  :file (incorrect) → {lowercase_file_count} nodes")

    # Check for any incorrect variants
    incorrect_total = uppercase_file_count + lowercase_file_count

    if incorrect_total > 0:
        pytest.fail(
            f"❌ Found {incorrect_total} file nodes with incorrect casing:\n"
            f"  - :FILE (uppercase): {uppercase_file_count}\n"
            f"  - :file (lowercase): {lowercase_file_count}\n\n"
            f"All file nodes should use :File (PascalCase)"
        )

    if file_count == 0:
        logger.warning("⚠️  No file nodes found in graph (may not be ingested yet)")
        pytest.skip("No file nodes found - skipping test")

    logger.info(f"✅ All {file_count} file nodes use correct :File label")


@pytest.mark.asyncio
async def test_directory_labels_consistent(label_checker):
    """
    Test 3: Verify directory nodes use :Directory (PascalCase)

    Expected: Directory nodes should use :Directory (not :DIRECTORY)
    Standard: PascalCase for structural labels

    This test validates directory node label consistency.
    """
    logger.info("🔍 Test 3: Checking directory label consistency...")

    is_consistent, message = await label_checker.check_label_consistency(
        correct_label="Directory", incorrect_label="DIRECTORY"
    )

    logger.info(message)

    if not is_consistent:
        pytest.fail(
            f"❌ Label consistency violation detected:\n{message}\n\n"
            "Action Required: Migrate :DIRECTORY labels to :Directory (PascalCase)"
        )

    directory_count = await label_checker.count_nodes_with_label("Directory")

    if directory_count == 0:
        logger.warning("⚠️  No directory nodes found in graph")
        pytest.skip("No directory nodes found - skipping test")

    logger.info(
        f"✅ All {directory_count} directory nodes use correct :Directory label"
    )


@pytest.mark.asyncio
async def test_project_labels_consistent(label_checker):
    """
    Test 4: Verify project nodes use :PROJECT (intentionally uppercase)

    Expected: Project nodes should use :PROJECT (uppercase)
    Standard: PROJECT is intentionally uppercase as a marker/anchor

    Note: Unlike other labels, :PROJECT is uppercase by design.
    """
    logger.info("🔍 Test 4: Checking project label consistency...")

    project_count = await label_checker.count_nodes_with_label("PROJECT")
    pascalcase_project_count = await label_checker.count_nodes_with_label("Project")

    logger.info(f"Project label distribution:")
    logger.info(f"  :PROJECT (correct) → {project_count} nodes")
    logger.info(f"  :Project (incorrect) → {pascalcase_project_count} nodes")

    if pascalcase_project_count > 0:
        samples = await label_checker.get_sample_nodes_with_label("Project", limit=3)
        sample_info = "\n".join([f"  - {node}" for node in samples])
        pytest.fail(
            f"❌ Found {pascalcase_project_count} project nodes with incorrect label :Project\n"
            f"Expected: :PROJECT (intentionally uppercase)\n"
            f"Sample nodes:\n{sample_info}"
        )

    if project_count == 0:
        logger.warning("⚠️  No project nodes found in graph")
        pytest.skip("No project nodes found - skipping test")

    logger.info(f"✅ All {project_count} project nodes use correct :PROJECT label")


@pytest.mark.asyncio
async def test_label_migration_summary(label_checker):
    """
    Summary test: Provide overall label consistency report

    This test runs after all label checks and provides a summary
    of the current state and any required migrations.
    """
    logger.info("📋 Generating label consistency summary...")

    all_labels = await label_checker.get_all_node_labels()

    # Identify incorrect labels
    incorrect_labels = []
    if "FILE" in all_labels:
        incorrect_labels.append(f"FILE → File ({all_labels['FILE']} nodes)")
    if "DIRECTORY" in all_labels:
        incorrect_labels.append(
            f"DIRECTORY → Directory ({all_labels['DIRECTORY']} nodes)"
        )
    if "file" in all_labels:
        incorrect_labels.append(f"file → File ({all_labels['file']} nodes)")
    if "directory" in all_labels:
        incorrect_labels.append(
            f"directory → Directory ({all_labels['directory']} nodes)"
        )
    if "Project" in all_labels:
        incorrect_labels.append(f"Project → PROJECT ({all_labels['Project']} nodes)")

    # Identify correct labels
    correct_labels = []
    if "File" in all_labels:
        correct_labels.append(f":File ({all_labels['File']} nodes)")
    if "Directory" in all_labels:
        correct_labels.append(f":Directory ({all_labels['Directory']} nodes)")
    if "PROJECT" in all_labels:
        correct_labels.append(f":PROJECT ({all_labels['PROJECT']} nodes)")

    logger.info("\n" + "=" * 70)
    logger.info("LABEL CONSISTENCY SUMMARY")
    logger.info("=" * 70)

    logger.info("\n✅ Correct Labels:")
    if correct_labels:
        for label in correct_labels:
            logger.info(f"  {label}")
    else:
        logger.info("  (None found)")

    if incorrect_labels:
        logger.info("\n❌ Incorrect Labels (Migration Required):")
        for label in incorrect_labels:
            logger.info(f"  {label}")
        logger.info("\n📝 Migration Action Items:")
        logger.info("  1. Update directory_indexer.py to use PascalCase labels")
        logger.info("  2. Run Cypher migration queries to update existing nodes")
        logger.info("  3. Re-run these tests to verify success")
        logger.info("=" * 70 + "\n")

        pytest.fail(
            f"\n❌ Found {len(incorrect_labels)} label inconsistency issue(s)\n"
            f"See log output above for migration action items."
        )
    else:
        logger.info("\n🎉 All labels are consistent!")
        logger.info("=" * 70 + "\n")
