#!/usr/bin/env python3
"""
Test Pattern Extraction Handler

Verifies that the PatternExtractionHandler can now query the execution_patterns
collection and return actual results.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "intelligence"))

from src.handlers.operations.pattern_extraction_handler import PatternExtractionHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pattern_extraction():
    """Test pattern extraction with real data."""
    try:
        logger.info("Initializing Pattern Extraction Handler...")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        handler = PatternExtractionHandler(qdrant_url=qdrant_url)

        # Test 1: Extract all patterns
        logger.info("\n=== Test 1: Extract all patterns ===")
        result1 = await handler.execute(
            source_path="node_*_*.py",
            options={
                "include_patterns": True,
                "pattern_types": [],
                "limit": 10,
            },
        )

        logger.info(f"✅ Found {result1.total_count} patterns in {result1.query_time_ms:.2f}ms")
        for i, pattern in enumerate(result1.patterns[:3], 1):
            logger.info(f"   {i}. {pattern['name']} ({pattern['node_types']})")
            logger.info(f"      Confidence: {pattern['confidence']:.2f}")

        # Test 2: Extract effect patterns only
        logger.info("\n=== Test 2: Extract effect patterns ===")
        result2 = await handler.execute(
            source_path="node_*_effect.py",
            options={
                "include_patterns": True,
                "pattern_types": ["effect"],
                "limit": 5,
            },
        )

        logger.info(f"✅ Found {result2.total_count} effect patterns in {result2.query_time_ms:.2f}ms")
        for i, pattern in enumerate(result2.patterns, 1):
            logger.info(f"   {i}. {pattern['name']}")
            logger.info(f"      Description: {pattern['description'][:80]}...")

        # Test 3: Extract orchestrator patterns
        logger.info("\n=== Test 3: Extract orchestrator patterns ===")
        result3 = await handler.execute(
            source_path="node_*_orchestrator.py",
            options={
                "include_patterns": True,
                "pattern_types": ["orchestrator"],
                "limit": 5,
            },
        )

        logger.info(f"✅ Found {result3.total_count} orchestrator patterns in {result3.query_time_ms:.2f}ms")
        for i, pattern in enumerate(result3.patterns, 1):
            logger.info(f"   {i}. {pattern['name']}")
            logger.info(f"      Use cases: {', '.join(pattern['use_cases'][:3])}")

        # Cleanup
        await handler.cleanup()

        logger.info("\n✅ All pattern extraction tests passed!")
        return 0

    except Exception as e:
        logger.error(f"❌ Pattern extraction test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_pattern_extraction())
    sys.exit(exit_code)
