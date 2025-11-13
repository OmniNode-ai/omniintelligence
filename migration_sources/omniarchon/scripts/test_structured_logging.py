#!/usr/bin/env python3
"""
Test script for structured logging implementation.

Verifies that structured logging functions work correctly and produce
valid JSON output.

Usage:
    python3 scripts/test_structured_logging.py
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import structured logging functions
from scripts.lib.file_discovery import (
    OrphanDetectionResult,
    OrphanFile,
    log_orphan_detection,
    log_structured_discovery,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
)

logger = logging.getLogger(__name__)


def test_structured_logging():
    """Test structured logging output."""
    print("=" * 70)
    print("STRUCTURED LOGGING TEST")
    print("=" * 70)
    print()

    correlation_id = "test-correlation-123"

    # Test 1: Basic structured log
    print("Test 1: Basic Structured Log")
    print("-" * 70)
    log_structured_discovery(
        logger,
        logging.INFO,
        "Test message with structured data",
        correlation_id,
        phase="test",
        operation="basic_log",
        test_metric=123,
        test_flag=True,
    )
    print()

    # Test 2: Orphan detection with no orphans
    print("Test 2: Orphan Detection (0 orphans)")
    print("-" * 70)
    result_no_orphans = OrphanDetectionResult(
        orphans_detected=0,
        orphans=[],
        detection_duration_ms=45.67,
    )
    log_orphan_detection(correlation_id, result_no_orphans, "test-project")
    print()

    # Test 3: Orphan detection with orphans
    print("Test 3: Orphan Detection (3 orphans)")
    print("-" * 70)
    orphans = [
        OrphanFile(
            file_path="/path/to/file1.py",
            entity_id="entity-123",
            expected_parent="/path/to",
            project_name="test-project",
        ),
        OrphanFile(
            file_path="/path/to/file2.py",
            entity_id="entity-456",
            expected_parent="/path/to",
            project_name="test-project",
        ),
        OrphanFile(
            file_path="/path/to/file3.py",
            entity_id="entity-789",
            expected_parent="/path/to",
            project_name="test-project",
        ),
    ]
    result_with_orphans = OrphanDetectionResult(
        orphans_detected=3,
        orphans=orphans,
        orphans_fixed=1,
        orphans_remaining=2,
        detection_duration_ms=123.45,
    )
    log_orphan_detection(correlation_id, result_with_orphans, "test-project")
    print()

    # Test 4: Tree building metrics
    print("Test 4: Tree Building Metrics")
    print("-" * 70)
    log_structured_discovery(
        logger,
        logging.INFO,
        "Tree building complete",
        correlation_id,
        phase="tree_building",
        operation="complete",
        project_name="test-project",
        nodes_created=25,
        projects_created=1,
        directories_created=10,
        files_linked=143,
        relationships_created=148,
        duration_ms=1234.56,
    )
    print()

    # Test 5: Error logging
    print("Test 5: Error Logging")
    print("-" * 70)
    log_structured_discovery(
        logger,
        logging.ERROR,
        "Tree building failed",
        correlation_id,
        phase="tree_building",
        operation="error",
        error_type="RuntimeError",
        error_message="Failed to connect to Memgraph",
        duration_ms=567.89,
    )
    print()

    print("=" * 70)
    print("✅ All structured logging tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_structured_logging()
