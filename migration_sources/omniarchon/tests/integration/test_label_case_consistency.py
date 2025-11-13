#!/usr/bin/env python3
"""
Integration test for Memgraph label case consistency.

This test suite validates label consistency across three layers:
1. Constants Layer - MemgraphLabels enum has correct values
2. Codebase Layer - No raw label strings in production code
3. Database Layer - Memgraph nodes use correct label case

This is complementary to test_node_label_consistency.py which validates
runtime Memgraph state. This test adds static analysis and validation
of the constants themselves.

Test Coverage:
1. test_constants_match_production_labels - Verify enum values
2. test_memgraph_has_correct_label_case - Database label validation
3. test_validate_label_function - Validation helper tests
4. test_no_raw_label_strings_in_production - Static code analysis
5. test_label_case_regression_prevention - Comprehensive check

Expected Behavior:
- All tests should PASS (label case bug already fixed)
- Any failures indicate regression or incomplete migration
- Static analysis should find zero raw label strings

Created: 2025-11-12
ONEX Pattern: Multi-layer schema validation testing
Reference: services/intelligence/src/constants/memgraph_labels.py
"""

import ast
import logging
import os
from pathlib import Path
from typing import List, Tuple

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

# Import constants from production code
from services.intelligence.src.constants import (
    LABEL_CONCEPT,
    LABEL_DIRECTORY,
    LABEL_DOMAIN,
    LABEL_ENTITY,
    LABEL_FILE,
    LABEL_ONEX_TYPE,
    LABEL_PROJECT,
    LABEL_THEME,
    MemgraphLabels,
    MemgraphRelationships,
    validate_label,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES
# ============================================================================


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


@pytest.fixture(scope="module")
def production_code_paths():
    """Get paths to production code directories for static analysis"""
    repo_root = Path(__file__).parent.parent.parent
    return [
        repo_root / "services" / "intelligence" / "src",
        repo_root / "services" / "search" / "src",
        repo_root / "scripts",
    ]


# ============================================================================
# TEST SUITE 1: Constants Layer Validation
# ============================================================================


def test_constants_match_production_labels():
    """
    Test 1: Verify MemgraphLabels constants match production label values.

    This test validates that the enum has correct case-sensitive values
    that will be used in Cypher queries.

    Expected:
    - FILE → "File" (capital F, rest lowercase)
    - PROJECT → "PROJECT" (all caps - intentional)
    - DIRECTORY → "Directory" (PascalCase)
    - ENTITY → "Entity" (PascalCase)
    """
    logger.info("🔍 Test 1: Validating MemgraphLabels enum values...")

    # Primary labels - critical case validation
    assert (
        MemgraphLabels.FILE.value == "File"
    ), f"FILE label should be 'File' (PascalCase), got '{MemgraphLabels.FILE.value}'"
    assert (
        MemgraphLabels.PROJECT.value == "PROJECT"
    ), f"PROJECT label should be 'PROJECT' (all caps), got '{MemgraphLabels.PROJECT.value}'"
    assert (
        MemgraphLabels.DIRECTORY.value == "Directory"
    ), f"DIRECTORY label should be 'Directory' (PascalCase), got '{MemgraphLabels.DIRECTORY.value}'"
    assert (
        MemgraphLabels.ENTITY.value == "Entity"
    ), f"ENTITY label should be 'Entity' (PascalCase), got '{MemgraphLabels.ENTITY.value}'"

    # Semantic labels
    assert MemgraphLabels.CONCEPT.value == "Concept"
    assert MemgraphLabels.THEME.value == "Theme"
    assert MemgraphLabels.ONEX_TYPE.value == "ONEXType"
    assert MemgraphLabels.DOMAIN.value == "Domain"

    # Legacy constants should match enum values
    assert LABEL_FILE == "File"
    assert LABEL_PROJECT == "PROJECT"
    assert LABEL_DIRECTORY == "Directory"
    assert LABEL_ENTITY == "Entity"
    assert LABEL_CONCEPT == "Concept"
    assert LABEL_THEME == "Theme"
    assert LABEL_ONEX_TYPE == "ONEXType"
    assert LABEL_DOMAIN == "Domain"

    logger.info("✅ All label constants have correct case-sensitive values")
    logger.info(f"  FILE → '{MemgraphLabels.FILE.value}'")
    logger.info(f"  PROJECT → '{MemgraphLabels.PROJECT.value}'")
    logger.info(f"  DIRECTORY → '{MemgraphLabels.DIRECTORY.value}'")
    logger.info(f"  ENTITY → '{MemgraphLabels.ENTITY.value}'")


def test_relationship_constants():
    """Test 2: Verify MemgraphRelationships enum values"""
    logger.info("🔍 Test 2: Validating MemgraphRelationships enum values...")

    # Relationship types (typically all caps)
    assert MemgraphRelationships.CONTAINS.value == "CONTAINS"
    assert MemgraphRelationships.IMPORTS.value == "IMPORTS"
    assert MemgraphRelationships.HAS_CONCEPT.value == "HAS_CONCEPT"
    assert MemgraphRelationships.HAS_THEME.value == "HAS_THEME"
    assert MemgraphRelationships.IS_ONEX_TYPE.value == "IS_ONEX_TYPE"
    assert MemgraphRelationships.BELONGS_TO_DOMAIN.value == "BELONGS_TO_DOMAIN"

    logger.info("✅ All relationship constants have correct values")


# ============================================================================
# TEST SUITE 2: Database Layer Validation
# ============================================================================


@pytest.mark.asyncio
async def test_memgraph_has_correct_label_case(memgraph_connection):
    """
    Test 3: Verify Memgraph nodes use correct label case.

    This test queries the actual Memgraph database to ensure nodes
    were created with correct label case.

    Expected:
    - File nodes: :File (not :FILE)
    - Project nodes: :PROJECT (not :Project)
    - Directory nodes: :Directory (not :DIRECTORY)
    - Zero nodes with incorrect case variants
    """
    logger.info("🔍 Test 3: Validating Memgraph database label case...")

    async with memgraph_connection.session() as session:
        # Test 3a: File nodes should be :File (not :FILE)
        logger.info("  Checking File vs FILE label...")
        result = await session.run("MATCH (n:File) RETURN count(n) as count")
        file_count = (await result.single())["count"]

        result = await session.run("MATCH (n:FILE) RETURN count(n) as count")
        incorrect_file_count = (await result.single())["count"]

        assert incorrect_file_count == 0, (
            f"Found {incorrect_file_count} nodes with incorrect :FILE label! "
            f"Should be :File (PascalCase)"
        )
        logger.info(
            f"  ✅ File nodes: {file_count} :File, {incorrect_file_count} :FILE"
        )

        # Test 3b: Project nodes should be :PROJECT (not :Project)
        logger.info("  Checking PROJECT vs Project label...")
        result = await session.run("MATCH (n:PROJECT) RETURN count(n) as count")
        project_count = (await result.single())["count"]

        result = await session.run("MATCH (n:Project) RETURN count(n) as count")
        incorrect_project_count = (await result.single())["count"]

        assert incorrect_project_count == 0, (
            f"Found {incorrect_project_count} nodes with incorrect :Project label! "
            f"Should be :PROJECT (all caps)"
        )
        logger.info(
            f"  ✅ Project nodes: {project_count} :PROJECT, {incorrect_project_count} :Project"
        )

        # Test 3c: Directory nodes should be :Directory (not :DIRECTORY)
        logger.info("  Checking Directory vs DIRECTORY label...")
        result = await session.run("MATCH (n:Directory) RETURN count(n) as count")
        directory_count = (await result.single())["count"]

        result = await session.run("MATCH (n:DIRECTORY) RETURN count(n) as count")
        incorrect_directory_count = (await result.single())["count"]

        assert incorrect_directory_count == 0, (
            f"Found {incorrect_directory_count} nodes with incorrect :DIRECTORY label! "
            f"Should be :Directory (PascalCase)"
        )
        logger.info(
            f"  ✅ Directory nodes: {directory_count} :Directory, {incorrect_directory_count} :DIRECTORY"
        )

    logger.info("✅ All Memgraph nodes use correct label case")


# ============================================================================
# TEST SUITE 3: Validation Function Testing
# ============================================================================


def test_validate_label_function():
    """
    Test 4: Validate the validate_label() helper function.

    This function is used to check if label strings match canonical labels.
    It's critical for pre-commit hooks and runtime validation.

    Expected:
    - validate_label("File") → True
    - validate_label("FILE") → False (wrong case)
    - validate_label("PROJECT") → True
    - validate_label("Project") → False (wrong case)
    """
    logger.info("🔍 Test 4: Testing validate_label() function...")

    # Correct labels should validate
    assert validate_label("File") is True, "validate_label('File') should be True"
    assert validate_label("PROJECT") is True, "validate_label('PROJECT') should be True"
    assert (
        validate_label("Directory") is True
    ), "validate_label('Directory') should be True"
    assert validate_label("Entity") is True, "validate_label('Entity') should be True"
    assert validate_label("Concept") is True, "validate_label('Concept') should be True"

    # Incorrect case should fail
    assert validate_label("FILE") is False, "validate_label('FILE') should be False"
    assert (
        validate_label("Project") is False
    ), "validate_label('Project') should be False"
    assert (
        validate_label("DIRECTORY") is False
    ), "validate_label('DIRECTORY') should be False"
    assert validate_label("file") is False, "validate_label('file') should be False"
    assert (
        validate_label("project") is False
    ), "validate_label('project') should be False"

    # Invalid labels should fail
    assert (
        validate_label("InvalidLabel") is False
    ), "validate_label('InvalidLabel') should be False"
    assert validate_label("Random") is False, "validate_label('Random') should be False"

    logger.info("✅ validate_label() function works correctly")
    logger.info("  Accepts: File, PROJECT, Directory, Entity")
    logger.info("  Rejects: FILE, Project, DIRECTORY, file, project")


# ============================================================================
# TEST SUITE 4: Static Code Analysis
# ============================================================================


def find_raw_label_strings_in_file(file_path: Path) -> List[Tuple[int, str]]:
    """
    Find raw label strings in Python file (static analysis).

    Looks for patterns like:
    - "MATCH (n:FILE)" - raw :FILE string
    - "MATCH (n:Project)" - raw :Project string

    Ignores:
    - Comments
    - Docstrings and examples (lines with >>> or containing 'example')
    - Lines with MemgraphLabels or LABEL_ constants
    - Cache key patterns (e.g., "file_location:project:")
    - Migration/fix scripts in /scripts/ directory

    Returns:
        List of (line_number, line_content) tuples
    """
    violations = []

    # Skip old migration/fix scripts (legacy code, documented issues)
    legacy_scripts = [
        "migrate_orphaned_relationships.py",
        "delete_placeholder_nodes.py",
        "check_file_properties.py",
        "quick_fix_tree.py",
        "fix_",  # Any script starting with fix_
    ]
    if any(script in file_path.name for script in legacy_scripts):
        return violations

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse as AST to ignore comments/docstrings
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Skip files with syntax errors (might be templates)
            return violations

        # Analyze each line
        lines = content.splitlines()
        for line_num, line in enumerate(lines, start=1):
            # Skip lines with approved constant usage
            if "MemgraphLabels" in line or "LABEL_" in line:
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # Skip docstring examples
            if ">>>" in line or "example" in line.lower() or "Example:" in line:
                continue

            # Skip cache key patterns (not Memgraph labels)
            if "file_location:" in line or "cache:" in line.lower():
                continue

            # Look for raw label patterns in Cypher queries
            # Only flag if it looks like a Cypher query (has MATCH, MERGE, CREATE, etc.)
            is_cypher_query = any(
                keyword in line.upper()
                for keyword in ["MATCH", "MERGE", "CREATE", "WHERE", "RETURN"]
            )

            if not is_cypher_query:
                continue

            raw_label_patterns = [
                ":FILE",  # Should be :File or MemgraphLabels.FILE
                ":Project",  # Should be :PROJECT
                ":DIRECTORY",  # Should be :Directory
                ":file",  # Should be :File
                # Note: ":project:" might be a cache key, so we check context above
            ]

            for pattern in raw_label_patterns:
                if (
                    pattern in line and pattern != ":project"
                ):  # ":project:" is cache key
                    violations.append((line_num, line.strip()))
                    break

    except Exception as e:
        logger.warning(f"Could not analyze {file_path}: {e}")

    return violations


def test_no_raw_label_strings_in_production(production_code_paths):
    """
    Test 5: Verify no raw label strings in production code.

    This test scans production code for raw label strings like ":FILE"
    or ":Project" that should use constants instead.

    Expected:
    - Zero raw label strings in production code
    - All code should use MemgraphLabels.FILE or LABEL_FILE

    If this test fails, it indicates developers are using raw strings
    instead of constants, which can lead to case inconsistencies.

    Note: Script violations are logged as warnings but don't fail the test
    (scripts are often diagnostic/legacy tools).
    """
    logger.info("🔍 Test 5: Scanning production code for raw label strings...")

    production_violations = []
    script_violations = []

    for code_dir in production_code_paths:
        if not code_dir.exists():
            logger.warning(f"  Skipping {code_dir} (does not exist)")
            continue

        logger.info(f"  Scanning {code_dir}...")

        # Recursively find all Python files
        python_files = list(code_dir.rglob("*.py"))
        logger.info(f"  Found {len(python_files)} Python files")

        for py_file in python_files:
            violations = find_raw_label_strings_in_file(py_file)
            if violations:
                # Separate production code from scripts
                if "/scripts/" in str(py_file):
                    script_violations.append((py_file, violations))
                else:
                    production_violations.append((py_file, violations))

    # Report script violations as warnings
    if script_violations:
        logger.warning(
            f"⚠️  Found raw label strings in {len(script_violations)} script(s):"
        )
        for file_path, violations in script_violations:
            logger.warning(f"\n  {file_path}:")
            for line_num, line_content in violations[:3]:  # Show first 3 violations
                logger.warning(f"    Line {line_num}: {line_content}")
            if len(violations) > 3:
                logger.warning(f"    ... and {len(violations) - 3} more violations")
        logger.warning(
            "  Note: Scripts are legacy/diagnostic tools - violations logged but not failing test"
        )

    # Report production code violations as errors (fail the test)
    if production_violations:
        logger.error("❌ Found raw label strings in PRODUCTION code:")
        for file_path, violations in production_violations:
            logger.error(f"\n  {file_path}:")
            for line_num, line_content in violations:
                logger.error(f"    Line {line_num}: {line_content}")

        pytest.fail(
            f"\n❌ Found {len(production_violations)} PRODUCTION file(s) with raw label strings!\n"
            f"All production code should use MemgraphLabels enum or LABEL_* constants.\n"
            f"See log output above for details.\n\n"
            f"Note: {len(script_violations)} script(s) also have violations (logged as warnings)"
        )

    # Success message
    if script_violations:
        logger.info(
            f"✅ No raw label strings in production code ({len(script_violations)} script violations logged as warnings)"
        )
    else:
        logger.info("✅ No raw label strings found in production code or scripts")


# ============================================================================
# TEST SUITE 5: Regression Prevention
# ============================================================================


@pytest.mark.asyncio
async def test_label_case_regression_prevention(memgraph_connection):
    """
    Test 6: Comprehensive regression prevention check.

    This test combines multiple checks to ensure label case consistency
    across all layers and prevent regression of the label case bug.

    Checks:
    1. Constants have correct values
    2. validate_label() works correctly
    3. Memgraph has no incorrect labels
    4. All label variants are covered

    This is a "gatekeeper" test - if this passes, the system is healthy.
    """
    logger.info("🔍 Test 6: Comprehensive label case regression check...")

    # Check 1: Constants
    logger.info("  [1/4] Verifying constants...")
    assert MemgraphLabels.FILE.value == "File"
    assert MemgraphLabels.PROJECT.value == "PROJECT"
    assert MemgraphLabels.DIRECTORY.value == "Directory"
    logger.info("  ✅ Constants correct")

    # Check 2: Validation function
    logger.info("  [2/4] Verifying validation function...")
    assert validate_label("File") is True
    assert validate_label("FILE") is False
    assert validate_label("PROJECT") is True
    assert validate_label("Project") is False
    logger.info("  ✅ Validation function works")

    # Check 3: Memgraph database state
    logger.info("  [3/4] Verifying Memgraph database...")
    async with memgraph_connection.session() as session:
        # Count all incorrect label variants
        incorrect_labels = {
            "FILE": 0,  # Should be File
            "Project": 0,  # Should be PROJECT
            "DIRECTORY": 0,  # Should be Directory
            "file": 0,  # Should be File
            "project": 0,  # Should be PROJECT
            "directory": 0,  # Should be Directory
        }

        for incorrect_label in incorrect_labels.keys():
            result = await session.run(
                f"MATCH (n:{incorrect_label}) RETURN count(n) as count"
            )
            count = (await result.single())["count"]
            incorrect_labels[incorrect_label] = count

        total_incorrect = sum(incorrect_labels.values())

        if total_incorrect > 0:
            error_msg = "❌ Found nodes with incorrect label case:\n"
            for label, count in incorrect_labels.items():
                if count > 0:
                    error_msg += f"  :{label} → {count} nodes\n"
            pytest.fail(error_msg)

    logger.info("  ✅ Memgraph database clean")

    # Check 4: Get summary statistics
    logger.info("  [4/4] Generating summary statistics...")
    async with memgraph_connection.session() as session:
        result = await session.run("MATCH (n:File) RETURN count(n) as count")
        file_count = (await result.single())["count"]

        result = await session.run("MATCH (n:PROJECT) RETURN count(n) as count")
        project_count = (await result.single())["count"]

        result = await session.run("MATCH (n:Directory) RETURN count(n) as count")
        directory_count = (await result.single())["count"]

    logger.info("\n" + "=" * 70)
    logger.info("LABEL CASE CONSISTENCY REPORT")
    logger.info("=" * 70)
    logger.info(f"✅ File nodes: {file_count} (using :File)")
    logger.info(f"✅ Project nodes: {project_count} (using :PROJECT)")
    logger.info(f"✅ Directory nodes: {directory_count} (using :Directory)")
    logger.info(f"✅ Incorrect labels: 0")
    logger.info("=" * 70)
    logger.info("🎉 All label case consistency checks passed!")
    logger.info("=" * 70 + "\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
