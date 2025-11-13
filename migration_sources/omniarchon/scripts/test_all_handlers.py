#!/usr/bin/env python3
"""
Test All Intelligence Operation Handlers

Comprehensive test of PatternExtraction, SchemaDiscovery, and InfrastructureScan handlers.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "intelligence"))

from src.handlers.operations.infrastructure_scan_handler import (
    InfrastructureScanHandler,
)
from src.handlers.operations.pattern_extraction_handler import PatternExtractionHandler
from src.handlers.operations.schema_discovery_handler import SchemaDiscoveryHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_all_handlers():
    """Test all three operation handlers."""
    results = {"passed": 0, "failed": 0}

    # Test 1: Pattern Extraction
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Pattern Extraction Handler")
    logger.info("=" * 70)
    try:
        handler = PatternExtractionHandler(
            qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333")
        )
        result = await handler.execute(
            source_path="node_*_*.py",
            options={"include_patterns": True, "pattern_types": [], "limit": 5},
        )

        logger.info(
            f"✅ Pattern Extraction: {result.total_count} patterns in {result.query_time_ms:.2f}ms"
        )
        for pattern in result.patterns[:3]:
            logger.info(
                f"   - {pattern['name']} (confidence: {pattern['confidence']:.2f})"
            )

        await handler.cleanup()
        results["passed"] += 1
    except Exception as e:
        logger.error(f"❌ Pattern Extraction failed: {e}")
        results["failed"] += 1

    # Test 2: Schema Discovery
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Schema Discovery Handler")
    logger.info("=" * 70)
    try:
        handler = SchemaDiscoveryHandler()
        result = await handler.execute(
            source_path="database_schemas",
            options={
                "include_tables": True,
                "include_columns": True,
                "schema_name": "public",
            },
        )

        logger.info(
            f"✅ Schema Discovery: {result.total_tables} tables in {result.query_time_ms:.2f}ms"
        )
        for table in result.tables[:3]:
            logger.info(
                f"   - {table['name']}: {table['row_count']} rows, {table['size_mb']:.2f} MB"
            )
            if "columns" in table:
                logger.info(f"     Columns: {len(table['columns'])}")

        results["passed"] += 1
    except Exception as e:
        logger.error(f"❌ Schema Discovery failed: {e}")
        results["failed"] += 1

    # Test 3: Infrastructure Scan
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Infrastructure Scan Handler")
    logger.info("=" * 70)
    try:
        handler = InfrastructureScanHandler()
        result = await handler.execute(
            source_path="infrastructure",
            options={
                "include_databases": True,
                "include_kafka_topics": True,
                "include_qdrant_collections": True,
                "include_docker_services": False,  # Skip Docker scan
            },
        )

        logger.info(f"✅ Infrastructure Scan completed in {result.query_time_ms:.2f}ms")

        if result.postgresql:
            logger.info(
                f"   PostgreSQL: {result.postgresql['status']} ({len(result.postgresql.get('tables', []))} tables)"
            )

        if result.kafka:
            logger.info(
                f"   Kafka: {result.kafka['status']} ({len(result.kafka.get('topics', []))} topics)"
            )

        if result.qdrant:
            logger.info(
                f"   Qdrant: {result.qdrant['status']} ({len(result.qdrant.get('collections', []))} collections)"
            )
            for coll in result.qdrant.get("collections", [])[:3]:
                logger.info(f"      - {coll['name']}: {coll['point_count']} points")

        results["passed"] += 1
    except Exception as e:
        logger.error(f"❌ Infrastructure Scan failed: {e}")
        results["failed"] += 1

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"✅ Passed: {results['passed']}/3")
    logger.info(f"❌ Failed: {results['failed']}/3")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_all_handlers())
    sys.exit(exit_code)
